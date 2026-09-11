"""Weather Data Service Interface and Unavailable Fallback implementation."""
from typing import Optional
from backend.app.schemas.prediction import ReasonCode
from backend.app.services.base import BaseWeatherService, WeatherResult


class UnavailableWeatherService(BaseWeatherService):
    """Default fallback weather service before Builder 2's ingestion pipeline is integrated.

    Always returns an explicit unavailable state safely without fabricating fake weather data.
    """

    def __init__(
        self,
        data_version: Optional[str] = None,
        reason_code: Optional[ReasonCode] = None,
    ):
        self.data_version = data_version
        self.reason_code = reason_code or ReasonCode.MODEL_NOT_READY

    def get_forecast(
        self, location: str, target_date: Optional[str] = None
    ) -> WeatherResult:
        """Return empty/unavailable data container safely."""
        return WeatherResult(
            location=location,
            target_date=target_date,
            raw_data={},
            data_version=self.data_version,
            is_available=False,
            quality_flags={},
            metadata={"status": self.reason_code.value},
            error="Weather data ingestion pipeline is not yet integrated",
        )
