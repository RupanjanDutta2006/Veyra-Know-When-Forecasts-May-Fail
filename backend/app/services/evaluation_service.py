"""Model Evaluation Integration Service for Veyra Phase 2 Day 12.

Provides a clean, stable boundary for discovering, validating, and exposing
model evaluation results, metrics, dataset partitions, and calibration parameters
without modifying model artifacts or leaking runtime exceptions.
"""
import json
import logging
import math
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from backend.app.schemas.evaluation import (
    CalibrationMetadata,
    EvaluationDatasetInfo,
    EvaluationMetrics,
    EvaluationStatus,
    ModelEvaluationResponse,
)
from backend.app.services.model_integration_service import (
    ModelIntegrationService,
)

logger = logging.getLogger(__name__)

DEFAULT_BUILDER2_METADATA_PATH = Path("models/day4/model_metadata.json")
DEFAULT_BASELINE_METADATA_PATH = Path("models/baseline_logistic_v1_metadata.json")

# Recognized model identifier aliases
SUPPORTED_ACTIVE_MODEL_ALIASES = {
    "builder2_gbm",
    "prototype-gbm-v1",
    "gbm",
    "lightgbm",
}

SUPPORTED_BASELINE_MODEL_ALIASES = {
    "baseline_logistic",
    "baseline-logistic-v1.0",
    "baseline",
    "logistic",
}


class BaseEvaluationService(ABC):
    """Abstract interface for model evaluation access."""

    @abstractmethod
    def get_evaluation(
        self, model_name: Optional[str] = None
    ) -> ModelEvaluationResponse:
        """Retrieve validated evaluation metadata for the active or requested model."""
        pass

    @abstractmethod
    def get_baseline_evaluation(self) -> ModelEvaluationResponse:
        """Retrieve evaluation metadata for the historical Phase 1 baseline model."""
        pass


