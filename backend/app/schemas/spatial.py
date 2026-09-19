"""Spatial Forecast Reliability Schemas for Veyra Phase 3 Day 27.

Defines typed request contracts, evaluated discrete spatial points,
aggregated spatial summary metrics, and orchestration response containers.
"""
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.schemas.dashboard import DashboardStatus
from backend.app.schemas.multi_location import MAX_MULTI_LOCATION_BATCH_SIZE
from backend.app.schemas.prediction import (
    MAX_SUPPORTED_LEAD_HOURS,
    CalibrationStatus,
    ReasonCode,
    RiskLevel,
    SUPPORTED_VARIABLES,
    TrustState,
)


class SpatialReliabilityRequest(BaseModel):
    """Request contract for spatial forecast reliability evaluation across multiple locations."""

    locations: List[str] = Field(
        ...,
        min_length=1,
        max_length=MAX_MULTI_LOCATION_BATCH_SIZE,
        description=f"List of discrete location names, station queries, or direct 'lat,lon' coordinates (1-{MAX_MULTI_LOCATION_BATCH_SIZE})",
        examples=[["Kolkata", "Delhi", "Mumbai", "Chennai", "Bengaluru"]],
    )
    variable: str = Field(
        default="temperature_2m",
        description="Forecast meteorological variable to evaluate (temperature_2m, wind_speed_10m, surface_pressure)",
        examples=["temperature_2m"],
    )
    lead_hours: int = Field(
        default=24,
        ge=24,
        le=MAX_SUPPORTED_LEAD_HOURS,
        description="Forecast lead horizon in hours (24 to 384)",
        examples=[24],
    )
    issue_time: Optional[str] = Field(
        default=None,
        description="Optional base forecast issuance timestamp in ISO 8601 UTC format (e.g., 2026-09-19T00:00:00Z)",
        examples=["2026-09-19T00:00:00Z"],
    )

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "example": {
                "locations": ["Kolkata", "Delhi", "Mumbai", "Chennai"],
                "variable": "temperature_2m",
                "lead_hours": 24,
            }
        },
    }

    @field_validator("locations")
    @classmethod
    def validate_locations_list(cls, v: List[str]) -> List[str]:
        """Validate that locations list is non-empty, bounded, and contains non-blank strings."""
        if not v:
            raise ValueError("locations list cannot be empty")
        if len(v) > MAX_MULTI_LOCATION_BATCH_SIZE:
            raise ValueError(
                f"Batch size {len(v)} exceeds maximum allowed limit of {MAX_MULTI_LOCATION_BATCH_SIZE}"
            )
        cleaned: List[str] = []
        for loc in v:
            if not isinstance(loc, str):
                raise ValueError(f"Each location must be a string, got {type(loc).__name__}")
            c = loc.strip()
            if not c:
                raise ValueError("Location entry cannot be empty or pure whitespace")
            cleaned.append(c)
        return cleaned

    @field_validator("variable")
    @classmethod
    def validate_variable(cls, v: str) -> str:
        """Validate variable against supported meteorological variables."""
        clean = v.strip().lower()
        if not clean or clean not in SUPPORTED_VARIABLES:
            raise ValueError(
                f"Unsupported forecast variable '{v}'. Supported variables: {', '.join(sorted(SUPPORTED_VARIABLES))}"
            )
        return clean

    @field_validator("lead_hours")
    @classmethod
    def validate_lead_hours(cls, v: int) -> int:
        """Validate lead hours within operational boundary [24, 384]."""
        if v < 24 or v > MAX_SUPPORTED_LEAD_HOURS:
            raise ValueError(
                f"lead_hours {v} out of bounds: must be between 24 and {MAX_SUPPORTED_LEAD_HOURS} hours"
            )
        return v


