"""Multi-Location Platform Schemas and Contracts for Veyra Phase 2 Day 10.

Defines typed request contracts, per-location item results, and aggregated
batch responses for multi-location historical data collection and prediction.
"""
from datetime import date, datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator

from backend.app.schemas.historical import (
    SUPPORTED_HISTORICAL_VARIABLES,
    VARIABLE_CANONICAL_NAMES,
    CanonicalHistoricalRecord,
)
from backend.app.schemas.prediction import PredictionResponse

# Configurable maximum batch size for multi-location operations
MAX_MULTI_LOCATION_BATCH_SIZE: int = 50


class MultiLocationHistoricalRequest(BaseModel):
    """Request contract for collecting historical weather data across multiple locations."""

    locations: list[str] = Field(
        ...,
        min_length=1,
        max_length=MAX_MULTI_LOCATION_BATCH_SIZE,
        description=f"List of location names or direct 'lat,lon' coordinates (1-{MAX_MULTI_LOCATION_BATCH_SIZE})",
    )
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

    @field_validator("locations")
    @classmethod
    def validate_locations(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("locations list cannot be empty")
        if len(v) > MAX_MULTI_LOCATION_BATCH_SIZE:
            raise ValueError(
                f"Batch size {len(v)} exceeds maximum allowed limit of {MAX_MULTI_LOCATION_BATCH_SIZE}"
            )
        cleaned_list: list[str] = []
        for loc in v:
            cleaned = loc.strip()
            if not cleaned:
                raise ValueError("Location entry cannot be empty or pure whitespace")
            cleaned_list.append(cleaned)
        return cleaned_list

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


class MultiLocationHistoricalItemResult(BaseModel):
    """Structured result for an individual location within a multi-location historical batch."""

    input_location: str = Field(..., description="Original raw location query as requested")
    is_success: bool = Field(..., description="Whether collection succeeded for this specific location")
    status: str = Field(
        ...,
        description="Status code (e.g. SUCCESS, INVALID_LOCATION, INVALID_COORDINATES, QC_FAILED, PROVIDER_ERROR)",
    )
    resolved_name: Optional[str] = Field(default=None, description="Resolved geographic name if resolved")
    latitude: Optional[float] = Field(default=None, description="Resolved latitude coordinate")
    longitude: Optional[float] = Field(default=None, description="Resolved longitude coordinate")
    records: list[CanonicalHistoricalRecord] = Field(
        default_factory=list,
        description="Canonical historical records collected for this location",
    )
    total_records: int = Field(default=0, description="Count of canonical records for this location")
    duplicates_removed: int = Field(default=0, description="Count of duplicate records eliminated")
    qc_passed: bool = Field(default=True, description="Whether dataset passed quality control")
    qc_violations: list[str] = Field(default_factory=list, description="List of QC violations if any")
    error_message: Optional[str] = Field(default=None, description="Detailed error description if failed")


class MultiLocationHistoricalResult(BaseModel):
    """Structured container returned from multi-location historical data collection."""

    is_success: bool = Field(..., description="True if at least one location succeeded or entire batch was processed")
    batch_size: int = Field(..., description="Total count of requested locations")
    successful_locations: int = Field(..., description="Count of locations with status SUCCESS")
    failed_locations: int = Field(..., description="Count of locations that failed or abstained")
    results: list[MultiLocationHistoricalItemResult] = Field(
        default_factory=list,
        description="Per-location results matching input order deterministically (1:1)",
    )
    all_records: list[CanonicalHistoricalRecord] = Field(
        default_factory=list,
        description="Aggregated canonical historical records across all successful locations for Builder 2",
    )
    total_records: int = Field(default=0, description="Total canonical records aggregated across the batch")
    start_date: str = Field(..., description="Collection start date")
    end_date: str = Field(..., description="Collection end date")
    variables: list[str] = Field(default_factory=list, description="Requested variables")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Batch execution metadata")


class MultiLocationPredictionRequest(BaseModel):
    """Request contract for executing forecast bust predictions across multiple locations."""

    locations: list[str] = Field(
        ...,
        min_length=1,
        max_length=MAX_MULTI_LOCATION_BATCH_SIZE,
        description=f"List of location names or direct 'lat,lon' coordinates (1-{MAX_MULTI_LOCATION_BATCH_SIZE})",
    )
    target_date: Optional[str] = Field(default=None, description="Optional target date YYYY-MM-DD")
    variable: Optional[str] = Field(default=None, description="Optional meteorological variable identifier")
    issue_time: Optional[str] = Field(default=None, description="Optional forecast issue timestamp")
    valid_time: Optional[str] = Field(default=None, description="Optional forecast valid timestamp")
    model_type: Optional[str] = Field(default=None, description="Optional model version identifier")

    @field_validator("locations")
    @classmethod
    def validate_locations(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("locations list cannot be empty")
        if len(v) > MAX_MULTI_LOCATION_BATCH_SIZE:
            raise ValueError(
                f"Batch size {len(v)} exceeds maximum allowed limit of {MAX_MULTI_LOCATION_BATCH_SIZE}"
            )
        cleaned_list: list[str] = []
        for loc in v:
            cleaned = loc.strip()
            if not cleaned:
                raise ValueError("Location entry cannot be empty or pure whitespace")
            cleaned_list.append(cleaned)
        return cleaned_list


class MultiLocationPredictionItemResult(BaseModel):
    """Prediction evaluation result for an individual location in a batch."""

    input_location: str = Field(..., description="Original requested location identifier")
    is_success: bool = Field(..., description="True if prediction produced non-abstained result")
    response: PredictionResponse = Field(..., description="Standardized PredictionResponse object")


class MultiLocationPredictionResult(BaseModel):
    """Container returned from batch prediction operations."""

    batch_size: int = Field(..., description="Total requested locations in batch")
    successful_predictions: int = Field(..., description="Count of confident predictions (abstain=False)")
    abstained_predictions: int = Field(..., description="Count of abstained predictions (abstain=True)")
    results: list[MultiLocationPredictionItemResult] = Field(
        default_factory=list,
        description="Per-location prediction outputs matching input order deterministically (1:1)",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Execution metadata")
