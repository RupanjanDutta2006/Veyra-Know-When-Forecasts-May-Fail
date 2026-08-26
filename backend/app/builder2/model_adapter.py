"""Builder 2 Model Inference Adapter for Veyra.

Adapts Builder 2's ForecastBustModelService (LightGBM + Platt Sigmoid Calibration)
to conform to Builder 1's BaseModelService interface.
"""
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from builder2.explainer import ForecastBustExplainer
from builder2.feature_pipeline import FEATURE_COLUMN_NAMES
from builder2.model_service import ForecastBustModelService
from backend.app.schemas.prediction import ReasonCode
from backend.app.services.base import BaseModelService, FeatureResult, ModelResult

logger = logging.getLogger(__name__)


class Builder2ModelAdapter(BaseModelService):
    """Production model adapter wrapping Builder 2's ForecastBustModelService.

    Uses the verified prototype-gbm-v1 LightGBM model with Platt Sigmoid calibration
    at the calibrated decision threshold of 0.280.

    When model artifacts are unavailable or unconfigured, safely abstains with
    probability=None and is_ready=False without fabricating probabilities or
    falling back to unrelated models.
    """

    def __init__(
        self,
        model_dir: Optional[Union[str, Path]] = None,
        aggregation_method: str = "max",
    ):
        self.model_dir = Path(model_dir) if model_dir else None
        self.aggregation_method = aggregation_method
        self.service: Optional[ForecastBustModelService] = None
        self.model_version: Optional[str] = None
        self.threshold: float = 0.280
        self.is_ready: bool = False

        self._initialize_service()

    def _initialize_service(self) -> None:
        """Attempt to load ForecastBustModelService from configured model_dir."""
        target_dir = self.model_dir or os.getenv("BUILDER2_MODEL_DIR")
        if not target_dir:
            logger.info("BUILDER2_MODEL_DIR is not set; Builder2ModelAdapter initialized in unavailable state.")
            self.is_ready = False
            self.service = None
            self.model_version = None
            return

        target_path = Path(target_dir)
        try:
            self.service = ForecastBustModelService(model_dir=target_path)
            self.model_version = self.service.model_version
            self.threshold = self.service.threshold
            self.is_ready = True
            logger.info("Builder2ModelAdapter successfully loaded model '%s' from '%s'", self.model_version, target_path)
        except Exception as exc:
            logger.warning("Builder2ModelAdapter could not load artifacts from '%s': %s", target_path, exc)
            self.service = None
            self.model_version = None
            self.is_ready = False

    def predict(self, feature_result: FeatureResult) -> ModelResult:
        """Compute calibrated forecast-bust probability using prototype-gbm-v1."""
        if not self.is_ready or self.service is None:
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={"status": ReasonCode.MODEL_NOT_READY.value},
                error="Builder 2 model artifact is unavailable (BUILDER2_MODEL_DIR unconfigured or invalid)",
            )

        if not feature_result.is_ready or feature_result.error:
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={"status": ReasonCode.FEATURES_NOT_READY.value},
                error=feature_result.error or "Features not ready for model inference",
            )

        # Reconstruct DataFrame with exact 26 canonical features
        matrix_rows = feature_result.metadata.get("feature_matrix_rows")
        if matrix_rows and isinstance(matrix_rows, list):
            df_features = pd.DataFrame(matrix_rows)
        else:
            # Reconstruct single row from features dict
            if not feature_result.features:
                return ModelResult(
                    probability=None,
                    model_version=self.model_version,
                    is_ready=False,
                    metadata={"status": ReasonCode.FEATURES_NOT_READY.value},
                    error="FeatureResult contains no feature data",
                )
            df_features = pd.DataFrame([feature_result.features])

        # Validate column existence
        missing_cols = [c for c in FEATURE_COLUMN_NAMES if c not in df_features.columns]
        if missing_cols:
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={"status": ReasonCode.QC_FAILED.value},
                error=f"Input features missing required canonical columns: {missing_cols}",
            )

        try:
            # Run inference strictly through Builder 2 ForecastBustModelService
            step_predictions = self.service.predict(df_features[FEATURE_COLUMN_NAMES])

            if not step_predictions:
                return ModelResult(
                    probability=None,
                    model_version=self.model_version,
                    is_ready=False,
                    metadata={"status": ReasonCode.INTERNAL_ERROR.value},
                    error="Model service returned zero predictions",
                )

            probabilities = [p["probability"] for p in step_predictions]
            alerts = [p["bust_alert"] for p in step_predictions]

            # Aggregate probability across forecast steps
            if self.aggregation_method == "max":
                agg_prob = float(np.max(probabilities))
            else:
                agg_prob = float(np.mean(probabilities))

            # Enforce probability bounds [0.0, 1.0]
            if not (0.0 <= agg_prob <= 1.0) or np.isnan(agg_prob) or np.isinf(agg_prob):
                return ModelResult(
                    probability=None,
                    model_version=self.model_version,
                    is_ready=False,
                    metadata={"status": ReasonCode.QC_FAILED.value},
                    error=f"Model produced invalid out-of-bounds probability: {agg_prob}",
                )

            # Generate physical explanation for the representative step
            rep_idx = int(np.argmax(probabilities)) if self.aggregation_method == "max" else 0
            rep_features = df_features.iloc[rep_idx].to_dict()
            explanation = ForecastBustExplainer.explain_row(
                feature_row=rep_features,
                bust_probability=agg_prob,
                threshold=self.threshold,
            )

            final_prob = round(agg_prob, 4)
            has_alert = bool(final_prob >= self.threshold)

            return ModelResult(
                probability=final_prob,
                model_version=self.model_version,
                is_ready=True,
                metadata={
                    "status": ReasonCode.SUCCESS.value,
                    "step_count": len(step_predictions),
                    "min_step_prob": round(float(np.min(probabilities)), 4),
                    "max_step_prob": round(float(np.max(probabilities)), 4),
                    "bust_alert": has_alert,
                    "decision_threshold": self.threshold,
                    "aggregation": self.aggregation_method,
                    "explanation": explanation.to_dict(),
                    "instability_fingerprint": feature_result.metadata.get("instability_fingerprint"),
                },
            )

        except Exception as exc:
            logger.error("Error during Builder2ModelAdapter.predict: %s", exc)
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={"status": ReasonCode.INTERNAL_ERROR.value},
                error=f"Builder 2 model inference failed: {exc}",
            )
