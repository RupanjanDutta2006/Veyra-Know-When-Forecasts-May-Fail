"""Prediction request and response schemas."""
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


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
    ELEVATED = "ELEVATED"
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
    QC_FAILED = "QC_FAILED"
    OOD_ABSTAIN = "OOD_ABSTAIN"
    OOD_DETECTED = "OOD_DETECTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    EXTREME_VOLATILITY = "EXTREME_VOLATILITY"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SUCCESS = "SUCCESS"


class PredictionRequest(BaseModel):
    """Forecast bust prediction request payload."""

    location: str = Field(
        ...,
        min_length=1,
        description="Location name, city, or coordinates for forecast evaluation",
        examples=["Delhi", "Mumbai", "Kolkata"],
    )
    target_date: Optional[str] = Field(
        default=None,
        description="Optional target forecast date (ISO format YYYY-MM-DD)",
        examples=["2026-09-01"],
    )

    @field_validator("location")
    @classmethod
    def validate_location_not_blank(cls, v: str) -> str:
        """Ensure location is not just whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("location cannot be empty or whitespace only")
        return stripped


class PredictionResponse(BaseModel):
    """Authoritative Forecast Bust Prediction Response payload with full V2 Intelligence."""

    location: str = Field(
        ...,
        description="Location requested for forecast evaluation",
    )
    bust_probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Calibrated probability (0.0 - 1.0) of forecast bust. null when unavailable or abstained.",
    )
    risk_level: Optional[RiskLevel] = Field(
        default=None,
        description="Categorical operational risk level (LOW < 0.060, ELEVATED >= 0.060, CRITICAL >= 0.600)",
    )
    trust_state: TrustState = Field(
        default=TrustState.UNAVAILABLE,
        description="Assessment of model reliability for this forecast instance",
    )
    confidence_index: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Non-probabilistic heuristic forecast reliability index (0-100)",
    )
    uncertainty_pct: Optional[float] = Field(
        default=None,
        description="Prediction uncertainty error margin (+/- %)",
    )
    ood_distance: Optional[float] = Field(
        default=None,
        description="Out-of-Distribution Mahalanobis novelty distance score",
    )
    revision: Optional[float] = Field(
        default=None,
        description="Cycle-over-cycle forecast trajectory revision magnitude",
    )
    stability: Optional[float] = Field(
        default=None,
        description="Forecast trajectory stability index (0-100)",
    )
    structural_overconfidence: Optional[float] = Field(
        default=None,
        description="Structural overconfidence physical signal score",
    )
    failure_fingerprint: Optional[str] = Field(
        default=None,
        description="Analytical failure archetype classification (e.g., STABLE_SYNOPTIC_CONSENSUS, ENSEMBLE_BIFURCATION)",
    )
    dominant_risk_drivers: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="List of primary physical risk drivers contributing to bust probability",
    )
    decision_mode: Optional[str] = Field(
        default=None,
        description="Actionable decision support mode (e.g. HIGH_TRUST, CAUTION, RECHECK_SOON, DO_NOT_RELY_SOLELY, ABSTAIN)",
    )
    within_trust_horizon: Optional[bool] = Field(
        default=None,
        description="Whether forecast lead time falls within the operational trust horizon",
    )
    operational_trust_horizon_hours: Optional[int] = Field(
        default=None,
        description="Operational trust horizon limit in lead hours before skill decay",
    )
    model_version: Optional[str] = Field(
        default=None,
        description="Identifier of the ML model used (e.g., veyra-v2-champion-lightgbm)",
    )
    data_version: Optional[str] = Field(
        default=None,
        description="Identifier of the weather data pipeline version used",
    )
    abstain: bool = Field(
        default=True,
        description="Whether the sentinel abstains from making a prediction",
    )
    reason_codes: list[str] = Field(
        default_factory=lambda: [ReasonCode.MODEL_NOT_READY.value],
        description="List of reason codes explaining the prediction or abstention decision",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "location": "Delhi",
                "bust_probability": 0.0996,
                "risk_level": "ELEVATED",
                "trust_state": "HIGH_CONFIDENCE",
                "confidence_index": 90.0,
                "uncertainty_pct": 3.37,
                "ood_distance": 0.0,
                "revision": None,
                "stability": 100.0,
                "structural_overconfidence": 0.0,
                "failure_fingerprint": "STABLE_SYNOPTIC_CONSENSUS",
                "dominant_risk_drivers": [],
                "model_version": "veyra-v2-champion-lightgbm",
                "data_version": "gefs-openmeteo-v1.0",
                "abstain": False,
                "reason_codes": ["SUCCESS"],
            }
        }
    }
