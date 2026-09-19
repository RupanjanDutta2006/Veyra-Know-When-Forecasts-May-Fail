"""Forecast Revision and Trajectory Intelligence Schemas for Veyra Phase 3 Day 30.

Provides typed, scientifically defensible API contracts for forecast revision
diagnostics derived from comparable forecast issue cycles for the exact same target
(same location, same variable, same valid target time).
"""
from enum import Enum
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.schemas.prediction import (
    MAX_SUPPORTED_LEAD_HOURS,
    CalibrationStatus,
    ReasonCode,
    RiskLevel,
    SUPPORTED_VARIABLES,
    TrustState,
)


class RevisionStatus(str, Enum):
    """Availability status of forecast revision diagnostics."""

    AVAILABLE = "AVAILABLE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    UNAVAILABLE = "UNAVAILABLE"
    ABSTAINED = "ABSTAINED"


class RevisionDirection(str, Enum):
    """Descriptive mathematical direction of forecast revision."""

    INCREASED = "INCREASED"    # revision_delta > 0
    DECREASED = "DECREASED"    # revision_delta < 0
    UNCHANGED = "UNCHANGED"    # revision_delta == 0


class TrajectoryPoint(BaseModel):
    """A single discrete forecast issue-cycle point in the forecast trajectory."""

    issue_time: str = Field(..., description="Forecast issue cycle timestamp (ISO 8601 UTC)")
    valid_time: str = Field(..., description="Target verification timestamp (ISO 8601 UTC)")
    lead_hours: int = Field(..., ge=0, description="Lead horizon in hours from this issue cycle to target")
    forecast_value: float = Field(..., description="Forecast value in native unit")
    ensemble_mean: Optional[float] = Field(default=None, description="Ensemble mean in native unit if available")
    ensemble_spread: Optional[float] = Field(default=None, description="Ensemble spread in native unit if available")


class TrajectoryDiagnostics(BaseModel):
    """Quantitative revision diagnostics comparing current and previous issue cycles."""

    current_value: float = Field(..., description="Forecast value from the current issue cycle")
    previous_value: float = Field(..., description="Forecast value from the previous comparable issue cycle")
    revision_delta: float = Field(
        ...,
        description="Signed change in forecast value: current_value - previous_value",
    )
    absolute_revision: float = Field(
        ...,
        ge=0.0,
        description="Absolute revision magnitude: |revision_delta|",
    )
    direction: RevisionDirection = Field(
        ...,
        description="Descriptive direction of revision (INCREASED, DECREASED, or UNCHANGED)",
    )


class EnsembleRevisionDiagnostics(BaseModel):
    """Quantitative change in ensemble distribution metrics across issue cycles."""

    current_mean: Optional[float] = Field(default=None, description="Current ensemble mean")
    previous_mean: Optional[float] = Field(default=None, description="Previous ensemble mean")
    mean_delta: Optional[float] = Field(
        default=None,
        description="Change in ensemble mean: current_mean - previous_mean",
    )
    current_spread: Optional[float] = Field(default=None, description="Current ensemble spread (std)")
    previous_spread: Optional[float] = Field(default=None, description="Previous ensemble spread (std)")
    spread_delta: Optional[float] = Field(
        default=None,
        description="Change in ensemble spread: current_spread - previous_spread",
    )


class RevisionUnits(BaseModel):
    """Physical unit labels for revision diagnostics."""

    value: str = Field(..., description="Physical unit of forecast value (e.g. °C, m/s, hPa)")
    revision_delta: str = Field(..., description="Physical unit of revision delta")
    absolute_revision: str = Field(..., description="Physical unit of absolute revision")
    ensemble_mean: str = Field(..., description="Physical unit of ensemble mean")
    ensemble_spread: str = Field(..., description="Physical unit of ensemble spread")