class SpatialReliabilityPoint(BaseModel):
    """Discrete evaluated spatial point exposing authoritative backend reliability intelligence."""

    location: str = Field(..., description="Original location query as requested")
    resolved_name: Optional[str] = Field(default=None, description="Resolved canonical station or location name")
    latitude: Optional[float] = Field(default=None, description="Resolved latitude in decimal degrees. null if unresolvable.")
    longitude: Optional[float] = Field(default=None, description="Resolved longitude in decimal degrees. null if unresolvable.")
    region_id: Optional[str] = Field(default=None, description="Regional or synoptic identifier if mapped")
    variable: str = Field(..., description="Evaluated meteorological variable")
    lead_hours: int = Field(..., ge=1, le=MAX_SUPPORTED_LEAD_HOURS, description="Forecast lead time in hours")
    lead_days: float = Field(..., ge=0.0, description="Forecast lead time in days")
    issue_time: Optional[str] = Field(default=None, description="Forecast issuance timestamp (ISO 8601 UTC)")
    valid_time: Optional[str] = Field(default=None, description="Forecast valid verification timestamp (ISO 8601 UTC)")
    bust_probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Calibrated probability (0.0-1.0) of forecast bust event. null if abstained or unavailable.",
    )
    risk_level: Optional[RiskLevel] = Field(
        default=None,
        description="Categorical risk level (LOW, MEDIUM, HIGH, CRITICAL). null if abstained.",
    )
    trust_state: TrustState = Field(
        default=TrustState.UNAVAILABLE,
        description="Assessment of model reliability for this evaluation point",
    )
    abstain: bool = Field(
        default=True,
        description="Whether the sentinel abstains from making a prediction at this location",
    )
    reason_codes: List[str] = Field(
        default_factory=list,
        description="Reason codes explaining prediction or abstention decision",
    )
    calibration_status: Optional[str] = Field(
        default=None,
        description="Probability calibration status: CALIBRATED, FAILED, or UNAVAILABLE",
    )
    model_version: Optional[str] = Field(
        default=None,
        description="Evaluated ML model version identifier",
    )
    data_version: Optional[str] = Field(
        default=None,
        description="Weather data pipeline schema version",
    )
    is_certified_horizon: bool = Field(
        default=True,
        description="Horizon-scope metadata: True if lead_hours <= 240 (lead is within the temporal scope evaluated by the Day 23 frozen benchmark; does not establish independent live-location performance certification). False for 264h-384h (extended operational horizon).",
    )
    scientific_scope: str = Field(
        default="FROZEN_BENCHMARK_LEAD_SCOPE",
        description="Formal temporal lead scope: FROZEN_BENCHMARK_LEAD_SCOPE (<=240h, Within Frozen Benchmark Lead Scope) or EXTENDED_OPERATIONAL_HORIZON (264h-384h, Extended Operational Horizon)",
    )
    # Contextual diagnostics (reused from authoritative V3 inference)
    confidence_index: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Model confidence index")
    uncertainty_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Forecast uncertainty percentage")
    ood_score: Optional[float] = Field(default=None, ge=0.0, description="Out-of-distribution diagnostic score")
    stability_index: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Feature stability index")
    dominant_risk_drivers: Optional[List[str]] = Field(default=None, description="Dominant physical risk drivers")
    decision_mode: Optional[str] = Field(default=None, description="Operational decision governance mode")
    decision_guidance: Optional[str] = Field(default=None, description="Human-readable decision guidance")


class SpatialReliabilitySummary(BaseModel):
    """Deterministic spatial aggregation metrics across all requested discrete locations."""

    total_locations: int = Field(..., ge=0, description="Total count of requested locations")
    available_locations: int = Field(..., ge=0, description="Count of locations with valid, non-abstained predictions")
    abstained_locations: int = Field(..., ge=0, description="Count of locations where the model safely abstained")
    max_bust_probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Maximum calibrated bust probability across valid points. null if all locations abstained.",
    )
    max_risk_level: Optional[RiskLevel] = Field(
        default=None,
        description="Peak categorical risk level across valid points. null if all locations abstained.",
    )
    max_risk_location: Optional[str] = Field(
        default=None,
        description="Location query exhibiting peak risk. First input order used as deterministic tie-breaker. null if all abstained.",
    )
    mean_bust_probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Mean calibrated bust probability across valid points. null if all locations abstained.",
    )
    elevated_risk_locations: int = Field(
        default=0,
        ge=0,
        description="Count of valid locations with risk level MEDIUM, HIGH, or CRITICAL",
    )


class SpatialReliabilityResponse(BaseModel):
    """Authoritative response container for spatial forecast reliability intelligence."""

    status: DashboardStatus = Field(..., description="Overall execution status: SUCCESS, PARTIAL, or ABSTAINED")
    variable: str = Field(..., description="Evaluated meteorological variable")
    lead_hours: int = Field(..., ge=1, le=MAX_SUPPORTED_LEAD_HOURS, description="Evaluated forecast lead horizon in hours")
    lead_days: float = Field(..., ge=0.0, description="Evaluated forecast lead horizon in days")
    issue_time: Optional[str] = Field(default=None, description="Forecast issuance timestamp (ISO 8601 UTC)")
    is_certified_horizon: bool = Field(
        ...,
        description="Horizon-scope metadata: True if lead_hours <= 240 (lead is within the temporal scope evaluated by the Day 23 frozen benchmark; does not establish independent live-location performance certification). False for 264h-384h (extended operational horizon).",
    )
    scientific_scope: str = Field(
        ...,
        description="Formal temporal lead scope: FROZEN_BENCHMARK_LEAD_SCOPE (<=240h, Within Frozen Benchmark Lead Scope) or EXTENDED_OPERATIONAL_HORIZON (264h-384h, Extended Operational Horizon)",
    )
    points: List[SpatialReliabilityPoint] = Field(
        ...,
        description="Evaluated discrete spatial points matching input order deterministically (1:1)",
    )
    summary: SpatialReliabilitySummary = Field(..., description="Aggregated spatial intelligence summary")
    request_id: Optional[str] = Field(default=None, description="Request correlation identifier for traceability")
