"""Builder 2 Integration Package for Forecast-Bust Sentinel.

Contains adapted copies of Builder 2 scientific modules and thin adapter
wrappers implementing Builder 1 abstract service interfaces.
"""
from backend.app.builder2.feature_pipeline import (
    FEATURE_COLUMN_NAMES,
    METADATA_COLUMNS,
    IssueTimeSafeFeaturePipeline,
)
from backend.app.builder2.model_service import ForecastBustModelService
from backend.app.builder2.feature_adapter import Builder2FeatureAdapter
from backend.app.builder2.model_adapter import Builder2ModelAdapter
from backend.app.builder2.weather_adapter import weather_result_to_dataframe

__all__ = [
    "FEATURE_COLUMN_NAMES",
    "METADATA_COLUMNS",
    "IssueTimeSafeFeaturePipeline",
    "ForecastBustModelService",
    "Builder2FeatureAdapter",
    "Builder2ModelAdapter",
    "weather_result_to_dataframe",
]
