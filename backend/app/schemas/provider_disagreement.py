"""Typed Pydantic Schemas for Cross-Provider Disagreement Intelligence for Veyra Phase 3 Day 38.

Defines API data contracts for multi-provider forecast comparison diagnostics,
ensuring strict separation between cross-provider difference and GEFS ensemble member spread.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ProviderForecastSummary(BaseModel):
    """Summary of a single provider's normalized forecast for diagnostic comparison."""

    provider_id: str = Field(..., description="Unique provider identifier")
    provider_name: str = Field(..., description="Human-readable provider display name")
    provider_source_mode: str = Field(..., description="Provider source mode (LIVE or FIXTURE)")
    canonical_location: str = Field(..., description="Normalized canonical location name")
    issue_time: str = Field(..., description="ISO 8601 UTC issue time")
    valid_time: str = Field(..., description="ISO 8601 UTC valid target time")
    lead_hours: int = Field(..., description="Forecast lead horizon in hours")
    variable: str = Field(..., description="Target atmospheric variable")
    forecast_value: Optional[float] = Field(None, description="Normalized forecast value in canonical units")
    unit: str = Field(..., description="Canonical unit (°C, m/s, hPa)")
    is_available: bool = Field(..., description="Whether forecast data was successfully fetched")


class CrossProviderDisagreementRequest(BaseModel):
    """API request payload for evaluating cross-provider forecast divergence."""

    location: str = Field(..., min_length=1, description="Target location name or query")
    variable: str = Field(default="temperature_2m", description="Target variable")
    lead_hours: int = Field(default=24, ge=0, le=384, description="Lead horizon in hours")
    issue_time: Optional[str] = Field(None, description="Optional ISO 8601 issue timestamp")
    valid_time: Optional[str] = Field(None, description="Optional ISO 8601 valid timestamp")
    primary_provider_id: Optional[str] = Field(default="openmeteo_gefs", description="Primary provider ID")
    secondary_provider_id: Optional[str] = Field(default="fixture_second_provider", description="Secondary provider ID")


class CrossProviderDisagreementResponse(BaseModel):
    """API response payload for cross-provider forecast divergence diagnostics."""

    status: str = Field(..., description="Diagnostic outcome status (AVAILABLE, INSUFFICIENT_PROVIDERS, NOT_COMPARABLE, etc.)")
    reason_code: str = Field(..., description="Machine-readable diagnostic reason code")
    canonical_location: str = Field(..., description="Canonical target location name")
    variable: str = Field(..., description="Target variable")
    valid_time: str = Field(..., description="Target valid timestamp")
    unit: str = Field(..., description="Canonical metric unit (°C, m/s, hPa)")
    primary_provider: Optional[ProviderForecastSummary] = Field(None, description="Primary provider forecast summary")
    secondary_provider: Optional[ProviderForecastSummary] = Field(None, description="Secondary provider forecast summary")
    signed_difference: Optional[float] = Field(None, description="Signed forecast difference (Primary - Secondary)")
    absolute_difference: Optional[float] = Field(None, description="Absolute forecast difference (|Primary - Secondary|)")
    provider_min: Optional[float] = Field(None, description="Minimum provider forecast value")
    provider_max: Optional[float] = Field(None, description="Maximum provider forecast value")
    provider_mean: Optional[float] = Field(None, description="Mean provider forecast value")
    relative_difference_pct: Optional[float] = Field(None, description="Relative difference percentage")
    is_comparable: bool = Field(..., description="Whether forecasts satisfied all scientific comparability criteria")
    has_fixture_provider: bool = Field(..., description="Whether fixture-backed secondary provider data was used")
    provenance_notice: str = Field(..., description="Explicit source mode notice")
    scope_note: str = Field(..., description="Scientific scope note clarifying diagnostic separation")
