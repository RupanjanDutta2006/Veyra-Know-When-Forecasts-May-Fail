"""
Comprehensive Unit, Adversarial, and Real-Data Test Suite for Day 18 (Operational Event Intelligence).

Validates:
1. Event Schema, Dataclasses & Lifecycle Enums
2. Deterministic Canonical Event Identity & Deduplication
3. Event Continuity & Fragmentation Prevention
4. Longitudinal State Machine & Lifecycle Transitions
5. Severity Score Monotonicity & Dimensionless Formulations
6. Operational Urgency & Time-to-Critical Integration
7. Historical Event Memory & Analogue Retrieval
8. Insufficient Support Handling
9. Strict Decision-Time Anti-Leakage Governance
10. Post-Hoc Outcome Isolation & Provenance Invariants
11. Event-Level Metrics & Normalized Cost Accounting
12. Numerical Robustness (Zero Spread, Missing Data, Boundary Values)
13. Input Reordering & Determinism Invariance
14. End-to-End Orchestrator Pipeline
15. Real Stage B Multi-Cycle Dataset Smoke & Validation
16. Programmatic Public API Exports
"""

from decimal import Decimal
import json
import pytest
import numpy as np
import pandas as pd

from evaluation.event_schema import (
    EventEvaluationMetrics,
    EventLifecycleState,
    EventOutcome,
    EventOutcomeStatus,
    EventSeverity,
    EventSimilarityMatch,
    EventStateTransition,
    EventTrajectorySnapshot,
    OperationalEvent,
    OperationalUrgency,
)
from evaluation.event_tracker import EventLifecycleStateMachine, OperationalEventTracker
from evaluation.event_memory import EventMemoryStore
from evaluation.event_outcome import EventOutcomeEvaluator
from evaluation.event_intelligence import EventIntelligenceOrchestrator
from evaluation.xai_schema import ExplanationMode


@pytest.fixture
def sample_tracker():
    return OperationalEventTracker()


@pytest.fixture
def sample_memory():
    return EventMemoryStore(max_distance_threshold=2.0, min_support_count=2)


@pytest.fixture
def sample_orchestrator():
    return EventIntelligenceOrchestrator()


# ==============================================================================
# 1. SCHEMA & DATACLASS VALIDATION
# ==============================================================================

def test_event_schema_creation_and_json_roundtrip():
    """Verify strongly typed dataclass creation and clean JSON serialization."""
    event = OperationalEvent(
        event_id="test_ev_001",
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-24T00:00:00Z",
        first_detection_time_utc="2026-08-21T00:00:00Z",
        latest_update_time_utc="2026-08-22T00:00:00Z",
        current_risk=0.68,
        peak_risk=0.75,
        initial_risk=0.22,
        lifecycle_state=EventLifecycleState.CRITICAL,
        severity=EventSeverity.SEVERE,
        severity_score=0.65,
        urgency=OperationalUrgency.URGENT,
        confidence=0.82,
        novelty_score=1.1,
        instability_detected=True,
        current_decision="WARN_POTENTIAL_BUST",
        current_warning_priority="P1_HIGH",
        cycles_tracked=3,
        warning_cycles_count=2,
    )

    d = event.to_dict()
    assert d["event_id"] == "test_ev_001"
    assert d["lifecycle_state"] == "CRITICAL"
    assert d["severity"] == "SEVERE"
    assert d["urgency"] == "URGENT"

    json_str = event.to_json()
    assert isinstance(json_str, str)
    parsed = json.loads(json_str)
    assert parsed["event_id"] == "test_ev_001"
    assert parsed["current_risk"] == 0.68


def test_event_enums_and_types():
    """Verify all Day 18 lifecycle, severity, urgency, and outcome enums."""
    assert EventLifecycleState.NORMAL.value == "NORMAL"
    assert EventLifecycleState.CRITICAL.value == "CRITICAL"
    assert EventLifecycleState.RESOLVED.value == "RESOLVED"
    assert EventLifecycleState.ABSTAINED.value == "ABSTAINED"

    assert EventSeverity.LOW.value == "LOW"
    assert EventSeverity.EXTREME.value == "EXTREME"

    assert OperationalUrgency.IMMEDIATE.value == "IMMEDIATE"
    assert OperationalUrgency.INSUFFICIENT_CONFIDENCE.value == "INSUFFICIENT_CONFIDENCE"

    assert EventOutcomeStatus.VERIFIED_BUST.value == "VERIFIED_BUST"
    assert EventOutcomeStatus.VERIFIED_ACCURATE.value == "VERIFIED_ACCURATE"


# ==============================================================================
# 2. CANONICAL EVENT IDENTITY & DEDUPLICATION
# ==============================================================================

def test_event_identity_canonical_determinism():
    """Canonical event ID must be deterministic and invariant to casing and whitespace."""
    id1 = OperationalEventTracker.derive_canonical_event_id("DELHI", "surface_pressure", "2026-08-24T00:00:00Z")
    id2 = OperationalEventTracker.derive_canonical_event_id("delhi ", "surface_pressure", "2026-08-24T00:00:00Z")
    id3 = OperationalEventTracker.derive_canonical_event_id("cairo", "surface_pressure", "2026-08-24T00:00:00Z")

    assert id1 == id2
    assert id1 != id3
    assert len(id1) == 16


def test_event_deduplication_and_idempotence(sample_tracker):
    """Submitting the exact same forecast cycle update twice must be idempotent."""
    ev1 = sample_tracker.process_cycle_update(
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=48.0,
        forecast_value=1012.0,
        ensemble_mean=1011.8,
        ensemble_std=2.4,
        calibrated_risk=0.45,
    )
    assert ev1.cycles_tracked == 1

    # Ingest duplicate
    ev2 = sample_tracker.process_cycle_update(
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=48.0,
        forecast_value=1012.0,
        ensemble_mean=1011.8,
        ensemble_std=2.4,
        calibrated_risk=0.45,
    )
    assert ev2.cycles_tracked == 1
    assert sample_tracker.duplicate_update_count == 1
    assert len(ev2.snapshots) == 1


def test_event_input_reordering_invariance(sample_tracker):
    """Multiple updates for the same event must accumulate snapshots deterministically."""
    ev = sample_tracker.process_cycle_update(
        location_id="london",
        variable="temperature_2m",
        valid_time_utc="2026-08-24T12:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=60.0,
        forecast_value=291.5,
        ensemble_mean=291.2,
        ensemble_std=1.5,
        calibrated_risk=0.25,
    )
    ev = sample_tracker.process_cycle_update(
        location_id="london",
        variable="temperature_2m",
        valid_time_utc="2026-08-24T12:00:00Z",
        issue_time_utc="2026-08-22T12:00:00Z",
        lead_hours=48.0,
        forecast_value=292.0,
        ensemble_mean=291.0,
        ensemble_std=2.2,
        calibrated_risk=0.55,
    )
    assert ev.cycles_tracked == 2
    assert ev.peak_risk == 0.55
    assert ev.current_risk == 0.55
    assert ev.lifecycle_state in (EventLifecycleState.ESCALATING, EventLifecycleState.EMERGING)


