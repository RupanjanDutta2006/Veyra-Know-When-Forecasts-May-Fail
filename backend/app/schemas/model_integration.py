"""Model Integration Layer Schemas and Contracts for Veyra Phase 2 Day 11.

Defines input/output contracts, validation constraints, and anti-leakage guards
for the integration boundary between the platform orchestrator and ML models.
"""
import math
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator

# Strict security set of fields that must NEVER appear in inference input contracts
FORBIDDEN_GROUND_TRUTH_FIELDS: set[str] = {
    "observed_value",
    "is_ground_truth_label",
    "reference_val",
    "reference_value",
    "bust_label",
    "actual_value",
    "ground_truth",
    "reference_records",
}


class ModelInputContract(BaseModel):
    """Standardized input contract for ML model inference.

    Carries engineered features, feature names, and metadata while strictly
    enforcing anti-data-leakage constraints and value finiteness.
    """

    location: str = Field(..., min_length=1, description="Location identifier for prediction context")
    features: dict[str, float] = Field(
        default_factory=dict,
        description="Dictionary mapping canonical feature names to numerical values",
    )
    feature_names: list[str] = Field(
        default_factory=list,
        description="Ordered list of feature column names",
    )
    feature_schema_version: Optional[str] = Field(
        default=None,
        description="Version string of the feature engineering pipeline",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Contextual metadata (e.g. feature matrix rows, time steps)",
    )

    @field_validator("features")
    @classmethod
    def validate_features_and_leakage(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate absence of ground-truth fields and ensure all values are finite."""
        for key, val in v.items():
            key_lower = key.strip().lower()
            if key_lower in FORBIDDEN_GROUND_TRUTH_FIELDS:
                raise ValueError(
                    f"CRITICAL LEAKAGE DETECTED: Ground-truth field '{key}' cannot be passed into model inference."
                )
            if isinstance(val, (int, float)):
                if math.isnan(val) or math.isinf(val):
                    raise ValueError(
                        f"Non-finite feature value detected for '{key}': {val}. Model input must be finite."
                    )
        return v

    @field_validator("metadata")
    @classmethod
    def validate_metadata_leakage(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Ensure metadata dictionary contains no ground truth verification records."""
        for key in v:
            if key.strip().lower() in FORBIDDEN_GROUND_TRUTH_FIELDS:
                raise ValueError(
                    f"CRITICAL LEAKAGE DETECTED: Ground-truth field '{key}' in metadata."
                )
        return v


class ModelOutputContract(BaseModel):
    """Standardized output contract returned from the Model Integration Layer."""

    is_success: bool = Field(..., description="Whether model inference succeeded without error")
    probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Calibrated forecast bust probability P(bust) in range [0.0, 1.0]",
    )
    model_version: Optional[str] = Field(default=None, description="Active model version identifier")
    model_type: Optional[str] = Field(default=None, description="Underlying model architecture / estimator type")
    feature_schema_version: Optional[str] = Field(default=None, description="Feature pipeline schema version")
    is_calibrated: bool = Field(default=False, description="Whether probability is calibrated")
    decision_threshold: Optional[float] = Field(
        default=None,
        description="Model decision threshold for triggering bust alerts",
    )
    bust_alert: bool = Field(default=False, description="Whether bust probability exceeds decision threshold")
    reason_code: str = Field(default="SUCCESS", description="Execution status or failure reason code")
    error_message: Optional[str] = Field(default=None, description="Structured error message if failed")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Detailed inference and explainer metadata")


class ModelMetadataInfo(BaseModel):
    """Introspection schema describing a registered model's metadata and readiness."""

    model_name: str = Field(..., description="Unique registered model name")
    model_version: str = Field(..., description="Model version string")
    model_type: str = Field(..., description="Underlying algorithm (e.g. LightGBM, LogisticRegression)")
    feature_schema_version: str = Field(..., description="Required feature schema version")
    expected_features: list[str] = Field(default_factory=list, description="List of expected feature names")
    expected_feature_count: int = Field(..., description="Number of expected features")
    decision_threshold: float = Field(..., description="Calibrated decision threshold")
    is_calibrated: bool = Field(default=True, description="Whether probability calibration is active")
    is_ready: bool = Field(..., description="Whether artifacts are loaded and ready for inference")
    artifact_path: Optional[str] = Field(default=None, description="Path to loaded artifact directory")
