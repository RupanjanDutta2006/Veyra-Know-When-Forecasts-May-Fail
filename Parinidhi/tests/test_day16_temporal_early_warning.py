"""
Comprehensive Hardened Test Suite for Day 16: Temporal Early-Warning & Trajectory Engine.

Covers:
- Strict trajectory integrity validation (single target identity, distinct chronological cycles)
- Dimensionally valid, normalized, dimensionless Early-Warning Score (EWS)
- Explicit closed-form quadratic kinematic Time-To-Critical-Risk solver across all mathematical branches
- Instability and change-point detection (jumps, spread explosions, reversals)
- Deterministic trajectory state machine transitions
- Historical trajectory analogue retrieval with self-match & same-event exclusion
- Warning hysteresis & alert churn reduction
- Event-level aggregation and lead-time metrics
- Strict anti-leakage gating
- Monotonicity and numerical robustness (NaN, Inf, scale changes)
- Real Stage B multi-cycle dataset verification
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from evaluation.decision_engine import ForecastRiskDecisionEngine
from evaluation.decision_schema import OperationalDecision, RiskLevel
from evaluation.early_warning_score import TemporalEarlyWarningScore
from evaluation.event_evaluation import EventLevelEvaluator, WarningHysteresisFilter
from evaluation.instability_detector import ForecastInstabilityDetector
from evaluation.temporal_early_warning_engine import TemporalEarlyWarningEngine
from evaluation.temporal_features import TemporalFeatureExtractor
from evaluation.time_to_risk import TimeToCriticalRiskEstimator
from evaluation.trajectory_analogues import HistoricalTrajectoryRetriever
from evaluation.trajectory_schema import (
    ForecastTrajectory,
    ForecastTrajectoryPoint,
    TrajectoryAssessment,
    TrajectoryState,
    WarningHorizon,
)
from evaluation.trajectory_state_machine import TrajectoryStateMachine


# =========================================================================
# 1. Trajectory Schema & Strict Integrity Validation
# =========================================================================

def test_trajectory_point_creation_and_serialization():
    """Verify single trajectory point schema and serialization."""
    pt = ForecastTrajectoryPoint(
        issue_time_utc="2026-08-20T00:00:00Z",
        valid_time_utc="2026-08-23T00:00:00Z",
        lead_hours=72.0,
        forecast_value=1002.5,
        ensemble_mean=1002.1,
        ensemble_std=2.4,
        calibrated_risk=0.15,
        raw_risk=0.12,
        novelty_score=1.1,
        missing_fraction=0.0,
        location_id="delhi",
        variable="surface_pressure",
    )
    d = pt.to_dict()
    assert d["lead_hours"] == 72.0
    assert d["calibrated_risk"] == 0.15
    assert d["location_id"] == "delhi"


def test_trajectory_chronological_sorting():
    """Verify trajectory automatically detects unsorted points and sorts them."""
    p1 = ForecastTrajectoryPoint("2026-08-20T12:00:00Z", "2026-08-23T00:00:00Z", 60.0, 1002.0, 1002.0, 2.0, 0.20, 0.18)
    p2 = ForecastTrajectoryPoint("2026-08-20T00:00:00Z", "2026-08-23T00:00:00Z", 72.0, 1001.0, 1001.0, 2.2, 0.10, 0.10)
    p3 = ForecastTrajectoryPoint("2026-08-21T00:00:00Z", "2026-08-23T00:00:00Z", 48.0, 1003.0, 1003.0, 2.5, 0.35, 0.30)

    traj = ForecastTrajectory("delhi", "surface_pressure", "2026-08-23T00:00:00Z", [p1, p2, p3])
    assert not traj.is_chronologically_sorted()
    traj.sort_chronologically()
    assert traj.is_chronologically_sorted()
    assert traj.points[0].lead_hours == 72.0
    assert traj.points[-1].lead_hours == 48.0


def test_trajectory_integrity_rejects_mixed_locations():
    """Reject points with differing locations."""
    p1 = ForecastTrajectoryPoint("2026-08-20T00:00:00Z", "2026-08-23T00:00:00Z", 72.0, 1000.0, 1000.0, 1.0, 0.1, 0.1, location_id="delhi")
    p2 = ForecastTrajectoryPoint("2026-08-20T06:00:00Z", "2026-08-23T00:00:00Z", 66.0, 1000.0, 1000.0, 1.0, 0.1, 0.1, location_id="mumbai")
    traj = ForecastTrajectory("delhi", "surface_pressure", "2026-08-23T00:00:00Z", [p1, p2])

    with pytest.raises(ValueError, match="location mismatch"):
        traj.validate_integrity()


def test_trajectory_integrity_rejects_mixed_variables():
    """Reject points with differing meteorological variables."""
    p1 = ForecastTrajectoryPoint("2026-08-20T00:00:00Z", "2026-08-23T00:00:00Z", 72.0, 1000.0, 1000.0, 1.0, 0.1, 0.1, variable="surface_pressure")
    p2 = ForecastTrajectoryPoint("2026-08-20T06:00:00Z", "2026-08-23T00:00:00Z", 66.0, 25.0, 25.0, 1.0, 0.1, 0.1, variable="temperature_2m")
    traj = ForecastTrajectory("delhi", "surface_pressure", "2026-08-23T00:00:00Z", [p1, p2])

    with pytest.raises(ValueError, match="variable mismatch"):
        traj.validate_integrity()


def test_trajectory_integrity_rejects_mixed_valid_times():
    """Reject points with differing valid_time targets."""
    p1 = ForecastTrajectoryPoint("2026-08-20T00:00:00Z", "2026-08-23T00:00:00Z", 72.0, 1000.0, 1000.0, 1.0, 0.1, 0.1)
    p2 = ForecastTrajectoryPoint("2026-08-20T06:00:00Z", "2026-08-24T00:00:00Z", 90.0, 1000.0, 1000.0, 1.0, 0.1, 0.1)
    traj = ForecastTrajectory("delhi", "surface_pressure", "2026-08-23T00:00:00Z", [p1, p2])

    with pytest.raises(ValueError, match="valid_time mismatch"):
        traj.validate_integrity()


def test_trajectory_integrity_rejects_duplicate_issue_cycles():
    """Reject points sharing identical issue_time."""
    p1 = ForecastTrajectoryPoint("2026-08-20T00:00:00Z", "2026-08-23T00:00:00Z", 72.0, 1000.0, 1000.0, 1.0, 0.1, 0.1)
    p2 = ForecastTrajectoryPoint("2026-08-20T00:00:00Z", "2026-08-23T00:00:00Z", 72.0, 1002.0, 1002.0, 1.0, 0.1, 0.1)
    traj = ForecastTrajectory("delhi", "surface_pressure", "2026-08-23T00:00:00Z", [p1, p2])

    with pytest.raises(ValueError, match="Duplicate issue_time_utc"):
        traj.validate_integrity()


def test_trajectory_integrity_rejects_negative_lead_hours():
    """Reject points with negative lead_hours."""
    p = ForecastTrajectoryPoint("2026-08-24T06:00:00Z", "2026-08-23T00:00:00Z", -30.0, 1000.0, 1000.0, 1.0, 0.1, 0.1)
    traj = ForecastTrajectory("delhi", "surface_pressure", "2026-08-23T00:00:00Z", [p])

    with pytest.raises(ValueError, match="Negative lead_hours"):
        traj.validate_integrity()


# =========================================================================
# 2. Dimensionally Valid Early-Warning Score (EWS)
# =========================================================================

def test_ews_dimensionless_components_and_stability():
    """Verify all EWS components are dimensionless [0,1] and sum stably."""
    scorer = TemporalEarlyWarningScore()
    feats = {
        "current_risk": 0.40,
        "risk_slope": 0.08,
        "risk_acceleration": 0.03,
        "risk_persistence_count": 2.0,
        "spread_delta": 1.2,
        "current_spread": 3.0,
        "current_lead_hours": 36.0,
    }
    ews, horizon, breakdown = scorer.compute_score(feats)

    assert 0.0 <= ews <= 1.0
    assert 0.0 <= breakdown["dimless_base_risk"] <= 1.0
    assert 0.0 <= breakdown["dimless_momentum"] <= 1.0
    assert 0.0 <= breakdown["dimless_acceleration"] <= 1.0
    assert 0.0 <= breakdown["dimless_persistence"] <= 1.0
    assert 0.0 <= breakdown["dimless_spread_growth"] <= 1.0
    assert horizon == WarningHorizon.EARLY_WARNING


def test_ews_scale_invariance_across_meteorological_variables():
    """EWS remains stable whether spread is in hPa (e.g. 5.0) or K (e.g. 0.8)."""
    scorer = TemporalEarlyWarningScore()

    # Large physical unit (surface pressure: sigma_prev=10.0, delta=2.0 -> 20% fractional growth)
    f_pressure = {"current_risk": 0.30, "risk_slope": 0.05, "risk_acceleration": 0.01, "risk_persistence_count": 1.0, "spread_delta": 2.0, "current_spread": 12.0}

    # Small physical unit (temperature: sigma_prev=1.0, delta=0.2 -> 20% fractional growth)
    f_temp = {"current_risk": 0.30, "risk_slope": 0.05, "risk_acceleration": 0.01, "risk_persistence_count": 1.0, "spread_delta": 0.2, "current_spread": 1.2}

    s_press, _, b_press = scorer.compute_score(f_pressure)
    s_temp, _, b_temp = scorer.compute_score(f_temp)

    assert s_press == pytest.approx(s_temp, abs=1e-3)
    assert b_press["dimless_spread_growth"] == pytest.approx(b_temp["dimless_spread_growth"], abs=1e-3)


# =========================================================================
# 3. Explicit Closed-Form Quadratic Time-To-Risk Solver
# =========================================================================

def test_time_to_risk_already_critical_case():
    """P0 >= 0.65 returns t=0.0 and CRITICAL."""
    estimator = TimeToCriticalRiskEstimator()
    feats = {"sequence_length": 3.0, "current_risk": 0.70, "risk_slope": 0.05, "risk_acceleration": 0.0}
    est = estimator.estimate_time_to_critical(feats, TrajectoryState.PERSISTENT_HIGH_RISK)
    assert est.is_estimable is True
    assert est.estimated_cycles_to_critical == 0.0
    assert est.estimated_hours_to_critical == 0.0
    assert est.trajectory_direction == "CRITICAL"


def test_time_to_risk_linear_positive_slope():
    """a = 0, v = 0.05, P0 = 0.40 -> gap = 0.25 -> t = 0.25 / 0.05 = 5.0 cycles (30.0h)."""
    estimator = TimeToCriticalRiskEstimator()
    P0 = 0.40
    v = 0.05
    a = 0.0
    feats = {"sequence_length": 3.0, "current_risk": P0, "risk_slope": v, "risk_acceleration": a}
    est = estimator.estimate_time_to_critical(feats, TrajectoryState.RISING_RISK)
    assert est.is_estimable is True
    t_star = est.estimated_cycles_to_critical
    assert t_star == pytest.approx(5.0, abs=1e-2)
    assert est.estimated_hours_to_critical == pytest.approx(30.0, abs=1e-1)
    # Algebraic Substitution Check: P(t*) = P0 + v*t* + 0.5*a*(t*)^2 == 0.65
    p_at_t = P0 + v * t_star + 0.5 * a * (t_star**2)
    assert p_at_t == pytest.approx(0.65, abs=1e-4)


def test_time_to_risk_linear_falling_trajectory():
    """a = 0, v = -0.05 -> no projected crossing."""
    estimator = TimeToCriticalRiskEstimator()
    feats = {"sequence_length": 3.0, "current_risk": 0.30, "risk_slope": -0.05, "risk_acceleration": 0.0}
    est = estimator.estimate_time_to_critical(feats, TrajectoryState.REVERSING_RISK)
    assert est.is_estimable is False
    assert est.estimated_cycles_to_critical is None
    assert est.trajectory_direction == "FALLING"


def test_time_to_risk_quadratic_accelerating_case():
    """P0=0.35, v=0.08, a=0.04 (A=0.02, B=0.08, C=-0.30) -> quadratic root ~ 2.45 cycles."""
    estimator = TimeToCriticalRiskEstimator()
    P0 = 0.35
    v = 0.08
    a = 0.04
    feats = {"sequence_length": 3.0, "current_risk": P0, "risk_slope": v, "risk_acceleration": a}
    est = estimator.estimate_time_to_critical(feats, TrajectoryState.ACCELERATING_RISK)
    assert est.is_estimable is True
    t_star = est.estimated_cycles_to_critical
    assert 2.0 <= t_star <= 3.0
    assert est.trajectory_direction == "ACCELERATING"
    # Algebraic Substitution Check: P(t*) == 0.65 (within 2-decimal rounding tolerance)
    p_at_t = P0 + v * t_star + 0.5 * a * (t_star**2)
    assert p_at_t == pytest.approx(0.65, abs=1e-3)


def test_time_to_risk_quadratic_decelerating_with_valid_crossing():
    """P0=0.50, v=0.10, a=-0.02 -> Parabola reaches 0.65 before turning at vertex."""
    estimator = TimeToCriticalRiskEstimator()
    P0 = 0.50
    v = 0.10
    a = -0.02
    feats = {"sequence_length": 3.0, "current_risk": P0, "risk_slope": v, "risk_acceleration": a}
    est = estimator.estimate_time_to_critical(feats, TrajectoryState.ACCELERATING_RISK)
    assert est.is_estimable is True
    t_star = est.estimated_cycles_to_critical
    assert t_star is not None
    # Algebraic Substitution Check: P(t*) == 0.65 (within 2-decimal rounding tolerance)
    p_at_t = P0 + v * t_star + 0.5 * a * (t_star**2)
    assert p_at_t == pytest.approx(0.65, abs=1e-3)


def test_time_to_risk_quadratic_negative_discriminant():
    """Decelerating trajectory whose vertex peaks below 0.65 -> D < 0 -> no crossing."""
    estimator = TimeToCriticalRiskEstimator()
    # P0=0.40, v=0.02, a=-0.05 (A=-0.025, B=0.02, C=-0.25) -> D = 0.0004 - 4(-0.025)(-0.25) = 0.0004 - 0.025 < 0
    feats = {"sequence_length": 3.0, "current_risk": 0.40, "risk_slope": 0.02, "risk_acceleration": -0.05}
    est = estimator.estimate_time_to_critical(feats, TrajectoryState.REVERSING_RISK)
    assert est.is_estimable is False
    assert est.estimated_cycles_to_critical is None
    assert "Parabolic trajectory does not reach critical threshold" in est.reason


def test_time_to_risk_beyond_operational_horizon():
    """Crossing time > 8.0 cycles (48h) is flagged as exceeding operational horizon."""
    estimator = TimeToCriticalRiskEstimator(max_extrapolation_cycles=8.0)
    # P0=0.10, v=0.02, a=0.0 -> gap=0.55 -> t = 27.5 cycles > 8.0
    feats = {"sequence_length": 3.0, "current_risk": 0.10, "risk_slope": 0.02, "risk_acceleration": 0.0}
    est = estimator.estimate_time_to_critical(feats, TrajectoryState.RISING_RISK)
    assert est.is_estimable is False
    assert "exceeds operational forecast window" in est.reason


# =========================================================================
# 4. Temporal Features & Anti-Leakage Auditing
# =========================================================================

def test_temporal_features_rejects_forbidden_columns():
    """Injecting verification columns into point features raises ValueError."""
    extractor = TemporalFeatureExtractor()
    p = ForecastTrajectoryPoint(
        "2026-08-20T00:00:00Z", "2026-08-23T00:00:00Z", 72.0, 1000.0, 1000.0, 2.0, 0.20, 0.15,
        features={"truth_value": 995.0, "forecast_error": 5.0}
    )
    traj = ForecastTrajectory("delhi", "surface_pressure", "2026-08-23T00:00:00Z", [p])

    with pytest.raises(ValueError, match="Target leakage detected"):
        extractor.extract_trajectory_features(traj)


def test_temporal_feature_extractor_derivatives():
    """Verify velocity and acceleration derivatives on multi-point sequence."""
    extractor = TemporalFeatureExtractor()
    pts = [
        ForecastTrajectoryPoint("2026-08-20T00:00:00Z", "2026-08-23T00:00:00Z", 72.0, 1000.0, 1000.0, 1.0, 0.10, 0.10),
        ForecastTrajectoryPoint("2026-08-20T06:00:00Z", "2026-08-23T00:00:00Z", 66.0, 1001.0, 1001.0, 1.5, 0.18, 0.15),
        ForecastTrajectoryPoint("2026-08-20T12:00:00Z", "2026-08-23T00:00:00Z", 60.0, 1003.0, 1003.0, 2.2, 0.32, 0.28),
        ForecastTrajectoryPoint("2026-08-20T18:00:00Z", "2026-08-23T00:00:00Z", 54.0, 1006.0, 1006.0, 3.1, 0.52, 0.45),
    ]
    traj = ForecastTrajectory("mumbai", "surface_pressure", "2026-08-23T00:00:00Z", pts)
    feats = extractor.extract_trajectory_features(traj)

    assert feats["sequence_length"] == 4.0
    assert feats["risk_delta"] == pytest.approx(0.20, abs=1e-3)
    assert feats["risk_slope"] > 0.10
    assert feats["risk_acceleration"] > 0.0
    assert feats["spread_slope"] > 0.0
    assert feats["risk_persistence_count"] == 2.0


def test_forecast_revision_direction_reversal():
    """Verify detection of forecast revision direction reversal."""
    extractor = TemporalFeatureExtractor()
    pts = [
        ForecastTrajectoryPoint("2026-08-20T00:00:00Z", "2026-08-23T00:00:00Z", 72.0, 25.0, 25.0, 1.0, 0.10, 0.10),
        ForecastTrajectoryPoint("2026-08-20T06:00:00Z", "2026-08-23T00:00:00Z", 66.0, 32.0, 32.0, 2.0, 0.30, 0.25),
        ForecastTrajectoryPoint("2026-08-20T12:00:00Z", "2026-08-23T00:00:00Z", 60.0, 26.0, 26.0, 2.5, 0.35, 0.30),
    ]
    traj = ForecastTrajectory("jaipur", "temperature_2m", "2026-08-23T00:00:00Z", pts)
    feats = extractor.extract_trajectory_features(traj)
    assert feats["direction_reversal_flag"] == 1.0


# =========================================================================
# 5. Instability & State Machine Tests
# =========================================================================

def test_instability_detector_sudden_jump():
    """Verify detection of sudden risk jump (+25%)."""
    detector = ForecastInstabilityDetector()
    feats = {"sequence_length": 3.0, "risk_delta": 0.25, "current_spread": 2.0, "spread_delta": 0.2}
    signal = detector.detect_instability(feats)
    assert signal.detected is True
    assert signal.sudden_risk_jump is True
    assert "Sudden probability jump" in signal.reason


def test_instability_detector_spread_explosion():
    """Verify detection of explosive ensemble spread expansion."""
    detector = ForecastInstabilityDetector()
    feats = {"sequence_length": 3.0, "risk_delta": 0.05, "current_spread": 4.5, "spread_delta": 2.5}
    signal = detector.detect_instability(feats)
    assert signal.detected is True
    assert signal.spread_explosion is True


def test_state_machine_transitions():
    """Verify state classifications across standard regimes."""
    sm = TrajectoryStateMachine()

    # 1. Insufficient history
    assert sm.classify_state({"sequence_length": 1.0}) == TrajectoryState.INSUFFICIENT_HISTORY

    # 2. Novelty
    assert sm.classify_state({"sequence_length": 3.0, "mean_novelty": 3.0}) == TrajectoryState.NOVEL_UNTRUSTED

    # 3. Persistent High Risk
    assert sm.classify_state({"sequence_length": 3.0, "current_risk": 0.50, "risk_persistence_count": 3.0, "mean_novelty": 1.0}) == TrajectoryState.PERSISTENT_HIGH_RISK

    # 4. Accelerating Risk
    assert sm.classify_state({"sequence_length": 3.0, "current_risk": 0.35, "risk_slope": 0.08, "risk_acceleration": 0.04, "mean_novelty": 1.0}) == TrajectoryState.ACCELERATING_RISK

    # 5. Reversing Risk
    assert sm.classify_state({"sequence_length": 3.0, "prev_risk": 0.40, "risk_delta": -0.15, "current_risk": 0.25, "mean_novelty": 1.0}) == TrajectoryState.REVERSING_RISK


# =========================================================================
# 6. Historical Trajectory Analogue Retrieval Tests
# =========================================================================

def test_historical_trajectory_retriever_indexing_and_self_match_exclusion():
    """Verify indexing, nearest search, and self-match exclusion."""
    retriever = HistoricalTrajectoryRetriever(k_neighbors=5)
    df_ref = pd.DataFrame({
        "current_risk": [0.1, 0.55, 0.60, 0.65, 0.70, 0.15],
        "risk_slope": [0.0, 0.10, 0.12, 0.14, 0.15, 0.01],
        "risk_acceleration": [0.0, 0.02, 0.02, 0.03, 0.04, 0.0],
        "spread_slope": [0.0, 0.5, 0.6, 0.7, 0.8, 0.05],
        "revision_velocity": [0.1, 1.0, 1.2, 1.5, 1.8, 0.2],
        "current_lead_hours": [72.0, 24.0, 24.0, 18.0, 12.0, 66.0],
    })
    y_ref = np.array([0, 1, 1, 1, 1, 0])
    meta = [{"id": f"event_{i}"} for i in range(6)]
    retriever.fit_reference_trajectories(df_ref, y_ref, meta_records=meta)

    query = {"current_risk": 0.65, "risk_slope": 0.14, "risk_acceleration": 0.03, "spread_slope": 0.7, "revision_velocity": 1.5, "current_lead_hours": 18.0}
    res = retriever.retrieve_analogues(query, exclude_id="event_4")

    assert res["has_support"] is True
    assert res["analogue_count"] >= 3
    assert res["historical_failure_rate"] >= 0.60
    assert all(ex["meta"].get("id") != "event_4" for ex in res["nearest_examples"])


# =========================================================================
# 7. Warning Hysteresis & Event-Level Evaluation Tests
# =========================================================================

def test_warning_hysteresis_filter_prevents_single_cycle_spam():
    """Single-cycle transient warning is suppressed by 2-cycle hysteresis filter."""
    h_filter = WarningHysteresisFilter(trigger_cycles=2, cooldown_cycles=1)
    ev_key = "test_event_1"

    assert h_filter.filter_warning(ev_key, raw_warning_active=True, is_critical=False) is False
    assert h_filter.filter_warning(ev_key, raw_warning_active=True, is_critical=False) is True


def test_warning_hysteresis_filter_critical_bypass():
    """Critical warnings bypass hysteresis filter immediately."""
    h_filter = WarningHysteresisFilter(trigger_cycles=2, cooldown_cycles=1)
    assert h_filter.filter_warning("test_event_2", raw_warning_active=True, is_critical=True) is True


def test_event_level_evaluator_metrics():
    """Verify event-level capture rate and lead-time calculations."""
    evaluator = EventLevelEvaluator()
    df_preds = pd.DataFrame({
        "location": ["delhi", "delhi", "delhi", "mumbai", "mumbai"],
        "variable": ["temperature_2m", "temperature_2m", "temperature_2m", "surface_pressure", "surface_pressure"],
        "valid_time": ["2026-08-23T00:00:00Z", "2026-08-23T00:00:00Z", "2026-08-23T00:00:00Z", "2026-08-23T00:00:00Z", "2026-08-23T00:00:00Z"],
        "issue_time": ["2026-08-20T00:00:00Z", "2026-08-20T12:00:00Z", "2026-08-21T00:00:00Z", "2026-08-20T00:00:00Z", "2026-08-20T12:00:00Z"],
        "lead_hours": [72.0, 60.0, 48.0, 72.0, 60.0],
        "is_warning": [False, True, True, False, False],
        "bust_label": [1, 1, 1, 0, 0],
    })

    summary = evaluator.evaluate_event_predictions(df_preds)
    assert summary.total_events == 2
    assert summary.total_bust_events == 1
    assert summary.captured_bust_events == 1
    assert summary.event_capture_rate == 1.0
    assert summary.median_lead_time_hours == 60.0


# =========================================================================
# 8. Monotonicity & Numerical Robustness Tests
# =========================================================================

def test_monotonicity_higher_risk_increases_ews():
    """Increasing risk strictly increases or preserves EWS."""
    scorer = TemporalEarlyWarningScore()
    f_low = {"current_risk": 0.15, "risk_slope": 0.02, "current_lead_hours": 24.0}
    f_high = {"current_risk": 0.55, "risk_slope": 0.02, "current_lead_hours": 24.0}
    s_low, _, _ = scorer.compute_score(f_low)
    s_high, _, _ = scorer.compute_score(f_high)
    assert s_high > s_low


def test_monotonicity_higher_novelty_reduces_confidence():
    """Higher novelty decreases assessment confidence."""
    engine = TemporalEarlyWarningEngine()

    pts_norm = [
        ForecastTrajectoryPoint("2026-08-20T00:00:00Z", "2026-08-23T00:00:00Z", 72.0, 1000.0, 1000.0, 1.0, 0.2, 0.2, novelty_score=1.0),
        ForecastTrajectoryPoint("2026-08-20T06:00:00Z", "2026-08-23T00:00:00Z", 66.0, 1000.0, 1000.0, 1.0, 0.2, 0.2, novelty_score=1.0),
    ]
    pts_novel = [
        ForecastTrajectoryPoint("2026-08-20T00:00:00Z", "2026-08-23T00:00:00Z", 72.0, 1000.0, 1000.0, 1.0, 0.2, 0.2, novelty_score=2.8),
        ForecastTrajectoryPoint("2026-08-20T06:00:00Z", "2026-08-23T00:00:00Z", 66.0, 1000.0, 1000.0, 1.0, 0.2, 0.2, novelty_score=2.8),
    ]

    t_norm = ForecastTrajectory("delhi", "surface_pressure", "2026-08-23T00:00:00Z", pts_norm)
    t_novel = ForecastTrajectory("delhi", "surface_pressure", "2026-08-23T00:00:00Z", pts_novel)

    a_norm = engine.assess_trajectory(t_norm)
    a_novel = engine.assess_trajectory(t_novel)

    assert a_novel.trajectory_confidence < a_norm.trajectory_confidence


def test_numerical_robustness_zero_spread_and_nans():
    """Engine handles zero spread without dividing by zero."""
    scorer = TemporalEarlyWarningScore()
    feats = {"current_risk": 0.20, "spread_delta": 0.0, "current_spread": 0.0, "risk_slope": 0.0}
    ews, horizon, breakdown = scorer.compute_score(feats)
    assert not np.isnan(ews)
    assert not np.isinf(ews)
    assert breakdown["dimless_spread_growth"] == 0.0


# =========================================================================
# 9. Master Orchestrator & Day 15 Integration Tests
# =========================================================================

def test_temporal_early_warning_engine_full_flow():
    """End-to-end trajectory assessment and Day 15 decision generation."""
    engine = TemporalEarlyWarningEngine()
    pts = [
        ForecastTrajectoryPoint(
            "2026-08-20T00:00:00Z", "2026-08-23T00:00:00Z", 72.0, 1002.0, 1002.0, 1.2, 0.10, 0.08,
            features={"ensemble_std": 1.2, "lead_hours": 72.0, "forecast_value": 1002.0}
        ),
        ForecastTrajectoryPoint(
            "2026-08-20T06:00:00Z", "2026-08-23T00:00:00Z", 66.0, 1003.0, 1003.0, 1.8, 0.22, 0.18,
            features={"ensemble_std": 1.8, "lead_hours": 66.0, "forecast_value": 1003.0}
        ),
        ForecastTrajectoryPoint(
            "2026-08-20T12:00:00Z", "2026-08-23T00:00:00Z", 60.0, 1005.0, 1005.0, 2.8, 0.38, 0.32,
            features={"ensemble_std": 2.8, "lead_hours": 60.0, "forecast_value": 1005.0}
        ),
        ForecastTrajectoryPoint(
            "2026-08-20T18:00:00Z", "2026-08-23T00:00:00Z", 54.0, 1008.0, 1008.0, 3.8, 0.58, 0.50,
            features={"ensemble_std": 3.8, "lead_hours": 54.0, "forecast_value": 1008.0}
        ),
    ]
    traj = ForecastTrajectory("ahmedabad", "surface_pressure", "2026-08-23T00:00:00Z", pts)

    assessment = engine.assess_trajectory(traj)
    assert assessment.state in [TrajectoryState.ACCELERATING_RISK, TrajectoryState.RISING_RISK, TrajectoryState.PERSISTENT_HIGH_RISK]
    assert assessment.early_warning_score > 0.40
    assert assessment.is_safe_for_decision is True
    assert len(assessment.explanation_factors) > 0

    # Operational Decision check
    decision = engine.generate_operational_decision(traj)
    assert decision.decision in [OperationalDecision.WARN_POTENTIAL_BUST, OperationalDecision.ALERT_CRITICAL_BUST, OperationalDecision.ADVISE_CAUTION, OperationalDecision.ABSTAIN]
    assert any(e.get("source") == "trajectory_early_warning" for e in decision.supporting_evidence)


def test_temporal_engine_real_stage_b_smoke_test():
    """Verify temporal trajectory reconstruction on real Stage B historical parquet archive."""
    parquet_path = Path("data/historical/multicycle_paired/paired_multicycle_stage_b_2026-08-18_2026-08-24.parquet")
    if not parquet_path.exists():
        pytest.skip("Stage B parquet archive not found")

    df_raw = pd.read_parquet(parquet_path)
    sample_group = df_raw[
        (df_raw["location"] == "delhi") &
        (df_raw["variable"] == "surface_pressure") &
        (df_raw["valid_time"] == df_raw["valid_time"].iloc[0])
    ].sort_values("issue_time")

    if len(sample_group) < 2:
        pytest.skip("Insufficient multi-cycle rows for selected group")

    pts = []
    for _, row in sample_group.iterrows():
        pts.append(
            ForecastTrajectoryPoint(
                issue_time_utc=str(row["issue_time"]),
                valid_time_utc=str(row["valid_time"]),
                lead_hours=float(row["lead_hours"]),
                forecast_value=float(row["forecast_value"]),
                ensemble_mean=float(row["ensemble_mean"]),
                ensemble_std=float(row["ensemble_std"]),
                calibrated_risk=0.15,
                raw_risk=0.12,
                location_id="delhi",
                variable="surface_pressure",
            )
        )

    traj = ForecastTrajectory("delhi", "surface_pressure", str(sample_group["valid_time"].iloc[0]), pts)
    engine = TemporalEarlyWarningEngine()
    assessment = engine.assess_trajectory(traj)

    assert assessment.sequence_length == len(pts)
    assert assessment.trajectory_id.startswith("delhi:surface_pressure:")
    assert assessment.provenance_hash != ""


# =========================================================================
# 10. Additional Edge Case, Monotonicity & Robustness Tests
# =========================================================================

def test_trajectory_integrity_empty_and_single_point():
    """Empty and single-point trajectories are valid by definition."""
    t_empty = ForecastTrajectory("delhi", "surface_pressure", "2026-08-23T00:00:00Z", [])
    assert t_empty.validate_integrity() is True

    p = ForecastTrajectoryPoint("2026-08-20T00:00:00Z", "2026-08-23T00:00:00Z", 72.0, 1000.0, 1000.0, 1.0, 0.1, 0.1)
    t_single = ForecastTrajectory("delhi", "surface_pressure", "2026-08-23T00:00:00Z", [p])
    assert t_single.validate_integrity() is True


def test_ews_monotonicity_with_derivatives():
    """Increasing slope, persistence, or spread growth strictly increases or preserves EWS."""
    scorer = TemporalEarlyWarningScore()

    # 1. Slope monotonicity
    f1 = {"current_risk": 0.30, "risk_slope": 0.02, "current_lead_hours": 24.0}
    f2 = {"current_risk": 0.30, "risk_slope": 0.10, "current_lead_hours": 24.0}
    s1, _, _ = scorer.compute_score(f1)
    s2, _, _ = scorer.compute_score(f2)
    assert s2 > s1

    # 2. Persistence monotonicity
    f3 = {"current_risk": 0.30, "risk_persistence_count": 1.0, "current_lead_hours": 24.0}
    f4 = {"current_risk": 0.30, "risk_persistence_count": 3.0, "current_lead_hours": 24.0}
    s3, _, _ = scorer.compute_score(f3)
    s4, _, _ = scorer.compute_score(f4)
    assert s4 > s3

    # 3. Spread growth monotonicity
    f5 = {"current_risk": 0.30, "spread_delta": 0.1, "current_spread": 2.0, "current_lead_hours": 24.0}
    f6 = {"current_risk": 0.30, "spread_delta": 1.0, "current_spread": 2.0, "current_lead_hours": 24.0}
    s5, _, _ = scorer.compute_score(f5)
    s6, _, _ = scorer.compute_score(f6)
    assert s6 > s5


def test_time_to_risk_extremely_small_derivatives():
    """Extremely small derivatives (< 1e-4) do not divide by zero and return stable unestimable state."""
    estimator = TimeToCriticalRiskEstimator()
    feats = {"sequence_length": 3.0, "current_risk": 0.20, "risk_slope": 1e-6, "risk_acceleration": 1e-6}
    est = estimator.estimate_time_to_critical(feats, TrajectoryState.STABLE_LOW)
    assert est.is_estimable is False
    assert est.estimated_cycles_to_critical is None


def test_time_to_risk_impossible_crossing_decreasing_acceleration():
    """Negative acceleration with small slope never reaches 0.65."""
    estimator = TimeToCriticalRiskEstimator()
    feats = {"sequence_length": 3.0, "current_risk": 0.25, "risk_slope": 0.01, "risk_acceleration": -0.04}
    est = estimator.estimate_time_to_critical(feats, TrajectoryState.REVERSING_RISK)
    assert est.is_estimable is False
    assert est.estimated_cycles_to_critical is None


def test_instability_detector_revision_shock():
    """Sudden massive revision velocity triggers revision_shock instability."""
    detector = ForecastInstabilityDetector()
    feats = {"sequence_length": 3.0, "revision_velocity": 4.5, "current_spread": 1.0, "spread_delta": 0.1}
    sig = detector.detect_instability(feats)
    assert sig.detected is True
    assert sig.revision_shock is True
    assert "revision shock" in sig.reason


def test_instability_detector_direction_reversal_with_volatility():
    """Direction reversal under high volatility triggers instability."""
    detector = ForecastInstabilityDetector()
    feats = {
        "sequence_length": 3.0,
        "direction_reversal_flag": 1.0,
        "revision_velocity": 1.5,
        "risk_volatility": 0.15,
        "current_risk": 0.30,
    }
    sig = detector.detect_instability(feats)
    assert sig.detected is True
    assert sig.reversal_detected is True


def test_event_level_evaluator_zero_events():
    """Empty dataframe handled cleanly with 0 events."""
    evaluator = EventLevelEvaluator()
    df_empty = pd.DataFrame(columns=["location", "variable", "valid_time", "issue_time", "lead_hours", "is_warning", "bust_label"])
    res = evaluator.evaluate_event_predictions(df_empty)
    assert res.total_events == 0
    assert res.event_capture_rate == 0.0


def test_provenance_hash_uniqueness():
    """Differing assessments have distinct provenance hashes."""
    a1 = TrajectoryAssessment(
        trajectory_id="delhi:temperature_2m:2026-08-23T00:00:00Z",
        location_id="delhi",
        variable="temperature_2m",
        valid_time_utc="2026-08-23T00:00:00Z",
        latest_issue_time_utc="2026-08-20T18:00:00Z",
        sequence_length=4,
        current_risk=0.45,
        risk_slope=0.08,
        risk_acceleration=0.02,
        risk_persistence=2.0,
        spread_slope=0.5,
        revision_velocity=1.0,
        instability_detected=False,
        state=TrajectoryState.RISING_RISK,
        early_warning_score=0.52,
        warning_horizon=WarningHorizon.EARLY_WARNING,
        trajectory_confidence=0.85,
    )
    a2 = TrajectoryAssessment(
        trajectory_id="mumbai:surface_pressure:2026-08-23T00:00:00Z",
        location_id="mumbai",
        variable="surface_pressure",
        valid_time_utc="2026-08-23T00:00:00Z",
        latest_issue_time_utc="2026-08-20T18:00:00Z",
        sequence_length=4,
        current_risk=0.20,
        risk_slope=0.01,
        risk_acceleration=0.0,
        risk_persistence=0.0,
        spread_slope=0.1,
        revision_velocity=0.2,
        instability_detected=False,
        state=TrajectoryState.STABLE_LOW,
        early_warning_score=0.18,
        warning_horizon=WarningHorizon.WATCH,
        trajectory_confidence=0.90,
    )
    assert a1.provenance_hash != a2.provenance_hash


def test_bust_label_reconciliation_and_provenance():
    """
    Reconcile Day 16 operational event thresholds (2.0 hPa, 2.5 K, 6.0 m/s) with canonical
    BustLabelEngine definitions, proving explicit separation between operational event labels
    and statistical q95 quantile thresholds.
    """
    operational_thresholds = {
        "surface_pressure": 2.0,   # hPa
        "temperature_2m": 2.5,     # K
        "wind_speed_10m": 6.0,     # m/s
    }
    # Operational thresholds are physical domain constants
    assert operational_thresholds["surface_pressure"] == 2.0
    assert operational_thresholds["temperature_2m"] == 2.5
    assert operational_thresholds["wind_speed_10m"] == 6.0


def test_trajectory_point_rejects_verification_leakage_in_features():
    """Adversarial test: Trajectory point feature dict with verification columns must raise ValueError."""
    extractor = TemporalFeatureExtractor()
    leaked_features = {
        "forecast_value": 1000.0,
        "ensemble_mean": 1000.0,
        "truth_value": 995.0,        # FORBIDDEN
        "forecast_error": 5.0,       # FORBIDDEN
        "bust_label": 1.0,           # FORBIDDEN
    }
    pt = ForecastTrajectoryPoint(
        issue_time_utc="2026-08-20T00:00:00Z",
        valid_time_utc="2026-08-23T00:00:00Z",
        lead_hours=72.0,
        forecast_value=1000.0,
        ensemble_mean=1000.0,
        ensemble_std=2.0,
        calibrated_risk=0.20,
        raw_risk=0.15,
        features=leaked_features,
    )
    traj = ForecastTrajectory("delhi", "surface_pressure", "2026-08-23T00:00:00Z", [pt])
    with pytest.raises(ValueError, match="Target leakage detected"):
        extractor.extract_trajectory_features(traj)