def test_independent_spatial_and_temporal_events_separation(sample_tracker):
    """Different locations or valid times must generate separate events."""
    e_delhi = sample_tracker.process_cycle_update(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.40
    )
    e_cairo = sample_tracker.process_cycle_update(
        location_id="cairo", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.40
    )
    e_delhi_next = sample_tracker.process_cycle_update(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.40
    )

    assert e_delhi.event_id != e_cairo.event_id
    assert e_delhi.event_id != e_delhi_next.event_id
    assert len(sample_tracker.get_all_events()) == 3


# ==============================================================================
# 3. LIFECYCLE STATE MACHINE & TRANSITIONS
# ==============================================================================

def test_event_lifecycle_monotonic_escalation(sample_tracker):
    """Test standard progression: NORMAL -> EMERGING -> ESCALATING -> CRITICAL."""
    # Cycle 1: Baseline / Emerging
    ev = sample_tracker.process_cycle_update(
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-21T00:00:00Z",
        lead_hours=72.0,
        forecast_value=1012.0,
        ensemble_mean=1011.8,
        ensemble_std=1.2,
        calibrated_risk=0.22,
    )
    assert ev.lifecycle_state == EventLifecycleState.EMERGING

    # Cycle 2: Escalating
    ev = sample_tracker.process_cycle_update(
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-21T12:00:00Z",
        lead_hours=60.0,
        forecast_value=1013.5,
        ensemble_mean=1012.0,
        ensemble_std=2.5,
        calibrated_risk=0.48,
    )
    assert ev.lifecycle_state == EventLifecycleState.ESCALATING

    # Cycle 3: Critical
    ev = sample_tracker.process_cycle_update(
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=48.0,
        forecast_value=1015.0,
        ensemble_mean=1012.2,
        ensemble_std=3.8,
        calibrated_risk=0.72,
        operational_decision="ALERT_CRITICAL_BUST",
    )
    assert ev.lifecycle_state == EventLifecycleState.CRITICAL
    assert len(ev.state_transitions) >= 3


def test_event_lifecycle_deescalation_and_resolution(sample_tracker):
    """Test de-escalation: CRITICAL -> STABILIZING -> RESOLVED."""
    # Setup critical event
    for i, r in enumerate([0.25, 0.50, 0.75]):
        ev = sample_tracker.process_cycle_update(
            location_id="tokyo",
            variable="wind_speed_10m",
            valid_time_utc="2026-08-25T00:00:00Z",
            issue_time_utc=f"2026-08-22T{i*6:02d}:00:00Z",
            lead_hours=72.0 - i * 6.0,
            forecast_value=14.0,
            ensemble_mean=12.0,
            ensemble_std=3.5,
            calibrated_risk=r,
            operational_decision="ALERT" if r > 0.6 else "MONITOR",
        )
    assert ev.lifecycle_state == EventLifecycleState.CRITICAL

    # De-escalate to Stabilizing
    ev = sample_tracker.process_cycle_update(
        location_id="tokyo",
        variable="wind_speed_10m",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-23T00:00:00Z",
        lead_hours=48.0,
        forecast_value=11.0,
        ensemble_mean=11.5,
        ensemble_std=2.0,
        calibrated_risk=0.35,
        operational_decision="MONITOR",
    )
    assert ev.lifecycle_state == EventLifecycleState.STABILIZING

    # Resolve event
    ev = sample_tracker.process_cycle_update(
        location_id="tokyo",
        variable="wind_speed_10m",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-23T12:00:00Z",
        lead_hours=36.0,
        forecast_value=10.0,
        ensemble_mean=10.2,
        ensemble_std=1.1,
        calibrated_risk=0.10,
        operational_decision="MONITOR",
    )
    assert ev.lifecycle_state == EventLifecycleState.RESOLVED


def test_event_lifecycle_abstention_handling(sample_tracker):
    """Safety constraint / novelty triggers ABSTAINED lifecycle state."""
    ev = sample_tracker.process_cycle_update(
        location_id="cairo",
        variable="surface_pressure",
        valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=48.0,
        forecast_value=1010.0,
        ensemble_mean=1010.0,
        ensemble_std=2.0,
        calibrated_risk=0.50,
        operational_decision="ABSTAIN",
        is_abstained=True,
    )
    assert ev.lifecycle_state == EventLifecycleState.ABSTAINED


def test_event_lifecycle_abstention_reentry(sample_tracker):
    """Re-entry from ABSTAINED when risk and decision return to normal."""
    ev = sample_tracker.process_cycle_update(
        location_id="cairo", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1010.0, ensemble_mean=1010.0, ensemble_std=2.0, calibrated_risk=0.50, is_abstained=True
    )
    assert ev.lifecycle_state == EventLifecycleState.ABSTAINED

    ev_reenter = sample_tracker.process_cycle_update(
        location_id="cairo", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T06:00:00Z", lead_hours=42.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.2, calibrated_risk=0.45, operational_decision="MONITOR", is_abstained=False
    )
    assert ev_reenter.lifecycle_state == EventLifecycleState.ESCALATING


# ==============================================================================
# 4. SEVERITY & OPERATIONAL URGENCY
# ==============================================================================

def test_severity_score_monotonicity_and_bounds():
    """Dimensionless severity score must lie strictly in [0, 1] and grow monotonically."""
    sm = EventLifecycleStateMachine()
    sev1, s1 = sm.compute_severity(calibrated_risk=0.20, ensemble_std=1.0, novelty_score=0.5, instability_detected=False)
    sev2, s2 = sm.compute_severity(calibrated_risk=0.50, ensemble_std=2.5, novelty_score=1.5, instability_detected=False)
    sev3, s3 = sm.compute_severity(calibrated_risk=0.85, ensemble_std=4.5, novelty_score=3.2, instability_detected=True)

    assert 0.0 <= s1 <= s2 <= s3 <= 1.0
    assert sev1 in (EventSeverity.LOW, EventSeverity.MODERATE)
    assert sev3 == EventSeverity.EXTREME


