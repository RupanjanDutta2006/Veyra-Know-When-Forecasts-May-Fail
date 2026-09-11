"""Canonical Forecast Data Schemas for Veyra.

Scientific data contract:
- preserve requested coordinates separately from provider grid coordinates
- preserve model/run provenance
- preserve ensemble statistics
- never fabricate ensemble metadata
"""

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class CanonicalForecastRecord(BaseModel):
    """One forecast variable at one valid time.

    `value` is the deterministic/control value.
    Ensemble statistics are populated only when actual member values
    were present in the provider response.
    """

    location: str = Field(...)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)

    # Actual provider grid cell, when supplied by the API.
    grid_latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    grid_longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)

    issue_time: str = Field(...)
    valid_time: str = Field(...)
    lead_hours: int = Field(..., ge=0)

    variable: str = Field(...)
    unit: str = Field(...)

    # Deterministic/control forecast.
    value: Optional[float] = Field(default=None)

    source: str = Field(default="OPEN_METEO_GFS_ENSEMBLE")

    # Model/run provenance.
    model: Optional[str] = Field(default=None)
    model_run: Optional[str] = Field(default=None)

    # Ensemble provenance/statistics.
    member_id: Optional[str] = Field(default=None)
    member_count: Optional[int] = Field(default=None, ge=1)
    ensemble_mean: Optional[float] = Field(default=None)
    ensemble_std: Optional[float] = Field(default=None, ge=0.0)
    ensemble_min: Optional[float] = Field(default=None)
    ensemble_max: Optional[float] = Field(default=None)
    q10: Optional[float] = Field(default=None)
    q90: Optional[float] = Field(default=None)

    # Keep raw/member-derived metadata without putting it into ML X
    # automatically.
    quality_flags: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("lead_hours")
    @classmethod
    def validate_lead_hours(cls, v: int) -> int:
        if v < 0:
            raise ValueError("lead_hours cannot be negative")
        return v


class CanonicalForecastDataset(BaseModel):
    """Collection of canonical forecast records for one location/run."""

    location: str = Field(...)
    latitude: float = Field(...)
    longitude: float = Field(...)

    grid_latitude: Optional[float] = Field(default=None)
    grid_longitude: Optional[float] = Field(default=None)

    issue_time: str = Field(...)
    source: str = Field(default="OPEN_METEO_GFS_ENSEMBLE")
    model: Optional[str] = Field(default=None)
    model_run: Optional[str] = Field(default=None)

    records: list[CanonicalForecastRecord] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)