"""Services package exporting base interfaces and concrete implementations."""
from backend.app.services.base import (
    BaseFeatureService,
    BaseModelService,
    BaseSafetyService,
    BaseWeatherService,
    FeatureResult,
    ModelResult,
    WeatherDataResult,
    WeatherResult,
)
from backend.app.services.feature_service import (
    LiveFeatureService,
    UnavailableFeatureService,
)
from backend.app.services.model_service import (
    LiveLogisticModelService,
    UnavailableModelService,
)
from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService
from backend.app.services.reference_service import (
    BaseReferenceWeatherService,
    OpenMeteoArchiveReferenceService,
)
from backend.app.services.weather_service import UnavailableWeatherService

__all__ = [
    "BaseWeatherService",
    "BaseFeatureService",
    "BaseModelService",
    "BaseSafetyService",
    "WeatherResult",
    "WeatherDataResult",
    "FeatureResult",
    "ModelResult",
    "UnavailableWeatherService",
    "OpenMeteoGEFSWeatherService",
    "UnavailableFeatureService",
    "LiveFeatureService",
    "UnavailableModelService",
    "LiveLogisticModelService",
    "BaseReferenceWeatherService",
    "OpenMeteoArchiveReferenceService",
]