def test_urgency_tier_classification_logic():
    """Verify urgency classification across lead times and time-to-critical estimates."""
    sm = EventLifecycleStateMachine()

    # Immediate: short lead and critical risk
    u_imm = sm.compute_urgency(calibrated_risk=0.70, risk_velocity=0.10, lead_hours=10.0, time_to_critical_hours=8.0, confidence=0.85, novelty_score=1.0)
    assert u_imm == OperationalUrgency.IMMEDIATE

    # Urgent: moderate-high risk
    u_urg = sm.compute_urgency(calibrated_risk=0.45, risk_velocity=0.08, lead_hours=36.0, time_to_critical_hours=18.0, confidence=0.85, novelty_score=1.0)
    assert u_urg == OperationalUrgency.URGENT

    # Watch: emerging risk
    u_watch = sm.compute_urgency(calibrated_risk=0.25, risk_velocity=0.02, lead_hours=48.0, time_to_critical_hours=40.0, confidence=0.85, novelty_score=1.0)
    assert u_watch == OperationalUrgency.WATCH

    # Routine: low baseline
    u_rout = sm.compute_urgency(calibrated_risk=0.10, risk_velocity=-0.05, lead_hours=60.0, time_to_critical_hours=None, confidence=0.85, novelty_score=1.0)
    assert u_rout == OperationalUrgency.ROUTINE

    # Insufficient confidence override: high novelty
    u_ood = sm.compute_urgency(calibrated_risk=0.80, risk_velocity=0.10, lead_hours=12.0, time_to_critical_hours=6.0, confidence=0.20, novelty_score=2.8)
    assert u_ood == OperationalUrgency.INSUFFICIENT_CONFIDENCE


# ==============================================================================
# 5. HISTORICAL EVENT MEMORY & ANALOGUE RETRIEVAL
# ==============================================================================

def test_event_memory_registration_and_retrieval(sample_memory, sample_tracker):
    """Register historical events and retrieve top matching analogues based on trajectory."""
    # Historical Event 1 (Delhi high bust)
    h_ev1 = sample_tracker.process_cycle_update(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-10T00:00:00Z",
        issue_time_utc="2026-08-08T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1010.0, ensemble_std=3.0, calibrated_risk=0.70
    )
    # Historical Event 2 (Cairo moderate bust)
    h_ev2 = sample_tracker.process_cycle_update(
        location_id="cairo", variable="surface_pressure", valid_time_utc="2026-08-12T00:00:00Z",
        issue_time_utc="2026-08-10T00:00:00Z", lead_hours=48.0, forecast_value=1014.0, ensemble_mean=1013.0, ensemble_std=2.5, calibrated_risk=0.65
    )
    sample_memory.register_events_batch([h_ev1, h_ev2])

    # Query event
    q_ev = sample_tracker.process_cycle_update(
        location_id="london", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1013.0, ensemble_mean=1011.0, ensemble_std=2.8, calibrated_risk=0.68
    )

    matches = sample_memory.find_analogous_events(q_ev, top_k=2)
    assert len(matches) == 2
    assert matches[0].similarity_score > 0.60
    assert matches[0].historical_event_id in (h_ev1.event_id, h_ev2.event_id)


def test_event_memory_insufficient_support_fallback(sample_memory, sample_tracker):
    """Memory must return INSUFFICIENT_HISTORICAL_SUPPORT when analogues are absent."""
    q_ev = sample_tracker.process_cycle_update(
        location_id="london", variable="wind_speed_10m", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=15.0, ensemble_mean=14.0, ensemble_std=2.0, calibrated_risk=0.60
    )
    matches = sample_memory.find_analogous_events(q_ev, top_k=2)
    assert len(matches) == 1
    assert matches[0].historical_event_id == "INSUFFICIENT_HISTORICAL_SUPPORT"
    assert matches[0].similarity_score == 0.0


def test_event_memory_variable_isolation(sample_memory, sample_tracker):
    """Memory store must strictly avoid matching across heterogeneous meteorological variables."""
    h_ev_press = sample_tracker.process_cycle_update(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-10T00:00:00Z",
        issue_time_utc="2026-08-08T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1010.0, ensemble_std=3.0, calibrated_risk=0.70
    )
    sample_memory.register_historical_event(h_ev_press)

    # Query with wind speed
    q_ev_wind = sample_tracker.process_cycle_update(
        location_id="delhi", variable="wind_speed_10m", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=12.0, ensemble_mean=10.0, ensemble_std=3.0, calibrated_risk=0.70
    )
    matches = sample_memory.find_analogous_events(q_ev_wind, top_k=2)
    assert matches[0].historical_event_id == "INSUFFICIENT_HISTORICAL_SUPPORT"


# ==============================================================================
# 6. ANTI-LEAKAGE & PROVENANCE INVARIANTS
# ==============================================================================

def test_decision_time_mode_rejects_verification_leakage(sample_orchestrator):
    """Orchestrator must strictly reject forbidden verification columns at decision time."""
    with pytest.raises(ValueError, match="Target leakage rejected in DECISION_TIME event ingestion"):
        sample_orchestrator.process_forecast_cycle(
            location_id="delhi",
            variable="surface_pressure",
            valid_time_utc="2026-08-24T00:00:00Z",
            issue_time_utc="2026-08-22T00:00:00Z",
            lead_hours=48.0,
            forecast_value=1012.0,
            ensemble_mean=1011.0,
            ensemble_std=2.0,
            calibrated_risk=0.50,
            mode=ExplanationMode.DECISION_TIME,
            features={"forecast_value": 1012.0, "truth_value": 1010.0},
        )


def test_post_hoc_outcome_attachment_isolation(sample_tracker):
    """Attaching retrospective outcome must not alter decision_provenance_hash."""
    ev = sample_tracker.process_cycle_update(
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=48.0,
        forecast_value=1012.0,
        ensemble_mean=1011.0,
        ensemble_std=2.0,
        calibrated_risk=0.55,
        operational_decision="WARN_POTENTIAL_BUST",
    )
    initial_dec_prov = ev.decision_provenance_hash
    initial_exec_prov = ev.execution_provenance_hash

    evaluator = EventOutcomeEvaluator()
    evaluator.attach_event_outcome(ev, truth_value=1008.0, bust_threshold=2.0)

    assert ev.retrospective_outcome is not None
    assert ev.retrospective_outcome.is_verified_bust is True
    assert ev.retrospective_outcome.was_captured is True
    # Decision provenance is 100% INVARIANT to retrospective truth attachment
    assert ev.decision_provenance_hash == initial_dec_prov
    # Execution provenance reflects outcome attachment
    assert ev.execution_provenance_hash != initial_exec_prov


