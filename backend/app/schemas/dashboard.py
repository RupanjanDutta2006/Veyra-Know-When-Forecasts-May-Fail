"""Dashboard Intelligence Schemas for Veyra Phase 3 Day 25.

Provides typed, dashboard-ready API contracts for the centralized orchestration
endpoint POST /v1/dashboard/intelligence.
"""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.schemas.prediction import (
    CalibrationStatus,
    PredictionRequest,
    PredictionResponse,
    ReasonCode,
    RiskLevel,
    SUPPORTED_VARIABLES,
    TrustState,
)


class DecisionMode(str, Enum):
    """Operational decision governance modes."""

    STANDARD_MONITORING = "STANDARD_MONITORING"
    ELEVATED_AWARENESS = "ELEVATED_AWARENESS"
    HIGH_UNCERTAINTY = "HIGH_UNCERTAINTY"
    CRITICAL_INTERVENTION = "CRITICAL_INTERVENTION"
    ABSTAINED = "ABSTAINED"


class DashboardMode(str, Enum):
    """Supported horizon evaluation modes for dashboard intelligence."""

    SINGLE = "single"          # Canonical 24h operational lead only
    STANDARD_7D = "standard_7d"  # 7-day timeline: 24, 48, 72, 96, 120, 144, 168 hours
    FULL_16D = "full_16d"        # Full 16-day operational timeline: 24 to 384 hours (every 24h)


class DashboardStatus(str, Enum):
    """Deterministic orchestration outcome status."""

    SUCCESS = "SUCCESS"      # All requested timeline points evaluated successfully
    PARTIAL = "PARTIAL"      # At least one point evaluated successfully and at least one abstained
    ABSTAINED = "ABSTAINED"  # Zero points evaluated successfully (all points abstained)


class DashboardLocationContext(BaseModel):
    """Geographic resolution and station metadata for the requested location."""

    query: str = Field(..., description="Original location query provided by client", examples=["Kolkata"])
    resolved_name: Optional[str] = Field(default=None, description="Standardized canonical place or station name", examples=["Kolkata"])
    latitude: Optional[float] = Field(default=None, description="Resolved geographic latitude in decimal degrees", examples=[22.5726])
    longitude: Optional[float] = Field(default=None, description="Resolved geographic longitude in decimal degrees", examples=[88.3639])
    region_id: Optional[str] = Field(default=None, description="Regional or synoptic identifier if mapped", examples=["IN_KOLKATA"])


class DashboardTimelinePoint(BaseModel):
    """Typed evaluation result for a specific forecast horizon."""

    lead_hours: int = Field(..., ge=1, le=384, description="Forecast lead time in hours", examples=[24])
    lead_days: float = Field(..., ge=0.0, description="Forecast lead time in days", examples=[1.0])
    valid_time: str = Field(..., description="Forecast valid verification timestamp (ISO 8601 UTC)", examples=["2026-09-11T00:00:00Z"])
    bust_probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Calibrated probability (0.0-1.0) of forecast failure. null if abstained or unavailable.",
        examples=[0.035],
    )
    risk_level: Optional[RiskLevel] = Field(default=None, description="Authoritative categorical risk tier (LOW, MEDIUM, HIGH, CRITICAL)")
    trust_state: TrustState = Field(default=TrustState.UNAVAILABLE, description="Operational model reliability assessment")
    abstain: bool = Field(default=True, description="Whether the model abstains from making a prediction at this horizon")
    reason_codes: List[ReasonCode] = Field(default_factory=list, description="Reason codes explaining evaluation or abstention")
    calibration_status: CalibrationStatus = Field(default=CalibrationStatus.UNAVAILABLE, description="Status of probability calibration (CALIBRATED, FAILED, UNAVAILABLE)")
    decision_mode: DecisionMode = Field(default=DecisionMode.ABSTAINED, description="Authoritative operational decision governance mode")
    within_trust_horizon: Optional[bool] = Field(default=True, description="Whether horizon is within operational trust bounds")
    operational_trust_horizon_hours: Optional[int] = Field(default=168, description="Operational trust horizon limit (hours)")
    is_certified_horizon: bool = Field(
        default=True,
        description="True if lead_hours <= 240 (covered by Day 23 frozen benchmark certification). False for 264h-384h (operational only).",
    )


