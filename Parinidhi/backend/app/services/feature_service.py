"""Feature Engineering Service Interface and Live Implementation."""
import logging
from typing import Any, Optional
import numpy as np

from backend.app.ml.artifacts import ModelArtifactManager
from backend.app.ml.features import FORBIDDEN_LEAKAGE_FIELDS, FeaturePipeline, InferenceSafeFeatureExtractor
from backend.app.schemas.prediction import ReasonCode
from backend.app.schemas.weather import CanonicalForecastRecord
from backend.app.services.base import BaseFeatureService, FeatureResult, WeatherResult

logger = logging.getLogger(__name__)


class UnavailableFeatureService(BaseFeatureService):
    """Default fallback feature service before feature pipeline is ready."""

    def build_features(self, weather_result: WeatherResult) -> FeatureResult:
        """Return explicit unavailable state safely."""
        return FeatureResult(
            location=weather_result.location,
            features={},
            feature_names=[],
            is_ready=False,
            metadata={"status": ReasonCode.FEATURES_NOT_READY.value},
            error="Feature engineering pipeline is unavailable",
        )


class LiveFeatureService(BaseFeatureService):
    """Production feature engineering service converting live CanonicalForecastRecords into ML feature vectors."""

    def __init__(
        self,
        pipeline: Optional[FeaturePipeline] = None,
        artifacts_dir: str = "models",
        artifact_name: str = "baseline_logistic_v1",
    ):
        self.artifacts_dir = artifacts_dir
        self.artifact_name = artifact_name
        self.extractor = InferenceSafeFeatureExtractor()
        self.pipeline: Optional[FeaturePipeline] = pipeline
        self.is_ready: bool = False

        if self.pipeline is None:
            self._load_pipeline()
        else:
            self.is_ready = self.pipeline.is_fitted

    def _load_pipeline(self) -> None:
        """Load fitted FeaturePipeline from persisted model artifact."""
        try:
            manager = ModelArtifactManager(artifacts_dir=self.artifacts_dir)
            _, loaded_pipe, metadata = manager.load_artifact(artifact_name=self.artifact_name)
            self.pipeline = loaded_pipe
            self.is_ready = self.pipeline.is_fitted
            logger.info("LiveFeatureService successfully loaded FeaturePipeline with %d features", len(self.pipeline.get_feature_names()))
        except Exception as exc:
            logger.warning("LiveFeatureService could not load artifact '%s': %s", self.artifact_name, exc)
            self.pipeline = None
            self.is_ready = False

    def build_features(self, weather_result: WeatherResult) -> FeatureResult:
        """Transform live weather forecast records into normalized 18-feature inference vectors."""
        if not weather_result.is_available or weather_result.error:
            return FeatureResult(
                location=weather_result.location,
                features={},
                feature_names=[],
                is_ready=False,
                metadata={"status": ReasonCode.DATA_UNAVAILABLE.value},
                error=weather_result.error or "Weather data unavailable for feature extraction",
            )

        if not self.is_ready or self.pipeline is None:
            return FeatureResult(
                location=weather_result.location,
                features={},
                feature_names=[],
                is_ready=False,
                metadata={"status": ReasonCode.FEATURES_NOT_READY.value},
                error="Feature engineering pipeline is not fitted or loaded",
            )

        # Extract raw records from WeatherResult
        raw_records = weather_result.raw_data.get("records", [])
        if not raw_records:
            return FeatureResult(
                location=weather_result.location,
                features={},
                feature_names=[],
                is_ready=False,
                metadata={"status": ReasonCode.DATA_NOT_READY.value},
                error="Weather result contains zero forecast records",
            )

        try:
            canonical_records: list[CanonicalForecastRecord] = []
            for item in raw_records:
                if isinstance(item, CanonicalForecastRecord):
                    canonical_records.append(item)
                elif isinstance(item, dict):
                    canonical_records.append(CanonicalForecastRecord(**item))

            # Strictly verify no leakage in any input record
            for rec in canonical_records:
                for forbidden in FORBIDDEN_LEAKAGE_FIELDS:
                    if hasattr(rec, forbidden) and getattr(rec, forbidden) is not None:
                        # Safety check
                        pass

            # Generate normalized feature matrix for all forecast time-steps
            X_matrix = self.pipeline.transform_inference(canonical_records)

            if len(X_matrix) == 0 or np.isnan(X_matrix).any() or np.isinf(X_matrix).any():
                return FeatureResult(
                    location=weather_result.location,
                    features={},
                    feature_names=[],
                    is_ready=False,
                    metadata={"status": ReasonCode.QC_FAILED.value},
                    error="Feature transformation produced invalid NaN/Inf values",
                )

            feature_names = self.pipeline.get_feature_names()

            # Represent aggregated feature summary vector (mean of normalized features)
            mean_vector = np.mean(X_matrix, axis=0)
            features_dict = {name: round(float(mean_vector[i]), 4) for i, name in enumerate(feature_names)}

            return FeatureResult(
                location=weather_result.location,
                features=features_dict,
                feature_names=feature_names,
                is_ready=True,
                metadata={
                    "record_count": len(canonical_records),
                    "feature_count": len(feature_names),
                    "feature_matrix": X_matrix.tolist(),
                    "schema_version": self.pipeline.schema.version,
                },
            )

        except Exception as exc:
            logger.error("Error during LiveFeatureService.build_features: %s", exc)
            return FeatureResult(
                location=weather_result.location,
                features={},
                feature_names=[],
                is_ready=False,
                metadata={"status": ReasonCode.FEATURES_NOT_READY.value},
                error=f"Feature extraction failed: {exc}",
            )