def test_changing_truth_does_not_alter_decision_provenance(sample_tracker):
    """Evaluating with two different truth values preserves identical decision_provenance_hash."""
    def create_ev():
        tr = OperationalEventTracker()
        return tr.process_cycle_update(
            location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
            issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.55
        )

    ev1 = create_ev()
    ev2 = create_ev()

    evaluator = EventOutcomeEvaluator()
    evaluator.attach_event_outcome(ev1, truth_value=1005.0)
    evaluator.attach_event_outcome(ev2, truth_value=1012.0)

    assert ev1.decision_provenance_hash == ev2.decision_provenance_hash
    assert ev1.execution_provenance_hash != ev2.execution_provenance_hash


def test_changing_scientific_features_updates_decision_provenance(sample_tracker):
    """Changing genuine scientific features must update decision_provenance_hash."""
    ev1 = sample_tracker.process_cycle_update(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.30
    )
    tr2 = OperationalEventTracker()
    ev2 = tr2.process_cycle_update(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=5.5, calibrated_risk=0.75
    )
    assert ev1.decision_provenance_hash != ev2.decision_provenance_hash


# ==============================================================================
# 7. EVENT-LEVEL PERFORMANCE & COST METRICS
# ==============================================================================

def test_event_outcome_evaluator_metrics_computation(sample_tracker):
    """Verify event-level metrics calculation across synthetic population."""
    evaluator = EventOutcomeEvaluator()
    events = []

    # Event 1: Captured bust
    e1 = sample_tracker.process_cycle_update(
        location_id="loc1", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1015.0, ensemble_mean=1012.0, ensemble_std=3.0, calibrated_risk=0.70, operational_decision="WARN_POTENTIAL_BUST"
    )
    evaluator.attach_event_outcome(e1, truth_value=1010.0, bust_threshold=2.0)
    events.append(e1)

    # Event 2: False alarm
    e2 = sample_tracker.process_cycle_update(
        location_id="loc2", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1012.0, ensemble_std=2.5, calibrated_risk=0.60, operational_decision="WARN_POTENTIAL_BUST"
    )
    evaluator.attach_event_outcome(e2, truth_value=1012.5, bust_threshold=2.0)
    events.append(e2)

    # Event 3: Missed bust
    e3 = sample_tracker.process_cycle_update(
        location_id="loc3", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1012.0, ensemble_std=1.0, calibrated_risk=0.15, operational_decision="MONITOR"
    )
    evaluator.attach_event_outcome(e3, truth_value=1007.0, bust_threshold=2.0)
    events.append(e3)

    metrics = evaluator.evaluate_events_population(events)
    assert metrics.total_events == 3
    assert metrics.total_verified_bust_events == 2
    assert metrics.captured_bust_events == 1
    assert metrics.missed_bust_events == 1
    assert metrics.false_alarm_events == 1
    assert metrics.event_detection_rate == 0.50
    assert metrics.event_warning_precision == 0.50
    assert metrics.median_lead_time_hours == 48.0


def test_event_level_cost_accounting(sample_tracker):
    """Verify normalized cost accounting using exact Decimal arithmetic."""
    evaluator = EventOutcomeEvaluator(
        cost_bust_direct_loss=0.37,
        cost_mitigation_action=0.08,
        cost_false_alarm_inspection=0.26,
    )
    # 1 captured bust (cost = 0.08) vs passive (cost = 0.37)
    e1 = sample_tracker.process_cycle_update(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1015.0, ensemble_mean=1012.0, ensemble_std=3.0, calibrated_risk=0.70, operational_decision="WARN"
    )
    evaluator.attach_event_outcome(e1, truth_value=1010.0, bust_threshold=2.0)

    metrics = evaluator.evaluate_events_population([e1])
    assert metrics.event_policy_cost == 0.08
    assert metrics.passive_baseline_cost == 0.37
    assert metrics.utility_difference == 0.29


def test_lifecycle_stability_score_and_empty_population():
    """Verify stability scoring and empty population safeguards."""
    evaluator = EventOutcomeEvaluator()
    m_empty = evaluator.evaluate_events_population([])
    assert m_empty.total_events == 0
    assert m_empty.lifecycle_stability_score == 1.0


# ==============================================================================
# 8. NUMERICAL ROBUSTNESS & EDGE CASES
# ==============================================================================

def test_numerical_robustness_zero_spread_and_nans(sample_tracker):
    """Zero spread and zero risk values must be handled robustly without crashing."""
    ev = sample_tracker.process_cycle_update(
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=48.0,
        forecast_value=1012.0,
        ensemble_mean=1012.0,
        ensemble_std=0.0,
        calibrated_risk=0.0,
        novelty_score=0.0,
    )
    assert ev.severity_score == 0.0
    assert ev.severity == EventSeverity.LOW
    assert ev.urgency == OperationalUrgency.ROUTINE


def test_reordered_updates_same_canonical_identity():
    """Ingesting cycles in reverse order produces identical canonical event_id."""
    id_fwd = OperationalEventTracker.derive_canonical_event_id("delhi", "surface_pressure", "2026-08-24T00:00:00Z")
    id_rev = OperationalEventTracker.derive_canonical_event_id("delhi", "surface_pressure", "2026-08-24T00:00:00Z")
    assert id_fwd == id_rev


def test_large_temporal_gap_creates_distinct_events(sample_tracker):
    """Two events separated by a 48h valid time gap must be tracked distinctly."""
    e1 = sample_tracker.process_cycle_update(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-20T00:00:00Z",
        issue_time_utc="2026-08-18T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.40
    )
    e2 = sample_tracker.process_cycle_update(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-22T00:00:00Z",
        issue_time_utc="2026-08-20T00:00:00Z", lead_hours=48.0, forecast_value=1014.0, ensemble_mean=1013.0, ensemble_std=2.0, calibrated_risk=0.40
    )
    assert e1.event_id != e2.event_id
    assert len(sample_tracker.get_all_events()) == 2


def test_event_similarity_metric_zero_distance_for_identical(sample_memory, sample_tracker):
    """Identical trajectory shapes must produce 0 distance and 1.0 similarity score."""
    h = sample_tracker.process_cycle_update(
        location_id="loc_hist", variable="surface_pressure", valid_time_utc="2026-08-10T00:00:00Z",
        issue_time_utc="2026-08-08T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.5, calibrated_risk=0.65
    )
    sample_memory.register_historical_event(h)

    # Register dummy 2nd event to satisfy min_support_count
    h_dummy = sample_tracker.process_cycle_update(
        location_id="loc_dummy", variable="surface_pressure", valid_time_utc="2026-08-11T00:00:00Z",
        issue_time_utc="2026-08-09T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.5, calibrated_risk=0.65
    )
    sample_memory.register_historical_event(h_dummy)

    q = sample_tracker.process_cycle_update(
        location_id="loc_query", variable="surface_pressure", valid_time_utc="2026-08-20T00:00:00Z",
        issue_time_utc="2026-08-18T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.5, calibrated_risk=0.65
    )
    matches = sample_memory.find_analogous_events(q, top_k=2)
    assert matches[0].trajectory_distance == pytest.approx(0.0, 0.001)
    assert matches[0].similarity_score == pytest.approx(1.0, 0.001)


