"""
Canonical Explainable AI (XAI) Schema & Data Structures (Day 17).

Defines strongly typed, machine-readable, and JSON-serializable dataclasses and enums
for comprehensive forecast-bust explanations, feature attributions, uncertainty diagnostics,
historical analogue alignment, decision rationales, temporal dynamics, and decision counterfactuals.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional
import numpy as np


class ExplanationMode(str, Enum):
    """Execution context for XAI generation."""
    DECISION_TIME = "DECISION_TIME"          # Live inference: strictly zero verification target data
    POST_HOC_EVALUATION = "POST_HOC_EVALUATION"  # Retrospective audit: compares decisions with verified truth


class ExplanationLevel(str, Enum):
    """Granularity of generated explanation."""
    OPERATOR_SUMMARY = "OPERATOR_SUMMARY"      # High-level operational brief (Level 1)
    TECHNICAL_EXPLANATION = "TECHNICAL_EXPLANATION"  # Detailed risk, uncertainty, temporal drivers (Level 2)
    FORENSIC_TRACE = "FORENSIC_TRACE"          # Full mathematical trace and provenance (Level 3)


class DriverCategory(str, Enum):
    """Categorization of individual feature risk contribution."""
    HIGH_RISK_DRIVER = "HIGH_RISK_DRIVER"
    MODERATE_RISK_DRIVER = "MODERATE_RISK_DRIVER"
    PROTECTIVE_FACTOR = "PROTECTIVE_FACTOR"
    NEUTRAL_FACTOR = "NEUTRAL_FACTOR"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class DriverDirection(str, Enum):
    """Sign of feature influence on forecast-bust probability."""
    INCREASES_RISK = "INCREASES_RISK"
    DECREASES_RISK = "DECREASES_RISK"
    NEUTRAL = "NEUTRAL"


class UncertaintySource(str, Enum):
    """Identified primary or secondary sources of forecast uncertainty."""
    ENSEMBLE_DISPERSION = "ENSEMBLE_DISPERSION"
    EPISTEMIC_NOVELTY = "EPISTEMIC_NOVELTY"
    TEMPORAL_INSTABILITY = "TEMPORAL_INSTABILITY"
    FORECAST_HORIZON = "FORECAST_HORIZON"
    DATA_QUALITY_MISSINGNESS = "DATA_QUALITY_MISSINGNESS"
    HISTORICAL_ANALOGUE_DISPERSION = "HISTORICAL_ANALOGUE_DISPERSION"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"


class HistoricalEvidenceAlignment(str, Enum):
    """Consensus between current assessment and historical analogues."""
    SUPPORTING = "SUPPORTING"
    CONTRADICTING = "CONTRADICTING"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


def _xai_json_fallback(obj: Any) -> Any:
    """Recursively converts NumPy / custom types to standard Python primitives."""
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return float(obj)
    if isinstance(obj, (np.ndarray, list, tuple)):
        return [_xai_json_fallback(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _xai_json_fallback(v) for k, v in obj.items()}
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, Enum):
        return obj.value
    return str(obj)


@dataclass
class FeatureRiskDriver:
    """Structured attribution for a single meteorological feature."""
    feature_name: str
    display_name: str
    value: float
    normalized_contribution: float
    direction: DriverDirection
    category: DriverCategory
    rank: int
    interpretation: str
    is_actionable: bool = False
    evidence_source: str = "FEATURE_ATTRIBUTION"
    confidence: float = 1.0


@dataclass
class UncertaintyExplanation:
    """Decomposition and explanation of forecast uncertainty."""
    dominant_source: UncertaintySource
    secondary_sources: List[UncertaintySource]
    ensemble_spread_magnitude: float
    epistemic_novelty_magnitude: float
    temporal_instability_magnitude: float
    confidence_impact_score: float  # [0.0, 1.0] degradation
    narrative: str


@dataclass
class NoveltyExplanation:
    """Evaluation of feature-space novelty and out-of-distribution status."""
    is_in_domain: bool
    novelty_score: float
    novelty_level: str  # NORMAL, MODERATE, EXTREME
    confidence_impact: float
    contributed_to_abstention: bool
    narrative: str


@dataclass
class HistoricalEvidenceExplanation:
    """Interpretation of historical failure analogues."""
    alignment: HistoricalEvidenceAlignment
    analogue_count: int
    historical_failure_rate: float
    trajectory_similarity: float
    has_sufficient_support: bool
    narrative: str
    sample_analogue_ids: List[str] = field(default_factory=list)


@dataclass
class EvidenceConflictItem:
    """Explicit representation of conflicting evidence channels."""
    source_a: str
    source_b: str
    conflict_category: str
    disagreement_magnitude: float
    effect_on_confidence: float
    effect_on_decision: str
    resolution_status: str  # RESOLVED, UNRESOLVED_DEGRADED, ABSTAINED


@dataclass
class TemporalDynamicsExplanation:
    """Explanation of multi-cycle forecast evolution and early warning."""
    sequence_length: int
    risk_trend: str  # RISING, FALLING, STABLE, ACCELERATING, REVERSING
    risk_velocity: float
    risk_acceleration: float
    persistence_cycles: int
    spread_growth_fraction: float
    forecast_revision_velocity: float
    instability_detected: bool
    trajectory_state: str
    warning_horizon: str
    time_to_critical_risk_str: str
    time_to_risk_estimable: bool
    narrative: str


@dataclass
class DecisionRationale:
    """Deterministic explanation of the operational decision selected."""
    decision: str
    risk_level: str
    warning_priority: str
    primary_triggers: List[str]
    governing_threshold_applied: str
    safety_constraints_applied: List[str]
    abstention_triggered: bool = False
    abstention_reason: Optional[str] = None
    recommended_action: str = ""


@dataclass
class DecisionCounterfactual:
    """
    Deterministic policy sensitivity counterfactual.
    Answers: 'What would need to change for the decision to become less/more severe?'
    Explicitly labeled as DECISION_COUNTERFACTUAL (not a physical causal claim).
    """
    target_decision_direction: str  # LESS_SEVERE, MORE_SEVERE
    parameter_name: str
    current_value: float
    required_value: float
    required_shift: float
    explanation: str
    governance_class: str = "DECISION_COUNTERFACTUAL"


@dataclass
class CanonicalXAIExplanation:
    """
    Master unified forecast failure risk explanation payload (Day 17).
    """
    explanation_id: str
    schema_version: str
    mode: ExplanationMode
    location_id: str
    variable: str
    valid_time_utc: str
    issue_time_utc: str
    risk_score: float
    calibrated_bust_probability: float
    risk_confidence: float
    explanation_confidence: float
    operational_decision: str
    warning_priority: str
    overall_narrative: str
    risk_drivers: List[FeatureRiskDriver] = field(default_factory=list)
    protective_drivers: List[FeatureRiskDriver] = field(default_factory=list)
    uncertainty: Optional[UncertaintyExplanation] = None
    novelty: Optional[NoveltyExplanation] = None
    historical_evidence: Optional[HistoricalEvidenceExplanation] = None
    temporal_dynamics: Optional[TemporalDynamicsExplanation] = None
    evidence_conflicts: List[EvidenceConflictItem] = field(default_factory=list)
    decision_rationale: Optional[DecisionRationale] = None
    counterfactuals: List[DecisionCounterfactual] = field(default_factory=list)
    recommended_operator_attention: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    post_hoc_verification: Optional[Dict[str, Any]] = None
    decision_provenance_hash: str = ""
    provenance_hash: str = ""

    def compute_decision_provenance_hash(self, governing_thresholds: Optional[tuple] = None) -> str:
        """
        Compute a canonical, deterministic SHA-256 fingerprint representing the pure
        scientific decision-time inputs, calibrated risk, feature attributions, uncertainty/novelty,
        analogue evidence, temporal trajectory, counterfactuals, and governing decision policy.

        Explicitly invariant to:
        - Execution mode (DECISION_TIME vs POST_HOC_EVALUATION)
        - Volatile timestamps (issue_time_utc, system clock)
        - Retrospective verification data (truth_value, forecast_error, bust_label)
        - Presentation line-wrapping and markdown formatting
        """
        thresh_str = str(governing_thresholds) if governing_thresholds else "default_policy"
        drivers_repr = [
            f"{d.feature_name}:{d.value:.3f}:{d.normalized_contribution:.4f}:{d.direction.value}"
            for d in sorted(self.risk_drivers + self.protective_drivers, key=lambda x: x.feature_name)
        ]
        cfs_repr = [
            f"{c.target_decision_direction}:{c.parameter_name}:{c.required_value:.3f}"
            for c in sorted(self.counterfactuals, key=lambda x: (x.target_decision_direction, x.parameter_name))
        ]
        unc_str = self.uncertainty.dominant_source.value if self.uncertainty else "NONE"
        nov_str = f"{self.novelty.novelty_level}:{self.novelty.novelty_score:.3f}" if self.novelty else "NONE"
        hist_str = f"{self.historical_evidence.alignment.value}:{self.historical_evidence.historical_failure_rate:.3f}" if self.historical_evidence else "NONE"
        temp_str = f"{self.temporal_dynamics.trajectory_state}:{self.temporal_dynamics.warning_horizon}:{self.temporal_dynamics.time_to_critical_risk_str}" if self.temporal_dynamics else "NONE"

        components = [
            f"schema={self.schema_version}",
            f"loc={self.location_id}",
            f"var={self.variable}",
            f"valid_time={self.valid_time_utc}",
            f"risk={self.calibrated_bust_probability:.4f}",
            f"decision={self.operational_decision}",
            f"priority={self.warning_priority}",
            f"drivers={','.join(drivers_repr)}",
            f"unc={unc_str}",
            f"nov={nov_str}",
            f"hist={hist_str}",
            f"temp={temp_str}",
            f"cfs={','.join(cfs_repr)}",
            f"thresh={thresh_str}",
            f"exp_conf={self.explanation_confidence:.4f}",
        ]
        payload = "|".join(components)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]

    def compute_provenance_hash(self, governing_thresholds: Optional[tuple] = None) -> str:
        """
        Compute the complete canonical explanation execution fingerprint.
        Combines the scientific decision_provenance_hash with the execution mode
        and, for POST_HOC_EVALUATION, a canonical digest of the retrospective verification payload.
        """
        dec_hash = self.compute_decision_provenance_hash(governing_thresholds)

        post_hoc_str = "NONE"
        if self.mode == ExplanationMode.POST_HOC_EVALUATION and self.post_hoc_verification:
            sorted_entries = [f"{k}={v}" for k, v in sorted(self.post_hoc_verification.items())]
            post_hoc_str = ",".join(sorted_entries)

        exec_payload = f"dec_hash={dec_hash}|mode={self.mode.value}|post_hoc={post_hoc_str}"
        return hashlib.sha256(exec_payload.encode("utf-8")).hexdigest()[:24]

    def __post_init__(self):
        if not self.decision_provenance_hash:
            self.decision_provenance_hash = self.compute_decision_provenance_hash()
        if not self.provenance_hash:
            self.provenance_hash = self.compute_provenance_hash()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to fully JSON-serializable dictionary."""
        d = asdict(self)
        return _xai_json_fallback(d)

    def to_json(self, indent: int = 2) -> str:
        """Convert to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalXAIExplanation":
        """Reconstruct CanonicalXAIExplanation from dictionary."""
        return cls(
            explanation_id=str(data.get("explanation_id", "")),
            schema_version=str(data.get("schema_version", "17.0.0")),
            mode=ExplanationMode(data.get("mode", ExplanationMode.DECISION_TIME.value)),
            location_id=str(data.get("location_id", "")),
            variable=str(data.get("variable", "")),
            valid_time_utc=str(data.get("valid_time_utc", "")),
            issue_time_utc=str(data.get("issue_time_utc", "")),
            risk_score=float(data.get("risk_score", 0.0)),
            calibrated_bust_probability=float(data.get("calibrated_bust_probability", 0.0)),
            risk_confidence=float(data.get("risk_confidence", 0.5)),
            explanation_confidence=float(data.get("explanation_confidence", 0.5)),
            operational_decision=str(data.get("operational_decision", "MONITOR")),
            warning_priority=str(data.get("warning_priority", "P4_INFORMATIONAL")),
            overall_narrative=str(data.get("overall_narrative", "")),
            provenance_hash=str(data.get("provenance_hash", "")),
            recommended_operator_attention=list(data.get("recommended_operator_attention", [])),
            limitations=list(data.get("limitations", [])),
            post_hoc_verification=data.get("post_hoc_verification"),
        )
