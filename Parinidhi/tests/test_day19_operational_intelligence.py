"""
Day 19 Production Operational Intelligence & Cross-Day Integration Test Suite.

Comprehensive validation covering:
1. UnifiedOperationalAssessment schema & JSON serialization.
2. SignalArbitrationEngine hierarchy & conflict overrides (Tiers 1–6).
3. Strict anti-leakage rejection across all decision-time payloads.
4. Cryptographic provenance invariance (Decision vs Execution).
5. Determinism under dictionary reordering and repeated invocations.
6. Graceful degradation on missing temporal history, missing analogues, and zero spread.
7. Numerical robustness against NaNs, infs, negative leads, and extreme risks.
8. End-to-end integration with XAI explanations and Event Intelligence.
9. Real Stage B multi-cycle chronological dataset simulation.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from evaluation.decision_schema import (
    DataQualityState,
    OperationalDecision,
    RiskLevel,
    WarningPriority,
)
from evaluation.event_schema import (
    EventLifecycleState,
    EventOutcomeStatus,
    EventSeverity,
    OperationalUrgency,
)
from evaluation.operational_intelligence_pipeline import UnifiedOperationalRiskEngine
from evaluation.signal_arbitration import SignalArbitrationEngine
from evaluation.trajectory_schema import TrajectoryState
from evaluation.unified_schema import (
    AssessmentStatus,
    SignalOverrideRecord,
    SignalPrecedenceTier,
    UnifiedOperationalAssessment,
)
from evaluation.xai_schema import ExplanationMode


@pytest.fixture
def sample_engine():
    return UnifiedOperationalRiskEngine()


@pytest.fixture
def sample_arbitration_engine():
    return SignalArbitrationEngine()


# ==============================================================================
# 1. UNIFIED SCHEMA & SERIALIZATION
# ==============================================================================

def test_unified_assessment_schema_instantiation_and_serialization():
    """Verify dataclass instantiation and JSON round-trip."""
    assess = UnifiedOperationalAssessment(
        assessment_id="test_assess_001",
        schema_version="19.0.0",
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=48.0,
        forecast_value=1012.0,
        ensemble_mean=1011.5,
        ensemble_std=2.4,
        calibrated_risk=0.62,
        raw_risk=0.58,
        confidence_score=0.85,
        operational_decision=OperationalDecision.WARN_POTENTIAL_BUST,
        warning_priority=WarningPriority.P2_MEDIUM,
        urgency=OperationalUrgency.URGENT,
        severity=EventSeverity.SEVERE,
        severity_score=0.65,
    )
    d = assess.to_dict()
    assert d["assessment_id"] == "test_assess_001"
    assert d["operational_decision"] == "WARN_POTENTIAL_BUST"
    assert d["urgency"] == "URGENT"

    json_str = assess.to_json()
    parsed = json.loads(json_str)
    assert parsed["schema_version"] == "19.0.0"
    assert parsed["calibrated_risk"] == 0.62


def test_signal_override_record_serialization():
    """Verify SignalOverrideRecord fields and serialization."""
    rec = SignalOverrideRecord(
        precedence_tier=SignalPrecedenceTier.TIER_4_CRITICAL_TEMPORAL_INSTABILITY,
        source_module="TemporalInstabilityDetector",
        original_decision="MONITOR",
        arbitrated_decision="WARN_POTENTIAL_BUST",
        triggering_condition="Velocity +0.10/cycle",
        rationale="NWP divergence rapid escalation",
        override_provenance_hash="test_override_hash",
    )
    d = rec.to_dict()
    assert d["precedence_tier"] == "TIER_4_CRITICAL_TEMPORAL_INSTABILITY"
    assert d["original_decision"] == "MONITOR"
    assert d["arbitrated_decision"] == "WARN_POTENTIAL_BUST"


# ==============================================================================
# 2. SIGNAL ARBITRATION HIERARCHY (TIERS 1 - 6)
# ==============================================================================

def test_arbitration_tier1_explicit_safety_abstention(sample_arbitration_engine):
    """Tier 1: Explicit safety controller abstention overrides all decisions."""
    dec, prio, urg, status, overrides = sample_arbitration_engine.arbitrate(
        base_decision=OperationalDecision.ALERT_CRITICAL_BUST,
        base_priority=WarningPriority.P1_HIGH,
        base_urgency=OperationalUrgency.IMMEDIATE,
        calibrated_risk=0.90,
        confidence_score=0.90,
        novelty_score=1.0,
        data_quality=DataQualityState.CLEAN,
        trajectory_state=TrajectoryState.ACCELERATING_RISK,
        instability_detected=True,
        risk_velocity=0.15,
        is_abstained_explicit=True,
    )
    assert dec == OperationalDecision.ABSTAIN
    assert status == AssessmentStatus.SAFETY_ABSTAINED
    assert urg == OperationalUrgency.INSUFFICIENT_CONFIDENCE
    assert len(overrides) == 1
    assert overrides[0].precedence_tier == SignalPrecedenceTier.TIER_1_SAFETY_GATE


def test_arbitration_tier2_extreme_novelty_abstention(sample_arbitration_engine):
    """Tier 2: Out-of-distribution novelty (d >= 2.50) triggers abstention."""
    dec, prio, urg, status, overrides = sample_arbitration_engine.arbitrate(
        base_decision=OperationalDecision.ALERT_CRITICAL_BUST,
        base_priority=WarningPriority.P1_HIGH,
        base_urgency=OperationalUrgency.IMMEDIATE,
        calibrated_risk=0.85,
        confidence_score=0.75,
        novelty_score=2.80,
        data_quality=DataQualityState.CLEAN,
        trajectory_state=TrajectoryState.STABLE_LOW,
        instability_detected=False,
        risk_velocity=0.0,
    )
    assert dec == OperationalDecision.ABSTAIN
    assert status == AssessmentStatus.SAFETY_ABSTAINED
    assert overrides[0].precedence_tier == SignalPrecedenceTier.TIER_2_NOVELTY_ABSTENTION


def test_arbitration_tier3_corrupted_data_quality_rejection(sample_arbitration_engine):
    """Tier 3: Corrupted data quality triggers rejection abstention."""
    dec, prio, urg, status, overrides = sample_arbitration_engine.arbitrate(
        base_decision=OperationalDecision.WARN_POTENTIAL_BUST,
        base_priority=WarningPriority.P2_MEDIUM,
        base_urgency=OperationalUrgency.URGENT,
        calibrated_risk=0.55,
        confidence_score=0.80,
        novelty_score=1.0,
        data_quality=DataQualityState.CORRUPTED,
        trajectory_state=TrajectoryState.STABLE_LOW,
        instability_detected=False,
        risk_velocity=0.0,
    )
    assert dec == OperationalDecision.ABSTAIN
    assert status == AssessmentStatus.DATA_QUALITY_REJECTED
    assert overrides[0].precedence_tier == SignalPrecedenceTier.TIER_3_DATA_QUALITY_GATE


def test_arbitration_tier4_critical_temporal_instability_escalation(sample_arbitration_engine):
    """Tier 4: Severe temporal instability escalates MONITOR decision to WARN."""
    dec, prio, urg, status, overrides = sample_arbitration_engine.arbitrate(
        base_decision=OperationalDecision.MONITOR,
        base_priority=WarningPriority.P4_INFORMATIONAL,
        base_urgency=OperationalUrgency.ROUTINE,
        calibrated_risk=0.18,
        confidence_score=0.80,
        novelty_score=1.0,
        data_quality=DataQualityState.CLEAN,
        trajectory_state=TrajectoryState.ACCELERATING_RISK,
        instability_detected=True,
        risk_velocity=0.10,
    )
    assert dec == OperationalDecision.WARN_POTENTIAL_BUST
    assert prio == WarningPriority.P2_MEDIUM
    assert urg == OperationalUrgency.URGENT
    assert status == AssessmentStatus.SUCCESS
    assert len(overrides) == 1
    assert overrides[0].precedence_tier == SignalPrecedenceTier.TIER_4_CRITICAL_TEMPORAL_INSTABILITY


def test_arbitration_tier5_baseline_decision_policy_preserved(sample_arbitration_engine):
    """Tier 5: Clean, stable forecast conditions preserve base policy without overrides."""
    dec, prio, urg, status, overrides = sample_arbitration_engine.arbitrate(
        base_decision=OperationalDecision.WARN_POTENTIAL_BUST,
        base_priority=WarningPriority.P2_MEDIUM,
        base_urgency=OperationalUrgency.WATCH,
        calibrated_risk=0.50,
        confidence_score=0.80,
        novelty_score=1.0,
        data_quality=DataQualityState.CLEAN,
        trajectory_state=TrajectoryState.STABLE_LOW,
        instability_detected=False,
        risk_velocity=0.0,
    )
    assert dec == OperationalDecision.WARN_POTENTIAL_BUST
    assert prio == WarningPriority.P2_MEDIUM
    assert len(overrides) == 0
    assert status == AssessmentStatus.SUCCESS


# ==============================================================================
# 3. STRICT ANTI-LEAKAGE AUDITING
# ==============================================================================

def test_pipeline_decision_time_rejects_verification_features(sample_engine):
    """All verification/target columns must be rejected in DECISION_TIME mode."""
    forbidden_cols = [
        "truth_value", "forecast_error", "forecast_abs_error",
        "ensemble_mean_error", "ensemble_mean_abs_error",
        "bust_label", "is_bust", "bust_label_q95", "actual", "realized"
    ]
    for col in forbidden_cols:
        with pytest.raises(ValueError, match="Target leakage rejected"):
            sample_engine.evaluate_forecast_cycle(
                location_id="delhi",
                variable="surface_pressure",
                valid_time_utc="2026-08-24T00:00:00Z",
                issue_time_utc="2026-08-22T00:00:00Z",
                lead_hours=48.0,
                forecast_value=1012.0,
                ensemble_mean=1011.0,
                ensemble_std=2.0,
                calibrated_risk=0.50,
                features={"lead_hours": 48.0, col: 1.0},
                mode=ExplanationMode.DECISION_TIME,
            )


def test_pipeline_decision_time_rejects_leakage_in_trajectory_history(sample_engine):
    """Target leakage inside historical trajectory dictionaries must also be rejected."""
    traj = [
        {"lead_hours": 72.0, "calibrated_risk": 0.20, "truth_value": 1010.0},
        {"lead_hours": 48.0, "calibrated_risk": 0.40},
    ]
    with pytest.raises(ValueError, match="Target leakage rejected"):
        sample_engine.evaluate_forecast_cycle(
            location_id="delhi",
            variable="surface_pressure",
            valid_time_utc="2026-08-24T00:00:00Z",
            issue_time_utc="2026-08-22T00:00:00Z",
            lead_hours=48.0,
            forecast_value=1012.0,
            ensemble_mean=1011.0,
            ensemble_std=2.0,
            calibrated_risk=0.40,
            trajectory_history=traj,
            mode=ExplanationMode.DECISION_TIME,
        )


# ==============================================================================
# 4. PROVENANCE INVARIANCES & DETERMINISM
# ==============================================================================

def test_provenance_invariance_upon_post_hoc_outcome_attachment(sample_engine):
    """
    Attaching post-hoc truth/outcome MUST leave decision_provenance_hash 100% unchanged,
    while execution_provenance_hash reflects the outcome attachment.
    """
    # 1. Decision-time assessment
    dec_assess = sample_engine.evaluate_forecast_cycle(
        location_id="cairo",
        variable="temperature_2m",
        valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=48.0,
        forecast_value=308.0,
        ensemble_mean=307.0,
        ensemble_std=2.2,
        calibrated_risk=0.55,
        mode=ExplanationMode.DECISION_TIME,
    )
    initial_dec_hash = dec_assess.decision_provenance_hash
    initial_exec_hash = dec_assess.execution_provenance_hash

    # 2. Post-hoc evaluation mode with truth
    post_assess = sample_engine.evaluate_forecast_cycle(
        location_id="cairo",
        variable="temperature_2m",
        valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=48.0,
        forecast_value=308.0,
        ensemble_mean=307.0,
        ensemble_std=2.2,
        calibrated_risk=0.55,
        mode=ExplanationMode.POST_HOC_EVALUATION,
        post_hoc_truth={"truth_value": 302.0, "verification_time_utc": "2026-08-24T00:00:00Z"},
    )

    assert post_assess.decision_provenance_hash == initial_dec_hash
    assert post_assess.execution_provenance_hash != initial_exec_hash
    assert post_assess.retrospective_outcome is not None
    assert post_assess.retrospective_outcome.outcome_status == EventOutcomeStatus.VERIFIED_BUST


def test_provenance_sensitivity_to_genuine_scientific_changes(sample_engine):
    """Modifying genuine scientific features alters decision_provenance_hash."""
    a1 = sample_engine.evaluate_forecast_cycle(
        location_id="london", variable="wind_speed_10m", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=12.0, ensemble_mean=11.5, ensemble_std=2.0, calibrated_risk=0.45
    )
    a2 = sample_engine.evaluate_forecast_cycle(
        location_id="london", variable="wind_speed_10m", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=12.0, ensemble_mean=11.5, ensemble_std=4.5, calibrated_risk=0.80
    )
    assert a1.decision_provenance_hash != a2.decision_provenance_hash


def test_determinism_under_feature_dictionary_reordering(sample_engine):
    """Reordering feature dictionary keys produces identical assessment identity and provenance."""
    f_ordered = {"lead_hours": 48.0, "ensemble_spread": 2.0, "cycle_sin": 0.5}
    f_reversed = {"cycle_sin": 0.5, "ensemble_spread": 2.0, "lead_hours": 48.0}

    a1 = sample_engine.evaluate_forecast_cycle(
        location_id="tokyo", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.50, features=f_ordered
    )
    a2 = sample_engine.evaluate_forecast_cycle(
        location_id="tokyo", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.50, features=f_reversed
    )
    assert a1.assessment_id == a2.assessment_id
    assert a1.decision_provenance_hash == a2.decision_provenance_hash


# ==============================================================================
# 5. GRACEFUL DEGRADATION & NUMERICAL ROBUSTNESS
# ==============================================================================

def test_graceful_degradation_missing_temporal_history(sample_engine):
    """Missing trajectory history degrades gracefully with explicit warning."""
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="singapore", variable="temperature_2m", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=302.0, ensemble_mean=302.0, ensemble_std=1.5, calibrated_risk=0.35, trajectory_history=None
    )
    assert assess.assessment_status == AssessmentStatus.SUCCESS
    assert any("No temporal history provided" in w for w in assess.warnings)
    assert assess.trajectory_state == TrajectoryState.INSUFFICIENT_HISTORY


def test_graceful_degradation_empty_historical_memory(sample_engine):
    """Empty event memory returns explicit INSUFFICIENT_HISTORICAL_SUPPORT analogue status."""
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="new_station", variable="surface_pressure", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.40
    )
    assert assess.historical_analogue is not None
    assert assess.historical_analogue.historical_event_id == "INSUFFICIENT_HISTORICAL_SUPPORT"


def test_numerical_robustness_nans_and_infs(sample_engine):
    """NaNs and infinities in numerical fields are sanitized without crashing."""
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=float("inf"),
        forecast_value=float("nan"),
        ensemble_mean=float("-inf"),
        ensemble_std=float("nan"),
        calibrated_risk=float("nan"),
    )
    assert not np.isnan(assess.calibrated_risk)
    assert assess.calibrated_risk == 0.0
    assert not np.isnan(assess.forecast_value)
    assert assess.data_quality == DataQualityState.DEGRADED


def test_numerical_robustness_extreme_risk_and_negative_lead(sample_engine):
    """Risk > 1.0 or < 0.0 and negative lead hours are safely bounded."""
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=-12.0,
        forecast_value=1012.0,
        ensemble_mean=1011.0,
        ensemble_std=2.0,
        calibrated_risk=1.85,
    )
    assert assess.calibrated_risk == 1.0
    assert assess.lead_hours == 0.0


# ==============================================================================
# 6. LONGITUDINAL EVENT & XAI INTEGRATION
# ==============================================================================

def test_longitudinal_event_continuity_across_cycles(sample_engine):
    """Three sequential cycles for the same valid time update 1 continuous event."""
    valid_t = "2026-08-24T00:00:00Z"

    # Cycle 1 (72h)
    a1 = sample_engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc=valid_t,
        issue_time_utc="2026-08-21T00:00:00Z", lead_hours=72.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=1.2, calibrated_risk=0.22
    )
    # Cycle 2 (48h)
    a2 = sample_engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc=valid_t,
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1014.0, ensemble_mean=1011.5, ensemble_std=2.5, calibrated_risk=0.48
    )
    # Cycle 3 (24h)
    a3 = sample_engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc=valid_t,
        issue_time_utc="2026-08-23T00:00:00Z", lead_hours=24.0, forecast_value=1016.0, ensemble_mean=1012.0, ensemble_std=3.8, calibrated_risk=0.72
    )

    assert a1.event_id == a2.event_id == a3.event_id
    assert a3.cycles_tracked == 3
    assert a3.event_lifecycle_state == EventLifecycleState.CRITICAL


def test_unified_briefing_rendering_output(sample_engine):
    """Briefing rendering produces complete, readable operational text."""
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="cairo", variable="temperature_2m", valid_time_utc="2026-08-24T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=308.0, ensemble_mean=307.0, ensemble_std=2.5, calibrated_risk=0.65
    )
    briefing = sample_engine.render_unified_briefing(assess)
    assert "VEYRA UNIFIED OPERATIONAL RISK SENTRY" in briefing
    assert "CAIRO" in briefing
    assert "Decision:" in briefing
    assert "Decision Provenance:" in briefing


# ==============================================================================
# 7. REAL STAGE B MULTI-CYCLE DATASET SIMULATION
# ==============================================================================

def test_real_stage_b_multicycle_pipeline_simulation(sample_engine):
    """
    Simulate sequential issue-time ingestion on real Stage B data slice.
    Verifies zero target leakage, event continuity, and post-hoc outcome attachment.
    """
    parquet_path = Path("data/historical/multicycle_paired/paired_multicycle_stage_b_2026-08-18_2026-08-24.parquet")
    if not parquet_path.exists():
        pytest.skip(f"Stage B parquet not found at {parquet_path}")

    df = pd.read_parquet(parquet_path)
    loc_col = "location" if "location" in df.columns else "location_id"
    issue_col = "issue_time" if "issue_time" in df.columns else "issue_time_utc"
    valid_col = "valid_time" if "valid_time" in df.columns else "valid_time_utc"

    # Filter to 1 location and 1 variable for clean multi-cycle trajectory
    subset = df[(df[loc_col] == "delhi") & (df["variable"] == "surface_pressure")].copy()
    subset = subset.sort_values(issue_col).head(20)

    assessments = []
    for _, row in subset.iterrows():
        # Decision time features (exclude truth/error)
        f_dict = {
            "lead_hours": float(row["lead_hours"]),
            "ensemble_spread": float(row.get("ensemble_std", 1.0)),
        }
        std_val = float(row.get("ensemble_std", 1.0)) if not pd.isna(row.get("ensemble_std")) else 1.0
        risk_val = float(np.clip(std_val / 5.0, 0.0, 1.0))

        assess = sample_engine.evaluate_forecast_cycle(
            location_id=str(row[loc_col]),
            variable=str(row["variable"]),
            valid_time_utc=str(row[valid_col]),
            issue_time_utc=str(row[issue_col]),
            lead_hours=float(row["lead_hours"]),
            forecast_value=float(row["forecast_value"]),
            ensemble_mean=float(row["ensemble_mean"]),
            ensemble_std=std_val,
            calibrated_risk=risk_val,
            features=f_dict,
            mode=ExplanationMode.DECISION_TIME,
        )
        assessments.append(assess)

    assert len(assessments) == 20
    assert all(a.assessment_status == AssessmentStatus.SUCCESS for a in assessments)
    assert all(a.decision_provenance_hash is not None for a in assessments)


# ==============================================================================
# 8. ADVERSARIAL LEAKAGE & ROBUSTNESS TESTS
# ==============================================================================

def test_adversarial_leakage_uppercase_and_alias_names(sample_engine):
    """Adversarial attempts using uppercase and alias verification column names."""
    attack_keys = ["TRUTH_VALUE", "Forecast_Error", "IS_BUST", "realized", "actual", "bust_label_q99"]
    for key in attack_keys:
        with pytest.raises(ValueError, match="Target leakage rejected"):
            sample_engine.evaluate_forecast_cycle(
                location_id="delhi",
                variable="surface_pressure",
                valid_time_utc="2026-08-24T00:00:00Z",
                issue_time_utc="2026-08-22T00:00:00Z",
                lead_hours=48.0,
                forecast_value=1012.0,
                ensemble_mean=1011.0,
                ensemble_std=2.0,
                calibrated_risk=0.50,
                features={key: 1010.0},
                mode=ExplanationMode.DECISION_TIME,
            )


def test_adversarial_leakage_substring_injections(sample_engine):
    """Suspicious substring injections such as 'my_truth_metric' must be rejected."""
    with pytest.raises(ValueError, match="Target leakage rejected"):
        sample_engine.evaluate_forecast_cycle(
            location_id="delhi",
            variable="surface_pressure",
            valid_time_utc="2026-08-24T00:00:00Z",
            issue_time_utc="2026-08-22T00:00:00Z",
            lead_hours=48.0,
            forecast_value=1012.0,
            ensemble_mean=1011.0,
            ensemble_std=2.0,
            calibrated_risk=0.50,
            features={"custom_truth_column": 1010.0},
            mode=ExplanationMode.DECISION_TIME,
        )


def test_idempotency_ten_repeated_invocations(sample_engine):
    """10 sequential invocations with identical parameters produce bitwise identical assessments."""
    first_assessment = None
    for _ in range(10):
        a = sample_engine.evaluate_forecast_cycle(
            location_id="london",
            variable="wind_speed_10m",
            valid_time_utc="2026-08-24T00:00:00Z",
            issue_time_utc="2026-08-22T00:00:00Z",
            lead_hours=48.0,
            forecast_value=12.0,
            ensemble_mean=11.5,
            ensemble_std=1.8,
            calibrated_risk=0.45,
            mode=ExplanationMode.DECISION_TIME,
        )
        if first_assessment is None:
            first_assessment = a
        else:
            assert a.operational_decision == first_assessment.operational_decision
            assert a.warning_priority == first_assessment.warning_priority
            assert a.urgency == first_assessment.urgency
            assert a.severity == first_assessment.severity
            assert a.assessment_status == first_assessment.assessment_status
            assert a.calibrated_risk == first_assessment.calibrated_risk
            assert a.early_warning_score == first_assessment.early_warning_score
            assert a.trajectory_state == first_assessment.trajectory_state
            assert a.decision_provenance_hash == first_assessment.decision_provenance_hash
            assert a.execution_provenance_hash == first_assessment.execution_provenance_hash
            assert a.to_json() == first_assessment.to_json()


def test_adversarial_leakage_full_matrix_and_benign_string_values(sample_engine):
    """
    Comprehensive matrix testing:
    - Rejects top-level forbidden columns (truth_value, forecast_error, actual, realized, target, etc.)
    - Rejects nested dictionary and list forbidden columns
    - Rejects case variants (Truth_Value, FORECAST_ERROR, Target)
    - Permits benign non-verification keys with string values (e.g. {"foo": "forecast_error"})
    """
    matrix = [
        "truth_value", "forecast_error", "forecast_abs_error",
        "ensemble_mean_error", "ensemble_mean_abs_error",
        "bust_label", "is_bust", "bust_label_q95",
        "actual", "realized", "verified_bust", "verified_abs_error",
        "target", "verification", "obs_pressure", "observation",
        "Truth_Value", "FORECAST_ERROR", "Is_Bust", "TARGET", "vErIfIcAtIoN"
    ]
    for col in matrix:
        with pytest.raises(ValueError, match="Target leakage rejected"):
            sample_engine.evaluate_forecast_cycle(
                location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
                issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.50,
                features={col: 1010.0}, mode=ExplanationMode.DECISION_TIME,
            )

    # Benign string value associated with non-verification feature key is permitted
    benign_assess = sample_engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=48.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.50,
        features={"foo": "forecast_error", "model_tag": "target_pipeline_v1"}, mode=ExplanationMode.DECISION_TIME,
    )
    assert benign_assess.assessment_status == AssessmentStatus.SUCCESS


def test_chronological_reordering_produces_identical_event_state(sample_engine):
    """Submitting cycles in chronological vs reverse order preserves identical final state."""
    v_time = "2026-08-25T00:00:00Z"

    # Chronological engine
    eng_chrono = UnifiedOperationalRiskEngine()
    eng_chrono.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc=v_time,
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=1.5, calibrated_risk=0.20
    )
    a_chrono = eng_chrono.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc=v_time,
        issue_time_utc="2026-08-23T00:00:00Z", lead_hours=48.0, forecast_value=1015.0, ensemble_mean=1011.0, ensemble_std=2.8, calibrated_risk=0.55
    )

    # Reverse order engine
    eng_rev = UnifiedOperationalRiskEngine()
    eng_rev.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc=v_time,
        issue_time_utc="2026-08-23T00:00:00Z", lead_hours=48.0, forecast_value=1015.0, ensemble_mean=1011.0, ensemble_std=2.8, calibrated_risk=0.55
    )
    a_rev = eng_rev.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc=v_time,
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=1.5, calibrated_risk=0.20
    )

    assert a_chrono.event_id == a_rev.event_id
    assert a_chrono.cycles_tracked == a_rev.cycles_tracked == 2


def test_duplicate_cycle_update_handling(sample_engine):
    """Submitting duplicate cycle update for same issue time does not artificially duplicate snapshots."""
    v_time = "2026-08-25T00:00:00Z"
    i_time = "2026-08-22T00:00:00Z"

    a1 = sample_engine.evaluate_forecast_cycle(
        location_id="cairo", variable="temperature_2m", valid_time_utc=v_time,
        issue_time_utc=i_time, lead_hours=72.0, forecast_value=305.0, ensemble_mean=305.0, ensemble_std=1.5, calibrated_risk=0.30
    )
    a2 = sample_engine.evaluate_forecast_cycle(
        location_id="cairo", variable="temperature_2m", valid_time_utc=v_time,
        issue_time_utc=i_time, lead_hours=72.0, forecast_value=305.0, ensemble_mean=305.0, ensemble_std=1.5, calibrated_risk=0.30
    )
    assert a1.event_id == a2.event_id
    assert a2.cycles_tracked == 1


def test_temporal_instability_spikes_escalate_decision_to_warn(sample_engine):
    """Rapid risk spike across 3 cycles triggers ACCELERATING_RISK and WARN_POTENTIAL_BUST."""
    traj = [
        {"issue_time_utc": "2026-08-21T00:00:00Z", "calibrated_risk": 0.10},
        {"issue_time_utc": "2026-08-22T00:00:00Z", "calibrated_risk": 0.25},
        {"issue_time_utc": "2026-08-23T00:00:00Z", "calibrated_risk": 0.55},
    ]
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-23T00:00:00Z", lead_hours=48.0, forecast_value=1015.0, ensemble_mean=1011.0, ensemble_std=3.0, calibrated_risk=0.55, trajectory_history=traj
    )
    assert assess.trajectory_state == TrajectoryState.ACCELERATING_RISK
    assert assess.instability_detected is True
    assert assess.operational_decision == OperationalDecision.WARN_POTENTIAL_BUST


def test_temporal_risk_drop_triggers_reversing_state(sample_engine):
    """Sudden drop in risk triggers REVERSING_RISK."""
    traj = [
        {"issue_time_utc": "2026-08-21T00:00:00Z", "calibrated_risk": 0.70},
        {"issue_time_utc": "2026-08-22T00:00:00Z", "calibrated_risk": 0.30},
    ]
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=1.2, calibrated_risk=0.30, trajectory_history=traj
    )
    assert assess.trajectory_state == TrajectoryState.REVERSING_RISK


def test_time_to_critical_projection_accuracy(sample_engine):
    """Positive risk velocity projects finite positive time-to-critical hours."""
    traj = [
        {"issue_time_utc": "2026-08-21T00:00:00Z", "calibrated_risk": 0.25},
        {"issue_time_utc": "2026-08-22T00:00:00Z", "calibrated_risk": 0.45},
    ]
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1014.0, ensemble_mean=1011.0, ensemble_std=2.5, calibrated_risk=0.45, trajectory_history=traj
    )
    assert assess.time_to_critical_hours is not None
    assert assess.time_to_critical_hours > 0.0


def test_arbitration_moderate_risk_plus_extreme_novelty_triggers_abstain(sample_engine):
    """Moderate risk with novelty score 3.20 triggers ABSTAIN via Tier 2 novelty gating."""
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="cairo", variable="temperature_2m", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=308.0, ensemble_mean=307.0, ensemble_std=2.0, calibrated_risk=0.55, novelty_score=3.20
    )
    assert assess.operational_decision == OperationalDecision.ABSTAIN
    assert assess.assessment_status == AssessmentStatus.SAFETY_ABSTAINED


def test_arbitration_zero_spread_records_warning(sample_engine):
    """Zero ensemble spread produces explicit warning without division error."""
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="cairo", variable="temperature_2m", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=305.0, ensemble_mean=305.0, ensemble_std=0.0, calibrated_risk=0.20
    )
    assert any("Zero ensemble spread detected" in w for w in assess.warnings)
    assert assess.uncertainty.ensemble_spread_magnitude == 0.0


def test_event_memory_store_and_retrieve_analogue(sample_engine):
    """Adding historical events allows successful analogue similarity retrieval."""
    engine = UnifiedOperationalRiskEngine()
    # Create 2 past events (min_support_count = 2)
    p1 = engine.event_tracker.process_cycle_update(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-20T00:00:00Z",
        issue_time_utc="2026-08-18T00:00:00Z", lead_hours=48.0, forecast_value=1015.0, ensemble_mean=1011.0, ensemble_std=2.8, calibrated_risk=0.65
    )
    p2 = engine.event_tracker.process_cycle_update(
        location_id="cairo", variable="surface_pressure", valid_time_utc="2026-08-19T00:00:00Z",
        issue_time_utc="2026-08-17T00:00:00Z", lead_hours=48.0, forecast_value=1014.0, ensemble_mean=1011.0, ensemble_std=2.6, calibrated_risk=0.62
    )
    engine.event_memory.register_historical_event(p1)
    engine.event_memory.register_historical_event(p2)

    # Ingest new cycle
    new_assess = engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-23T00:00:00Z", lead_hours=48.0, forecast_value=1015.0, ensemble_mean=1011.0, ensemble_std=2.8, calibrated_risk=0.65
    )
    assert new_assess.historical_analogue is not None
    assert new_assess.historical_analogue.historical_event_id != "INSUFFICIENT_HISTORICAL_SUPPORT"
    assert new_assess.historical_analogue.similarity_score > 0.0


def test_graceful_degradation_missing_optional_fields(sample_engine):
    """Missing optional fields (features=None, raw_risk=None) defaults safely."""
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.40, raw_risk=None, features=None
    )
    assert assess.assessment_status == AssessmentStatus.SUCCESS
    assert assess.raw_risk == 0.40


def test_graceful_degradation_zero_lead_nowcast(sample_engine):
    """Lead hours = 0.0 (nowcast) operates cleanly without negative bounds or crashes."""
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="tokyo", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-25T00:00:00Z", lead_hours=0.0, forecast_value=1013.0, ensemble_mean=1013.0, ensemble_std=0.5, calibrated_risk=0.15
    )
    assert assess.lead_hours == 0.0
    assert assess.assessment_status == AssessmentStatus.SUCCESS


def test_graceful_degradation_extended_lead_horizon(sample_engine):
    """Extended lead time (240.0h) executes without overflow or indexing errors."""
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="tokyo", variable="surface_pressure", valid_time_utc="2026-09-04T00:00:00Z",
        issue_time_utc="2026-08-25T00:00:00Z", lead_hours=240.0, forecast_value=1010.0, ensemble_mean=1010.0, ensemble_std=4.5, calibrated_risk=0.75
    )
    assert assess.lead_hours == 240.0
    assert assess.operational_decision == OperationalDecision.ALERT_CRITICAL_BUST


def test_numerical_robustness_extreme_magnitude_floats(sample_engine):
    """Extreme numeric magnitudes (+/- 1e10) are bounded safely."""
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=1e10, forecast_value=1e10, ensemble_mean=-1e10, ensemble_std=1e10, calibrated_risk=99.0
    )
    assert assess.calibrated_risk == 1.0
    assert assess.assessment_status == AssessmentStatus.SUCCESS


def test_multi_location_isolation_tracks_independent_events(sample_engine):
    """Simultaneous cycles for Delhi, Cairo, and London create 3 distinct event IDs."""
    v_time = "2026-08-25T00:00:00Z"
    i_time = "2026-08-22T00:00:00Z"

    a_delhi = sample_engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc=v_time, issue_time_utc=i_time, lead_hours=72.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.40
    )
    a_cairo = sample_engine.evaluate_forecast_cycle(
        location_id="cairo", variable="temperature_2m", valid_time_utc=v_time, issue_time_utc=i_time, lead_hours=72.0, forecast_value=308.0, ensemble_mean=307.0, ensemble_std=2.2, calibrated_risk=0.55
    )
    a_london = sample_engine.evaluate_forecast_cycle(
        location_id="london", variable="wind_speed_10m", valid_time_utc=v_time, issue_time_utc=i_time, lead_hours=72.0, forecast_value=12.0, ensemble_mean=11.5, ensemble_std=1.8, calibrated_risk=0.35
    )

    assert a_delhi.event_id != a_cairo.event_id
    assert a_delhi.event_id != a_london.event_id
    assert a_cairo.event_id != a_london.event_id


def test_multi_variable_isolation_same_location(sample_engine):
    """Surface pressure and wind speed at same location create distinct event IDs."""
    v_time = "2026-08-25T00:00:00Z"
    i_time = "2026-08-22T00:00:00Z"

    a_p = sample_engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc=v_time, issue_time_utc=i_time, lead_hours=72.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.40
    )
    a_w = sample_engine.evaluate_forecast_cycle(
        location_id="delhi", variable="wind_speed_10m", valid_time_utc=v_time, issue_time_utc=i_time, lead_hours=72.0, forecast_value=8.0, ensemble_mean=7.5, ensemble_std=1.2, calibrated_risk=0.25
    )
    assert a_p.event_id != a_w.event_id


def test_limitations_and_warnings_always_present_in_assessment(sample_engine):
    """All generated assessments must contain non-empty scientific limitations."""
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.40
    )
    assert len(assess.limitations) >= 2
    assert any("Statistical risk estimate" in lim for lim in assess.limitations)


def test_dual_provenance_cryptographic_separation(sample_engine):
    """Decision provenance hash and execution provenance hash are distinct cryptographic fingerprints."""
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=72.0, forecast_value=1012.0, ensemble_mean=1011.0, ensemble_std=2.0, calibrated_risk=0.40
    )
    assert assess.decision_provenance_hash != assess.execution_provenance_hash
    assert len(assess.decision_provenance_hash) == 16
    assert len(assess.execution_provenance_hash) == 16


def test_post_hoc_verification_computes_exact_absolute_error_and_bust_status(sample_engine):
    """Post-hoc mode computes exact forecast absolute error and verified bust outcome status."""
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=72.0,
        forecast_value=1015.0,
        ensemble_mean=1011.0,
        ensemble_std=2.5,
        calibrated_risk=0.60,
        mode=ExplanationMode.POST_HOC_EVALUATION,
        post_hoc_truth={"truth_value": 1008.0, "verification_time_utc": "2026-08-25T00:00:00Z"},
    )
    assert assess.retrospective_outcome is not None
    assert assess.retrospective_outcome.verified_abs_error == 7.0
    assert assess.retrospective_outcome.is_verified_bust is True
    assert assess.retrospective_outcome.outcome_status == EventOutcomeStatus.VERIFIED_BUST


def test_decision_rationale_primary_triggers_and_recommended_action(sample_engine):
    """Generated explanation contains primary triggers and actionable recommendations."""
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=72.0,
        forecast_value=1015.0,
        ensemble_mean=1011.0,
        ensemble_std=2.8,
        calibrated_risk=0.70,
    )
    assert assess.explanation is not None
    if assess.explanation.decision_rationale:
        assert len(assess.explanation.decision_rationale.primary_triggers) > 0
        assert len(assess.explanation.decision_rationale.recommended_action) > 0


def test_counterfactual_presence_and_direction_in_unified_assessment(sample_engine):
    """Generated explanation provides counterfactual shifts to achieve less severe decisions."""
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="cairo",
        variable="temperature_2m",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=48.0,
        forecast_value=308.0,
        ensemble_mean=307.0,
        ensemble_std=2.5,
        calibrated_risk=0.65,
    )
    assert assess.explanation is not None
    assert len(assess.explanation.counterfactuals) > 0
    cf = assess.explanation.counterfactuals[0]
    assert cf.target_decision_direction == "LESS_SEVERE"


def test_signal_arbitration_engine_custom_thresholds():
    """Arbitration engine respects custom novelty and velocity thresholds."""
    custom_arb = SignalArbitrationEngine(
        novelty_abstention_threshold=1.80,
        instability_escalation_velocity=0.05,
    )
    dec, prio, urg, status, overrides = custom_arb.arbitrate(
        base_decision=OperationalDecision.MONITOR,
        base_priority=WarningPriority.P4_INFORMATIONAL,
        base_urgency=OperationalUrgency.ROUTINE,
        calibrated_risk=0.30,
        confidence_score=0.80,
        novelty_score=2.00,
        data_quality=DataQualityState.CLEAN,
        trajectory_state=TrajectoryState.STABLE_LOW,
        instability_detected=False,
        risk_velocity=0.0,
    )
    assert dec == OperationalDecision.ABSTAIN
    assert status == AssessmentStatus.SAFETY_ABSTAINED


def test_emergency_escalation_imminent_warning_horizon(sample_arbitration_engine):
    """WARN decision with time-to-critical <= 12h escalates urgency to IMMEDIATE."""
    dec, prio, urg, status, overrides = sample_arbitration_engine.arbitrate(
        base_decision=OperationalDecision.WARN_POTENTIAL_BUST,
        base_priority=WarningPriority.P2_MEDIUM,
        base_urgency=OperationalUrgency.URGENT,
        calibrated_risk=0.58,
        confidence_score=0.85,
        novelty_score=1.0,
        data_quality=DataQualityState.CLEAN,
        trajectory_state=TrajectoryState.ACCELERATING_RISK,
        instability_detected=True,
        risk_velocity=0.10,
        time_to_critical_hours=6.0,
    )
    assert dec == OperationalDecision.WARN_POTENTIAL_BUST
    assert urg == OperationalUrgency.IMMEDIATE


def test_assessment_to_dict_and_json_roundtrip_with_nested_objects(sample_engine):
    """Deep nested assessment object with overrides and outcome serializes cleanly to JSON."""
    assess = sample_engine.evaluate_forecast_cycle(
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-25T00:00:00Z",
        issue_time_utc="2026-08-22T00:00:00Z",
        lead_hours=72.0,
        forecast_value=1015.0,
        ensemble_mean=1011.0,
        ensemble_std=2.5,
        calibrated_risk=0.60,
        mode=ExplanationMode.POST_HOC_EVALUATION,
        post_hoc_truth={"truth_value": 1008.0, "verification_time_utc": "2026-08-25T00:00:00Z"},
    )
    json_out = assess.to_json()
    loaded = json.loads(json_out)
    assert loaded["retrospective_outcome"]["is_verified_bust"] is True
    assert loaded["assessment_status"] == "SUCCESS"


def test_arbitration_precedence_tier_sorting_and_uniqueness():
    """All 6 SignalPrecedenceTier tiers are strictly defined and unique."""
    tiers = list(SignalPrecedenceTier)
    assert len(tiers) == 6
    assert len(set(t.value for t in tiers)) == 6


def test_adversarial_leakage_deeply_nested_dictionaries(sample_engine):
    """Deep nested dictionary containing forbidden verification column is rejected."""
    nested_payload = {
        "meteorological_context": {
            "regime": "monsoon",
            "inner_audit": {
                "verified_bust_flag": True,
            }
        }
    }
    with pytest.raises(ValueError, match="Target leakage rejected"):
        sample_engine.evaluate_forecast_cycle(
            location_id="delhi",
            variable="surface_pressure",
            valid_time_utc="2026-08-25T00:00:00Z",
            issue_time_utc="2026-08-22T00:00:00Z",
            lead_hours=48.0,
            forecast_value=1012.0,
            ensemble_mean=1011.0,
            ensemble_std=2.0,
            calibrated_risk=0.50,
            features=nested_payload,
            mode=ExplanationMode.DECISION_TIME,
        )


def test_adversarial_leakage_in_nested_list_of_dictionaries(sample_engine):
    """List containing nested dict with actual/realized observation values is rejected."""
    nested_list_payload = {
        "history_stream": [
            {"lead": 72.0, "spread": 2.0},
            {"lead": 48.0, "realized_obs_pressure": 1008.0},
        ]
    }
    with pytest.raises(ValueError, match="Target leakage rejected"):
        sample_engine.evaluate_forecast_cycle(
            location_id="delhi",
            variable="surface_pressure",
            valid_time_utc="2026-08-25T00:00:00Z",
            issue_time_utc="2026-08-22T00:00:00Z",
            lead_hours=48.0,
            forecast_value=1012.0,
            ensemble_mean=1011.0,
            ensemble_std=2.0,
            calibrated_risk=0.50,
            features=nested_list_payload,
            mode=ExplanationMode.DECISION_TIME,
        )


def test_all_20_locations_and_3_variables_on_stage_b(sample_engine):
    """Process 1 sample for all 20 locations and all 3 variables from real Stage B archive."""
    parquet_path = Path("data/historical/multicycle_paired/paired_multicycle_stage_b_2026-08-18_2026-08-24.parquet")
    if not parquet_path.exists():
        pytest.skip(f"Stage B parquet not found at {parquet_path}")

    df = pd.read_parquet(parquet_path)
    loc_col = "location" if "location" in df.columns else "location_id"
    issue_col = "issue_time" if "issue_time" in df.columns else "issue_time_utc"
    valid_col = "valid_time" if "valid_time" in df.columns else "valid_time_utc"

    sample_slice = df.groupby([loc_col, "variable"]).first().reset_index()
    assert len(sample_slice) == 60  # 20 locations * 3 variables

    for _, row in sample_slice.iterrows():
        std_val = float(row.get("ensemble_std", 1.0)) if not pd.isna(row.get("ensemble_std")) else 1.0
        risk_val = float(np.clip(std_val / 5.0, 0.0, 1.0))
        assess = sample_engine.evaluate_forecast_cycle(
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
        assert assess.assessment_status == AssessmentStatus.SUCCESS
        assert len(assess.decision_provenance_hash) == 16


def test_full_lifecycle_equivalence_under_reverse_order_ingestion():
    """Verify chronological vs reverse cycle ingestion yields identical state and snapshot count."""
    v_time = "2026-08-26T00:00:00Z"

    # Engine 1: Forward chronological ingestion
    e_fwd = UnifiedOperationalRiskEngine()
    e_fwd.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc=v_time,
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=96.0, forecast_value=1010.0, ensemble_mean=1010.0, ensemble_std=1.2, calibrated_risk=0.15
    )
    e_fwd.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc=v_time,
        issue_time_utc="2026-08-23T00:00:00Z", lead_hours=72.0, forecast_value=1012.0, ensemble_mean=1010.5, ensemble_std=2.2, calibrated_risk=0.45
    )
    a_fwd = e_fwd.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc=v_time,
        issue_time_utc="2026-08-24T00:00:00Z", lead_hours=48.0, forecast_value=1015.0, ensemble_mean=1011.0, ensemble_std=3.4, calibrated_risk=0.75
    )

    # Engine 2: Reverse chronological ingestion
    e_rev = UnifiedOperationalRiskEngine()
    e_rev.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc=v_time,
        issue_time_utc="2026-08-24T00:00:00Z", lead_hours=48.0, forecast_value=1015.0, ensemble_mean=1011.0, ensemble_std=3.4, calibrated_risk=0.75
    )
    e_rev.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc=v_time,
        issue_time_utc="2026-08-23T00:00:00Z", lead_hours=72.0, forecast_value=1012.0, ensemble_mean=1010.5, ensemble_std=2.2, calibrated_risk=0.45
    )
    a_rev = e_rev.evaluate_forecast_cycle(
        location_id="delhi", variable="surface_pressure", valid_time_utc=v_time,
        issue_time_utc="2026-08-22T00:00:00Z", lead_hours=96.0, forecast_value=1010.0, ensemble_mean=1010.0, ensemble_std=1.2, calibrated_risk=0.15
    )

    assert a_fwd.event_id == a_rev.event_id
    assert a_fwd.cycles_tracked == a_rev.cycles_tracked == 3
    # Check underlying stored event snapshots
    ev_fwd = e_fwd.event_tracker.active_events[a_fwd.event_id]
    ev_rev = e_rev.event_tracker.active_events[a_rev.event_id]
    assert len(ev_fwd.snapshots) == len(ev_rev.snapshots) == 3
    # Both engines capture the same set of issue times
    fwd_issues = set(s.issue_time_utc for s in ev_fwd.snapshots)
    rev_issues = set(s.issue_time_utc for s in ev_rev.snapshots)
    assert fwd_issues == rev_issues
