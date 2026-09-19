"""Scientific Certification Schemas for Veyra Phase 3 Day 32.

Defines typed Pydantic models, certification status enums, and machine-readable
reason codes for the Day 32 Scientific Certification Gate (C1).
"""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class CertificationStatus(str, Enum):
    """Machine-readable scientific certification status."""

    CERTIFIED = "CERTIFIED"
    OUTSIDE_CERTIFIED_SCOPE = "OUTSIDE_CERTIFIED_SCOPE"
    CERTIFICATION_UNKNOWN = "CERTIFICATION_UNKNOWN"


class CertificationReasonCode(str, Enum):
    """Deterministic scientific certification reason codes."""

    CERTIFIED_FROZEN_BENCHMARK_SCOPE = "CERTIFIED_FROZEN_BENCHMARK_SCOPE"
    UNCERTIFIED_LEAD_HORIZON = "UNCERTIFIED_LEAD_HORIZON"
    UNCERTIFIED_LOCATION = "UNCERTIFIED_LOCATION"
    UNCERTIFIED_VARIABLE = "UNCERTIFIED_VARIABLE"
    CERTIFICATION_METADATA_UNAVAILABLE = "CERTIFICATION_METADATA_UNAVAILABLE"
    MODEL_ARTIFACT_MISMATCH = "MODEL_ARTIFACT_MISMATCH"
    CALIBRATOR_ARTIFACT_MISMATCH = "CALIBRATOR_ARTIFACT_MISMATCH"


class ScientificCertificationResult(BaseModel):
    """Evaluated scientific certification gate decision for a prediction request."""

    status: CertificationStatus = Field(
        ...,
        description="Machine-readable scientific certification decision status",
        examples=[CertificationStatus.CERTIFIED],
    )
    is_certified: bool = Field(
        ...,
        description="True if and only if request lies strictly inside the frozen scientific evidence boundary",
    )
    reason_code: CertificationReasonCode = Field(
        ...,
        description="Deterministic reason code detailing the scientific certification boundary result",
    )
    reason_detail: str = Field(
        ...,
        description="Human-readable explanation of certification decision and evidence boundary",
    )
    policy_version: str = Field(
        default="v3.0.0-frozen-benchmark",
        description="Authoritative scientific certification policy version",
    )
    model_sha256: str = Field(
        ...,
        description="SHA-256 digest of the evaluated serving model artifact",
    )
    calibrator_sha256: str = Field(
        ...,
        description="SHA-256 digest of the evaluated probability calibrator artifact",
    )
    evaluated_location: Optional[str] = Field(
        default=None,
        description="Target location evaluated for certification",
    )
    evaluated_variable: Optional[str] = Field(
        default=None,
        description="Target meteorological variable evaluated for certification",
    )
    evaluated_lead_hours: Optional[int] = Field(
        default=None,
        description="Target forecast lead horizon evaluated for certification",
    )
    certified_benchmark_stations: List[str] = Field(
        default_factory=list,
        description="List of canonical synoptic stations certified in the frozen benchmark dataset",
    )
    certified_variables: List[str] = Field(
        default_factory=list,
        description="List of meteorological variables certified in the frozen benchmark dataset",
    )
    max_certified_lead_hours: int = Field(
        default=240,
        description="Maximum forecast lead horizon (hours) certified in frozen benchmark",
    )
    certified_evaluation_period: str = Field(
        default="2017-2019 (Test Holdout)",
        description="Chronological period certified in offline evaluation",
    )


class CertificationEvaluationRequest(BaseModel):
    """Request contract for evaluating scientific certification gate."""

    location: str = Field(
        ...,
        description="Geographic location query or station name to evaluate for scientific certification",
        examples=["Kolkata", "Delhi", "London"],
    )
    variable: str = Field(
        default="temperature_2m",
        description="Meteorological variable name",
        examples=["temperature_2m", "wind_speed_10m", "surface_pressure"],
    )
    lead_hours: int = Field(
        default=24,
        ge=1,
        le=384,
        description="Forecast lead horizon in hours",
        examples=[24],
    )
