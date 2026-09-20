"""OOD Policy and Diagnostics Schemas for Veyra Phase 3 Day 33.

Defines deterministic, machine-readable representations for physical out-of-distribution
diagnostics, distinct from scientific certification or operational risk levels.
"""
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class OODState(str, Enum):
    """Enumeration of deterministic OOD diagnostic evaluation states."""

    IN_DISTRIBUTION = "IN_DISTRIBUTION"
    OUT_OF_DISTRIBUTION = "OUT_OF_DISTRIBUTION"
    OOD_UNKNOWN = "OOD_UNKNOWN"


class OODReasonCode(str, Enum):
    """Machine-readable reason codes for OOD diagnostic policy decisions."""

    WITHIN_PHYSICAL_TRAINING_SUPPORT = "WITHIN_PHYSICAL_TRAINING_SUPPORT"
    OUT_OF_PHYSICAL_SUPPORT = "OUT_OF_PHYSICAL_SUPPORT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNSUPPORTED_VARIABLE = "UNSUPPORTED_VARIABLE"
    INVALID_REQUEST_PARAMETERS = "INVALID_REQUEST_PARAMETERS"


class OODDiagnosticResult(BaseModel):
    """Structured result of an out-of-distribution diagnostic policy evaluation."""

    status: OODState = Field(
        ...,
        description="OOD diagnostic classification (IN_DISTRIBUTION, OUT_OF_DISTRIBUTION, OOD_UNKNOWN)",
    )
    is_ood: Optional[bool] = Field(
        ...,
        description="Boolean flag indicating whether the forecast input lies outside physical training support",
    )
    reason_code: OODReasonCode = Field(
        ...,
        description="Machine-readable diagnostic reason code",
    )
    reason_detail: str = Field(
        ...,
        description="Human-readable explanation of the OOD diagnostic determination",
    )
    ood_score: Optional[float] = Field(
        default=None,
        description="Raw heuristic physical domain distance score (0.0 to 100.0)",
    )
    policy_version: str = Field(
        ...,
        description="Version string of the authoritative OOD diagnostic policy",
    )
    causes_abstention: bool = Field(
        default=False,
        description="Whether this OOD determination caused automated pipeline abstention (strictly False for diagnostic-only OOD)",
    )
    diagnostic_inputs: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Observed meteorological input parameters evaluated against physical bounds",
    )


class OODPolicyMetadata(BaseModel):
    """Authoritative metadata and bounding definitions for the OOD Diagnostic Policy."""

    policy_version: str = Field(..., description="OOD policy version identifier")
    description: str = Field(..., description="Human-readable policy specification")
    supported_variables: list[str] = Field(..., description="Atmospheric variables evaluated by the policy")
    physical_bounding_ranges: Dict[str, Dict[str, Any]] = Field(
        ..., description="Nominal in-distribution physical domain bounds per variable"
    )
    causes_abstention: bool = Field(
        default=False,
        description="Whether OOD classification forces model abstention (False under current scientific evidence)",
    )
    governance_note: str = Field(
        ...,
        description="Scientific disclaimer distinguishing OOD diagnostics from formal statistical coverage or certification",
    )