class EvaluationIntegrationService(BaseEvaluationService):
    """Production Evaluation Integration Service.

    Discovers evaluation outputs on disk, enforces version and schema compatibility,
    strictly validates metric bounds and finiteness, and exposes structured evaluation
    contracts for API consumers, monitoring dashboards, and frontend platforms.
    """

    def __init__(
        self,
        model_integration_service: Optional[ModelIntegrationService] = None,
        builder2_metadata_path: Optional[Path] = None,
        baseline_metadata_path: Optional[Path] = None,
    ):
        self.model_integration_service = model_integration_service or ModelIntegrationService()
        self.builder2_metadata_path = builder2_metadata_path or DEFAULT_BUILDER2_METADATA_PATH
        self.baseline_metadata_path = baseline_metadata_path or DEFAULT_BASELINE_METADATA_PATH

    def _read_json_file(self, filepath: Path) -> Optional[dict[str, Any]]:
        """Safely read and parse a JSON metadata file from disk."""
        if not filepath.exists():
            logger.info("Evaluation metadata file not found at '%s'", filepath)
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Failed to parse evaluation metadata JSON from '%s': %s", filepath, exc)
            return None

    def _validate_and_build_metrics(self, raw: dict[str, Any]) -> Optional[EvaluationMetrics]:
        """Validate and construct EvaluationMetrics container enforcing value finiteness."""
        try:
            # Clean non-finite values
            cleaned: dict[str, Any] = {}
            for k, v in raw.items():
                if isinstance(v, (int, float)):
                    if math.isnan(v) or math.isinf(v):
                        raise ValueError(f"Metric '{k}' has non-finite value: {v}")
                    cleaned[k] = float(v)
                else:
                    cleaned[k] = v

            # Map raw keys into EvaluationMetrics fields
            return EvaluationMetrics(
                accuracy=cleaned.get("accuracy"),
                precision=cleaned.get("precision"),
                recall=cleaned.get("recall"),
                f1_score=cleaned.get("f1_score"),
                roc_auc=cleaned.get("roc_auc"),
                pr_auc=cleaned.get("pr_auc"),
                brier_score=cleaned.get("brier_score", cleaned.get("brier_score_calibrated")),
                brier_score_uncalibrated=cleaned.get("brier_score_uncalibrated"),
                brier_score_calibrated=cleaned.get("brier_score_calibrated"),
                brier_improvement_pct=cleaned.get("brier_improvement_pct"),
                spread_baseline_roc_auc=cleaned.get("spread_baseline_roc_auc"),
                spread_baseline_pr_auc=cleaned.get("spread_baseline_pr_auc"),
            )
        except Exception as exc:
            logger.warning("Metrics validation failed: %s", exc)
            return None

    def get_evaluation(
        self, model_name: Optional[str] = None
    ) -> ModelEvaluationResponse:
        """Retrieve validated evaluation metadata for the active or requested model."""
        try:
            active_info = self.model_integration_service.get_active_model_info()

            # Normalize requested model name
            req_name = model_name.strip() if (model_name and isinstance(model_name, str) and model_name.strip()) else None

            # Collect recognized active model aliases
            active_aliases = set(SUPPORTED_ACTIVE_MODEL_ALIASES)
            if active_info.model_name:
                active_aliases.add(active_info.model_name.lower())
            if active_info.model_version:
                active_aliases.add(active_info.model_version.lower())

            # 1. Validate requested model name
            if req_name is not None:
                req_lower = req_name.lower()
                if req_lower in SUPPORTED_BASELINE_MODEL_ALIASES:
                    return self.get_baseline_evaluation()
                elif req_lower in active_aliases:
                    target_name = active_info.model_name
                else:
                    logger.info("Unknown model requested for evaluation: '%s'", req_name)
                    return ModelEvaluationResponse(
                        model_name=req_name,
                        model_version="unknown",
                        evaluation_status=EvaluationStatus.UNAVAILABLE,
                        metrics=None,
                        calibration=None,
                        dataset_info=None,
                        reason_codes=["UNKNOWN_MODEL"],
                        metadata={"error": f"Requested model '{req_name}' is not recognized or registered."},
                    )
            else:
                target_name = active_info.model_name

            # 2. Check if active model is unavailable
            if active_info.model_name == "unavailable":
                return ModelEvaluationResponse(
                    model_name="unavailable",
                    model_version="unknown",
                    evaluation_status=EvaluationStatus.UNAVAILABLE,
                    metrics=None,
                    calibration=None,
                    dataset_info=None,
                    reason_codes=["MODEL_UNAVAILABLE"],
                    metadata={"error": "Active model is currently unavailable"},
                )

            # 3. Builder 2 LightGBM model evaluation
            metadata_dict = self._read_json_file(self.builder2_metadata_path)
            if not metadata_dict:
                return ModelEvaluationResponse(
                    model_name=target_name,
                    model_version=active_info.model_version,
                    model_type=active_info.model_type,
                    data_version="gefs-openmeteo-v1.0",
                    feature_schema_version=active_info.feature_schema_version,
                    feature_count=active_info.expected_feature_count,
                    evaluation_status=EvaluationStatus.UNAVAILABLE,
                    metrics=None,
                    calibration=CalibrationMetadata(
                        is_calibrated=active_info.is_calibrated,
                        decision_threshold=active_info.decision_threshold,
                        calibration_method="sigmoid",
                        calibrator_status="UNAVAILABLE",
                    ),
                    dataset_info=None,
                    reason_codes=["EVALUATION_METADATA_UNAVAILABLE"],
                    metadata={"error": "Metadata file not found on disk"},
                )

            # 4. Model-version compatibility check
            meta_version = metadata_dict.get("model_version")
            if meta_version and meta_version != active_info.model_version:
                logger.warning(
                    "Model version mismatch: metadata specifies '%s' but active model is '%s'",
                    meta_version,
                    active_info.model_version,
                )
                return ModelEvaluationResponse(
                    model_name=target_name,
                    model_version=active_info.model_version,
                    model_type=metadata_dict.get("model_type", active_info.model_type),
                    data_version="gefs-openmeteo-v1.0",
                    feature_schema_version=active_info.feature_schema_version,
                    feature_count=active_info.expected_feature_count,
                    evaluation_status=EvaluationStatus.INCOMPATIBLE,
                    metrics=None,
                    calibration=None,
                    dataset_info=None,
                    reason_codes=["MODEL_VERSION_MISMATCH"],
                    metadata={
                        "expected_version": active_info.model_version,
                        "metadata_version": meta_version,
                    },
                )

            # 5. Parse & validate metrics
            raw_test_metrics = metadata_dict.get("test_metrics") or {}
            metrics = self._validate_and_build_metrics(raw_test_metrics)
            if metrics is None and bool(raw_test_metrics):
                return ModelEvaluationResponse(
                    model_name=target_name,
                    model_version=active_info.model_version,
                    model_type=metadata_dict.get("model_type", active_info.model_type),
                    data_version="gefs-openmeteo-v1.0",
                    feature_schema_version=active_info.feature_schema_version,
                    feature_count=active_info.expected_feature_count,
                    evaluation_status=EvaluationStatus.INVALID,
                    metrics=None,
                    calibration=None,
                    dataset_info=None,
                    reason_codes=["METRICS_VALIDATION_ERROR"],
                    metadata={"error": "Test metrics contains non-finite or invalid values"},
                )

            # 6. Extract sample counts and time ranges
            sample_counts = metadata_dict.get("sample_counts") or {}
            time_ranges = metadata_dict.get("time_ranges") or {}
            dataset_info = EvaluationDatasetInfo(
                dataset_name="builder2_prototype_dataset",
                split_name="test",
                total_samples=sample_counts.get("total"),
                train_samples=sample_counts.get("train"),
                validation_samples=sample_counts.get("validation"),
                test_samples=sample_counts.get("test"),
                time_ranges=time_ranges,
            )

            # 7. Extract calibration metadata
            calib = CalibrationMetadata(
                is_calibrated=True,
                calibration_method=metadata_dict.get("calibration_method", "sigmoid"),
                decision_threshold=metadata_dict.get("decision_threshold", 0.28),
                calibrator_status="OPERATIONAL",
            )

            return ModelEvaluationResponse(
                model_name=target_name,
                model_version=active_info.model_version,
                model_type=metadata_dict.get("model_type", active_info.model_type),
                data_version="gefs-openmeteo-v1.0",
                feature_schema_version=metadata_dict.get("feature_schema_version", active_info.feature_schema_version),
                feature_count=len(metadata_dict.get("features", [])) or active_info.expected_feature_count,
                evaluation_status=EvaluationStatus.AVAILABLE if metrics else EvaluationStatus.UNAVAILABLE,
                metrics=metrics,
                calibration=calib,
                dataset_info=dataset_info,
                reason_codes=["SUCCESS"] if metrics else ["EVALUATION_METRICS_EMPTY"],
                metadata={
                    "brier_improvement_pct": raw_test_metrics.get("brier_improvement_pct"),
                    "spread_baseline_roc_auc": raw_test_metrics.get("spread_baseline_roc_auc"),
                    "spread_baseline_pr_auc": raw_test_metrics.get("spread_baseline_pr_auc"),
                },
            )

        except Exception as exc:
            logger.error("Unhandled error in get_evaluation: %s", exc)
            return ModelEvaluationResponse(
                model_name=model_name or "unknown",
                model_version="unknown",
                evaluation_status=EvaluationStatus.UNAVAILABLE,
                metrics=None,
                reason_codes=["INTERNAL_ERROR"],
                metadata={"error": "Failed to load model evaluation"},
            )

    def get_baseline_evaluation(self) -> ModelEvaluationResponse:
        """Retrieve evaluation metadata for the historical Phase 1 baseline logistic model."""
        try:
            metadata_dict = self._read_json_file(self.baseline_metadata_path)
            if not metadata_dict:
                return ModelEvaluationResponse(
                    model_name="baseline_logistic",
                    model_version="baseline-logistic-v1.0",
                    model_type="LogisticRegression",
                    data_version="gefs-openmeteo-v1.0",
                    feature_schema_version="veyra-features-v1.0",
                    feature_count=18,
                    evaluation_status=EvaluationStatus.UNAVAILABLE,
                    metrics=None,
                    calibration=CalibrationMetadata(
                        is_calibrated=False,
                        calibration_method=None,
                        decision_threshold=0.5,
                        calibrator_status="UNAVAILABLE",
                    ),
                    dataset_info=None,
                    reason_codes=["BASELINE_METADATA_UNAVAILABLE"],
                )

            raw_test = metadata_dict.get("test_metrics") or {}
            metrics = self._validate_and_build_metrics(raw_test)

            dataset_info = EvaluationDatasetInfo(
                dataset_name="phase1_baseline_dataset",
                split_name="test",
                total_samples=(metadata_dict.get("train_samples", 0) + metadata_dict.get("val_samples", 0) + metadata_dict.get("test_samples", 0)),
                train_samples=metadata_dict.get("train_samples"),
                validation_samples=metadata_dict.get("val_samples"),
                test_samples=metadata_dict.get("test_samples"),
                time_ranges={
                    "train": metadata_dict.get("train_time_range"),
                    "val": metadata_dict.get("val_time_range"),
                    "test": metadata_dict.get("test_time_range"),
                },
            )

            return ModelEvaluationResponse(
                model_name="baseline_logistic",
                model_version=metadata_dict.get("model_version", "baseline-logistic-v1.0"),
                model_type=metadata_dict.get("model_type", "LogisticRegression"),
                data_version="gefs-openmeteo-v1.0",
                feature_schema_version=metadata_dict.get("feature_schema_version", "veyra-features-v1.0"),
                feature_count=len(metadata_dict.get("feature_names", [])) or 18,
                evaluation_status=EvaluationStatus.AVAILABLE if metrics else EvaluationStatus.UNAVAILABLE,
                metrics=metrics,
                calibration=CalibrationMetadata(
                    is_calibrated=False,
                    calibration_method=None,
                    decision_threshold=0.5,
                    calibrator_status="NOT_CALIBRATED",
                ),
                dataset_info=dataset_info,
                reason_codes=["SUCCESS"] if metrics else ["BASELINE_METRICS_EMPTY"],
                evaluated_at=metadata_dict.get("created_at"),
                metadata={
                    "split_strategy": metadata_dict.get("split_strategy"),
                    "threshold_policy": metadata_dict.get("threshold_policy"),
                    "val_metrics": metadata_dict.get("val_metrics"),
                },
            )

        except Exception as exc:
            logger.error("Unhandled error in get_baseline_evaluation: %s", exc)
            return ModelEvaluationResponse(
                model_name="baseline_logistic",
                model_version="baseline-logistic-v1.0",
                evaluation_status=EvaluationStatus.UNAVAILABLE,
                metrics=None,
                reason_codes=["INTERNAL_ERROR"],
                metadata={"error": "Failed to load baseline evaluation"},
            )