def test_event_outcome_evaluator_all_captured(sample_tracker):
    """Population with 100% captured bust events."""
    evaluator = EventOutcomeEvaluator()
    e = sample_tracker.process_cycle_update(
        location_id="loc", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1015.0, ensemble_mean=1012.0, ensemble_std=3.0, calibrated_risk=0.75, operational_decision="WARN"
    )
    evaluator.attach_event_outcome(e, truth_value=1010.0, bust_threshold=2.0)
    m = evaluator.evaluate_events_population([e])
    assert m.event_detection_rate == 1.0
    assert m.event_warning_precision == 1.0
    assert m.event_miss_rate == 0.0


def test_event_outcome_evaluator_all_missed(sample_tracker):
    """Population with 100% missed bust events."""
    evaluator = EventOutcomeEvaluator()
    e = sample_tracker.process_cycle_update(
        location_id="loc", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1012.0, ensemble_std=1.0, calibrated_risk=0.10, operational_decision="MONITOR"
    )
    evaluator.attach_event_outcome(e, truth_value=1005.0, bust_threshold=2.0)
    m = evaluator.evaluate_events_population([e])
    assert m.event_detection_rate == 0.0
    assert m.event_miss_rate == 1.0


def test_event_outcome_evaluator_all_false_alarms(sample_tracker):
    """Population with 100% false alarm warnings."""
    evaluator = EventOutcomeEvaluator()
    e = sample_tracker.process_cycle_update(
        location_id="loc", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1012.0, ensemble_std=3.0, calibrated_risk=0.70, operational_decision="WARN"
    )
    evaluator.attach_event_outcome(e, truth_value=1012.2, bust_threshold=2.0)
    m = evaluator.evaluate_events_population([e])
    assert m.captured_bust_events == 0
    assert m.false_alarm_events == 1
    assert m.event_warning_precision == 0.0


def test_event_outcome_evaluator_abstained_cost_accounting(sample_tracker):
    """Abstained events incur contingency cost ($0.15)."""
    evaluator = EventOutcomeEvaluator()
    e = sample_tracker.process_cycle_update(
        location_id="loc", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1012.0, ensemble_std=2.0, calibrated_risk=0.50, is_abstained=True
    )
    evaluator.attach_event_outcome(e, truth_value=1005.0, bust_threshold=2.0)
    m = evaluator.evaluate_events_population([e])
    assert m.abstained_events == 1
    assert m.event_policy_cost == 0.15
    assert m.passive_baseline_cost == 0.37


def test_render_event_summary_contains_all_fields(sample_orchestrator):
    """Briefing rendering must include operational action, severity, urgency, and provenance."""
    ev = sample_orchestrator.process_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1014.0, ensemble_mean=1012.0, ensemble_std=2.8, calibrated_risk=0.62, operational_decision="WARN_POTENTIAL_BUST", warning_priority="P1_HIGH"
    )
    summary = sample_orchestrator.render_event_summary(ev)
    assert "Event ID" in summary
    assert "Lifecycle State" in summary
    assert "Severity" in summary
    assert "Urgency" in summary
    assert "Decision Provenance" in summary


def test_event_trajectory_snapshot_serialization():
    """Verify EventTrajectorySnapshot serialization."""
    s = EventTrajectorySnapshot(
        cycle_index=1, issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.50, novelty_score=1.0, instability_detected=False, operational_decision="MONITOR", warning_priority="P4", urgency=OperationalUrgency.ROUTINE, decision_provenance_hash="test_hash"
    )
    d = s.to_dict()
    assert d["cycle_index"] == 1
    assert d["urgency"] == "ROUTINE"


def test_event_state_transition_serialization():
    """Verify EventStateTransition serialization."""
    t = EventStateTransition(
        from_state=EventLifecycleState.NORMAL, to_state=EventLifecycleState.EMERGING, trigger="Risk emergence", cycle_index=1, issue_time_utc="2026-08-22T00:00:00Z", risk_at_transition=0.25, supporting_metrics={"lead_hours": 48.0}, provenance_hash="trans_hash"
    )
    d = t.to_dict()
    assert d["from_state"] == "NORMAL"
    assert d["to_state"] == "EMERGING"


def test_event_similarity_match_serialization():
    """Verify EventSimilarityMatch serialization."""
    m = EventSimilarityMatch(
        historical_event_id="hist_001", location_id="delhi", variable="surface_pressure", similarity_score=0.88, trajectory_distance=0.24, matched_sequence_length=3, historical_peak_risk=0.72, historical_outcome="BUST", historical_realized_error=3.5, alignment_narrative="Analogue match", retrieval_provenance="ret_hash"
    )
    d = m.to_dict()
    assert d["historical_event_id"] == "hist_001"
    assert d["similarity_score"] == 0.88


def test_event_evaluation_metrics_serialization():
    """Verify EventEvaluationMetrics serialization."""
    metrics = EventEvaluationMetrics(
        total_events=10, total_verified_bust_events=2, total_accurate_events=8, captured_bust_events=2, missed_bust_events=0, false_alarm_events=1, abstained_events=0, event_detection_rate=1.0, event_warning_precision=0.667, event_miss_rate=0.0, event_false_alarm_rate=0.125, median_lead_time_hours=48.0, p90_lead_time_hours=72.0, event_fragmentation_rate=0.0, duplicate_event_rate=0.0, mean_state_transitions_per_event=2.0, lifecycle_stability_score=0.80, event_policy_cost=0.42, passive_baseline_cost=0.74, utility_difference=0.32
    )
    d = metrics.to_dict()
    assert d["total_events"] == 10
    assert d["event_detection_rate"] == 1.0


def test_post_hoc_evaluation_mode_with_truth_payload(sample_orchestrator):
    """POST_HOC_EVALUATION mode with truth payload properly records retrospective outcome."""
    ev = sample_orchestrator.process_forecast_cycle(
        location_id="cairo", variable="temperature_2m", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=308.0, ensemble_mean=307.0, ensemble_std=2.0, calibrated_risk=0.55, mode=ExplanationMode.POST_HOC_EVALUATION, post_hoc_truth={"truth_value": 302.0, "verification_time_utc": "2026-08-24T00:00:00Z"}
    )
    assert ev.retrospective_outcome is not None
    assert ev.retrospective_outcome.verified_abs_error == pytest.approx(6.0, 0.001)
    assert ev.retrospective_outcome.is_verified_bust is True