class ForecastRevisionRequest(BaseModel):
    """Request payload for forecast revision / trajectory intelligence."""

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
        description="Optional current forecast cycle issuance timestamp in ISO 8601 UTC format",
        examples=["2026-09-19T06:00:00Z"],
    )
    valid_time: Optional[str] = Field(
        default=None,
        description="Optional target verification timestamp in ISO 8601 UTC format",
        examples=["2026-09-20T06:00:00Z"],
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

    @model_validator(mode="after")
    def validate_temporal_target(self) -> "ForecastRevisionRequest":
        """Require a complete, bounded timestamp pair when timestamps are supplied."""
        if (self.issue_time is None) != (self.valid_time is None):
            raise ValueError("issue_time and valid_time must be supplied together")

        if self.issue_time is None:
            return self

        def parse_utc(value: str, field_name: str) -> datetime:
            try:
                parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            except Exception as exc:
                raise ValueError(f"Invalid {field_name} timestamp: must be valid ISO 8601") from exc
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)

        issue_dt = parse_utc(self.issue_time, "issue_time")
        valid_dt = parse_utc(self.valid_time or "", "valid_time")
        lead_seconds = (valid_dt - issue_dt).total_seconds()
        if lead_seconds <= 0:
            raise ValueError("valid_time must be strictly after issue_time")
        if lead_seconds % 3600 != 0:
            raise ValueError("issue_time and valid_time must define a whole-hour forecast lead")

        derived_lead = int(lead_seconds // 3600)
        if derived_lead > MAX_SUPPORTED_LEAD_HOURS:
            raise ValueError(
                f"Forecast lead time exceeds the maximum supported horizon of {MAX_SUPPORTED_LEAD_HOURS} hours"
            )

        self.issue_time = issue_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.valid_time = valid_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return self


class ForecastRevisionResponse(BaseModel):
    """Standardized response payload exposing authoritative forecast revision / trajectory intelligence."""

    status: RevisionStatus = Field(
        ...,
        description="Availability status: AVAILABLE, INSUFFICIENT_HISTORY, UNAVAILABLE, or ABSTAINED",
    )
    location: str = Field(..., description="Location string requested by caller")
    resolved_name: Optional[str] = Field(default=None, description="Resolved standardized location name")
    latitude: Optional[float] = Field(default=None, description="Resolved latitude in decimal degrees")
    longitude: Optional[float] = Field(default=None, description="Resolved longitude in decimal degrees")
    variable: str = Field(..., description="Meteorological variable evaluated")
    lead_hours: int = Field(..., ge=1, le=MAX_SUPPORTED_LEAD_HOURS, description="Forecast lead time in hours")
    lead_days: float = Field(..., ge=0.0, description="Forecast lead time in days")

    # Timestamps
    current_issue_time: Optional[str] = Field(default=None, description="Current issue cycle timestamp (ISO 8601 UTC)")
    previous_issue_time: Optional[str] = Field(default=None, description="Previous issue cycle timestamp (ISO 8601 UTC)")
    valid_time: Optional[str] = Field(default=None, description="Target forecast verification timestamp (ISO 8601 UTC)")

    # Diagnostics
    trajectory: Optional[TrajectoryDiagnostics] = Field(
        default=None,
        description="Quantitative revision diagnostics between current and previous runs. null if unavailable or abstained.",
    )
    ensemble_revision: Optional[EnsembleRevisionDiagnostics] = Field(
        default=None,
        description="Quantitative change in ensemble mean and spread across runs. null if unavailable or abstained.",
    )
    trajectory_points: List[TrajectoryPoint] = Field(
        default_factory=list,
        description="Discrete issue-cycle points for valid trajectory visualization. Empty or 1-point if prior unavailable.",
    )
    current_value: Optional[float] = Field(
        default=None,
        description="Current forecast value only when backed by verified comparable run evidence",
    )
    previous_value: Optional[float] = Field(
        default=None,
        description="Previous forecast value only when backed by verified comparable run evidence",
    )
    revision_delta: Optional[float] = Field(
        default=None,
        description="current_value - previous_value; null without verified comparable history",
    )
    units: Optional[RevisionUnits] = Field(
        default=None,
        description="Physical units corresponding to revision diagnostics. null if abstained or unavailable.",
    )

    # Calibrated Bust Risk (Separately Preserved; Revision != Disagreement != P(BUST))
    bust_probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Calibrated probability of forecast bust event (V3 LightGBM + isotonic calibration). null if abstained.",
    )
    previous_bust_probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Previous calibrated P(BUST), null unless legitimately reconstructed from a compatible frozen pipeline",
    )
    bust_probability_delta: Optional[float] = Field(
        default=None,
        description="Current minus previous P(BUST); null when previous P(BUST) is unavailable",
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
    history_is_durable: bool = Field(
        default=False,
        description="Whether revision history comes from a durable provider-verified forecast-run source",
    )
    history_source: Optional[str] = Field(
        default=None,
        description="Durable historical forecast source used for comparison; null when unavailable",
    )

    # Safety and Provenance
    abstain: bool = Field(
        default=False,
        description="Whether safety abstention is active",
    )
    reason_codes: List[str] = Field(
        default_factory=list,
        description="Operational reason codes explaining evaluation, revision status, or abstention",
    )
    request_id: str = Field(..., description="Unique request tracking identifier")
