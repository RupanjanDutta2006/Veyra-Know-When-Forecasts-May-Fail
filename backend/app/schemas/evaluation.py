"""Model Evaluation Schemas and Contracts for Veyra Phase 2 Day 12.

Defines structured contracts for exposing validated model performance metrics,
sample counts, calibration metadata, and dataset split information.
"""
import math
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class EvaluationStatus(str, Enum):
    """Status indicating availability and validity of model evaluation metrics."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    INVALID = "INVALID"


class EvaluationMetrics(BaseModel):
    """Validated model performance metrics container."""

    accuracy: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Classification accuracy")
    precision: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Precision score")
    recall: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Recall / sensitivity score")
    f1_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Harmonic mean F1 score")
    roc_auc: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Area under ROC curve")
    pr_auc: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Area under Precision-Recall curve")
    brier_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Brier calibration score")
    brier_score_uncalibrated: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Uncalibrated model Brier score"
    )
    brier_score_calibrated: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Calibrated model Brier score"
    )
    brier_improvement_pct: Optional[float] = Field(
        default=None, description="Percentage calibration improvement"
    )
    spread_baseline_roc_auc: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Ensemble spread baseline ROC-AUC benchmark"
    )
    spread_baseline_pr_auc: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Ensemble spread baseline PR-AUC benchmark"
    )

    @field_validator("*", mode="before")
    @classmethod
    def validate_finiteness(cls, v: Any) -> Any:
        """Validate that all numerical metrics are finite and non-NaN."""
        if isinstance(v, (int, float)):
            if math.isnan(v) or math.isinf(v):
                raise ValueError("Evaluation metric must be a finite numerical value")
        return v


class CalibrationMetadata(BaseModel):
    """Model calibration metadata container."""

    is_calibrated: bool = Field(default=False, description="Whether probability calibration is active")
    calibration_method: Optional[str] = Field(default=None, description="Calibration algorithm (e.g. sigmoid, isotonic)")
    decision_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Calibrated decision threshold")
    calibrator_status: Optional[str] = Field(default=None, description="Operational status of calibrator artifact")


class EvaluationDatasetInfo(BaseModel):
    """Information regarding the dataset splits used during model evaluation."""

    dataset_name: Optional[str] = Field(default=None, description="Evaluation dataset identifier")
    split_name: Optional[str] = Field(default=None, description="Evaluated split (e.g. test, validation)")
    total_samples: Optional[int] = Field(default=None, ge=0, description="Total dataset sample count")
    train_samples: Optional[int] = Field(default=None, ge=0, description="Training partition sample count")
    validation_samples: Optional[int] = Field(default=None, ge=0, description="Validation partition sample count")
    test_samples: Optional[int] = Field(default=None, ge=0, description="Test partition sample count")
    time_ranges: dict[str, Any] = Field(default_factory=dict, description="Chronological split time ranges")


class ModelEvaluationResponse(BaseModel):
    """Standardized API response contract for model evaluation metadata."""

    model_name: str = Field(..., description="Registered model name identifier")
    model_version: str = Field(..., description="Evaluated model version string")
    model_type: Optional[str] = Field(default=None, description="Underlying model algorithm / architecture")
    data_version: Optional[str] = Field(default=None, description="Weather data ingestion version")
    feature_schema_version: Optional[str] = Field(default=None, description="Feature pipeline schema version")
    feature_count: Optional[int] = Field(default=None, description="Number of expected features")
    evaluation_status: EvaluationStatus = Field(..., description="Status of evaluation availability and validity")
    metrics: Optional[EvaluationMetrics] = Field(default=None, description="Validated performance metrics")
    calibration: Optional[CalibrationMetadata] = Field(default=None, description="Calibration information")
    dataset_info: Optional[EvaluationDatasetInfo] = Field(default=None, description="Dataset split information")
    reason_codes: list[str] = Field(default_factory=list, description="Descriptive status / diagnostic reason codes")
    evaluated_at: Optional[str] = Field(default=None, description="Timestamp of evaluation execution")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional contextual evaluation metadata")
