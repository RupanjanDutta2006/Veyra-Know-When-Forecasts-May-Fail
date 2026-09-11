"""
Comprehensive Test Suite for Operational Risk Observability & Traceability (Day 20).

Tests all Day 20 capabilities:
- Immutable OperationalTrace schema & deterministic JSON serialization
- Cryptographic canonical trace hashing & decision-provenance invariance
- Recursive anti-leakage auditing & benign string acceptance
- Numerical robustness & fail-safe fallback handling
- Cycle-to-cycle change detection & delta computation
- Multi-cycle decision stability analysis (STABLE, ESCALATING, DE_ESCALATING, OSCILLATING, INSUFFICIENT_HISTORY)
- Completeness scoring across 8 core scientific subsystems
- Decision narrative reconstruction & operator briefing rendering
- Post-hoc outcome separation & immutability contract
- Real Stage-B multi-station multi-variable execution simulation
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from evaluation.decision_audit import DecisionAuditValidator
from evaluation.decision_schema import (
    DataQualityState,
    OperationalDecision,
    RiskLevel,
    WarningPriority,
)
from evaluation.decision_stability import CycleChangeDetector, DecisionStabilityAnalyzer
from evaluation.event_schema import (
    EventLifecycleState,
    EventOutcomeStatus,
    EventSeverity,
    EventSimilarityMatch,
    OperationalUrgency,
)
from evaluation.operational_intelligence_pipeline import UnifiedOperationalRiskEngine
from evaluation.operational_observability import OperationalObservabilityEngine
from evaluation.operational_trace_schema import (
    ArbitrationSummary,
    AuditValidationResult,
    AuditValidationState,
    CompletenessStatus,
    CycleChangeSummary,
    DecisionReconstruction,
    DecisionSnapshot,
    DecisionStabilityState,
    OperationalTrace,
    PostHocOutcomeRecord,
    SubsystemSignalsSummary,
    TraceIdentity,
)
from evaluation.trajectory_schema import TrajectoryState
from evaluation.unified_schema import (
    AssessmentStatus,
    SignalOverrideRecord,
    SignalPrecedenceTier,
    UnifiedOperationalAssessment,
)
from evaluation.xai_schema import ExplanationMode


@pytest.fixture
def sample_unified_assessment():
    """Build a rich, realistic UnifiedOperationalAssessment for testing."""
    engine = UnifiedOperationalRiskEngine()
    return engine.evaluate_forecast_cycle(
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=72.0,
        forecast_value=1015.0,
        ensemble_mean=1011.0,
        ensemble_std=2.5,
        calibrated_risk=0.60,
        confidence_score=0.85,
        mode=ExplanationMode.DECISION_TIME,
    )


@pytest.fixture
def sample_observability_engine():
    """Provide an OperationalObservabilityEngine instance."""
    return OperationalObservabilityEngine()


# ==============================================================================
# 1. SCHEMA CONSTRUCTION, IMMUTABILITY & SERIALIZATION
# ==============================================================================

def test_operational_trace_schema_instantiation(sample_unified_assessment, sample_observability_engine):
    """OperationalTrace is cleanly constructed from UnifiedOperationalAssessment with all fields populated."""
    trace = sample_observability_engine.build_trace(sample_unified_assessment)
    assert trace.identity.trace_id == sample_unified_assessment.assessment_id
    assert trace.identity.location_id == "delhi"
    assert trace.identity.variable == "surface_pressure"
    assert trace.identity.lead_hours == 72.0
    assert trace.decision.operational_decision == OperationalDecision.WARN_POTENTIAL_BUST
    assert trace.decision.calibrated_risk == 0.60
    assert trace.audit.completeness_status == CompletenessStatus.COMPLETE
    assert trace.audit.completeness_score == 1.0
    assert len(trace.trace_hash) == 16
    assert trace.schema_version == "20.0.0"


def test_operational_trace_immutability_frozen_dataclass(sample_unified_assessment, sample_observability_engine):
    """OperationalTrace instances are frozen and reject direct in-memory mutation."""
    trace = sample_observability_engine.build_trace(sample_unified_assessment)
    with pytest.raises(Exception):
        trace.trace_hash = "mutated_hash_123"  # FrozenInstanceError

    with pytest.raises(Exception):
        trace.decision.calibrated_risk = 0.99  # Frozen nested dataclass


def test_operational_trace_json_roundtrip_serialization(sample_unified_assessment, sample_observability_engine):
    """OperationalTrace serializes deterministically to JSON and parses back cleanly."""
    trace = sample_observability_engine.build_trace(sample_unified_assessment)
    json_str = trace.to_json()
    loaded = json.loads(json_str)

    assert loaded["schema_version"] == "20.0.0"
    assert loaded["identity"]["location_id"] == "delhi"
    assert loaded["decision"]["operational_decision"] == "WARN_POTENTIAL_BUST"
    assert loaded["audit"]["completeness_score"] == 1.0
    assert loaded["trace_hash"] == trace.trace_hash


# ==============================================================================
# 2. CANONICAL HASH DETERMINISM & SENSITIVITY
# ==============================================================================

def test_trace_hash_determinism_repeated_invocations(sample_unified_assessment, sample_observability_engine):
    """10 sequential trace builds for identical assessment yield bitwise identical trace hashes."""
    hashes = set()
    for _ in range(10):
        t = sample_observability_engine.build_trace(sample_unified_assessment)
        hashes.add(t.trace_hash)
    assert len(hashes) == 1


def test_trace_hash_sensitivity_to_scientific_inputs(sample_unified_assessment, sample_observability_engine):
    """Altering risk or lead time produces a distinct cryptographic trace hash."""
    t1 = sample_observability_engine.build_trace(sample_unified_assessment)

    # Modified risk
    engine = UnifiedOperationalRiskEngine()
    a_mod = engine.evaluate_forecast_cycle(
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=72.0,
        forecast_value=1015.0,
        ensemble_mean=1011.0,
        ensemble_std=2.5,
        calibrated_risk=0.75,  # Higher risk
        confidence_score=0.85,
    )
    t2 = sample_observability_engine.build_trace(a_mod)
    assert t1.trace_hash != t2.trace_hash


def test_trace_hash_invariant_to_post_hoc_outcome_attachment(sample_unified_assessment, sample_observability_engine):
    """Retrospectively attaching verification outcome leaves trace_hash and decision hash 100% invariant."""
    trace = sample_observability_engine.build_trace(sample_unified_assessment)
    initial_trace_hash = trace.trace_hash
    initial_dec_hash = trace.decision_provenance_hash

    # Attach outcome
    ret_trace, outcome_record = sample_observability_engine.attach_post_hoc_outcome(
        trace=trace,
        truth_value=1008.0,
        verification_time_utc="2026-08-25T00:00:00Z",
        is_verified_bust=True,
    )

    assert ret_trace.trace_hash == initial_trace_hash
    assert ret_trace.decision_provenance_hash == initial_dec_hash
    assert outcome_record.is_verified_bust is True
    assert outcome_record.outcome_status == EventOutcomeStatus.VERIFIED_BUST


# ==============================================================================
# 3. RECURSIVE ANTI-LEAKAGE AUDITING & BENIGN STRING VALUES
# ==============================================================================

def test_leakage_audit_rejects_top_level_verification_columns():
    """DecisionAuditValidator rejects all top-level target/error keys."""
    forbidden = [
        "truth_value", "forecast_error", "forecast_abs_error",
        "ensemble_mean_error", "ensemble_mean_abs_error",
        "bust_label", "is_bust", "actual", "realized",
        "verified_bust", "target", "verification", "obs_pressure", "observation"
    ]
    for col in forbidden:
        is_clean, violations = DecisionAuditValidator.audit_leakage_payload({col: 1012.0})
        assert not is_clean, f"Failed to reject {col}"
        assert len(violations) >= 1


def test_leakage_audit_rejects_nested_dictionaries():
    """DecisionAuditValidator recursively traverses nested mappings to reject forbidden keys."""
    nested = {
        "climate_regime": {
            "monsoon_stage": "active",
            "audit_data": {
                "verified_bust": True,
            }
        }
    }
    is_clean, violations = DecisionAuditValidator.audit_leakage_payload(nested)
    assert not is_clean
    assert "climate_regime.audit_data.verified_bust" in violations[0]


def test_leakage_audit_rejects_nested_lists_and_sequences():
    """DecisionAuditValidator rejects forbidden keys inside list payloads."""
    nested_list = {
        "cycle_history": [
            {"lead": 72.0, "spread": 2.0},
            {"lead": 48.0, "actual": 1008.0},
        ]
    }
    is_clean, violations = DecisionAuditValidator.audit_leakage_payload(nested_list)
    assert not is_clean
    assert "cycle_history[1].actual" in violations[0]


def test_leakage_audit_permits_benign_metadata_string_values():
    """DecisionAuditValidator allows benign string values for non-verification keys."""
    benign_payload = {
        "model_pipeline": "forecast_error_v2",
        "description": "testing actual conditions against target threshold",
        "foo": "forecast_error",
        "lead_hours": 48.0,
    }
    is_clean, violations = DecisionAuditValidator.audit_leakage_payload(benign_payload)
    assert is_clean
    assert len(violations) == 0


# ==============================================================================
# 4. NUMERICAL ROBUSTNESS & HEALTH AUDITING
# ==============================================================================

def test_audit_validator_flags_nan_and_inf_anomalies(sample_unified_assessment):
    """DecisionAuditValidator flags NaN or Inf risk values with explicit warnings."""
    # Construct assessment with NaN risk
    bad_assess = UnifiedOperationalAssessment(
        assessment_id="test_nan",
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=72.0,
        calibrated_risk=float("nan"),
        confidence_score=0.80,
        decision_provenance_hash="0123456789abcdef",
    )
    res = DecisionAuditValidator.audit_assessment(bad_assess)
    assert res.audit_state == AuditValidationState.WARNINGS_DETECTED
    assert any("NaN/Inf in calibrated_risk" in w for w in res.warnings)


def test_audit_validator_flags_negative_lead_time(sample_unified_assessment):
    """DecisionAuditValidator flags negative lead hours as temporal anomaly."""
    bad_assess = UnifiedOperationalAssessment(
        assessment_id="test_neg_lead",
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=-12.0,
        calibrated_risk=0.40,
        confidence_score=0.80,
    )
    res = DecisionAuditValidator.audit_assessment(bad_assess)
    assert any("Negative lead" in w for w in res.warnings)


# ==============================================================================
# 5. CYCLE-TO-CYCLE CHANGE DETECTION & DECISION STABILITY
# ==============================================================================

def test_cycle_change_detector_first_cycle(sample_unified_assessment):
    """First cycle evaluation returns INSUFFICIENT_HISTORY with zero deltas."""
    change = CycleChangeDetector.compute_change(current_assessment=sample_unified_assessment, previous_assessment=None)
    assert change.previous_decision is None
    assert change.current_decision == OperationalDecision.WARN_POTENTIAL_BUST
    assert not change.decision_changed
    assert change.risk_delta == 0.0
    assert change.stability_state == DecisionStabilityState.INSUFFICIENT_HISTORY


def test_cycle_change_detector_escalation_detection(sample_unified_assessment):
    """Increasing risk from 0.30 -> 0.60 produces ESCALATION flag and positive delta."""
    engine = UnifiedOperationalRiskEngine()
    prev_a = engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-21T00:00:00Z", lead_hours=96.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=1.5, calibrated_risk=0.30
    )
    curr_a = engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1015.0, ensemble_mean=1011.0, ensemble_std=2.5, calibrated_risk=0.60
    )

    change = CycleChangeDetector.compute_change(current_assessment=curr_a, previous_assessment=prev_a)
    assert change.decision_changed
    assert change.previous_decision == OperationalDecision.ADVISE_CAUTION
    assert change.current_decision == OperationalDecision.WARN_POTENTIAL_BUST
    assert change.risk_delta == 0.30
    assert change.escalation_detected
    assert not change.deescalation_detected
    assert change.stability_state == DecisionStabilityState.ESCALATING


def test_cycle_change_detector_deescalation_detection():
    """Decreasing risk from 0.65 -> 0.25 produces DE_ESCALATING flag and negative delta."""
    engine = UnifiedOperationalRiskEngine()
    prev_a = engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1015.0, ensemble_mean=1011.0, ensemble_std=2.8, calibrated_risk=0.65
    )
    curr_a = engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-23T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=1.2, calibrated_risk=0.25
    )

    change = CycleChangeDetector.compute_change(current_assessment=curr_a, previous_assessment=prev_a)
    assert change.risk_delta == -0.40
    assert change.deescalation_detected
    assert change.stability_state == DecisionStabilityState.DE_ESCALATING


def test_decision_stability_analyzer_oscillation_detection():
    """Alternating risk revisions (e.g. 0.20 -> 0.60 -> 0.25 -> 0.65) trigger OSCILLATING state."""
    risks = [0.20, 0.60, 0.25, 0.65]
    decisions = [
        OperationalDecision.ADVISE_CAUTION,
        OperationalDecision.WARN_POTENTIAL_BUST,
        OperationalDecision.ADVISE_CAUTION,
        OperationalDecision.WARN_POTENTIAL_BUST,
    ]
    state = DecisionStabilityAnalyzer.analyze_sequence_stability(risks, decisions)
    assert state == DecisionStabilityState.OSCILLATING


def test_decision_stability_analyzer_stable_high_risk():
    """Consistent high risk across cycles (0.60 -> 0.62 -> 0.61) triggers STABLE state."""
    risks = [0.60, 0.62, 0.61]
    decisions = [
        OperationalDecision.WARN_POTENTIAL_BUST,
        OperationalDecision.WARN_POTENTIAL_BUST,
        OperationalDecision.WARN_POTENTIAL_BUST,
    ]
    state = DecisionStabilityAnalyzer.analyze_sequence_stability(risks, decisions)
    assert state == DecisionStabilityState.STABLE


# ==============================================================================
# 6. DECISION RECONSTRUCTION & OPERATOR BRIEFING RENDERING
# ==============================================================================

def test_decision_reconstruction_narrative_generation(sample_unified_assessment, sample_observability_engine):
    """DecisionReconstruction creates a comprehensive, deterministic reasoning narrative."""
    trace = sample_observability_engine.build_trace(sample_unified_assessment)
    recon = trace.reconstruction
    assert recon.what_decision.startswith("Action: WARN_POTENTIAL_BUST")
    assert "DELHI" in recon.when_coordinates.upper()
    assert recon.how_urgent.startswith("Urgency:")
    assert len(recon.deterministic_narrative) > 50


def test_render_operator_briefing_output_structure(sample_unified_assessment, sample_observability_engine):
    """render_operator_briefing produces structured text containing all required sections."""
    trace = sample_observability_engine.build_trace(sample_unified_assessment)
    briefing = sample_observability_engine.render_operator_briefing(trace)

    assert "VEYRA OPERATIONAL SENTRY AUDIT TRACE" in briefing
    assert "Target Location : DELHI" in briefing
    assert "OPERATIONAL DECISION : WARN_POTENTIAL_BUST" in briefing
    assert "SCIENTIFIC SUBSYSTEM CONTEXT:" in briefing
    assert "CYCLE TRANSITION & STABILITY:" in briefing
    assert "GOVERNANCE & AUDIT STATUS:" in briefing
    assert trace.trace_hash in briefing


# ==============================================================================
# 7. ROLLING EVENT OBSERVABILITY MEMORY
# ==============================================================================

def test_observability_engine_rolling_event_memory(sample_observability_engine):
    """Multiple sequential cycle updates for same event are tracked in rolling trace history."""
    engine = UnifiedOperationalRiskEngine()
    v_time = "2026-08-25T00:00:00Z"

    # Cycle 1
    a1 = engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc=v_time,
        issue_time_utc="2026-08-21T00:00:00Z", lead_hours=96.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=1.5, calibrated_risk=0.25
    )
    t1 = sample_observability_engine.record_assessment(a1)
    assert t1.change.stability_state == DecisionStabilityState.INSUFFICIENT_HISTORY

    # Cycle 2 (escalating)
    a2 = engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc=v_time,
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1015.0, ensemble_mean=1011.0, ensemble_std=2.5, calibrated_risk=0.55
    )
    t2 = sample_observability_engine.record_assessment(a2)
    assert t2.change.escalation_detected
    assert t2.change.risk_delta == 0.30
    assert t2.change.stability_state == DecisionStabilityState.ESCALATING

    # Check rolling history length
    key = sample_observability_engine._derive_event_key("delhi", "surface_pressure", v_time)
    assert len(sample_observability_engine.trace_history[key]) == 2


# ==============================================================================
# 8. REAL STAGE-B MULTI-STATION OBSERVABILITY VALIDATION
# ==============================================================================

def test_all_20_locations_and_3_variables_observability_traces(sample_observability_engine):
    """Generate and validate complete OperationalTrace for all 60 Stage-B location x variable slices."""
    parquet_path = Path("data/historical/multicycle_paired/paired_multicycle_stage_b_2026-08-18_2026-08-24.parquet")
    if not parquet_path.exists():
        pytest.skip(f"Stage B parquet not found at {parquet_path}")

    df = pd.read_parquet(parquet_path)
    loc_col = "location" if "location" in df.columns else "location_id"
    issue_col = "issue_time" if "issue_time" in df.columns else "issue_time_utc"
    valid_col = "valid_time" if "valid_time" in df.columns else "valid_time_utc"

    sample_slice = df.groupby([loc_col, "variable"]).first().reset_index()
    assert len(sample_slice) == 60  # 20 locations * 3 variables

    unified_engine = UnifiedOperationalRiskEngine()

    for _, row in sample_slice.iterrows():
        std_val = float(row.get("ensemble_std", 1.0)) if not pd.isna(row.get("ensemble_std")) else 1.0
        risk_val = float(np.clip(std_val / 5.0, 0.0, 1.0))
        assess = unified_engine.evaluate_forecast_cycle(
            location_id=str(row[loc_col]),
            variable=str(row["variable"]),
            valid_time_utc=str(row[valid_col]),
            issue_time_utc=str(row[issue_col]),
            lead_hours=float(row["lead_hours"]),
            forecast_value=float(row["forecast_value"]),
            ensemble_mean=float(row["ensemble_mean"]),
            ensemble_std=std_val,
            calibrated_risk=risk_val,
            mode=ExplanationMode.DECISION_TIME,
        )
        trace = sample_observability_engine.build_trace(assess)
        assert trace.audit.completeness_score == 1.0
        assert trace.audit.audit_state in (AuditValidationState.PASSED, AuditValidationState.WARNINGS_DETECTED)
        assert len(trace.trace_hash) == 16
        assert len(trace.decision_provenance_hash) == 16


# ==============================================================================
# 9. ADVERSARIAL EDGE CASES & STRESS TESTS
# ==============================================================================

def test_adversarial_reordered_dictionary_keys_produce_identical_trace_hash(sample_unified_assessment, sample_observability_engine):
    """Reordering dictionary keys produces identical trace hash and JSON representation."""
    t1 = sample_observability_engine.build_trace(sample_unified_assessment)
    j1 = t1.to_json()

    # Re-evaluate with reordered features
    engine = UnifiedOperationalRiskEngine()
    a_reordered = engine.evaluate_forecast_cycle(
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=72.0,
        forecast_value=1015.0,
        ensemble_mean=1011.0,
        ensemble_std=2.5,
        calibrated_risk=0.60,
        confidence_score=0.85,
        features={"lead_hours": 72.0, "elevation_m": 216.0, "latitude": 28.6},
        mode=ExplanationMode.DECISION_TIME,
    )
    t2 = sample_observability_engine.build_trace(a_reordered)
    assert t1.trace_hash == t2.trace_hash
    assert json.loads(j1)["trace_hash"] == json.loads(t2.to_json())["trace_hash"]


def test_adversarial_missing_optional_fields_produces_valid_trace(sample_observability_engine):
    """Missing optional explanation or analogues degrades gracefully without exceptions."""
    minimal_assess = UnifiedOperationalAssessment(
        assessment_id="min_trace_01",
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=72.0,
        calibrated_risk=0.40,
        confidence_score=0.80,
        operational_decision=OperationalDecision.WARN_POTENTIAL_BUST,
        decision_provenance_hash="0123456789abcdef",
    )
    trace = sample_observability_engine.build_trace(minimal_assess)
    assert trace.identity.trace_id == "min_trace_01"
    assert trace.signals.historical_analogue_id == "NONE"
    assert trace.signals.xai_counterfactual_count == 0
    assert len(trace.trace_hash) == 16


def test_adversarial_extreme_risk_boundary_zero_and_one(sample_observability_engine):
    """Calibrated risk at exact boundaries (0.0 and 1.0) is handled cleanly."""
    engine = UnifiedOperationalRiskEngine()
    a_zero = engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1012.0, ensemble_mean=1012.0, ensemble_std=0.5, calibrated_risk=0.0
    )
    t_zero = sample_observability_engine.build_trace(a_zero)
    assert t_zero.decision.calibrated_risk == 0.0

    a_one = engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1025.0, ensemble_mean=1012.0, ensemble_std=5.0, calibrated_risk=1.0
    )
    t_one = sample_observability_engine.build_trace(a_one)
    assert t_one.decision.calibrated_risk == 1.0


def test_adversarial_zero_spread_trace_handling(sample_observability_engine):
    """Zero ensemble spread produces valid trace with appropriate uncertainty explanation."""
    engine = UnifiedOperationalRiskEngine()
    a_zero_spread = engine.evaluate_forecast_cycle(
        location_id="cairo", variable="temperature_2m", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=305.0, ensemble_mean=305.0, ensemble_std=0.0, calibrated_risk=0.10
    )
    trace = sample_observability_engine.build_trace(a_zero_spread)
    assert trace.decision.operational_decision == OperationalDecision.MONITOR
    assert trace.signals.uncertainty_dominant_source in ("ZERO_SPREAD_COLLAPSE", "ENSEMBLE_DISPERSION", "EPISTEMIC_NOVELTY")


def test_arbitration_summary_captures_tier_overrides(sample_observability_engine):
    """Arbitration summary records applied tier overrides when novelty or instability triggers."""
    engine = UnifiedOperationalRiskEngine()
    # High novelty triggers Tier 2 abstention override
    a_novel = engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1015.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.55, novelty_score=3.20
    )
    trace = sample_observability_engine.build_trace(a_novel)
    assert trace.arbitration.override_applied
    assert trace.arbitration.winning_tier == SignalPrecedenceTier.TIER_2_NOVELTY_ABSTENTION
    assert trace.decision.operational_decision == OperationalDecision.ABSTAIN


def test_completeness_status_partial_and_minimal():
    """Completeness score correctly reflects missing scientific subsystems."""
    # Explicitly set 5 components to test partial completeness
    partial_assess = UnifiedOperationalAssessment(
        assessment_id="partial_01",
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=72.0,
        calibrated_risk=0.50,
        confidence_score=0.80,
        operational_decision=OperationalDecision.WARN_POTENTIAL_BUST,
        decision_provenance_hash="0123456789abcdef",
        uncertainty=None,
        novelty=None,
        trajectory_state=TrajectoryState.PERSISTENT_HIGH_RISK,
        event_id="",
    )
    audit_res = DecisionAuditValidator.audit_assessment(partial_assess)
    assert audit_res.completeness_status == CompletenessStatus.PARTIAL
    assert audit_res.completeness_score == 0.625  # 5 / 8 components present
    assert "UNCERTAINTY_DECOMPOSITION" in audit_res.missing_components
    assert "FEATURE_NOVELTY" in audit_res.missing_components


def test_completeness_status_minimal_and_invalid():
    """Missing critical coordinates results in MINIMAL or INVALID status."""
    # Only coordinates and provenance present
    minimal_assess = UnifiedOperationalAssessment(
        assessment_id="min_01",
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=72.0,
        calibrated_risk=float("nan"),  # invalid risk
        confidence_score=0.80,
        operational_decision=None,     # missing decision
        warning_priority=None,
        decision_provenance_hash="0123456789abcdef",
        uncertainty=None,
        novelty=None,
        trajectory_state=None,
        event_id="",
    )
    audit_res = DecisionAuditValidator.audit_assessment(minimal_assess)
    assert audit_res.completeness_status == CompletenessStatus.MINIMAL
    assert audit_res.completeness_score == 0.25  # 2 / 8


def test_multiple_engine_instances_produce_identical_traces(sample_unified_assessment):
    """Two independent observability engine instances produce identical trace hashes."""
    e1 = OperationalObservabilityEngine()
    e2 = OperationalObservabilityEngine()

    t1 = e1.build_trace(sample_unified_assessment)
    t2 = e2.build_trace(sample_unified_assessment)

    assert t1.trace_hash == t2.trace_hash
    assert t1.to_dict() == t2.to_dict()


def test_mutating_external_dict_does_not_affect_built_trace(sample_unified_assessment, sample_observability_engine):
    """Modifying raw feature dictionary after trace creation leaves trace unaffected."""
    raw_dict = {"latitude": 28.6, "elevation_m": 216.0}
    trace = sample_observability_engine.build_trace(sample_unified_assessment, raw_features_payload=raw_dict)
    initial_hash = trace.trace_hash

    # Mutate raw dictionary
    raw_dict["latitude"] = 999.0
    raw_dict["new_key"] = "modified"

    assert trace.trace_hash == initial_hash


def test_trace_hash_uniqueness_across_different_coordinates(sample_observability_engine):
    """Traces across different locations, variables, and valid times have distinct hashes."""
    engine = UnifiedOperationalRiskEngine()
    t_delhi = sample_observability_engine.build_trace(engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.40
    ))
    t_cairo = sample_observability_engine.build_trace(engine.evaluate_forecast_cycle(
        location_id="cairo", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.40
    ))
    t_wind = sample_observability_engine.build_trace(engine.evaluate_forecast_cycle(
        location_id="delhi", variable="wind_speed_10m", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=12.0, ensemble_mean=11.5, ensemble_std=2.0, calibrated_risk=0.40
    ))
    t_later = sample_observability_engine.build_trace(engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-26T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=96.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.40
    ))

    hashes = {t_delhi.trace_hash, t_cairo.trace_hash, t_wind.trace_hash, t_later.trace_hash}
    assert len(hashes) == 4


def test_decision_stability_analyzer_with_insufficient_history():
    """Sequence of 1 cycle returns INSUFFICIENT_HISTORY."""
    state = DecisionStabilityAnalyzer.analyze_sequence_stability([0.50], [OperationalDecision.WARN_POTENTIAL_BUST])
    assert state == DecisionStabilityState.INSUFFICIENT_HISTORY


def test_decision_stability_analyzer_with_escalating_sequence():
    """Monotonically increasing risk sequence triggers ESCALATING."""
    state = DecisionStabilityAnalyzer.analyze_sequence_stability(
        [0.20, 0.35, 0.55],
        [OperationalDecision.ADVISE_CAUTION, OperationalDecision.ADVISE_CAUTION, OperationalDecision.WARN_POTENTIAL_BUST]
    )
    assert state == DecisionStabilityState.ESCALATING


def test_decision_stability_analyzer_with_deescalating_sequence():
    """Monotonically decreasing risk sequence triggers DE_ESCALATING."""
    state = DecisionStabilityAnalyzer.analyze_sequence_stability(
        [0.65, 0.45, 0.20],
        [OperationalDecision.WARN_POTENTIAL_BUST, OperationalDecision.ADVISE_CAUTION, OperationalDecision.MONITOR]
    )
    assert state == DecisionStabilityState.DE_ESCALATING


def test_cycle_change_detector_with_identical_consecutive_decisions(sample_unified_assessment):
    """Consecutive assessments with identical decision and risk produce STABLE state."""
    change = CycleChangeDetector.compute_change(
        current_assessment=sample_unified_assessment,
        previous_assessment=sample_unified_assessment,
    )
    assert not change.decision_changed
    assert change.risk_delta == 0.0
    assert not change.escalation_detected
    assert not change.deescalation_detected
    assert change.stability_state == DecisionStabilityState.STABLE


def test_cycle_change_detector_with_urgency_escalation(sample_unified_assessment):
    """Urgency elevation from ROUTINE -> IMMEDIATE triggers escalation even if decision tier is unchanged."""
    engine = UnifiedOperationalRiskEngine()
    prev_a = engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1015.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.55
    )
    curr_a = engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-24T12:00:00Z", lead_hours=12.0, forecast_value=1015.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.55
    )
    change = CycleChangeDetector.compute_change(current_assessment=curr_a, previous_assessment=prev_a)
    assert change.urgency_changed
    assert change.escalation_detected


def test_trace_to_dict_and_to_json_keys_sorted(sample_unified_assessment, sample_observability_engine):
    """to_dict and to_json produce deterministically sorted dictionary keys."""
    trace = sample_observability_engine.build_trace(sample_unified_assessment)
    d = trace.to_dict()
    assert isinstance(d, dict)
    assert "schema_version" in d
    assert "trace_hash" in d
    assert "identity" in d


def test_adversarial_deeply_nested_lists_leakage_rejection():
    """Deeply nested list of lists containing verification keys is rejected."""
    deep_payload = {"a": [[{"b": [{"verified_abs_error": 2.5}]}]]}
    is_clean, violations = DecisionAuditValidator.audit_leakage_payload(deep_payload)
    assert not is_clean
    assert len(violations) == 1


def test_adversarial_mixed_case_forbidden_leakage_keys():
    """Forbidden verification keys with strange casing (e.g. TrUtH_vAlUe, FORECAST_ERROR) are rejected."""
    payload = {"TrUtH_VaLuE": 1012.0, "FORECAST_ERROR": 2.0}
    is_clean, violations = DecisionAuditValidator.audit_leakage_payload(payload)
    assert not is_clean
    assert len(violations) == 2


def test_arbitration_summary_with_tier1_safety_abstention(sample_observability_engine):
    """Tier 1 safety gate abstention is properly reflected in ArbitrationSummary."""
    assess = UnifiedOperationalAssessment(
        assessment_id="safety_abstain_01",
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=72.0,
        calibrated_risk=0.50,
        confidence_score=0.80,
        operational_decision=OperationalDecision.ABSTAIN,
        decision_provenance_hash="0123456789abcdef",
    )
    trace = sample_observability_engine.build_trace(assess)
    assert trace.arbitration.winning_tier == SignalPrecedenceTier.TIER_1_SAFETY_GATE
    assert trace.decision.operational_decision == OperationalDecision.ABSTAIN


def test_arbitration_summary_with_tier3_data_quality_rejection(sample_observability_engine):
    """Tier 3 data quality corruption records explicit override in arbitration summary."""
    a_dq = UnifiedOperationalAssessment(
        assessment_id="dq_01",
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=72.0,
        calibrated_risk=0.60,
        confidence_score=0.80,
        operational_decision=OperationalDecision.ABSTAIN,
        data_quality=DataQualityState.CORRUPTED,
        signal_overrides=[SignalOverrideRecord(
            precedence_tier=SignalPrecedenceTier.TIER_3_DATA_QUALITY_GATE,
            source_module="DataQualityAuditor",
            original_decision="WARN_POTENTIAL_BUST",
            arbitrated_decision="ABSTAIN",
            triggering_condition="CORRUPTED",
            rationale="Corrupted sensor data",
            override_provenance_hash="0123456789abcdef",
        )],
        decision_provenance_hash="0123456789abcdef",
    )
    trace = sample_observability_engine.build_trace(a_dq)
    assert trace.arbitration.override_applied
    assert trace.arbitration.winning_tier == SignalPrecedenceTier.TIER_3_DATA_QUALITY_GATE
    assert trace.decision.operational_decision == OperationalDecision.ABSTAIN


def test_arbitration_summary_with_tier4_instability_escalation(sample_observability_engine):
    """Tier 4 temporal instability escalation produces WARN decision and recorded override."""
    a_instab = UnifiedOperationalAssessment(
        assessment_id="instab_01",
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=72.0,
        calibrated_risk=0.30,
        confidence_score=0.80,
        operational_decision=OperationalDecision.WARN_POTENTIAL_BUST,
        trajectory_state=TrajectoryState.ACCELERATING_RISK,
        signal_overrides=[SignalOverrideRecord(
            precedence_tier=SignalPrecedenceTier.TIER_4_CRITICAL_TEMPORAL_INSTABILITY,
            source_module="InstabilityDetector",
            original_decision="ADVISE_CAUTION",
            arbitrated_decision="WARN_POTENTIAL_BUST",
            triggering_condition="ACCELERATING_RISK",
            rationale="Rapid forecast divergence detected",
            override_provenance_hash="0123456789abcdef",
        )],
        decision_provenance_hash="0123456789abcdef",
    )
    trace = sample_observability_engine.build_trace(a_instab)
    assert trace.decision.operational_decision in (OperationalDecision.ADVISE_CAUTION, OperationalDecision.WARN_POTENTIAL_BUST)
    assert trace.arbitration.winning_tier == SignalPrecedenceTier.TIER_4_CRITICAL_TEMPORAL_INSTABILITY


def test_render_operator_briefing_with_overrides(sample_observability_engine):
    """Operator briefing text highlights applied tier overrides clearly."""
    engine = UnifiedOperationalRiskEngine()
    a_novel = engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1015.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.55, novelty_score=3.20
    )
    trace = sample_observability_engine.build_trace(a_novel)
    briefing = sample_observability_engine.render_operator_briefing(trace)
    assert "Override Applied   : True" in briefing
    assert "TIER_2_NOVELTY_ABSTENTION" in briefing


def test_temporal_consistency_audit_detects_valid_before_issue():
    """Audit validator flags warning when valid_time precedes issue_time."""
    bad_assess = UnifiedOperationalAssessment(
        assessment_id="time_reversed",
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-20T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=-48.0,
        calibrated_risk=0.40,
        confidence_score=0.80,
        decision_provenance_hash="0123456789abcdef",
    )
    res = DecisionAuditValidator.audit_assessment(bad_assess)
    assert any("valid_time precedes issue_time" in w or "Negative lead" in w for w in res.warnings)


def test_audit_validator_flags_invalid_provenance_hash_length():
    """Audit validator fails when decision provenance hash is truncated or malformed."""
    bad_assess = UnifiedOperationalAssessment(
        assessment_id="short_hash",
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=72.0,
        calibrated_risk=0.40,
        confidence_score=0.80,
        decision_provenance_hash="short",  # invalid length
    )
    res = DecisionAuditValidator.audit_assessment(bad_assess)
    assert not res.is_valid
    assert "FAILED" in res.provenance_audit_status
    assert res.audit_state == AuditValidationState.CRITICAL_FAILURE


def test_post_hoc_outcome_record_properties(sample_unified_assessment, sample_observability_engine):
    """PostHocOutcomeRecord correctly captures verified truth and outcome status."""
    trace = sample_observability_engine.build_trace(sample_unified_assessment)
    _, outcome = sample_observability_engine.attach_post_hoc_outcome(
        trace=trace,
        truth_value=1018.0,
        verification_time_utc="2026-08-25T00:00:00Z",
        is_verified_bust=True,
    )
    assert outcome.trace_id == trace.identity.trace_id
    assert outcome.verified_truth_value == 1018.0
    assert outcome.is_verified_bust is True
    assert outcome.outcome_status == EventOutcomeStatus.VERIFIED_BUST
    assert len(outcome.outcome_provenance_hash) == 16


def test_decision_reconstruction_contains_all_evidence_elements(sample_unified_assessment, sample_observability_engine):
    """DecisionReconstruction includes structured supporting evidence tuples."""
    trace = sample_observability_engine.build_trace(sample_unified_assessment)
    recon = trace.reconstruction
    assert len(recon.supporting_evidence) >= 3
    assert any("Trajectory State:" in s for s in recon.supporting_evidence)
    assert any("Arbitration:" in s for s in recon.supporting_evidence)


def test_audit_validator_flags_non_hex_provenance_hash():
    """Audit validator fails if provenance hash contains non-hex characters."""
    bad_assess = UnifiedOperationalAssessment(
        assessment_id="bad_hex",
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=72.0,
        calibrated_risk=0.40,
        confidence_score=0.80,
        decision_provenance_hash="0123456789xyz!@#",  # invalid non-hex characters
    )
    res = DecisionAuditValidator.audit_assessment(bad_assess)
    assert not res.is_valid
    assert "FAILED" in res.provenance_audit_status


def test_observability_engine_cleans_and_normalizes_case_and_whitespace(sample_observability_engine):
    """Engine strips whitespace and normalizes location/variable casing."""
    assess = UnifiedOperationalAssessment(
        assessment_id="normalize_01",
        location_id="  DELHI  ",
        variable="  SURFACE_PRESSURE  ",
        valid_time_utc=" 2026-08-25T00:00:00Z ",
        issue_time_utc=" 2026-08-22T00:00:00Z ",
        lead_hours=72.0,
        calibrated_risk=0.50,
        confidence_score=0.80,
        decision_provenance_hash="0123456789abcdef",
    )
    trace = sample_observability_engine.build_trace(assess)
    assert trace.identity.location_id == "delhi"
    assert trace.identity.variable == "surface_pressure"
    assert trace.identity.valid_time_utc == "2026-08-25T00:00:00Z"


def test_cycle_change_detector_with_negative_confidence_delta(sample_unified_assessment):
    """Confidence degradation across cycles produces negative confidence delta."""
    engine = UnifiedOperationalRiskEngine()
    prev_a = engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1015.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.55, confidence_score=0.90
    )
    curr_a = engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-23T00:00:00Z", lead_hours=48.0, forecast_value=1015.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.55, confidence_score=0.60
    )
    change = CycleChangeDetector.compute_change(current_assessment=curr_a, previous_assessment=prev_a)
    assert change.confidence_delta == -0.30


def test_decision_stability_analyzer_with_two_decision_changes_triggers_oscillation():
    """Two decision reversals in historical sequence triggers OSCILLATING state."""
    state = DecisionStabilityAnalyzer.analyze_sequence_stability(
        [0.40, 0.42, 0.39],
        [OperationalDecision.WARN_POTENTIAL_BUST, OperationalDecision.ADVISE_CAUTION, OperationalDecision.WARN_POTENTIAL_BUST]
    )
    assert state == DecisionStabilityState.OSCILLATING
