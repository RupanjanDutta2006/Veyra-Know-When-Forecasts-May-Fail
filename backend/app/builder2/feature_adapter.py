"""Builder 2 Feature Engineering Adapter for Veyra.

Adapts Builder 2's 26-feature IssueTimeSafeFeaturePipeline to conform to
Builder 1's BaseFeatureService interface.
"""
import logging
from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from builder2.feature_pipeline import (
    FEATURE_COLUMN_NAMES,
    IssueTimeSafeFeaturePipeline,
)
from builder2.instability_fingerprint import ForecastInstabilityFingerprintEngine
from backend.app.builder2.weather_adapter import weather_result_to_dataframe
from backend.app.schemas.prediction import ReasonCode
from backend.app.services.base import BaseFeatureService, FeatureResult, WeatherResult

logger = logging.getLogger(__name__)


class Builder2FeatureAdapter(BaseFeatureService):
    """Production feature adapter wrapping Builder 2's IssueTimeSafeFeaturePipeline.

    Extracts the canonical 26-feature matrix from WeatherResult and passes
    experimental Day 7 instability fingerprint as structured metadata.
    """

    def __init__(self, eps: float = 1e-6, include_fingerprint: bool = True):
        self.pipeline = IssueTimeSafeFeaturePipeline(eps=eps)
        self.fingerprint_engine = ForecastInstabilityFingerprintEngine() if include_fingerprint else None
        self.is_ready = True

    def build_features(self, weather_result: WeatherResult) -> FeatureResult:
        """Transform WeatherResult into 26-feature FeatureResult."""
        if not weather_result.is_available or weather_result.error:
            return FeatureResult(
                location=weather_result.location,
                features={},
                feature_names=[],
                is_ready=False,
                metadata={"status": ReasonCode.DATA_UNAVAILABLE.value},
                error=weather_result.error or "Weather data unavailable for feature extraction",
            )

        df_forecast = weather_result_to_dataframe(weather_result)
        if df_forecast.empty:
            return FeatureResult(
                location=weather_result.location,
                features={},
                feature_names=[],
                is_ready=False,
                metadata={"status": ReasonCode.DATA_NOT_READY.value},
                error="Weather result contains zero parseable forecast records",
            )

        try:
            # Extract canonical 26 features strictly via Builder 2 pipeline
            X, metadata_df = self.pipeline.extract_features(df_forecast)

            if X.empty:
                return FeatureResult(
                    location=weather_result.location,
                    features={},
                    feature_names=[],
                    is_ready=False,
                    metadata={"status": ReasonCode.FEATURES_NOT_READY.value},
                    error="Feature pipeline produced empty feature matrix",
                )

            # Validate exact canonical 26-feature contract
            if list(X.columns) != FEATURE_COLUMN_NAMES:
                return FeatureResult(
                    location=weather_result.location,
                    features={},
                    feature_names=[],
                    is_ready=False,
                    metadata={"status": ReasonCode.QC_FAILED.value},
                    error=f"Feature columns do not match canonical contract. Expected {len(FEATURE_COLUMN_NAMES)}, got {len(X.columns)}",
                )

            # Build summary feature dictionary (first row or mean vector with NaNs preserved for revisions)
            first_row = X.iloc[0].to_dict()
            features_dict = {
                col: (float(first_row[col]) if first_row[col] is not None and not np.isnan(first_row[col]) else None)
                for col in FEATURE_COLUMN_NAMES
            }

            # Generate experimental Day 7 instability fingerprint (metadata only — NOT fed into model)
            fingerprint_dict = None
            if self.fingerprint_engine is not None and len(X) > 0:
                try:
                    var_name = metadata_df["variable"].iloc[0] if "variable" in metadata_df.columns else "temperature_2m"
                    fingerprint_dict = self.fingerprint_engine.build_fingerprint(
                        row=X.iloc[0].to_dict(),
                        variable=var_name,
                    )
                except Exception as fp_exc:
                    logger.debug("Optional instability fingerprint extraction skipped: %s", fp_exc)

            return FeatureResult(
                location=weather_result.location,
                features=features_dict,
                feature_names=FEATURE_COLUMN_NAMES.copy(),
                is_ready=True,
                metadata={
                    "status": ReasonCode.SUCCESS.value,
                    "record_count": len(X),
                    "feature_count": len(FEATURE_COLUMN_NAMES),
                    "feature_matrix_rows": X.to_dict(orient="records"),
                    "metadata_rows": metadata_df.to_dict(orient="records") if not metadata_df.empty else [],
                    "instability_fingerprint": fingerprint_dict,
                    "schema_version": "builder2-canonical-26-v1.0",
                },
            )

        except Exception as exc:
            logger.error("Error during Builder2FeatureAdapter.build_features: %s", exc)
            return FeatureResult(
                location=weather_result.location,
                features={},
                feature_names=[],
                is_ready=False,
                metadata={"status": ReasonCode.FEATURES_NOT_READY.value},
                error=f"Feature extraction failed: {exc}",
            )
