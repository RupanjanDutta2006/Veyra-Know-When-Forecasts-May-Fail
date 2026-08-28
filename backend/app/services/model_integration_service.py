"""Model Integration Layer Service for Veyra Phase 2 Day 11.

Provides a centralized, production-oriented integration boundary between the
platform orchestrator/API layer and machine learning model pipelines.
Encapsulates artifact discovery, feature contract validation, anti-leakage guards,
safe model degradation, and dynamic model registration for Builder 2.
"""
import logging
import math
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, Union

from backend.app.builder2.feature_pipeline import FEATURE_COLUMN_NAMES
from backend.app.builder2.model_adapter import Builder2ModelAdapter
from backend.app.core.config import settings
from backend.app.schemas.model_integration import (
    FORBIDDEN_GROUND_TRUTH_FIELDS,
    ModelInputContract,
    ModelMetadataInfo,
    ModelOutputContract,
)
from backend.app.schemas.prediction import ReasonCode
from backend.app.services.base import (
    BaseModelService,
    FeatureResult,
    ModelResult,
)
from backend.app.services.model_service import (
    LiveLogisticModelService,
    UnavailableModelService,
)

logger = logging.getLogger(__name__)

DEFAULT_BUILDER2_MODEL_PATH = Path("models/builder2/prototype-gbm-v1")
DEFAULT_BASELINE_MODEL_PATH = Path("models/baseline_logistic_v1.joblib")


class BaseModelIntegrationService(BaseModelService, ABC):
    """Abstract interface for the Model Integration Layer."""

    @abstractmethod
    def evaluate_contract(self, input_contract: ModelInputContract) -> ModelOutputContract:
        """Execute inference against a validated ModelInputContract."""
        pass

    @abstractmethod
    def get_active_model_info(self) -> ModelMetadataInfo:
        """Return introspection metadata for the currently active model."""
        pass


