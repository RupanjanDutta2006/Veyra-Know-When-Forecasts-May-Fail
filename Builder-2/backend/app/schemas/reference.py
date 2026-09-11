"""Reference and Ground Truth Weather Schemas for Verification."""
from typing import Any, Optional
from pydantic import BaseModel, Field


class ReferenceWeatherRecord(BaseModel):
    """Standardized observed or reanalysis truth record for historical verification.

    Strictly marked with is_ground_truth_label=True and prohibited from live feature inputs.
    """

    location: str = Field(..., description="Location name or identifier")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude")
    variable: str = Field(..., description="Meteorological variable name")
    unit: str = Field(..., description="Measurement unit")
    valid_time: str = Field(..., description="Observation valid timestamp (ISO 8601 UTC)")
    observed_value: float = Field(..., description="Ground truth observed / reanalysis value")
    source: str = Field(default="ERA5_REANALYSIS", description="Observation or reanalysis source")
    availability_time: Optional[str] = Field(
        default=None,
        description="Timestamp when this reference observation became publicly available (strictly > valid_time)",
    )
    is_ground_truth_label: bool = Field(
        default=True,
        description="Security flag ensuring this record is isolated from live inference features",
    )
    quality_flags: dict[str, Any] = Field(default_factory=dict, description="Reference QC flags")


class ReferenceWeatherDataset(BaseModel):
    """Collection of reference ground-truth observations."""

    location: str
    latitude: float
    longitude: float
    source: str = "ERA5_REANALYSIS"
    records: list[ReferenceWeatherRecord] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
