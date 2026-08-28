"""Explainability contracts and schemas for Veyra Phase 2 Day 13.

Defines typed Pydantic models for physical feature attributions, contributing factors,
explanation summaries, and explainability status codes.
"""
from enum import Enum
import math
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class ExplainabilityStatus(str, Enum):
    """Operational status of the model explainability layer."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    INVALID = "INVALID"


class ContributingFactor(BaseModel):
    """Individual physical feature attribution factor."""

    factor: str = Field(
        ...,
        description="Canonical feature name contributing to the forecast bust prediction",
        examples=["forecast_delta_24h", "ensemble_std", "lead_hours"],
    )
    value: Optional[float] = Field(
        default=None,
        description="Physical numerical value of the feature (finite float or null)",
        examples=[2.45, 1.82, 120.0],
    )
    signal: str = Field(
        ...,
        description="Standardized physical signal category or interpretation code",
        examples=["HIGH_REVISION_DRIFT", "HIGH_ENSEMBLE_SPREAD", "EXTENDED_RANGE_DEGRADATION"],
    )

    @field_validator("value")
    @classmethod
    def validate_finite_value(cls, v: Optional[float]) -> Optional[float]:
        """Ensure numerical value is strictly finite and not NaN or Infinity."""
        if v is not None:
            if math.isnan(v) or math.isinf(v):
                raise ValueError(f"Contributing factor value must be finite; received {v}")
            return round(v, 4)
        return None

    model_config = {
        "json_schema_extra": {
            "example": {
                "factor": "ensemble_std",
                "value": 2.15,
                "signal": "ELEVATED_ENSEMBLE_SPREAD",
            }
        }
    }


class ExplanationItem(BaseModel):
    """Structured physical explanation of forecast bust risk."""

    primary_driver: str = Field(
        ...,
        description="Primary identifier for the dominant risk driver",
        examples=["stable_ensemble_agreement", "rapid_inter_cycle_revision", "high_ensemble_uncertainty"],
    )
    driver_summary: str = Field(
        ...,
        description="Model-grounded human-readable summary narrative explaining physical attribution signals",
        examples=[
            "Forecast is stable with low ensemble dispersion and consistent inter-cycle agreement.",
            "High risk driven by rapid 24h run-to-run forecast revision (+2.40 unit drift).",
        ],
    )
    top_contributing_factors: list[ContributingFactor] = Field(
        default_factory=list,
        description="Ranked list of physical contributing factors and signals",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "primary_driver": "stable_ensemble_agreement",
                "driver_summary": "Forecast is stable with low ensemble dispersion and consistent inter-cycle agreement.",
                "top_contributing_factors": [
                    {
                        "factor": "forecast_delta_24h",
                        "value": None,
                        "signal": "NO_PRIOR_CYCLE_BASELINE",
                    },
                    {
                        "factor": "ensemble_std",
                        "value": 0.0,
                        "signal": "LOW_ENSEMBLE_SPREAD",
                    },
                    {
                        "factor": "lead_hours",
                        "value": 116.0,
                        "signal": "MEDIUM_RANGE_HORIZON",
                    },
                ],
            }
        }
    }


class ModelExplanationResponse(BaseModel):
    """Standardized response payload for dedicated explainability endpoints or diagnostics."""

    model_name: str = Field(
        ...,
        description="Identifier of the model evaluated",
        examples=["builder2_gbm"],
    )
    model_version: str = Field(
        ...,
        description="Model version identifier",
        examples=["prototype-gbm-v1"],
    )
    explainability_status: ExplainabilityStatus = Field(
        default=ExplainabilityStatus.AVAILABLE,
        description="Availability and validity status of the explanation",
    )
    explanation: Optional[ExplanationItem] = Field(
        default=None,
        description="Structured physical explanation item",
    )
    reason_codes: list[str] = Field(
        default_factory=lambda: ["SUCCESS"],
        description="Standardized reason codes explaining the attribution decision",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional attribution diagnostics and metadata",
    )
