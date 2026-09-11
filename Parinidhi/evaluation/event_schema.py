"""
Operational Event Schema, Dataclasses & Lifecycle Enums (Day 18).

Defines strongly typed, JSON-serializable structures representing an operational
forecast-risk event lifecycle, tracking longitudinal hazard evolution across successive
NWP issue cycles.

Scientific Safeguards:
- Strict separation of decision-time event state and post-hoc retrospective verification.
- Deterministic canonical event identity derivation (no random UUIDs).
- Comprehensive dual-provenance support (decision provenance vs execution provenance).
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np


def _json_serializable(obj: Any) -> Any:
    """Recursively convert dataclass/numpy objects to standard JSON serializable types."""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, float)):
        return float(obj) if not np.isnan(obj) and not np.isinf(obj) else 0.0
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, dict):
        return {k: _json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_serializable(v) for v in obj]
    return obj


class EventLifecycleState(str, Enum):
    """Longitudinal lifecycle phases of an operational forecast-risk event."""
    NORMAL = "NORMAL"
    EMERGING = "EMERGING"
    ESCALATING = "ESCALATING"
    CRITICAL = "CRITICAL"
    STABILIZING = "STABILIZING"
    RESOLVED = "RESOLVED"
    ABSTAINED = "ABSTAINED"


class EventSeverity(str, Enum):
    """Dimensionless composite hazard severity classification."""
    LOW = "LOW"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    EXTREME = "EXTREME"


class OperationalUrgency(str, Enum):
    """Time-to-action operational urgency tier."""
    ROUTINE = "ROUTINE"
    WATCH = "WATCH"
    URGENT = "URGENT"
    IMMEDIATE = "IMMEDIATE"
    INSUFFICIENT_CONFIDENCE = "INSUFFICIENT_CONFIDENCE"


class EventOutcomeStatus(str, Enum):
    """Post-hoc retrospective verification outcome categorization."""
    VERIFIED_BUST = "VERIFIED_BUST"
    VERIFIED_ACCURATE = "VERIFIED_ACCURATE"
    UNVERIFIED_PENDING = "UNVERIFIED_PENDING"
    ABSTAINED = "ABSTAINED"


@dataclass(frozen=True)
class EventStateTransition:
    """Immutable record of an event lifecycle state transition."""
    from_state: EventLifecycleState
    to_state: EventLifecycleState
    trigger: str
    cycle_index: int
    issue_time_utc: str
    risk_at_transition: float
    supporting_metrics: Dict[str, float]
    provenance_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return _json_serializable(asdict(self))


@dataclass
class EventTrajectorySnapshot:
    """Observation snapshot from a single NWP forecast issue cycle inside an event."""
    cycle_index: int
    issue_time_utc: str
    lead_hours: float
    forecast_value: float
    ensemble_mean: float
    ensemble_std: float
    calibrated_risk: float
    novelty_score: float
    instability_detected: bool
    operational_decision: str
    warning_priority: str
    urgency: OperationalUrgency
    decision_provenance_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return _json_serializable(asdict(self))


@dataclass
class EventSimilarityMatch:
    """Historical analogue event match retrieved from event memory."""
    historical_event_id: str
    location_id: str
    variable: str
    similarity_score: float  # In [0, 1], 1.0 is exact match
    trajectory_distance: float
    matched_sequence_length: int
    historical_peak_risk: float
    historical_outcome: str  # BUST, ACCURATE, UNKNOWN (post-hoc context only)
    historical_realized_error: Optional[float]
    alignment_narrative: str
    retrieval_provenance: str

    def to_dict(self) -> Dict[str, Any]:
        return _json_serializable(asdict(self))


@dataclass
class EventOutcome:
    """
    Retrospective post-hoc verification outcome for an event.
    Structurally isolated from decision-time event state.
    """
    event_id: str
    valid_time_utc: str
    verified_truth_value: float
    verified_forecast_error: float
    verified_abs_error: float
    is_verified_bust: bool
    outcome_status: EventOutcomeStatus
    lead_time_at_first_warning_hours: Optional[float]
    total_warnings_issued: int
    was_captured: bool
    was_false_alarm: bool
    was_missed: bool
    was_abstained: bool
    verification_time_utc: str
    outcome_provenance_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return _json_serializable(asdict(self))


@dataclass
class OperationalEvent:
    """
    Master longitudinal operational forecast-risk event object.
    Tracks a developing atmospheric forecast hazard across consecutive NWP issue cycles.
    """
    event_id: str
    location_id: str
    variable: str
    valid_time_utc: str
    first_detection_time_utc: str
    latest_update_time_utc: str
    current_risk: float
    peak_risk: float
    initial_risk: float
    lifecycle_state: EventLifecycleState
    severity: EventSeverity
    severity_score: float  # Dimensionless [0, 1]
    urgency: OperationalUrgency
    confidence: float
    novelty_score: float
    instability_detected: bool
    current_decision: str
    current_warning_priority: str
    cycles_tracked: int
    warning_cycles_count: int
    snapshots: List[EventTrajectorySnapshot] = field(default_factory=list)
    state_transitions: List[EventStateTransition] = field(default_factory=list)
    analogue_matches: List[EventSimilarityMatch] = field(default_factory=list)
    decision_provenance_hash: str = ""
    execution_provenance_hash: str = ""
    retrospective_outcome: Optional[EventOutcome] = None

    def compute_decision_provenance(self) -> str:
        """
        Compute deterministic SHA-256 fingerprint for scientific decision-time event state.
        Invariant to retrospective verification, issue order, and volatile timestamps.
        """
        snapshot_reprs = [
            f"{s.cycle_index}:{s.lead_hours:.1f}:{s.calibrated_risk:.4f}:{s.ensemble_std:.3f}:{s.operational_decision}"
            for s in sorted(self.snapshots, key=lambda x: x.cycle_index)
        ]
        components = [
            f"event_id={self.event_id}",
            f"loc={self.location_id}",
            f"var={self.variable}",
            f"valid_time={self.valid_time_utc}",
            f"current_risk={self.current_risk:.4f}",
            f"peak_risk={self.peak_risk:.4f}",
            f"state={self.lifecycle_state.value}",
            f"severity={self.severity.value}:{self.severity_score:.4f}",
            f"urgency={self.urgency.value}",
            f"confidence={self.confidence:.4f}",
            f"snapshots={','.join(snapshot_reprs)}",
        ]
        payload = "|".join(components)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]

    def compute_execution_provenance(self) -> str:
        """
        Compute full execution provenance combining decision state, transition history, and post-hoc outcome.
        """
        dec_prov = self.compute_decision_provenance()
        trans_reprs = [
            f"{t.from_state.value}->{t.to_state.value}@{t.issue_time_utc}:{t.trigger}"
            for t in self.state_transitions
        ]
        outcome_str = f"outcome={self.retrospective_outcome.outcome_status.value}" if self.retrospective_outcome else "outcome=NONE"
        exec_payload = f"dec_prov={dec_prov}|transitions={','.join(trans_reprs)}|{outcome_str}"
        return hashlib.sha256(exec_payload.encode("utf-8")).hexdigest()[:24]

    def __post_init__(self):
        if not self.decision_provenance_hash:
            self.decision_provenance_hash = self.compute_decision_provenance()
        if not self.execution_provenance_hash:
            self.execution_provenance_hash = self.compute_execution_provenance()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return _json_serializable(d)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class EventEvaluationMetrics:
    """Comprehensive event-level performance, stability, and cost metrics."""
    total_events: int
    total_verified_bust_events: int
    total_accurate_events: int
    captured_bust_events: int
    missed_bust_events: int
    false_alarm_events: int
    abstained_events: int
    event_detection_rate: float  # captured / total_bust_events
    event_warning_precision: float  # captured / (captured + false_alarms)
    event_miss_rate: float  # missed / total_bust_events
    event_false_alarm_rate: float  # false_alarms / total_accurate_events
    median_lead_time_hours: Optional[float]
    p90_lead_time_hours: Optional[float]
    event_fragmentation_rate: float  # fragmented events / total events
    duplicate_event_rate: float  # duplicate inputs / total updates
    mean_state_transitions_per_event: float
    lifecycle_stability_score: float  # In [0, 1]
    event_policy_cost: float
    passive_baseline_cost: float
    utility_difference: float
    sample_size_status: str = "INSUFFICIENT_SAMPLE_SIZE"

    def to_dict(self) -> Dict[str, Any]:
        return _json_serializable(asdict(self))
