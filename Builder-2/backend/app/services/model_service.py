"""Model Service Interface and Production Implementation."""
import logging
from typing import Any, Optional
import numpy as np

from backend.app.ml.artifacts import ModelArtifactManager
from backend.app.ml.baseline_model import LogisticRegressionBustModel
from backend.app.schemas.prediction import ReasonCode
from backend.app.services.base import BaseModelService, FeatureResult, ModelResult

logger = logging.getLogger(__name__)


class UnavailableModelService(BaseModelService):
    """Default fallback model service when ML model is unavailable."""

    def __init__(self, model_version: Optional[str] = None):
        self.model_version = model_version

    def predict(self, feature_result: FeatureResult) -> ModelResult:
        """Return explicit unavailable state without fabricating any probabilities."""
        return ModelResult(
            probability=None,
            model_version=self.model_version,
            is_ready=False,
            metadata={"status": ReasonCode.MODEL_NOT_READY.value},
            error="ML model is not yet integrated",
        )


class LiveLogisticModelService(BaseModelService):
    """Production ML model service executing inference with the trained Day-5 Logistic Regression model."""

    def __init__(
        self,
        model: Optional[LogisticRegressionBustModel] = None,
        artifacts_dir: str = "models",
        artifact_name: str = "baseline_logistic_v1",
        aggregation_method: str = "mean",
    ):
        self.artifacts_dir = artifacts_dir
        self.artifact_name = artifact_name
        self.aggregation_method = aggregation_method
        self.model: Optional[LogisticRegressionBustModel] = model
        self.model_version: Optional[str] = None
        self.metadata: dict[str, Any] = {}
        self.is_ready: bool = False

        if self.model is None:
            self._load_model()
        else:
            self.is_ready = self.model.is_trained
            self.model_version = "baseline-logistic-v1.0"

    def _load_model(self) -> None:
        """Load persisted Logistic Regression model and metadata from disk."""
        try:
            manager = ModelArtifactManager(artifacts_dir=self.artifacts_dir)
            loaded_model, _, meta_dict = manager.load_artifact(artifact_name=self.artifact_name)
            self.model = loaded_model
            self.metadata = meta_dict or {}
            self.model_version = self.metadata.get("model_version", "baseline-logistic-v1.0")
            self.is_ready = self.model.is_trained
            logger.info("LiveLogisticModelService loaded model version '%s'", self.model_version)
        except Exception as exc:
            logger.warning("LiveLogisticModelService could not load artifact '%s': %s", self.artifact_name, exc)
            self.model = None
            self.model_version = None
            self.is_ready = False

    def predict(self, feature_result: FeatureResult) -> ModelResult:
        """Generate real P(BUST) probability from engineered inference features."""
        if not self.is_ready or self.model is None:
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={"status": ReasonCode.MODEL_NOT_READY.value},
                error="Trained ML model artifact is unavailable",
            )

        if not feature_result.is_ready or feature_result.error:
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={"status": ReasonCode.FEATURES_NOT_READY.value},
                error=feature_result.error or "Features not ready for model inference",
            )

        # Retrieve feature matrix from metadata or features dict
        feature_matrix_raw = feature_result.metadata.get("feature_matrix")
        if feature_matrix_raw:
            X_matrix = np.array(feature_matrix_raw, dtype=np.float64)
        else:
            # Reconstruct single-row vector from feature dictionary
            if not feature_result.features or not feature_result.feature_names:
                return ModelResult(
                    probability=None,
                    model_version=self.model_version,
                    is_ready=False,
                    metadata={"status": ReasonCode.FEATURES_NOT_READY.value},
                    error="Feature result contains no feature vectors",
                )
            vector = [feature_result.features.get(name, 0.0) for name in feature_result.feature_names]
            X_matrix = np.array([vector], dtype=np.float64)

        # Dimension validation (18 features expected)
        if X_matrix.shape[1] != 18:
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={"status": ReasonCode.QC_FAILED.value},
                error=f"Expected 18 features, got {X_matrix.shape[1]}",
            )

        try:
            # Predict P(bust) using the trained model's logistic sigmoid probability
            step_probabilities = self.model.predict_proba(X_matrix)

            if len(step_probabilities) == 0:
                return ModelResult(
                    probability=None,
                    model_version=self.model_version,
                    is_ready=False,
                    metadata={"status": ReasonCode.INTERNAL_ERROR.value},
                    error="Model produced empty predictions",
                )

            # Compute representative aggregate bust probability
            if self.aggregation_method == "max":
                prob_val = float(np.max(step_probabilities))
            else:
                prob_val = float(np.mean(step_probabilities))

            # Strictly validate probability bounds [0.0, 1.0]
            if not (0.0 <= prob_val <= 1.0) or np.isnan(prob_val) or np.isinf(prob_val):
                return ModelResult(
                    probability=None,
                    model_version=self.model_version,
                    is_ready=False,
                    metadata={"status": ReasonCode.QC_FAILED.value},
                    error=f"Model produced invalid probability: {prob_val}",
                )

            final_prob = round(prob_val, 4)

            return ModelResult(
                probability=final_prob,
                model_version=self.model_version,
                is_ready=True,
                metadata={
                    "step_count": len(step_probabilities),
                    "min_step_prob": round(float(np.min(step_probabilities)), 4),
                    "max_step_prob": round(float(np.max(step_probabilities)), 4),
                    "aggregation": self.aggregation_method,
                    "model_type": self.metadata.get("model_type", "LogisticRegression"),
                    "threshold_policy": self.metadata.get("threshold_policy", "FixedThresholdPolicy"),
                },
            )

        except Exception as exc:
            logger.error("Error during LiveLogisticModelService.predict: %s", exc)
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={"status": ReasonCode.INTERNAL_ERROR.value},
                error=f"Model inference failed: {exc}",
            )
