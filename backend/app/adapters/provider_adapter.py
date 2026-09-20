"""Authoritative Provider Adapter Abstraction & Data Contracts for Veyra Phase 3 Day 37 (Gate C7).

Provides normalized, multi-provider forecast retrieval interfaces, unit conversions,
and time contracts while maintaining 100% backward compatibility with Veyra's scientific model.

SCIENTIFIC GOVERNANCE INVARIANTS:
1. Canonical Unit Normalization: All provider adapters must normalize forecast values to Veyra canonical units:
   - Temperature: °C
   - Wind Speed: m/s
   - Surface Pressure: hPa
2. Temporal Alignment: Times must normalize to UTC ISO 8601 strings, enforcing canonical valid-time matching.
3. Explicit Failure States: Provider failures or missing data return typed unavailable status instead of fake zero or zero bust probability.
4. Non-Destructive Abstraction: Does not modify the frozen 50-feature V3 LightGBM model or P(BUST) estimation.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.time_contract import (
    derive_and_validate_lead_hours,
    parse_utc_timestamp,
)

logger = logging.getLogger(__name__)


class ProviderSourceMode(str, Enum):
    """Enumeration of provider execution modes."""

    LIVE = "LIVE"
    FIXTURE = "FIXTURE"


class ProviderResponseStatus(str, Enum):
    """Enumeration of normalized provider retrieval outcomes."""

    SUCCESS = "SUCCESS"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNSUPPORTED_VARIABLE = "UNSUPPORTED_VARIABLE"
    TIME_MISMATCH = "TIME_MISMATCH"
    ERROR = "ERROR"


@dataclass
class NormalizedProviderForecast:
    """Standardized, provider-agnostic forecast record container."""

    provider_id: str
    provider_name: str
    provider_source_mode: ProviderSourceMode
    canonical_location: str
    latitude: float
    longitude: float
    issue_time: str
    valid_time: str
    lead_hours: int
    variable: str
    forecast_value: Optional[float]
    unit: str
    ensemble_mean: Optional[float] = None
    ensemble_std: Optional[float] = None
    member_values: Optional[List[float]] = None
    is_available: bool = False
    status: ProviderResponseStatus = ProviderResponseStatus.SUCCESS
    error_detail: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def normalize_unit_value(value: float, source_unit: str, target_variable: str) -> Tuple[float, str]:
    """Convert raw forecast values into Veyra canonical units (°C, m/s, hPa).

    Args:
        value: Raw numerical value.
        source_unit: Unit string reported by source provider.
        target_variable: Veyra variable identifier.

    Returns:
        Tuple of (normalized_value, canonical_unit).
    """
    unit_clean = (source_unit or "").strip().lower()

    if target_variable == "temperature_2m":
        if unit_clean in ["k", "kelvin"]:
            return (value - 273.15, "°C")
        elif unit_clean in ["°f", "f", "fahrenheit"]:
            return ((value - 32.0) * 5.0 / 9.0, "°C")
        else:
            # Default assumes °C
            return (value, "°C")

    elif target_variable == "wind_speed_10m":
        if unit_clean in ["km/h", "kmh"]:
            return (value / 3.6, "m/s")
        elif unit_clean in ["kt", "knots", "knot"]:
            return (value * 0.514444, "m/s")
        else:
            # Default assumes m/s
            return (value, "m/s")

    elif target_variable == "surface_pressure":
        if unit_clean in ["pa", "pascal", "pascals"]:
            return (value / 100.0, "hPa")
        elif unit_clean in ["bar"]:
            return (value * 1000.0, "hPa")
        elif unit_clean in ["atm"]:
            return (value * 1013.25, "hPa")
        else:
            # Default assumes hPa
            return (value, "hPa")

    return (value, source_unit)


class BaseProviderAdapter(ABC):
    """Abstract interface for forecast provider adapters."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique machine identifier for the provider."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable display name of the provider."""
        pass

    @property
    @abstractmethod
    def provider_source_mode(self) -> ProviderSourceMode:
        """Operating mode (LIVE or FIXTURE)."""
        pass

    @abstractmethod
    def fetch_forecast(
        self,
        location: str,
        variable: str,
        lead_hours: int = 24,
        issue_time: Optional[str] = None,
        valid_time: Optional[str] = None,
    ) -> NormalizedProviderForecast:
        """Fetch and normalize a forecast record for a given location, variable, and time horizon."""
        pass
