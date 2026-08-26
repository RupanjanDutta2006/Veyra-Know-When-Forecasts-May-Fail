"""Builder 2 Integration Adapters for Veyra.

Contains thin adapter wrappers implementing Builder 1's abstract service interfaces
by delegating to Builder 2's root scientific engine (builder2.*).
"""
from backend.app.builder2.feature_adapter import Builder2FeatureAdapter
from backend.app.builder2.model_adapter import Builder2ModelAdapter
from backend.app.builder2.weather_adapter import weather_result_to_dataframe

__all__ = [
    "Builder2FeatureAdapter",
    "Builder2ModelAdapter",
    "weather_result_to_dataframe",
]
