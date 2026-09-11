"""Abstract Base Service Interfaces and Typed Result Containers for Forecast-Bust Sentinel.

Defines the integration boundary between Builder 1 (Orchestrator, API, Safety)
and Builder 2 (Weather Ingestion, Feature Pipeline, Calibrated ML Models).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class WeatherResult:
    """Standardized container for fetched weather forecast and atmospheric observation data."""

    location: str
    target_date: Optional[str] = None
    raw_data: dict[str, Any] = field(default_factory=dict)
    data_version: Optional[str] = None
    is_available: bool = False
    quality_flags: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


# Alias for backward-compatibility with Day-1 code
WeatherDataResult = WeatherResult


@dataclass
class FeatureResult:
    """Standardized container for engineered ML feature vectors."""

    location: str
    features: dict[str, float] = field(default_factory=dict)
    feature_names: list[str] = field(default_factory=list)
    is_ready: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class ModelResult:
    """Standardized container for calibrated ML model prediction output."""

    probability: Optional[float] = None
    model_version: Optional[str] = None
    is_ready: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class BaseWeatherService(ABC):
    """Interface for Weather Data Collection services (Builder 2 integration hook)."""

    @abstractmethod
    def get_forecast(
        self, location: str, target_date: Optional[str] = None
    ) -> WeatherResult:
        """Fetch raw forecast and atmospheric data for a given location."""
        pass

    def fetch_forecast_data(
        self, location: str, target_date: Optional[str] = None
    ) -> WeatherResult:
        """Alias for backward-compatibility with Day-1 callers."""
        return self.get_forecast(location, target_date)


class BaseFeatureService(ABC):
    """Interface for Feature Engineering services (Builder 2 integration hook)."""

    @abstractmethod
    def build_features(self, weather_result: WeatherResult) -> FeatureResult:
        """Transform raw forecast data into engineered feature vectors."""
        pass

    def extract_features(self, weather_data: WeatherResult) -> FeatureResult:
        """Alias for backward-compatibility with Day-1 callers."""
        return self.build_features(weather_data)


class BaseModelService(ABC):
    """Interface for ML Bust Probability Estimation models (Builder 2 integration hook)."""

    @abstractmethod
    def predict(self, feature_result: FeatureResult) -> ModelResult:
        """Generate calibrated forecast-bust probability given engineered features."""
        pass


class BaseSafetyService(ABC):
    """Interface for Safety, OOD Detection, and Abstention evaluation."""

    @abstractmethod
    def evaluate(
        self,
        weather_result: WeatherResult,
        feature_result: FeatureResult,
        model_result: ModelResult,
        context: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Perform safety evaluation and return a SafetyAssessment."""
        pass