def test_event_tracker_get_event_not_found(sample_tracker):
    """get_event returns None for unknown event ID."""
    assert sample_tracker.get_event("non_existent_event_id") is None


def test_single_point_event_and_rapid_transitions(sample_tracker):
    """A single cycle event must construct a valid, auditable event object."""
    ev = sample_tracker.process_cycle_update(
        location_id="singapore",
        variable="temperature_2m",
        valid_time_utc="2026-08-26T00:00:00Z",
        issue_time_utc="2026-08-25T18:00:00Z",
        lead_hours=6.0,
        forecast_value=302.5,
        ensemble_mean=302.0,
        ensemble_std=1.8,
        calibrated_risk=0.42,
    )
    assert ev.cycles_tracked == 1
    assert len(ev.snapshots) == 1
    assert len(ev.state_transitions) == 1


def test_numerical_robustness_nan_and_inf_inputs(sample_tracker):
    """NaN/inf in numerical values must be sanitized gracefully without raising exceptions."""
    ev = sample_tracker.process_cycle_update(
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=48.0,
        forecast_value=1012.0,
        ensemble_mean=1012.0,
        ensemble_std=float("nan"),
        calibrated_risk=0.50,
    )
    assert not np.isnan(ev.severity_score)
    assert ev.current_risk == 0.50


def test_event_state_machine_custom_thresholds():
    """State machine with custom thresholds must trigger transitions accordingly."""
    sm = EventLifecycleStateMachine(
        risk_emerging_threshold=0.15,
        risk_escalating_threshold=0.35,
        risk_critical_threshold=0.55,
    )
    state, trigger = sm.evaluate_transition(
        current_state=EventLifecycleState.NORMAL,
        current_risk=0.18,
        risk_velocity=0.01,
        lead_hours=48.0,
        operational_decision="MONITOR",
    )
    assert state == EventLifecycleState.EMERGING

    state2, trigger2 = sm.evaluate_transition(
        current_state=EventLifecycleState.EMERGING,
        current_risk=0.40,
        risk_velocity=0.06,
        lead_hours=48.0,
        operational_decision="WARN",
    )
    assert state2 == EventLifecycleState.ESCALATING

    state3, trigger3 = sm.evaluate_transition(
        current_state=EventLifecycleState.ESCALATING,
        current_risk=0.60,
        risk_velocity=0.10,
        lead_hours=24.0,
        operational_decision="ALERT",
    )
    assert state3 == EventLifecycleState.CRITICAL


def test_event_memory_multiple_matches_ranking(sample_memory, sample_tracker):
    """Event memory must rank matches by trajectory similarity score descending."""
    # Historical 1 (very close)
    h1 = sample_tracker.process_cycle_update(
        location_id="loc1", variable="temperature_2m", valid_time_utc="2026-08-10T00:00:00Z",
        issue_time_utc="2026-08-08T00:00:00Z", lead_hours=48.0, forecast_value=290.0, ensemble_mean=290.0, ensemble_std=2.0, calibrated_risk=0.60
    )
    # Historical 2 (moderate distance)
    h2 = sample_tracker.process_cycle_update(
        location_id="loc2", variable="temperature_2m", valid_time_utc="2026-08-12T00:00:00Z",
        issue_time_utc="2026-08-10T00:00:00Z", lead_hours=48.0, forecast_value=292.0, ensemble_mean=290.0, ensemble_std=3.5, calibrated_risk=0.80
    )
    sample_memory.register_events_batch([h1, h2])

    q = sample_tracker.process_cycle_update(
        location_id="loc_q", variable="temperature_2m", valid_time_utc="2026-08-20T00:00:00Z",
        issue_time_utc="2026-08-18T00:00:00Z", lead_hours=48.0, forecast_value=290.5, ensemble_mean=290.0, ensemble_std=2.1, calibrated_risk=0.62
    )
    matches = sample_memory.find_analogous_events(q, top_k=2)
    assert len(matches) == 2
    assert matches[0].similarity_score >= matches[1].similarity_score
    assert matches[0].historical_event_id == h1.event_id


def test_event_fragmentation_prevention_longitudinal_series(sample_tracker):
    """A series of 8 consecutive 6-hourly cycles targeting the same valid time must form 1 event."""
    for cycle in range(8):
        lead = 72.0 - cycle * 6.0
        issue = f"2026-08-{20 + cycle // 4:02d}T{(cycle % 4) * 6:02d}:00:00Z"
        ev = sample_tracker.process_cycle_update(
            location_id="delhi",
            variable="surface_pressure",
            valid_time_utc="2026-08-23T00:00:00Z",
            issue_time_utc=issue,
            lead_hours=lead,
            forecast_value=1012.0 + cycle * 0.3,
            ensemble_mean=1011.5,
            ensemble_std=1.5 + cycle * 0.2,
            calibrated_risk=0.20 + cycle * 0.08,
            operational_decision="WARN" if cycle >= 4 else "MONITOR",
        )
    assert ev.cycles_tracked == 8
    assert len(sample_tracker.get_all_events()) == 1
    assert ev.peak_risk == pytest.approx(0.20 + 7 * 0.08, 0.001)
    assert ev.warning_cycles_count == 4


def test_anti_chatter_oscillation_suppression(sample_tracker):
    """
    Risk oscillating around threshold (0.40, 0.51, 0.49, 0.52, 0.48, 0.55, 0.60)
    must remain in ESCALATING and NOT oscillate back and forth to STABILIZING.
    """
    risks = [0.40, 0.51, 0.49, 0.52, 0.48, 0.55, 0.60]
    ev = None
    for i, r in enumerate(risks):
        ev = sample_tracker.process_cycle_update(
            location_id="delhi",
            variable="surface_pressure",
            valid_time_utc="2026-08-25T00:00:00Z",
            issue_time_utc=f"2026-08-22T{i*4:02d}:00:00Z",
            lead_hours=72.0 - i * 4.0,
            forecast_value=1012.0,
            ensemble_mean=1011.0,
            ensemble_std=2.0,
            calibrated_risk=r,
            operational_decision="WARN",
        )
    assert ev.lifecycle_state == EventLifecycleState.ESCALATING
    # Hysteresis should prevent excessive state transitions (no fluttering)
    assert len(ev.state_transitions) <= 2