class DashboardSummary(BaseModel):
    """Deterministic aggregated intelligence synthesized across the timeline."""

    available_points: int = Field(..., ge=0, description="Count of points with valid (non-null) predictions")
    abstained_points: int = Field(..., ge=0, description="Count of points where the model abstained (null probability)")
    total_points: int = Field(..., ge=0, description="Total requested timeline horizons")
    max_bust_probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Maximum calibrated bust probability across valid timeline points. null if all abstained.",
    )
    max_risk_level: Optional[RiskLevel] = Field(
        default=None,
        description="Peak categorical risk level across valid timeline points. null if all abstained.",
    )
    max_risk_lead_hours: Optional[int] = Field(
        default=None,
        description="Lead horizon in hours corresponding to peak risk. null if all abstained.",
    )
    mean_bust_probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Null-safe arithmetic mean of calibrated bust probabilities over available points only. null if all abstained.",
    )
    elevated_risk_points: int = Field(
        default=0,
        ge=0,
        description="Count of valid timeline points exhibiting elevated risk (MEDIUM, HIGH, or CRITICAL; p >= 0.20)",
    )
    first_elevated_risk_lead_hours: Optional[int] = Field(
        default=None,
        description="Earliest forecast horizon in hours where risk reaches MEDIUM, HIGH, or CRITICAL. null if none.",
    )
    overall_decision_mode: DecisionMode = Field(
        default=DecisionMode.ABSTAINED,
        description="Peak operational decision guidance across timeline (CRITICAL_INTERVENTION > HIGH_UNCERTAINTY > ELEVATED_AWARENESS > STANDARD_MONITORING)",
    )


class HistoricalBenchmarkContext(BaseModel):
    """Frozen Day 23 championship benchmark diagnostics and scientific provenance."""

    dataset: str = Field(default="canonical_reforecast_test", description="Certified benchmark test partition")
    period: str = Field(default="2017-01-01 to 2019-12-31", description="Certified temporal evaluation window")
    test_samples: int = Field(default=116250, description="Number of evaluated test instances")
    test_cycles: int = Field(default=155, description="Number of independent test forecast cycles")
    average_precision: float = Field(default=0.2047, description="Area under Precision-Recall curve (scikit-learn average_precision_score)")
    pr_auc_trapezoidal: float = Field(default=0.2124, description="Trapezoidal rule Area Under Precision-Recall curve")
    roc_auc: float = Field(default=0.7698, description="Area Under ROC curve")
    brier_score: float = Field(default=0.053798, description="Mean squared probability calibration error (lower is better)")
    bss_vs_e0: float = Field(default=0.0807, description="Brier Skill Score relative to Climatology baseline E0")
    bss_vs_e1b: float = Field(default=0.0778, description="Brier Skill Score relative to Ensemble Spread baseline E1b")
    ece: float = Field(default=0.0064, description="Expected Calibration Error under 10-bin uniform partitioning")


