"""
Unified Operational Risk Assessment Schema (Day 19).

Defines strongly typed, versioned, immutable/validated data structures for the
end-to-end operational forecast-bust intelligence pipeline.

Unifies:
- Calibrated risk & uncertainty characterization (Day 14)
- Operational decision policy & safety gates (Day 15)
- Temporal trajectory dynamics & instability signals (Day 16)
- XAI explainability & counterfactual rationales (Day 17)
- Longitudinal event tracking & memory analogues (Day 18)
- Signal arbitration records & graceful degradation states (Day 19)
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional, Union

from evaluation.decision_schema import (
    DataQualityState,
    EvidenceItem,
    OperationalDecision,
    RiskLevel,
    WarningPriority,
)
from evaluation.event_schema import (
    EventLifecycleState,
    EventOutcome,
    EventSeverity,
    EventSimilarityMatch,
    OperationalUrgency,
)
from evaluation.trajectory_schema import TrajectoryState, WarningHorizon
from evaluation.xai_schema import (
    CanonicalXAIExplanation,
    DecisionCounterfactual,
    DecisionRationale,
    ExplanationMode,
    FeatureRiskDriver,
    NoveltyExplanation,
    TemporalDynamicsExplanation,
    UncertaintyExplanation,
    UncertaintySource,
)


class AssessmentStatus(str, Enum):
    """Execution status of the unified operational assessment."""
    SUCCESS = "SUCCESS"
    DEGRADED_PARTIAL_EVIDENCE = "DEGRADED_PARTIAL_EVIDENCE"
    SAFETY_ABSTAINED = "SAFETY_ABSTAINED"
    DATA_QUALITY_REJECTED = "DATA_QUALITY_REJECTED"


class SignalPrecedenceTier(str, Enum):
    """Hierarchy tiers for signal arbitration and conflict resolution."""
    TIER_1_SAFETY_GATE = "TIER_1_SAFETY_GATE"
    TIER_2_NOVELTY_ABSTENTION = "TIER_2_NOVELTY_ABSTENTION"
    TIER_3_DATA_QUALITY_GATE = "TIER_3_DATA_QUALITY_GATE"
    TIER_4_CRITICAL_TEMPORAL_INSTABILITY = "TIER_4_CRITICAL_TEMPORAL_INSTABILITY"
    TIER_5_DECISION_POLICY = "TIER_5_DECISION_POLICY"
    TIER_6_ROUTINE_MONITORING = "TIER_6_ROUTINE_MONITORING"


@dataclass(frozen=True)
class SignalOverrideRecord:
    """Audit record when one operational signal overrides another via arbitration."""
    precedence_tier: SignalPrecedenceTier
    source_module: str
    original_decision: str
    arbitrated_decision: str
    triggering_condition: str
    rationale: str
    override_provenance_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "precedence_tier": self.precedence_tier.value,
            "source_module": self.source_module,
            "original_decision": self.original_decision,
            "arbitrated_decision": self.arbitrated_decision,
            "triggering_condition": self.triggering_condition,
            "rationale": self.rationale,
            "override_provenance_hash": self.override_provenance_hash,
        }


def _clean_for_json(obj: Any) -> Any:
    """Helper to convert enums and dataclasses recursively for JSON serialization."""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean_for_json(x) for x in obj]
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()
    if hasattr(obj, "__dataclass_fields__"):
        return _clean_for_json(asdict(obj))
    return obj


@dataclass
class UnifiedOperationalAssessment:
    """
    Master operational assessment object unifying all Veyra intelligence layers.
    """
    assessment_id: str
    schema_version: str = "19.0.0"
    issue_time_utc: str = ""
    valid_time_utc: str = ""
    location_id: str = ""
    variable: str = ""
    lead_hours: float = 0.0

    # Core NWP & Risk Characterization
    forecast_value: float = 0.0
    ensemble_mean: float = 0.0
    ensemble_std: float = 0.0
    calibrated_risk: float = 0.0
    raw_risk: float = 0.0
    confidence_score: float = 0.80

    # Decision & Classification
    risk_level: RiskLevel = RiskLevel.LOW
    operational_decision: OperationalDecision = OperationalDecision.MONITOR
    warning_priority: WarningPriority = WarningPriority.P4_INFORMATIONAL
    urgency: OperationalUrgency = OperationalUrgency.ROUTINE
    severity: EventSeverity = EventSeverity.LOW
    severity_score: float = 0.0

    # Evidence Subsystems
    uncertainty: UncertaintyExplanation = field(default_factory=lambda: UncertaintyExplanation(
        dominant_source=UncertaintySource.ENSEMBLE_DISPERSION,
        secondary_sources=[],
        ensemble_spread_magnitude=0.0,
        epistemic_novelty_magnitude=0.0,
        temporal_instability_magnitude=0.0,
        confidence_impact_score=0.0,
        narrative="Baseline uncertainty"
    ))
    novelty: NoveltyExplanation = field(default_factory=lambda: NoveltyExplanation(
        is_in_domain=True,
        novelty_score=1.0,
        novelty_level="NORMAL",
        confidence_impact=0.0,
        contributed_to_abstention=False,
        narrative="In-distribution"
    ))
    data_quality: DataQualityState = DataQualityState.CLEAN

    # Temporal & Trajectory Layer
    trajectory_state: TrajectoryState = TrajectoryState.STABLE_LOW
    early_warning_score: float = 0.0
    time_to_critical_hours: Optional[float] = None
    instability_detected: bool = False
    instability_narrative: str = "No rapid NWP instability detected"

    # Longitudinal Event Intelligence Layer
    event_id: str = ""
    event_lifecycle_state: EventLifecycleState = EventLifecycleState.NORMAL
    cycles_tracked: int = 1
    warning_cycles_count: int = 0
    historical_analogue: Optional[EventSimilarityMatch] = None

    # XAI & Rationale Layer
    explanation: Optional[CanonicalXAIExplanation] = None

    # Pipeline Governance & Arbitration
    assessment_status: AssessmentStatus = AssessmentStatus.SUCCESS
    signal_overrides: List[SignalOverrideRecord] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Cryptographic Audit Hashes
    decision_provenance_hash: str = ""
    execution_provenance_hash: str = ""

    # Retrospective Outcome (Isolated to Post-Hoc Mode)
    retrospective_outcome: Optional[EventOutcome] = None

    def compute_decision_provenance(self) -> str:
        """
        Generate deterministic 16-character SHA-256 decision provenance fingerprint.
        Strictly excludes post-hoc retrospective verification outcomes.
        """
        core_tokens = [
            f"schema:{self.schema_version}",
            f"assessment:{self.assessment_id}",
            f"loc:{self.location_id.lower().strip()}",
            f"var:{self.variable.lower().strip()}",
            f"issue:{self.issue_time_utc.strip()}",
            f"valid:{self.valid_time_utc.strip()}",
            f"lead:{self.lead_hours:.1f}",
            f"risk:{self.calibrated_risk:.4f}",
            f"dec:{self.operational_decision.value}",
            f"urg:{self.urgency.value}",
            f"sev:{self.severity.value}",
            f"sev_score:{self.severity_score:.4f}",
            f"conf:{self.confidence_score:.4f}",
            f"nov:{self.novelty.novelty_score:.3f}",
            f"temp_state:{self.trajectory_state.value}",
            f"ews:{self.early_warning_score:.4f}",
            f"instab:{self.instability_detected}",
            f"event_id:{self.event_id}",
            f"lifecycle:{self.event_lifecycle_state.value}",
            f"status:{self.assessment_status.value}",
        ]
        raw_str = "|".join(core_tokens)
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()[:16]

    def compute_execution_provenance(self) -> str:
        """
        Generate deterministic 16-character SHA-256 execution provenance hash.
        Combines decision provenance with arbitration overrides and post-hoc outcome.
        """
        dec_hash = self.decision_provenance_hash or self.compute_decision_provenance()
        override_hashes = [o.override_provenance_hash for o in self.signal_overrides]
        outcome_hash = self.retrospective_outcome.outcome_provenance_hash if self.retrospective_outcome else "NONE"
        raw_str = f"{dec_hash}|overrides:{','.join(override_hashes)}|outcome:{outcome_hash}"
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize assessment to clean JSON-compatible dictionary."""
        return _clean_for_json(asdict(self))

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Serialize assessment to deterministic JSON string."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)
