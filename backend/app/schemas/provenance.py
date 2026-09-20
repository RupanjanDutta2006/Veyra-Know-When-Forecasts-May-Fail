"""Model Provenance and Determinism Schemas for Veyra Phase 3 Day 33 (Gate C3).

Formalizes deterministic model identity, artifact checksum verification, and feature contracts.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class ModelProvenanceInfo(BaseModel):
    """Authoritative machine-readable model provenance and cryptographic digest."""

    model_name: str = Field(..., description="Canonical model architecture name")
    model_version: str = Field(..., description="Model release version identifier")
    model_sha256: str = Field(..., description="Authoritative SHA-256 cryptographic digest of model artifact")
    calibrator_type: str = Field(..., description="Probability calibration algorithm (e.g., IsotonicRegression)")
    calibrator_sha256: str = Field(..., description="Authoritative SHA-256 cryptographic digest of calibrator artifact")
    feature_count: int = Field(..., description="Exact ordered feature vector length (must equal 50 for V3)")
    feature_schema_version: str = Field(..., description="Feature contract schema version identifier")
    decision_threshold: float = Field(..., description="Operational decision threshold for bust classification")
    is_calibrated: bool = Field(..., description="Whether probability outputs undergo post-hoc calibration")
    is_deterministic: bool = Field(default=True, description="Whether repeated inference on identical inputs produces identical outputs")
    artifact_path: Optional[str] = Field(default=None, description="Local or container filesystem path to artifact directory")
