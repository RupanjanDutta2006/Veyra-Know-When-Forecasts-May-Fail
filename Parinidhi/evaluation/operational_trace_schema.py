"""
Operational Risk Observability, Traceability & Audit Schema (Day 20).

Defines the formal, immutable operational trace data structures, change records,
decision reconstructions, and audit validation payloads for Veyra.

Scientific Safeguards:
- 100% Immutable Decision Traces: Frozen dataclasses and defensive copies prevent in-flight mutation.
- Strict Post-Hoc Separation: Retrospective verification records are structurally separated
  from decision-time traces, leaving `trace_hash` and `decision_provenance_hash` 100% invariant.
- Deterministic Cryptographic Hashing: Stable canonical key ordering, dimensionless normalized values,
  and zero runtime timestamp injection.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from evaluation.decision_schema import DataQualityState, OperationalDecision, RiskLevel, WarningPriority
from evaluation.event_schema import EventLifecycleState, EventOutcomeStatus, EventSeverity, OperationalUrgency
from evaluation.trajectory_schema import TrajectoryState
from evaluation.unified_schema import AssessmentStatus, SignalOverrideRecord, SignalPrecedenceTier


class CompletenessStatus(str, Enum):
    """Dimensional completeness rating for an operational assessment."""
    COMPLETE = "COMPLETE"          # All 8 core subsystems present
    PARTIAL = "PARTIAL"            # >= 5 subsystems present
    MINIMAL = "MINIMAL"            # >= 2 subsystems present
    INVALID = "INVALID"            # Critical decision coordinates missing


class DecisionStabilityState(str, Enum):
    """Multi-cycle operational decision stability classification."""
    STABLE = "STABLE"                      # Decision maintained across cycles with low risk volatility
    ESCALATING = "ESCALATING"              # Systematic upward risk/urgency revision
    DE_ESCALATING = "DE_ESCALATING"        # Systematic downward risk/urgency revision
    OSCILLATING = "OSCILLATING"            # Direction-reversing chatter across cycles
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"  # < 2 consecutive cycles available


class AuditValidationState(str, Enum):
    """Overall compliance rating from automated audit validator."""
    PASSED = "PASSED"
    WARNINGS_DETECTED = "WARNINGS_DETECTED"
    CRITICAL_FAILURE = "CRITICAL_FAILURE"
    ABSTAINED = "ABSTAINED"


def _clean_for_json(obj: Any) -> Any:
    """Helper to convert enums, tuples, and dataclasses recursively for JSON serialization."""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _clean_for_json(v) for k, v in sorted(obj.items(), key=lambda x: str(x[0]))}
    if isinstance(obj, (list, tuple)):
        return [_clean_for_json(x) for x in obj]
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()
    if hasattr(obj, "__dataclass_fields__"):
        return _clean_for_json(asdict(obj))
    return obj


@dataclass(frozen=True)
class TraceIdentity:
    """Immutable identity and spatio-temporal coordinates for an operational decision trace."""
    trace_id: str
    event_id: str
    location_id: str
    variable: str
    valid_time_utc: str
    issue_time_utc: str
    lead_hours: float

    def to_dict(self) -> Dict[str, Any]:
        return _clean_for_json(asdict(self))


@dataclass(frozen=True)
class DecisionSnapshot:
    """Immutable snapshot of the primary operational risk decisions and metrics."""
    operational_decision: OperationalDecision
    assessment_status: AssessmentStatus
    warning_priority: WarningPriority
    urgency: OperationalUrgency
    severity: EventSeverity
    severity_score: float
    confidence_score: float
    calibrated_risk: float
    raw_risk: float
    early_warning_score: float
    trajectory_state: TrajectoryState

    def to_dict(self) -> Dict[str, Any]:
        return _clean_for_json(asdict(self))


@dataclass(frozen=True)
class SubsystemSignalsSummary:
    """Summary of all contributing scientific subsystem signals at decision time."""
    uncertainty_dominant_source: str
    novelty_score: float
    novelty_is_in_domain: bool
    data_quality_state: DataQualityState
    trajectory_state: TrajectoryState
    instability_detected: bool
    event_lifecycle_state: EventLifecycleState
    event_cycles_tracked: int
    historical_analogue_id: str
    historical_analogue_similarity: float
    xai_primary_triggers: Tuple[str, ...] = ()
    xai_counterfactual_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return _clean_for_json(asdict(self))


@dataclass(frozen=True)
class ArbitrationSummary:
    """Audit summary of the signal arbitration process and applied tier overrides."""
    winning_tier: SignalPrecedenceTier
    contributing_tiers: Tuple[SignalPrecedenceTier, ...] = ()
    override_applied: bool = False
    override_records: Tuple[SignalOverrideRecord, ...] = ()
    arbitration_rationale: str = "Standard tier resolution"

    def to_dict(self) -> Dict[str, Any]:
        return _clean_for_json(asdict(self))


@dataclass(frozen=True)
class CycleChangeSummary:
    """Cycle-to-cycle delta tracking between consecutive forecast updates for the same event."""
    previous_decision: Optional[OperationalDecision]
    current_decision: OperationalDecision
    decision_changed: bool
    risk_delta: float
    confidence_delta: float
    severity_changed: bool
    urgency_changed: bool
    trajectory_state_changed: bool
    escalation_detected: bool
    deescalation_detected: bool
    stability_state: DecisionStabilityState
    transition_narrative: str

    def to_dict(self) -> Dict[str, Any]:
        return _clean_for_json(asdict(self))


@dataclass(frozen=True)
class AuditValidationResult:
    """Detailed automated compliance and governance audit evaluation for a trace."""
    is_valid: bool
    completeness_score: float
    completeness_status: CompletenessStatus
    leakage_audit_status: str
    provenance_audit_status: str
    numerical_validity_status: str
    temporal_consistency_status: str
    audit_state: AuditValidationState
    warnings: Tuple[str, ...] = ()
    limitations: Tuple[str, ...] = ()
    missing_components: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return _clean_for_json(asdict(self))


@dataclass(frozen=True)
class DecisionReconstruction:
    """Reconstructible structured explanation of the complete decision reasoning chain."""
    what_decision: str
    why_triggers: Tuple[str, ...]
    when_coordinates: str
    how_urgent: str
    how_confident: str
    what_changed: str
    supporting_evidence: Tuple[str, ...]
    audit_status: str
    deterministic_narrative: str

    def to_dict(self) -> Dict[str, Any]:
        return _clean_for_json(asdict(self))


@dataclass(frozen=True)
class PostHocOutcomeRecord:
    """
    Retrospective post-hoc verification outcome record.
    Structurally isolated from the decision-time operational trace.
    """
    trace_id: str
    event_id: str
    valid_time_utc: str
    verification_time_utc: str
    verified_truth_value: float
    verified_abs_error: float
    is_verified_bust: bool
    outcome_status: EventOutcomeStatus
    outcome_provenance_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return _clean_for_json(asdict(self))


@dataclass(frozen=True)
class OperationalTrace:
    """
    Master immutable operational risk decision trace object (Day 20).
    Provides a complete, auditable, deterministic record of an operational forecast assessment.
    """
    identity: TraceIdentity
    decision: DecisionSnapshot
    signals: SubsystemSignalsSummary
    arbitration: ArbitrationSummary
    change: Optional[CycleChangeSummary]
    audit: AuditValidationResult
    reconstruction: DecisionReconstruction
    decision_provenance_hash: str
    execution_provenance_hash: str
    trace_hash: str
    schema_version: str = "20.0.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to deterministic JSON-compatible dictionary."""
        return _clean_for_json(asdict(self))

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Serialize trace to clean deterministic JSON string."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @staticmethod
    def derive_canonical_trace_hash(
        identity: TraceIdentity,
        decision: DecisionSnapshot,
        signals: SubsystemSignalsSummary,
        arbitration: ArbitrationSummary,
        decision_provenance_hash: str,
        schema_version: str = "20.0.0",
    ) -> str:
        """
        Generate deterministic 16-character SHA-256 canonical trace hash.
        Strictly covers decision-time inputs, decision snapshot, and provenance.
        Excludes retrospective verification outcomes.
        """
        tokens = [
            f"schema:{schema_version}",
            f"trace_id:{identity.trace_id}",
            f"event_id:{identity.event_id}",
            f"loc:{identity.location_id.lower().strip()}",
            f"var:{identity.variable.lower().strip()}",
            f"issue:{identity.issue_time_utc.strip()}",
            f"valid:{identity.valid_time_utc.strip()}",
            f"lead:{identity.lead_hours:.1f}",
            f"dec:{decision.operational_decision.value}",
            f"prio:{decision.warning_priority.value}",
            f"urg:{decision.urgency.value}",
            f"sev:{decision.severity.value}",
            f"risk:{decision.calibrated_risk:.4f}",
            f"conf:{decision.confidence_score:.4f}",
            f"ews:{decision.early_warning_score:.4f}",
            f"traj:{decision.trajectory_state.value}",
            f"winning_tier:{arbitration.winning_tier.value}",
            f"override:{arbitration.override_applied}",
            f"dec_hash:{decision_provenance_hash}",
        ]
        raw_str = "|".join(tokens)
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()[:16]
