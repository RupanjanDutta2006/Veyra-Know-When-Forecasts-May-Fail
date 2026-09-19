"""Forecast Disagreement Intelligence Schemas for Veyra Phase 3 Day 29.

Provides typed, scientifically defensible API contracts for ensemble forecast
dispersion diagnostics derived from authoritative NOAA GEFS ensemble records.
"""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from backend.app.schemas.prediction import (
    MAX_SUPPORTED_LEAD_HOURS,
    CalibrationStatus,
    ReasonCode,
    RiskLevel,
    SUPPORTED_VARIABLES,
    TrustState,
)


class DisagreementStatus(str, Enum):
    """Availability status of ensemble disagreement diagnostics."""

    AVAILABLE = "AVAILABLE"        # Ensemble dispersion diagnostics successfully evaluated
    UNAVAILABLE = "UNAVAILABLE"    # Upstream ensemble data missing or insufficient
    ABSTAINED = "ABSTAINED"        # Safety abstention active (e.g. invalid location)


class DisagreementDiagnostics(BaseModel):
    """Quantitative dispersion diagnostics derived from real ensemble members."""

    ensemble_spread: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Ensemble sample standard deviation with Bessel correction (ddof=1) in native units. Direct measure of forecast spread.",
    )
    ensemble_std: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Alias for ensemble_spread for contract compatibility.",
    )
    ensemble_range: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Full spread span between highest and lowest member values (max - min) in native units.",
    )
    ensemble_iqr: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Inter-percentile range between 90th and 10th percentiles (p90 - p10) in native units.",
    )
    ensemble_cv: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Dimensionless coefficient of variation (std / |mean|), assessing relative dispersion.",
    )
    spread_to_iqr_ratio: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Dimensionless ratio of standard deviation to IQR, indicating distribution tail concentration.",
    )
    ensemble_mean: Optional[float] = Field(
        default=None,
        description="Mean forecast value across evaluated ensemble members in native units.",
    )
    ensemble_min: Optional[float] = Field(
        default=None,
        description="Minimum forecast value across evaluated ensemble members in native units.",
    )
    ensemble_max: Optional[float] = Field(
        default=None,
        description="Maximum forecast value across evaluated ensemble members in native units.",
    )


class DisagreementUnits(BaseModel):
    """Explicit physical unit labels for disagreement diagnostics."""

    spread: str = Field(..., description="Physical unit of spread (e.g., °C, m/s, hPa)")
    range: str = Field(..., description="Physical unit of range (e.g., °C, m/s, hPa)")
    iqr: str = Field(..., description="Physical unit of IQR (e.g., °C, m/s, hPa)")
    mean: str = Field(..., description="Physical unit of mean and extrema (e.g., °C, m/s, hPa)")
    cv: str = Field(default="dimensionless", description="Unit label for coefficient of variation")
    spread_to_iqr_ratio: str = Field(default="dimensionless", description="Unit label for spread/IQR ratio")


class ForecastDisagreementRequest(BaseModel):
    """Request payload for forecast disagreement intelligence."""

    location: str = Field(
        ...,
        min_length=1,
        description="Target location name, city, station query, or 'lat,lon' coordinates",
        examples=["Kolkata", "Delhi", "22.5726,88.3639"],
    )
    variable: str = Field(
        default="temperature_2m",
        description="Forecast meteorological variable (temperature_2m, wind_speed_10m, surface_pressure)",
        examples=["temperature_2m"],
    )
    lead_hours: int = Field(
        default=24,
        ge=1,
        le=MAX_SUPPORTED_LEAD_HOURS,
        description="Forecast lead horizon in hours (1 to 384)",
        examples=[24],
    )
    issue_time: Optional[str] = Field(
        default=None,
        description="Optional forecast cycle issuance timestamp in ISO 8601 UTC format",
        examples=["2026-09-19T00:00:00Z"],
    )
    valid_time: Optional[str] = Field(
        default=None,
        description="Optional target verification timestamp in ISO 8601 UTC format",
        examples=["2026-09-20T00:00:00Z"],
    )
    target_date: Optional[str] = Field(
        default=None,
        description="Optional target forecast date (YYYY-MM-DD)",
        examples=["2026-09-20"],
    )

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "example": {
                "location": "Kolkata",
                "variable": "temperature_2m",
                "lead_hours": 24,
            }
        },
    }

    @field_validator("location")
    @classmethod
    def validate_location(cls, v: str) -> str:
        loc = v.strip()
        if not loc:
            raise ValueError("Location cannot be empty or whitespace only")
        return loc

    @field_validator("variable")
    @classmethod
    def validate_variable(cls, v: str) -> str:
        var = v.strip().lower()
        if var not in SUPPORTED_VARIABLES:
            raise ValueError(
                f"Unsupported forecast variable '{v}'. Supported: {sorted(SUPPORTED_VARIABLES)}"
            )
        return var