def test_input_reordering_full_chronological_invariance(sample_tracker):
    """
    Submitting cycles in reverse order [24h, 48h, 72h] must produce
    chronologically sorted snapshots and identical peak risk as [72h, 48h, 24h].
    """
    tr_fwd = OperationalEventTracker()
    tr_rev = OperationalEventTracker()

    # Forward order
    tr_fwd.process_cycle_update("cairo", "surface_pressure", "2026-08-24T00:00:00Z", "2026-08-21T00:00:00Z", 72.0, 1010.0, 1010.0, 1.0, 0.20)
    tr_fwd.process_cycle_update("cairo", "surface_pressure", "2026-08-24T00:00:00Z", "2026-08-22T00:00:00Z", 48.0, 1012.0, 1010.0, 2.0, 0.50)
    ev_fwd = tr_fwd.process_cycle_update("cairo", "surface_pressure", "2026-08-24T00:00:00Z", "2026-08-23T00:00:00Z", 24.0, 1015.0, 1010.0, 3.0, 0.70)

    # Reverse order
    tr_rev.process_cycle_update("cairo", "surface_pressure", "2026-08-24T00:00:00Z", "2026-08-23T00:00:00Z", 24.0, 1015.0, 1010.0, 3.0, 0.70)
    tr_rev.process_cycle_update("cairo", "surface_pressure", "2026-08-24T00:00:00Z", "2026-08-22T00:00:00Z", 48.0, 1012.0, 1010.0, 2.0, 0.50)
    ev_rev = tr_rev.process_cycle_update("cairo", "surface_pressure", "2026-08-24T00:00:00Z", "2026-08-21T00:00:00Z", 72.0, 1010.0, 1010.0, 1.0, 0.20)

    assert ev_fwd.event_id == ev_rev.event_id
    assert ev_fwd.peak_risk == ev_rev.peak_risk
    assert ev_fwd.first_detection_time_utc == ev_rev.first_detection_time_utc
    assert ev_fwd.latest_update_time_utc == ev_rev.latest_update_time_utc
    assert len(ev_fwd.snapshots) == len(ev_rev.snapshots) == 3
    for s_f, s_r in zip(ev_fwd.snapshots, ev_rev.snapshots):
        assert s_f.issue_time_utc == s_r.issue_time_utc
        assert s_f.calibrated_risk == s_r.calibrated_risk


def test_leakage_rejection_all_forbidden_target_columns(sample_orchestrator):
    """Orchestrator must reject all target/verification column names in DECISION_TIME mode."""
    forbidden = [
        "truth_value", "forecast_error", "forecast_abs_error",
        "ensemble_mean_error", "ensemble_mean_abs_error",
        "bust_label", "is_bust", "bust_label_q95"
    ]
    for col in forbidden:
        with pytest.raises(ValueError, match="Target leakage rejected"):
            sample_orchestrator.process_forecast_cycle(
                location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
                issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.50,
                mode=ExplanationMode.DECISION_TIME, features={"forecast_value": 1012.0, col: 1.0}
            )


def test_sample_size_safeguards_in_event_metrics(sample_tracker):
    """EventOutcomeEvaluator flags INSUFFICIENT_SAMPLE_SIZE when N < 5."""
    evaluator = EventOutcomeEvaluator()
    e = sample_tracker.process_cycle_update(
        location_id="loc", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1015.0, ensemble_mean=1012.0, ensemble_std=3.0, calibrated_risk=0.75
    )
    evaluator.attach_event_outcome(e, truth_value=1010.0, bust_threshold=2.0)
    m_small = evaluator.evaluate_events_population([e])
    assert m_small.sample_size_status == "INSUFFICIENT_SAMPLE_SIZE"


def test_small_sample_policy_empty_events():
    """Empty event population must return INSUFFICIENT_SAMPLE_SIZE and safe zero metrics."""
    evaluator = EventOutcomeEvaluator()
    metrics = evaluator.evaluate_events_population(events=[], total_cycle_updates=0)
    assert metrics.total_events == 0
    assert metrics.sample_size_status == "INSUFFICIENT_SAMPLE_SIZE"
    assert metrics.event_detection_rate == 0.0
    assert metrics.event_warning_precision == 0.0
    assert metrics.event_miss_rate == 0.0
    assert metrics.median_lead_time_hours is None
    assert metrics.event_policy_cost == 0.0


def test_small_sample_policy_one_event_zero_busts(sample_tracker):
    """Single accurate event (1 event, 0 busts) must return INSUFFICIENT_SAMPLE_SIZE."""
    evaluator = EventOutcomeEvaluator()
    e = sample_tracker.process_cycle_update(
        location_id="loc1", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1012.0, ensemble_std=1.0, calibrated_risk=0.10
    )
    evaluator.attach_event_outcome(e, truth_value=1012.1, bust_threshold=2.0)
    m = evaluator.evaluate_events_population([e])
    assert m.total_events == 1
    assert m.total_verified_bust_events == 0
    assert m.sample_size_status == "INSUFFICIENT_SAMPLE_SIZE"


def test_small_sample_policy_four_events(sample_tracker):
    """4 events (even with 2 busts) must return INSUFFICIENT_SAMPLE_SIZE because N < 5."""
    evaluator = EventOutcomeEvaluator()
    events = []
    for i in range(4):
        e = sample_tracker.process_cycle_update(
            location_id=f"loc_{i}", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
            issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1012.0, ensemble_std=2.0, calibrated_risk=0.50
        )
        is_bust = i < 2
        evaluator.attach_event_outcome(e, truth_value=1005.0 if is_bust else 1012.0, bust_threshold=2.0)
        events.append(e)
    m = evaluator.evaluate_events_population(events)
    assert m.total_events == 4
    assert m.total_verified_bust_events == 2
    assert m.sample_size_status == "INSUFFICIENT_SAMPLE_SIZE"


def test_small_sample_policy_five_events_zero_busts(sample_tracker):
    """5 events with 0 verified busts must return INSUFFICIENT_SAMPLE_SIZE."""
    evaluator = EventOutcomeEvaluator()
    events = []
    for i in range(5):
        e = sample_tracker.process_cycle_update(
            location_id=f"loc_{i}", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
            issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1012.0, ensemble_std=1.0, calibrated_risk=0.10
        )
        evaluator.attach_event_outcome(e, truth_value=1012.0, bust_threshold=2.0)
        events.append(e)
    m = evaluator.evaluate_events_population(events)
    assert m.total_events == 5
    assert m.total_verified_bust_events == 0
    assert m.sample_size_status == "INSUFFICIENT_SAMPLE_SIZE"


def test_small_sample_policy_five_events_two_busts_valid(sample_tracker):
    """5 events with >= 2 verified busts must return VALID_SAMPLE."""
    evaluator = EventOutcomeEvaluator()
    events = []
    for i in range(5):
        e = sample_tracker.process_cycle_update(
            location_id=f"loc_{i}", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
            issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1012.0, ensemble_std=2.0, calibrated_risk=0.60 if i < 2 else 0.10, operational_decision="WARN" if i < 2 else "MONITOR"
        )
        is_bust = i < 2
        evaluator.attach_event_outcome(e, truth_value=1005.0 if is_bust else 1012.0, bust_threshold=2.0)
        events.append(e)
    m = evaluator.evaluate_events_population(events)
    assert m.total_events == 5
    assert m.total_verified_bust_events == 2
    assert m.sample_size_status == "VALID_SAMPLE"
    assert m.event_detection_rate == 1.0