class ModelIntegrationService(BaseModelIntegrationService):
    """Production Model Integration Layer.

    Serves as the single authoritative model integration gateway for Veyra.
    Enforces feature contracts, prevents data leakage, manages artifact resolution,
    and isolates inference failures without exposing raw exceptions to callers.
    """

    def __init__(
        self,
        primary_model: Optional[BaseModelService] = None,
        builder2_model_dir: Optional[Union[str, Path]] = None,
        fallback_to_baseline: bool = True,
    ):
        self._models: dict[str, BaseModelService] = {}
        self._active_model_name: str = "unavailable"
        self.fallback_to_baseline = fallback_to_baseline

        if primary_model is not None:
            self.register_model("custom_primary", primary_model, set_active=True)
        else:
            self._auto_discover_and_register_models(builder2_model_dir)

    def _auto_discover_and_register_models(
        self, custom_builder2_dir: Optional[Union[str, Path]] = None
    ) -> None:
        """Discover and initialize available model adapters based on environment and disk artifacts."""
        # 1. Check for Builder 2 LightGBM model
        target_b2_dir = (
            custom_builder2_dir
            or settings.BUILDER2_MODEL_DIR
            or os.getenv("BUILDER2_MODEL_DIR")
            or (str(DEFAULT_BUILDER2_MODEL_PATH) if DEFAULT_BUILDER2_MODEL_PATH.exists() else None)
        )

        b2_loaded = False
        if target_b2_dir:
            try:
                b2_adapter = Builder2ModelAdapter(model_dir=target_b2_dir)
                if b2_adapter.is_ready:
                    self.register_model("builder2_gbm", b2_adapter, set_active=True)
                    b2_loaded = True
                    logger.info("ModelIntegrationService registered primary model 'builder2_gbm' from %s", target_b2_dir)
            except Exception as exc:
                logger.warning("Failed to initialize Builder2ModelAdapter from %s: %s", target_b2_dir, exc)

        # 2. Check for Baseline Logistic model as fallback
        if self.fallback_to_baseline and DEFAULT_BASELINE_MODEL_PATH.exists():
            try:
                baseline_service = LiveLogisticModelService()
                if baseline_service.is_ready:
                    self.register_model("baseline_logistic", baseline_service, set_active=not b2_loaded)
                    logger.info("ModelIntegrationService registered fallback model 'baseline_logistic'")
            except Exception as exc:
                logger.warning("Failed to initialize LiveLogisticModelService: %s", exc)

        # 3. If no model loaded successfully, register explicit unavailable service
        if not self._models:
            self.register_model("unavailable", UnavailableModelService(), set_active=True)
            logger.warning("ModelIntegrationService initialized in UNAVAILABLE state (no valid artifacts found)")

    def register_model(
        self, name: str, model_service: BaseModelService, set_active: bool = False
    ) -> None:
        """Register a model service with the integration layer (Builder 2 extensibility hook)."""
        self._models[name] = model_service
        if set_active or len(self._models) == 1:
            self._active_model_name = name

    def set_active_model(self, name: str) -> None:
        """Switch the active prediction model by registered name."""
        if name not in self._models:
            raise KeyError(f"Model '{name}' not found in registry. Available: {list(self._models.keys())}")
        self._active_model_name = name

    @property
    def active_model(self) -> BaseModelService:
        """Return the active model service instance."""
        return self._models[self._active_model_name]

    @property
    def is_ready(self) -> bool:
        """Check if active model is loaded and ready for inference."""
        active = self.active_model
        return getattr(active, "is_ready", False)

    def validate_feature_result(self, feature_result: FeatureResult) -> Optional[str]:
        """Validate feature contract, finiteness, and absence of data leakage.

        Returns None if valid, or an error string if contract is violated.
        """
        if not feature_result.is_ready or feature_result.error:
            return feature_result.error or "Features are marked as not ready for inference"

        features = feature_result.features
        if not features and not feature_result.metadata.get("feature_matrix_rows"):
            return "FeatureResult contains no feature data"

        # Check for forbidden ground truth / reference leakage
        for feat_name in features:
            if feat_name.strip().lower() in FORBIDDEN_GROUND_TRUTH_FIELDS:
                return f"CRITICAL LEAKAGE: Ground-truth field '{feat_name}' present in feature vector"

        for meta_key in feature_result.metadata:
            if meta_key.strip().lower() in FORBIDDEN_GROUND_TRUTH_FIELDS:
                return f"CRITICAL LEAKAGE: Ground-truth field '{meta_key}' present in feature metadata"

        # Validate finiteness of numerical feature values
        for feat_name, val in features.items():
            if isinstance(val, (int, float)):
                if math.isnan(val) or math.isinf(val):
                    return f"Non-finite feature value for '{feat_name}': {val}"

        # If active model is Builder 2 LightGBM, check canonical 26-column contract
        if self._active_model_name == "builder2_gbm":
            missing_cols = [c for c in FEATURE_COLUMN_NAMES if c not in features and c not in (feature_result.metadata.get("feature_names") or [])]
            # If feature_matrix_rows exists, check columns there
            matrix_rows = feature_result.metadata.get("feature_matrix_rows")
            if matrix_rows and isinstance(matrix_rows, list) and len(matrix_rows) > 0:
                first_row = matrix_rows[0]
                missing_cols = [c for c in FEATURE_COLUMN_NAMES if c not in first_row]
            if missing_cols:
                return f"Missing required canonical features for Builder 2 model: {missing_cols[:5]}"

        return None

    def predict(self, feature_result: FeatureResult) -> ModelResult:
        """Execute inference through the Model Integration Layer.

        Validates feature contract, executes active model in safe sandbox,
        strictly checks probability bounds, and prevents traceback leakage.
        """
        # 1. Feature contract & anti-leakage validation
        validation_error = self.validate_feature_result(feature_result)
        if validation_error:
            logger.warning("Model integration feature validation rejected: %s", validation_error)
            is_leakage = "CRITICAL LEAKAGE" in validation_error
            status_code = ReasonCode.QC_FAILED.value if is_leakage else ReasonCode.FEATURES_NOT_READY.value
            return ModelResult(
                probability=None,
                model_version=getattr(self.active_model, "model_version", None),
                is_ready=False,
                metadata={"status": status_code, "validation_error": validation_error},
                error=validation_error,
            )

        # 2. Check model readiness
        active = self.active_model
        if not getattr(active, "is_ready", False):
            return ModelResult(
                probability=None,
                model_version=getattr(active, "model_version", None),
                is_ready=False,
                metadata={"status": ReasonCode.MODEL_NOT_READY.value},
                error=f"Active model '{self._active_model_name}' is not ready for inference",
            )

        # 3. Execute inference safely
        try:
            raw_result = active.predict(feature_result)

            # 4. Strict probability validation [0.0, 1.0]
            prob = raw_result.probability
            if prob is not None:
                if not (0.0 <= prob <= 1.0) or math.isnan(prob) or math.isinf(prob):
                    logger.error("Active model returned invalid out-of-bounds probability: %s", prob)
                    return ModelResult(
                        probability=None,
                        model_version=raw_result.model_version,
                        is_ready=False,
                        metadata={"status": ReasonCode.QC_FAILED.value},
                        error=f"Model produced invalid out-of-bounds probability: {prob}",
                    )

            # Ensure metadata reflects model integration layer info
            enriched_metadata = dict(raw_result.metadata or {})
            enriched_metadata["model_integration_gateway"] = "ModelIntegrationService/v2.0"
            enriched_metadata["active_model_key"] = self._active_model_name

            return ModelResult(
                probability=raw_result.probability,
                model_version=raw_result.model_version,
                is_ready=raw_result.is_ready,
                metadata=enriched_metadata,
                error=raw_result.error,
            )

        except Exception as exc:
            logger.error("Unhandled exception during model inference on '%s': %s", self._active_model_name, exc)
            return ModelResult(
                probability=None,
                model_version=getattr(active, "model_version", None),
                is_ready=False,
                metadata={"status": ReasonCode.INTERNAL_ERROR.value},
                error=f"Model inference failed in integration layer: {str(exc)}",
            )

    def evaluate_contract(self, input_contract: ModelInputContract) -> ModelOutputContract:
        """Execute inference against a validated ModelInputContract."""
        # Adapt ModelInputContract to FeatureResult
        feat_result = FeatureResult(
            location=input_contract.location,
            features=input_contract.features,
            feature_names=input_contract.feature_names,
            is_ready=True,
            metadata=input_contract.metadata,
        )

        model_res = self.predict(feat_result)

        if not model_res.is_ready or model_res.probability is None:
            return ModelOutputContract(
                is_success=False,
                probability=None,
                model_version=model_res.model_version,
                model_type=model_res.metadata.get("model_type"),
                feature_schema_version=input_contract.feature_schema_version,
                is_calibrated=False,
                decision_threshold=model_res.metadata.get("decision_threshold"),
                bust_alert=False,
                reason_code=model_res.metadata.get("status", "MODEL_ERROR"),
                error_message=model_res.error,
                metadata=model_res.metadata,
            )

        threshold = model_res.metadata.get("decision_threshold", 0.280)
        prob = model_res.probability
        has_alert = model_res.metadata.get("bust_alert", bool(prob >= threshold))

        return ModelOutputContract(
            is_success=True,
            probability=prob,
            model_version=model_res.model_version,
            model_type=model_res.metadata.get("model_type", "LightGBM/PlattSigmoid"),
            feature_schema_version=input_contract.feature_schema_version,
            is_calibrated=True,
            decision_threshold=threshold,
            bust_alert=has_alert,
            reason_code="SUCCESS",
            error_message=None,
            metadata=model_res.metadata,
        )

    def get_active_model_info(self) -> ModelMetadataInfo:
        """Return introspection information for the currently active model."""
        active = self.active_model
        version = getattr(active, "model_version", "unknown")
        is_ready = getattr(active, "is_ready", False)

        if self._active_model_name == "builder2_gbm":
            return ModelMetadataInfo(
                model_name="builder2_gbm",
                model_version=version or "prototype-gbm-v1",
                model_type="LightGBMClassifier + PlattSigmoidCalibrator",
                feature_schema_version="veyra-26-features-v1.0",
                expected_features=list(FEATURE_COLUMN_NAMES),
                expected_feature_count=len(FEATURE_COLUMN_NAMES),
                decision_threshold=getattr(active, "threshold", 0.280),
                is_calibrated=True,
                is_ready=is_ready,
                artifact_path=str(getattr(active, "model_dir", DEFAULT_BUILDER2_MODEL_PATH)),
            )

        return ModelMetadataInfo(
            model_name=self._active_model_name,
            model_version=version or "baseline-logistic-v1.0",
            model_type="LogisticRegression",
            feature_schema_version="veyra-features-v1.0",
            expected_features=[],
            expected_feature_count=18,
            decision_threshold=0.5,
            is_calibrated=False,
            is_ready=is_ready,
            artifact_path=str(DEFAULT_BASELINE_MODEL_PATH),
        )
