"""Builder 2 — Forecast-Bust Sentinel Scientific Engine.

Provides core scientific intelligence:
- 26-feature canonical issue-time safe pipeline
- prototype-gbm-v1 model inference and Platt Sigmoid calibration
- deterministic physical feature attribution (explainer)
- 20-city location registry and spatial colocation
- Day 7 experimental instability dynamics and fingerprinting
"""
from builder2.feature_pipeline import (
    FEATURE_COLUMN_NAMES,
    METADATA_COLUMNS,
    IssueTimeSafeFeaturePipeline,
)
from builder2.model_service import ForecastBustModelService
from builder2.location_service import LocationRegistry
from builder2.explainer import ForecastBustExplainer

__all__ = [
    "FEATURE_COLUMN_NAMES",
    "METADATA_COLUMNS",
    "IssueTimeSafeFeaturePipeline",
    "ForecastBustModelService",
    "LocationRegistry",
    "ForecastBustExplainer",
]