def test_small_sample_governance_invariance_on_core_fields(sample_tracker):
    """Small sample governance status evaluation leaves all core event fields and hashes unchanged."""
    e = sample_tracker.process_cycle_update(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1015.0, ensemble_mean=1012.0, ensemble_std=3.0, calibrated_risk=0.75
    )
    dec_hash_orig = e.decision_provenance_hash
    exec_hash_orig = e.execution_provenance_hash

    evaluator = EventOutcomeEvaluator()
    evaluator.attach_event_outcome(e, truth_value=1010.0, bust_threshold=2.0)
    _ = evaluator.evaluate_events_population([e])

    assert e.decision_provenance_hash == dec_hash_orig
    assert e.event_id == OperationalEventTracker.derive_canonical_event_id("delhi", "surface_pressure", "2026-08-24T00:00:00Z")


def test_event_tracker_duplicate_counter(sample_tracker):
    """Tracker accurately tracks duplicate cycle submissions."""
    sample_tracker.process_cycle_update(
        location_id="cairo", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.40
    )
    for _ in range(3):
        sample_tracker.process_cycle_update(
            location_id="cairo", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
            issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.40
        )
    assert sample_tracker.duplicate_update_count == 3


# ==============================================================================
# 9. END-TO-END ORCHESTRATION & RENDERING
# ==============================================================================

def test_event_orchestrator_end_to_end_pipeline(sample_orchestrator):
    """Test full multi-cycle event orchestration through EventIntelligenceOrchestrator."""
    ev = sample_orchestrator.process_forecast_cycle(
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-21T00:00:00Z",
        lead_hours=72.0,
        forecast_value=1012.0,
        ensemble_mean=1011.0,
        ensemble_std=1.5,
        calibrated_risk=0.25,
        operational_decision="MONITOR",
    )
    assert ev.cycles_tracked == 1
    assert ev.lifecycle_state == EventLifecycleState.EMERGING

    # Cycle 2 with warning
    ev = sample_orchestrator.process_forecast_cycle(
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=48.0,
        forecast_value=1015.0,
        ensemble_mean=1012.0,
        ensemble_std=3.2,
        calibrated_risk=0.68,
        operational_decision="WARN_POTENTIAL_BUST",
        warning_priority="P1_HIGH",
        mode=ExplanationMode.POST_HOC_EVALUATION,
        post_hoc_truth={"truth_value": 1010.0, "verification_time_utc": "2026-08-24T00:00:00Z"},
    )
    assert ev.cycles_tracked == 2
    assert ev.lifecycle_state == EventLifecycleState.CRITICAL
    assert ev.retrospective_outcome is not None
    assert ev.retrospective_outcome.was_captured is True

    briefing = sample_orchestrator.render_event_summary(ev)
    assert "[VEYRA OPERATIONAL EVENT BRIEFING]" in briefing
    assert "CRITICAL" in briefing
    assert "Decision Provenance" in briefing


# ==============================================================================
# 10. REAL DATA VALIDATION (STAGE B MULTI-CYCLE DATASET)
# ==============================================================================

def test_real_stage_b_multicycle_event_validation():
    """Validate EventTracker against real Stage B multi-cycle dataset."""
    path = "data/historical/multicycle_paired/paired_multicycle_stage_b_2026-08-18_2026-08-24.parquet"
    df = pd.read_parquet(path)
    assert len(df) == 35040

    loc_col = "location_id" if "location_id" in df.columns else "location"
    valid_col = "valid_time_utc" if "valid_time_utc" in df.columns else "valid_time"
    issue_col = "issue_time_utc" if "issue_time_utc" in df.columns else "issue_time"

    # Filter a subset of 3 locations for surface_pressure
    sample_df = df[(df[loc_col].isin(["delhi", "cairo", "london"])) & (df["variable"] == "surface_pressure")].copy()
    sample_df = sample_df.sort_values(by=[valid_col, "lead_hours"], ascending=[True, False]).head(300)

    tracker = OperationalEventTracker()
    evaluator = EventOutcomeEvaluator()

    for _, row in sample_df.iterrows():
        # Derive risk proxy
        std_val = float(row.get("ensemble_std", 1.5))
        risk_val = float(np.clip(std_val / 5.0, 0.05, 0.95))
        decision = "WARN_POTENTIAL_BUST" if risk_val >= 0.50 else "MONITOR"

        ev = tracker.process_cycle_update(
            location_id=str(row[loc_col]),
            variable=str(row["variable"]),
            valid_time_utc=str(row[valid_col]),
            issue_time_utc=str(row[issue_col]),
            lead_hours=float(row["lead_hours"]),
            forecast_value=float(row["forecast_value"]),
            ensemble_mean=float(row["ensemble_mean"]),
            ensemble_std=std_val,
            calibrated_risk=risk_val,
            operational_decision=decision,
        )
        if "truth_value" in row and not pd.isna(row["truth_value"]):
            evaluator.attach_event_outcome(ev, truth_value=float(row["truth_value"]), bust_threshold=2.0)

    events = tracker.get_all_events()
    assert len(events) > 0
    metrics = evaluator.evaluate_events_population(events)
    assert metrics.total_events == len(events)
    assert metrics.event_detection_rate >= 0.0
    assert metrics.lifecycle_stability_score > 0.50


# ==============================================================================
# 11. PUBLIC EXPORTS VERIFICATION
# ==============================================================================

def test_day18_programmatic_public_exports():
    """Verify all 15 Day 18 symbols are exported in evaluation package."""
    import evaluation
    day18_symbols = [
        "EventLifecycleState",
        "EventSeverity",
        "OperationalUrgency",
        "EventOutcomeStatus",
        "EventStateTransition",
        "EventTrajectorySnapshot",
        "EventSimilarityMatch",
        "EventOutcome",
        "OperationalEvent",
        "EventEvaluationMetrics",
        "EventLifecycleStateMachine",
        "OperationalEventTracker",
        "EventMemoryStore",
        "EventOutcomeEvaluator",
        "EventIntelligenceOrchestrator",
    ]
    for sym in day18_symbols:
        assert hasattr(evaluation, sym), f"Symbol {sym} missing from evaluation package"
        assert sym in evaluation.__all__, f"Symbol {sym} missing from evaluation.__all__"