class ForecastDisagreementResponse(BaseModel):
    """Standardized response payload exposing authoritative forecast disagreement intelligence."""

    status: DisagreementStatus = Field(
        ...,
        description="Availability status: AVAILABLE, UNAVAILABLE, or ABSTAINED",
    )
    location: str = Field(..., description="Location string requested by caller")
    resolved_name: Optional[str] = Field(default=None, description="Resolved standardized location name")
    latitude: Optional[float] = Field(default=None, description="Resolved latitude in decimal degrees")
    longitude: Optional[float] = Field(default=None, description="Resolved longitude in decimal degrees")
    variable: str = Field(..., description="Meteorological variable evaluated")
    lead_hours: int = Field(..., ge=1, le=MAX_SUPPORTED_LEAD_HOURS, description="Forecast lead time in hours")
    lead_days: float = Field(..., ge=0.0, description="Forecast lead time in days")
    issue_time: Optional[str] = Field(default=None, description="Forecast issue cycle timestamp (ISO 8601 UTC)")
    valid_time: Optional[str] = Field(default=None, description="Target forecast verification timestamp (ISO 8601 UTC)")

    # Disagreement & Dispersion Diagnostics (Real GEFS data)
    diagnostics: Optional[DisagreementDiagnostics] = Field(
        default=None,
        description="Quantitative ensemble dispersion metrics. null if abstained or unavailable.",
    )
    units: Optional[DisagreementUnits] = Field(
        default=None,
        description="Physical units corresponding to dispersion diagnostics. null if abstained or unavailable.",
    )
    member_count: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of evaluated ensemble forecast members (e.g., 31)",
    )
    has_full_ensemble: Optional[bool] = Field(
        default=None,
        description="True if full operational ensemble (>=30 members) was ingested",
    )

    # Calibrated Bust Risk (Separately Preserved; Disagreement != P(BUST))
    bust_probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Calibrated probability of forecast bust event (V3 LightGBM + isotonic calibration). null if abstained.",
    )
    risk_level: Optional[RiskLevel] = Field(
        default=None,
        description="Authoritative categorical risk tier (LOW, MEDIUM, HIGH, CRITICAL). null if abstained.",
    )
    trust_state: TrustState = Field(
        default=TrustState.UNAVAILABLE,
        description="Model reliability trust state",
    )
    calibration_status: Optional[str] = Field(
        default=None,
        description="Probability calibration status: CALIBRATED, FAILED, or UNAVAILABLE",
    )

    # Horizon Scientific Scope
    scientific_scope: str = Field(
        ...,
        description="Formal temporal lead scope: WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE (<=240h) or EXTENDED_OPERATIONAL_HORIZON (264-384h)",
    )
    is_certified_horizon: bool = Field(
        default=True,
        description="True if lead_hours <= 240 (within frozen benchmark scope). False for 264h-384h.",
    )

    # Safety and Provenance
    abstain: bool = Field(
        default=False,
        description="Whether safety abstention is active",
    )
    reason_codes: List[str] = Field(
        default_factory=list,
        description="Operational reason codes explaining evaluation or abstention",
    )
    request_id: str = Field(..., description="Unique request tracking identifier")
