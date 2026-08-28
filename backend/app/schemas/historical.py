"""Historical Data Schemas and Contracts for Veyra Phase 2.

Defines typed request contracts, canonical historical records,
and structured collection results for historical weather data.
"""
from datetime import date, datetime
import hashlib
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


SUPPORTED_HISTORICAL_VARIABLES: set[str] = {
    "temperature_2m",
    "surface_pressure",
    "wind_speed_10m",
    "relative_humidity_2m",
    "precipitation",
    "temperature",
    "pressure",
    "wind_speed",
    "humidity",
}

VARIABLE_CANONICAL_NAMES: dict[str, str] = {
    "temperature": "temperature_2m",
    "temperature_2m": "temperature_2m",
    "pressure": "surface_pressure",
    "surface_pressure": "surface_pressure",
    "wind_speed": "wind_speed_10m",
    "wind_speed_10m": "wind_speed_10m",
    "humidity": "relative_humidity_2m",
    "relative_humidity_2m": "relative_humidity_2m",
    "precipitation": "precipitation",
}

VARIABLE_CANONICAL_UNITS: dict[str, str] = {
    "temperature_2m": "celsius",
    "surface_pressure": "hPa",
    "wind_speed_10m": "m/s",
    "relative_humidity_2m": "%",
    "precipitation": "mm",
}


class HistoricalDataRequest(BaseModel):
    """Structured request contract for collecting historical weather and forecast data."""

    location: str = Field(..., min_length=1, description="Location name or direct 'lat,lon' coordinates")
    start_date: str = Field(..., description="Start date (ISO format YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)")
    end_date: str = Field(..., description="End date (ISO format YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)")
    variables: list[str] = Field(
        default_factory=lambda: [
            "temperature_2m",
            "surface_pressure",
            "wind_speed_10m",
            "relative_humidity_2m",
            "precipitation",
        ],
        description="List of meteorological variables to collect",
    )
    data_version: str = Field(default="gefs-openmeteo-v1.0", description="Data pipeline schema version")
    source: str = Field(default="OPENMETEO_ARCHIVE", description="Target provider / archive source")
    timezone: str = Field(default="UTC", description="Temporal timezone for collection")

    @field_validator("location")
    @classmethod
    def validate_location(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("location cannot be empty or pure whitespace")
        return cleaned

    @field_validator("variables")
    @classmethod
    def validate_variables(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("variables list cannot be empty")
        normalized: list[str] = []
        for var in v:
            var_clean = var.strip().lower()
            if var_clean not in SUPPORTED_HISTORICAL_VARIABLES:
                raise ValueError(
                    f"Unsupported variable '{var}'. Supported: {sorted(SUPPORTED_HISTORICAL_VARIABLES)}"
                )
            normalized.append(VARIABLE_CANONICAL_NAMES.get(var_clean, var_clean))
        return list(dict.fromkeys(normalized))

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        cleaned = v.strip()
        # Accept YYYY-MM-DD or full ISO timestamp
        try:
            if "T" in cleaned or "Z" in cleaned:
                dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
                return dt.strftime("%Y-%m-%d")
            else:
                date.fromisoformat(cleaned)
                return cleaned
        except Exception as exc:
            raise ValueError(f"Invalid date format '{v}': must be valid ISO format (e.g. 'YYYY-MM-DD')") from exc

    def model_post_init(self, __context: Any) -> None:
        """Validate chronological start_date <= end_date."""
        start_d = date.fromisoformat(self.start_date)
        end_d = date.fromisoformat(self.end_date)
        if start_d > end_d:
            raise ValueError(
                f"start_date ({self.start_date}) must be before or equal to end_date ({self.end_date})"
            )


class CanonicalHistoricalRecord(BaseModel):
    """Standardized single historical weather / reanalysis observation record.

    Preserves full spatial, temporal, and variable coordinates with strict anti-leakage guards.
    """

    record_id: str = Field(..., description="Deterministic unique identifier for record")
    location: str = Field(..., description="Location name or requested identifier")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    valid_time: str = Field(..., description="Verification / observation timestamp (ISO 8601 UTC)")
    variable: str = Field(..., description="Standardized meteorological variable name")
    unit: str = Field(..., description="Standardized measurement unit")
    value: float = Field(..., description="Observed, reanalyzed, or forecast value")
    source: str = Field(default="OPENMETEO_ARCHIVE", description="Provider / data source")
    record_type: str = Field(default="OBSERVATION", description="Record type: OBSERVATION, FORECAST, or REANALYSIS")
    issue_time: Optional[str] = Field(default=None, description="Forecast cycle issue time if forecast record")
    lead_hours: Optional[int] = Field(default=None, ge=0, description="Forecast lead hours if forecast record")
    is_ground_truth_label: bool = Field(
        default=True,
        description="Security flag ensuring ground truth records are never fed to live feature extractors",
    )
    quality_flags: dict[str, Any] = Field(default_factory=dict, description="QC evaluation flags")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional provider metadata")

    @classmethod
    def create(
        cls,
        location: str,
        latitude: float,
        longitude: float,
        valid_time: str,
        variable: str,
        unit: str,
        value: float,
        source: str = "OPENMETEO_ARCHIVE",
        record_type: str = "OBSERVATION",
        issue_time: Optional[str] = None,
        lead_hours: Optional[int] = None,
        is_ground_truth_label: bool = True,
        quality_flags: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "CanonicalHistoricalRecord":
        """Factory method computing deterministic record_id hash."""
        id_material = (
            f"{location.strip().lower()}:{latitude:.4f}:{longitude:.4f}:"
            f"{valid_time}:{variable.lower()}:{source.upper()}:{record_type.upper()}:{lead_hours}"
        )
        record_id = hashlib.sha256(id_material.encode("utf-8")).hexdigest()[:16]
        return cls(
            record_id=record_id,
            location=location,
            latitude=latitude,
            longitude=longitude,
            valid_time=valid_time,
            variable=variable,
            unit=unit,
            value=value,
            source=source,
            record_type=record_type,
            issue_time=issue_time,
            lead_hours=lead_hours,
            is_ground_truth_label=is_ground_truth_label,
            quality_flags=quality_flags or {},
            metadata=metadata or {},
        )


class HistoricalCollectionResult(BaseModel):
    """Standardized output container from historical data collection operations."""

    is_success: bool = Field(..., description="Whether collection succeeded")
    location: str = Field(..., description="Requested location identifier")
    latitude: Optional[float] = Field(default=None, description="Resolved geographical latitude")
    longitude: Optional[float] = Field(default=None, description="Resolved geographical longitude")
    start_date: str = Field(..., description="Collection start date")
    end_date: str = Field(..., description="Collection end date")
    records: list[CanonicalHistoricalRecord] = Field(default_factory=list, description="Canonical historical records")
    total_records: int = Field(default=0, description="Total records returned after deduplication")
    duplicates_removed: int = Field(default=0, description="Count of duplicate records eliminated")
    qc_passed: bool = Field(default=True, description="Whether dataset passed quality control")
    qc_violations: list[str] = Field(default_factory=list, description="List of QC violations if any")
    error_message: Optional[str] = Field(default=None, description="Error reason if collection failed")
    source: str = Field(default="OPENMETEO_ARCHIVE", description="Provider source identifier")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata and execution timing")
