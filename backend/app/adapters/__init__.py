"""Provider Adapters Module for Veyra Phase 3 Day 37 (Gate C7)."""

from backend.app.adapters.fixture_second_provider_adapter import FixtureSecondProviderAdapter
from backend.app.adapters.openmeteo_adapter import OpenMeteoProviderAdapter
from backend.app.adapters.provider_adapter import (
    BaseProviderAdapter,
    NormalizedProviderForecast,
    ProviderResponseStatus,
    ProviderSourceMode,
    normalize_unit_value,
)
from backend.app.adapters.provider_registry import (
    ProviderRegistry,
    UnknownProviderError,
    default_provider_registry,
)

__all__ = [
    "BaseProviderAdapter",
    "NormalizedProviderForecast",
    "ProviderResponseStatus",
    "ProviderSourceMode",
    "normalize_unit_value",
    "OpenMeteoProviderAdapter",
    "FixtureSecondProviderAdapter",
    "ProviderRegistry",
    "UnknownProviderError",
    "default_provider_registry",
]
