"""Prediction request and response schemas."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class TrustState(str, Enum):
    """Trust state of the forecast bust assessment."""

    UNAVAILABLE = "UNAVAILABLE"
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    MODERATE_CONFIDENCE = "MODERATE_CONFIDENCE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    ABSTAINED = "ABSTAINED"


class RiskLevel(str, Enum):
    """Categorical risk level of forecast bust."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ReasonCode(str, Enum):
    """Standardized reason codes explaining trust state, pipeline status, and abstention."""

    DATA_NOT_READY = "DATA_NOT_READY"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    FEATURES_NOT_READY = "FEATURES_NOT_READY"
    MODEL_NOT_READY = "MODEL_NOT_READY"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    INVALID_LOCATION = "INVALID_LOCATION"
    INVALID_REGION = "INVALID_REGION"
    QC_FAILED = "QC_FAILED"
    OOD_ABSTAIN = "OOD_ABSTAIN"
    OOD_DETECTED = "OOD_DETECTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    EXTREME_VOLATILITY = "EXTREME_VOLATILITY"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SUCCESS = "SUCCESS"


SUPPORTED_VARIABLES: set[str] = {
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

SUPPORTED_MODEL_TYPES: set[str] = {
    "prototype-gbm-v1",
    "lightgbm",
    "lgbm",
    "baseline-logistic-v1.0",
    "logistic",
    "baseline",
    "default",
}

MAX_SUPPORTED_LEAD_HOURS: int = 384  # 16-day NOAA GEFS operational horizon


class PredictionRequest(BaseModel):
    """Forecast bust prediction request payload."""

    location: Optional[str] = Field(
        default=None,
        description="Location name, city, or coordinates for forecast evaluation",
        examples=["London", "Tokyo", "Kolkata"],
    )
    region_id: Optional[str] = Field(
        default=None,
        description="Region identifier or city name (supported alias for location)",
        examples=["Kolkata", "Delhi", "London"],
    )
    issue_time: Optional[str] = Field(
        default=None,
        description="Forecast issuance timestamp in ISO 8601 UTC format (e.g., 2026-08-27T00:00:00Z)",
        examples=["2026-08-27T00:00:00Z"],
    )
    valid_time: Optional[str] = Field(
        default=None,
        description="Forecast valid target timestamp in ISO 8601 UTC format (e.g., 2026-08-28T00:00:00Z)",
        examples=["2026-08-28T00:00:00Z"],
    )
    variable: Optional[str] = Field(
        default="temperature_2m",
        description="Forecast meteorological variable to evaluate (e.g., temperature_2m, surface_pressure)",
        examples=["temperature_2m"],
    )
    model_type: Optional[str] = Field(
        default=None,
        description="Optional model type identifier or override (e.g., prototype-gbm-v1, baseline-logistic-v1.0)",
    )
    target_date: Optional[str] = Field(
        default=None,
        description="Optional target forecast date (ISO format YYYY-MM-DD)",
        examples=["2026-09-01"],
    )

    @model_validator(mode="after")
    def validate_request_payload(self) -> "PredictionRequest":
        """Comprehensive input validation for location, variable, timestamps, and horizons."""
        # 1. Location & region_id resolution and blank check
        loc_candidate = self.location if self.location is not None else self.region_id
        if loc_candidate is None:
            raise ValueError("Either 'location' or 'region_id' must be provided")

        loc_clean = loc_candidate.strip()
        if not loc_clean:
            raise ValueError("location or region_id cannot be empty or whitespace only")

        self.location = loc_clean

        # 2. Variable validation
        if self.variable is not None:
            v_clean = self.variable.strip().lower()
            if not v_clean or v_clean not in SUPPORTED_VARIABLES:
                raise ValueError(
                    f"Unsupported forecast variable '{self.variable}'. "
                    f"Supported variables: {', '.join(sorted(SUPPORTED_VARIABLES))}"
                )

        # 3. Model Type validation
        if self.model_type is not None:
            mt_clean = self.model_type.strip().lower()
            if not mt_clean or mt_clean not in SUPPORTED_MODEL_TYPES:
                raise ValueError(
                    f"Unsupported model_type '{self.model_type}'. "
                    f"Supported model types: prototype-gbm-v1, baseline-logistic-v1.0"
                )

        # 4. Target Date validation
        if self.target_date is not None:
            td_clean = self.target_date.strip()
            try:
                datetime.strptime(td_clean, "%Y-%m-%d")
            except ValueError as err:
                raise ValueError(
                    f"Invalid target_date format '{self.target_date}'. Expected ISO format YYYY-MM-DD"
                ) from err

        # 5. Timestamp Parsing & Chronological Ordering
        dt_issue = None
        dt_valid = None

        if self.issue_time is not None:
            raw_issue = self.issue_time.strip()
            try:
                parsed_issue = datetime.fromisoformat(raw_issue.replace("Z", "+00:00"))
                if parsed_issue.tzinfo is None:
                    dt_issue = parsed_issue.replace(tzinfo=timezone.utc)
                else:
                    dt_issue = parsed_issue.astimezone(timezone.utc)
            except Exception as err:
                raise ValueError(
                    f"Invalid issue_time timestamp '{self.issue_time}': must be valid ISO 8601 format"
                ) from err

        if self.valid_time is not None:
            raw_valid = self.valid_time.strip()
            try:
                parsed_valid = datetime.fromisoformat(raw_valid.replace("Z", "+00:00"))
                if parsed_valid.tzinfo is None:
                    dt_valid = parsed_valid.replace(tzinfo=timezone.utc)
                else:
                    dt_valid = parsed_valid.astimezone(timezone.utc)
            except Exception as err:
                raise ValueError(
                    f"Invalid valid_time timestamp '{self.valid_time}': must be valid ISO 8601 format"
                ) from err

        if dt_issue is not None and dt_valid is not None:
            lead_seconds = (dt_valid - dt_issue).total_seconds()
            lead_hours = lead_seconds / 3600.0

            if lead_seconds <= 0:
                raise ValueError(
                    f"valid_time ({self.valid_time}) must be strictly after issue_time ({self.issue_time}). "
                    f"Negative or zero forecast lead time ({lead_hours:.1f}h) is invalid for forecast inference."
                )

            if lead_hours > MAX_SUPPORTED_LEAD_HOURS:
                raise ValueError(
                    f"Forecast lead time ({lead_hours:.1f}h) exceeds the maximum supported forecast horizon of "
                    f"{MAX_SUPPORTED_LEAD_HOURS} hours (16 days)."
                )

        return self


class PredictionResponse(BaseModel):
    """Forecast bust prediction response payload."""

    location: str = Field(
        ...,
        description="Location requested for forecast evaluation",
    )
    bust_probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Estimated probability (0.0 - 1.0) of forecast bust. null when unavailable or abstained.",
    )
    risk_level: Optional[RiskLevel] = Field(
        default=None,
        description="Categorical risk level for forecast failure",
    )
    trust_state: TrustState = Field(
        default=TrustState.UNAVAILABLE,
        description="Assessment of model reliability for this forecast instance",
    )
    abstain: bool = Field(
        default=True,
        description="Whether the sentinel abstains from making a prediction",
    )
    reason_codes: list[str] = Field(
        default_factory=lambda: [ReasonCode.MODEL_NOT_READY.value],
        description="List of reason codes explaining the prediction or abstention decision",
    )
    model_version: Optional[str] = Field(
        default=None,
        description="Identifier of the ML model used, if available",
    )
    data_version: Optional[str] = Field(
        default=None,
        description="Identifier of the weather data pipeline version used, if available",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "location": "London",
                "bust_probability": None,
                "risk_level": None,
                "trust_state": "UNAVAILABLE",
                "abstain": True,
                "reason_codes": ["MODEL_NOT_READY"],
                "model_version": None,
                "data_version": None,
            }
        }
    }

