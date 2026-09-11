"""Canonical Forecast Data Schemas for Veyra."""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class CanonicalForecastRecord(BaseModel):
    """Standardized single time-step forecast observation or ensemble record.

    Preserves issue_time, valid_time, and strictly calculated lead_hours.
    """

    location: str = Field(..., description="Location name or identifier")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Geographical latitude in decimal degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Geographical longitude in decimal degrees")
    issue_time: str = Field(..., description="Model initialization / run cycle time (ISO 8601 format)")
    valid_time: str = Field(..., description="Target forecast verification time (ISO 8601 format)")
    lead_hours: int = Field(..., ge=0, description="Lead time in hours between issue_time and valid_time")
    variable: str = Field(..., description="Standardized meteorological variable name (e.g., temperature_2m)")
    unit: str = Field(..., description="Standardized unit of measurement (e.g., celsius, hPa, m/s)")
    value: Optional[float] = Field(default=None, description="Deterministic or control forecast value")
    source: str = Field(default="NOAA_GEFS_OPENMETEO", description="Source forecast model / provider")

    # Ensemble summary metrics (populated when available)
    member_id: Optional[str] = Field(default=None, description="Ensemble member identifier if member-level data")
    member_count: Optional[int] = Field(default=None, ge=1, description="Number of ensemble members evaluated")
    ensemble_mean: Optional[float] = Field(default=None, description="Ensemble mean value")
    ensemble_std: Optional[float] = Field(default=None, ge=0.0, description="Ensemble standard deviation / spread")
    ensemble_min: Optional[float] = Field(default=None, description="Ensemble minimum value across members")
    ensemble_max: Optional[float] = Field(default=None, description="Ensemble maximum value across members")
    q10: Optional[float] = Field(default=None, description="10th percentile ensemble quantile")
    q90: Optional[float] = Field(default=None, description="90th percentile ensemble quantile")
    quality_flags: dict[str, Any] = Field(default_factory=dict, description="Quality control evaluation flags")

    @field_validator("lead_hours")
    @classmethod
    def validate_lead_hours(cls, v: int) -> int:
        if v < 0:
            raise ValueError("lead_hours cannot be negative")
        return v


class CanonicalForecastDataset(BaseModel):
    """Collection of canonical forecast records for a specific location and issue cycle."""

    location: str = Field(..., description="Target geographical location")
    latitude: float = Field(..., description="Latitude")
    longitude: float = Field(..., description="Longitude")
    issue_time: str = Field(..., description="Forecast issue / initialization cycle")
    source: str = Field(default="NOAA_GEFS_OPENMETEO", description="Forecast data source")
    records: list[CanonicalForecastRecord] = Field(default_factory=list, description="List of time-step records")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Dataset metadata and provider headers")