class DashboardScientificContext(BaseModel):
    """Scientific metadata separating live operational inference from frozen historical benchmarks."""

    model_version: str = Field(default="veyra-v3-benchmark-lightgbm", description="Active production model artifact version")
    model_family: str = Field(default="LightGBM + Isotonic Calibration", description="Model architecture")
    calibration_method: str = Field(default="isotonic", description="Active probability calibration algorithm")
    feature_count: int = Field(default=50, description="Exact canonical feature dimension contract")
    probability_semantics: str = Field(
        default=(
            "Calibrated empirical probability of forecast absolute error meeting or exceeding the stratum-specific bust threshold "
            "under certified Day 22 label definitions. Does NOT represent severe weather, precipitation, or disaster probability."
        ),
        description="Explicit probabilistic semantic contract",
    )
    benchmark_scope: str = Field(default="25 canonical stations, 3 variables, 10 lead horizons (24h to 240h)", description="Geographic and variable coverage")
    benchmark_lead_horizon_max_hours: int = Field(default=240, description="Maximum lead horizon covered by Day 23 frozen benchmark certification")
    operational_horizon_max_hours: int = Field(default=384, description="Maximum operational forecast horizon supported by serving architecture")
    historical_benchmark: HistoricalBenchmarkContext = Field(default_factory=HistoricalBenchmarkContext, description="Frozen Day 23 benchmark evaluation diagnostics")
    generalization_limits: List[str] = Field(
        default=[
            "Certified across 25 canonical synoptic stations in India only",
            "Certified for 3 target variables: temperature_2m, wind_speed_10m, surface_pressure",
            "Certified across 10 benchmark lead horizons (24h to 240h); horizons >240h (264h-384h) are operational only and uncertified by benchmark",
            "Certified on historical Test partition (2017-2019)",
            "Evaluated on historical N=5 ensemble; operational live N=31 equivalence uncertified",
            "Post-2019 operational performance uncertified",
            "Unseen-station / universal geographic generalization uncertified",
            "Model estimates empirical forecast-bust probability, not severe weather, disaster risk, or general meteorological failure",
        ],
        description="Scientific limitations and generalization caveats that frontend MUST preserve",
    )


class DashboardRequest(BaseModel):
    """Request payload for unified dashboard intelligence orchestration."""

    location: str = Field(
        ...,
        description="Location name, city, or coordinates for dashboard evaluation",
        examples=["Kolkata", "Delhi", "London"],
    )
    variable: Optional[str] = Field(
        default="temperature_2m",
        description="Forecast meteorological variable to evaluate (temperature_2m, surface_pressure, wind_speed_10m)",
        examples=["temperature_2m"],
    )
    mode: DashboardMode = Field(
        default=DashboardMode.STANDARD_7D,
        description="Horizon evaluation mode: single (24h), standard_7d (24h-168h), or full_16d (24h-384h)",
        examples=["standard_7d"],
    )
    issue_time: Optional[str] = Field(
        default=None,
        description="Optional forecast issuance timestamp (ISO 8601 UTC). Defaults to latest operational model cycle.",
        examples=["2026-09-10T00:00:00Z"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "location": "Kolkata",
                "variable": "temperature_2m",
                "mode": "standard_7d",
            }
        }
    }

    @field_validator("location")
    @classmethod
    def validate_location(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("location cannot be empty or whitespace only")
        return v.strip()

    @field_validator("variable")
    @classmethod
    def validate_variable(cls, v: Optional[str]) -> str:
        if v is None:
            return "temperature_2m"
        clean = v.strip().lower()
        if clean not in SUPPORTED_VARIABLES:
            raise ValueError(
                f"Unsupported forecast variable '{v}'. Supported: {', '.join(sorted(SUPPORTED_VARIABLES))}"
            )
        return clean


class DashboardIntelligenceResponse(BaseModel):
    """Complete, dashboard-ready intelligence payload synthesized by backend."""

    status: DashboardStatus = Field(..., description="Orchestration outcome status (SUCCESS, PARTIAL, ABSTAINED)")
    location: DashboardLocationContext = Field(..., description="Geographic and station resolution details")
    variable: str = Field(..., description="Evaluated meteorological variable", examples=["temperature_2m"])
    issue_time: Optional[str] = Field(default=None, description="Forecast issuance timestamp (ISO 8601 UTC)")
    mode: DashboardMode = Field(..., description="Evaluated horizon mode")
    selected_prediction: PredictionResponse = Field(..., description="Authoritative single prediction (canonical 24h operational lead)")
    timeline: List[DashboardTimelinePoint] = Field(..., description="Ordered list of evaluated horizon points")
    summary: DashboardSummary = Field(..., description="Deterministic aggregated summary intelligence across timeline")
    scientific_context: DashboardScientificContext = Field(
        default_factory=DashboardScientificContext,
        description="Model provenance, historical benchmark diagnostics, and generalization boundaries",
    )
    request_id: Optional[str] = Field(default=None, description="Correlation identifier for request tracing and debugging")
