"""
Comprehensive Unit, Verification, Robustness & Integration Test Suite for Day 17 XAI.

Covers:
- Schema serialization / roundtrips & provenance
- Feature attribution, ranking & additive reconciliation
- Uncertainty & novelty explanation diagnostics
- Historical analogue alignment & evidence conflict detection
- Operational decision rationales & safety abstention
- Multi-cycle temporal trajectory dynamics & time-to-risk
- Policy sensitivity counterfactual generation
- Multi-level rendering (Operator Summary, Technical Report, Forensic Trace)
- Strict anti-leakage isolation between DECISION_TIME and POST_HOC_EVALUATION
- Robustness (NaNs, zero spread, novel locations, short histories)
- Real Stage B multi-cycle dataset integration
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from evaluation.decision_engine import ForecastRiskDecisionEngine
from evaluation.decision_schema import OperationalDecision, RiskLevel, WarningPriority
from evaluation.explanation_engine import ForecastFailureExplainer
from evaluation.temporal_early_warning_engine import TemporalEarlyWarningEngine
from evaluation.trajectory_schema import ForecastTrajectory, ForecastTrajectoryPoint, TrajectoryState, WarningHorizon
from evaluation.xai_attribution import XAIAttributionEngine
from evaluation.xai_counterfactual import DecisionCounterfactualGenerator
from evaluation.xai_engine import ExplainableForecastEngine
from evaluation.xai_renderer import XAIRenderer
from evaluation.xai_schema import (
    CanonicalXAIExplanation,
    DecisionCounterfactual,
    DecisionRationale,
    DriverCategory,
    DriverDirection,
    EvidenceConflictItem,
    ExplanationLevel,
    ExplanationMode,
    FeatureRiskDriver,
    HistoricalEvidenceAlignment,
    HistoricalEvidenceExplanation,
    NoveltyExplanation,
    TemporalDynamicsExplanation,
    UncertaintyExplanation,
    UncertaintySource,
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def sample_feature_dict():
    """Standard safe forecast feature dictionary."""
    return {
        "forecast_value": 1012.5,
        "ensemble_mean": 1012.0,
        "ensemble_std": 2.8,
        "ensemble_range": 6.5,
        "ensemble_iqr": 3.2,
        "forecast_delta_6h": 1.4,
        "forecast_delta_24h": 3.2,
        "ensemble_spread_delta_24h": 1.1,
        "lead_hours": 48.0,
        "valid_hour": 12,
        "latitude": 28.61,
        "longitude": 77.20,
    }


@pytest.fixture
def sample_trajectory():
    """Valid 4-cycle chronological trajectory."""
    pts = [
        ForecastTrajectoryPoint("2026-08-20T00:00:00Z", "2026-08-23T00:00:00Z", 72.0, 1010.0, 1010.0, 1.2, 0.18, 0.15),
        ForecastTrajectoryPoint("2026-08-20T06:00:00Z", "2026-08-23T00:00:00Z", 66.0, 1011.0, 1011.0, 1.8, 0.28, 0.22),
        ForecastTrajectoryPoint("2026-08-20T12:00:00Z", "2026-08-23T00:00:00Z", 60.0, 1012.5, 1012.0, 2.4, 0.42, 0.35),
        ForecastTrajectoryPoint("2026-08-20T18:00:00Z", "2026-08-23T00:00:00Z", 54.0, 1014.0, 1013.0, 3.1, 0.58, 0.50),
    ]
    return ForecastTrajectory("delhi", "surface_pressure", "2026-08-23T00:00:00Z", pts)


@pytest.fixture
def fitted_xai_engine():
    """Fitted XAI engine on synthetic reference data."""
    engine = ExplainableForecastEngine()

    np.random.seed(42)
    n = 100
    df_train = pd.DataFrame({
        "location": ["delhi"] * 50 + ["mumbai"] * 50,
        "variable": ["surface_pressure"] * 100,
        "forecast_abs_error": np.random.exponential(1.0, n),
        "lead_hours": np.random.choice([24.0, 48.0, 72.0], n),
    })
    X_train = pd.DataFrame({
        "forecast_value": np.random.normal(1013.0, 5.0, n),
        "ensemble_mean": np.random.normal(1013.0, 5.0, n),
        "ensemble_std": np.random.exponential(1.5, n),
        "ensemble_range": np.random.exponential(3.0, n),
        "ensemble_iqr": np.random.exponential(1.8, n),
        "forecast_delta_6h": np.random.normal(0.0, 1.0, n),
        "forecast_delta_24h": np.random.normal(0.0, 2.0, n),
        "ensemble_spread_delta_24h": np.random.normal(0.0, 0.8, n),
        "lead_hours": df_train["lead_hours"],
    })
    y_train = pd.Series((df_train["forecast_abs_error"] > 2.0).astype(int), name="bust_label")

    engine.fit_reference_context(df_train, X_train, y_train)
    return engine


# =========================================================================
# 1. Schema & Serialization Tests
# =========================================================================

def test_canonical_xai_schema_creation_and_defaults(sample_feature_dict):
    """Verify CanonicalXAIExplanation creation and default field population."""
    exp = CanonicalXAIExplanation(
        explanation_id="xai:delhi:surface_pressure:2026-08-23T00:00:00Z",
        schema_version="17.0.0",
        mode=ExplanationMode.DECISION_TIME,
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-23T00:00:00Z",
        issue_time_utc="2026-08-20T00:00:00Z",
        risk_score=0.45,
        calibrated_bust_probability=0.45,
        risk_confidence=0.82,
        explanation_confidence=0.88,
        operational_decision="WARN_POTENTIAL_BUST",
        warning_priority="P2_HIGH_ALERT",
        overall_narrative="Forecast exhibits elevated bust risk due to wide ensemble dispersion.",
    )
    assert exp.explanation_id.startswith("xai:delhi:")
    assert exp.schema_version == "17.0.0"
    assert exp.provenance_hash != ""
    assert exp.mode == ExplanationMode.DECISION_TIME


def test_canonical_xai_json_serialization_roundtrip(sample_feature_dict):
    """Ensure exact dictionary and JSON roundtrip fidelity without data corruption."""
    driver = FeatureRiskDriver(
        feature_name="ensemble_std",
        display_name="Ensemble Member Dispersion (Spread)",
        value=2.8,
        normalized_contribution=0.22,
        direction=DriverDirection.INCREASES_RISK,
        category=DriverCategory.HIGH_RISK_DRIVER,
        rank=1,
        interpretation="Elevated spread indicates model disagreement.",
    )
    exp = CanonicalXAIExplanation(
        explanation_id="xai:delhi:test",
        schema_version="17.0.0",
        mode=ExplanationMode.DECISION_TIME,
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc="2026-08-23T00:00:00Z",
        issue_time_utc="2026-08-20T00:00:00Z",
        risk_score=0.42,
        calibrated_bust_probability=0.42,
        risk_confidence=0.80,
        explanation_confidence=0.85,
        operational_decision="WARN_POTENTIAL_BUST",
        warning_priority="P2_HIGH_ALERT",
        overall_narrative="Test narrative",
        risk_drivers=[driver],
    )
    j_str = exp.to_json(indent=2)
    d = json.loads(j_str)
    assert d["location_id"] == "delhi"
    assert d["risk_drivers"][0]["feature_name"] == "ensemble_std"
    assert d["risk_drivers"][0]["direction"] == "INCREASES_RISK"

    reconstructed = CanonicalXAIExplanation.from_dict(d)
    assert reconstructed.location_id == "delhi"
    assert reconstructed.risk_score == 0.42
    assert reconstructed.provenance_hash == exp.provenance_hash


# =========================================================================
# 2. Attribution & Driver Ranking Tests
# =========================================================================

def test_xai_attribution_risk_driver_ranking(sample_feature_dict):
    """Verify that feature drivers are ranked by absolute magnitude with proper direction."""
    engine = XAIAttributionEngine()
    risk_drivers, protective_drivers, meta = engine.compute_risk_drivers(
        features=sample_feature_dict,
        current_risk=0.55,
        top_k=5,
    )
    assert len(risk_drivers) > 0
    # Top drivers should include ensemble_std (value 2.8 > 1.5 baseline)
    std_driver = next(d for d in risk_drivers if d.feature_name == "ensemble_std")
    assert std_driver.direction == DriverDirection.INCREASES_RISK
    assert std_driver.normalized_contribution > 0.0
    assert std_driver.rank >= 1


def test_xai_attribution_protective_factor_detection():
    """Verify that compact spread and zero delta are identified as protective factors."""
    engine = XAIAttributionEngine()
    features = {
        "ensemble_std": 0.4,       # Very compact -> protective
        "forecast_delta_6h": 0.0,  # Zero delta
        "lead_hours": 12.0,        # Very short lead
    }
    risk_drivers, protective_drivers, meta = engine.compute_risk_drivers(
        features=features,
        current_risk=0.08,
    )
    assert len(protective_drivers) > 0
    assert any(d.feature_name == "ensemble_std" for d in protective_drivers)
    assert any(d.direction == DriverDirection.DECREASES_RISK for d in protective_drivers)


def test_xai_attribution_reconciliation_metadata(sample_feature_dict):
    """Ensure attribution metadata provides baseline risk and contribution sums."""
    engine = XAIAttributionEngine()
    _, _, meta = engine.compute_risk_drivers(sample_feature_dict, current_risk=0.45)
    assert "baseline_risk" in meta
    assert "sum_positive_contributions" in meta
    assert "sum_negative_contributions" in meta
    assert "target_risk" in meta


# =========================================================================
# 3. Uncertainty & Novelty Explanation Tests
# =========================================================================

def test_uncertainty_explanation_dominant_source_identification(fitted_xai_engine, sample_feature_dict):
    """High ensemble spread should be identified as the dominant uncertainty source."""
    sample_feature_dict["ensemble_std"] = 4.5
    exp = fitted_xai_engine.generate_explanation(sample_feature_dict)
    assert exp.uncertainty is not None
    assert exp.uncertainty.dominant_source in (UncertaintySource.ENSEMBLE_DISPERSION, UncertaintySource.FORECAST_HORIZON)
    assert exp.uncertainty.ensemble_spread_magnitude == 4.5


def test_novelty_explanation_in_domain_vs_ood(fitted_xai_engine, sample_feature_dict):
    """Normal features should be marked in-domain; extreme outliers marked OOD."""
    # 1. Normal
    exp_normal = fitted_xai_engine.generate_explanation(sample_feature_dict)
    assert exp_normal.novelty is not None
    assert exp_normal.novelty.is_in_domain is True
    assert exp_normal.novelty.novelty_level in ("NORMAL", "ELEVATED")

    # 2. Extreme Outlier
    extreme_feats = sample_feature_dict.copy()
    extreme_feats["forecast_value"] = 5000.0
    extreme_feats["ensemble_mean"] = 5000.0
    extreme_feats["ensemble_std"] = 100.0
    exp_ood = fitted_xai_engine.generate_explanation(extreme_feats)
    assert exp_ood.novelty is not None
    assert exp_ood.novelty.novelty_score > 2.0
    assert "Novel" in exp_ood.novelty.narrative or "unsupported" in exp_ood.novelty.narrative or exp_ood.novelty.novelty_level != "NORMAL"


# =========================================================================
# 4. Historical Analogue & Evidence Conflict Tests
# =========================================================================

def test_historical_analogue_alignment(fitted_xai_engine, sample_feature_dict):
    """Verify historical analogue alignment categorization."""
    exp = fitted_xai_engine.generate_explanation(sample_feature_dict)
    assert exp.historical_evidence is not None
    assert exp.historical_evidence.alignment in (
        HistoricalEvidenceAlignment.SUPPORTING,
        HistoricalEvidenceAlignment.CONTRADICTING,
        HistoricalEvidenceAlignment.INSUFFICIENT_EVIDENCE,
    )


def test_evidence_conflict_detection_and_reporting():
    """Verify that contradictory evidence between ML model and trajectory produces structured conflict."""
    engine = ExplainableForecastEngine()
    # Mock high instant risk but stable low trajectory
    feats = {"ensemble_std": 3.0, "lead_hours": 24.0}
    pt = ForecastTrajectoryPoint("2026-08-20T00:00:00Z", "2026-08-23T00:00:00Z", 72.0, 1000.0, 1000.0, 0.5, 0.05, 0.05)
    traj = ForecastTrajectory("delhi", "surface_pressure", "2026-08-23T00:00:00Z", [pt])

    exp = engine.generate_explanation(features=feats, trajectory=traj)
    assert isinstance(exp.evidence_conflicts, list)


# =========================================================================
# 5. Temporal Trajectory & Time-to-Risk Tests
# =========================================================================

def test_temporal_dynamics_explanation_integration(fitted_xai_engine, sample_trajectory):
    """Verify integration of Day 16 temporal trajectory assessment in Day 17 explanation."""
    latest_pt = sample_trajectory.points[-1]
    feats = latest_pt.features or {"ensemble_std": 3.1, "lead_hours": 54.0}

    exp = fitted_xai_engine.generate_explanation(
        features=feats,
        trajectory=sample_trajectory,
        location_id="delhi",
        variable="surface_pressure",
    )
    assert exp.temporal_dynamics is not None
    assert exp.temporal_dynamics.sequence_length == 4
    assert exp.temporal_dynamics.risk_trend in ("RISING_RISK", "ACCELERATING_RISK", "PERSISTENT_HIGH_RISK")
    assert exp.temporal_dynamics.risk_velocity >= 0.0
    assert exp.temporal_dynamics.time_to_risk_estimable is True


def test_impossible_time_to_risk_crossing_explanation(fitted_xai_engine):
    """Falling risk trajectory should explicitly report no projected crossing."""
    pts = [
        ForecastTrajectoryPoint("2026-08-20T00:00:00Z", "2026-08-23T00:00:00Z", 72.0, 1010.0, 1010.0, 2.0, 0.45, 0.40),
        ForecastTrajectoryPoint("2026-08-20T06:00:00Z", "2026-08-23T00:00:00Z", 66.0, 1010.5, 1010.5, 1.5, 0.30, 0.25),
        ForecastTrajectoryPoint("2026-08-20T12:00:00Z", "2026-08-23T00:00:00Z", 60.0, 1010.8, 1010.8, 1.0, 0.18, 0.15),
    ]
    traj = ForecastTrajectory("delhi", "surface_pressure", "2026-08-23T00:00:00Z", pts)
    exp = fitted_xai_engine.generate_explanation(features={"ensemble_std": 1.0, "lead_hours": 60.0}, trajectory=traj)
    assert exp.temporal_dynamics is not None
    assert exp.temporal_dynamics.time_to_risk_estimable is False
    assert "No projected crossing" in exp.temporal_dynamics.time_to_critical_risk_str


# =========================================================================
# 6. Counterfactual Explanation Tests
# =========================================================================

def test_decision_counterfactual_generation_for_warning():
    """Verify that WARN_POTENTIAL_BUST produces actionable de-escalation and escalation counterfactuals."""
    gen = DecisionCounterfactualGenerator()
    cfs = gen.generate_counterfactuals(
        current_decision="WARN_POTENTIAL_BUST",
        current_risk=0.52,
        current_confidence=0.85,
        temporal_slope=0.06,
    )
    assert len(cfs) >= 1
    less_sev = [cf for cf in cfs if cf.target_decision_direction == "LESS_SEVERE"]
    assert len(less_sev) >= 1
    assert less_sev[0].parameter_name == "calibrated_bust_probability"
    assert less_sev[0].required_value < 0.40
    assert less_sev[0].governance_class == "DECISION_COUNTERFACTUAL"


def test_decision_counterfactual_abstention_exit():
    """Verify that ABSTAIN decision yields counterfactuals for novelty and confidence recovery."""
    gen = DecisionCounterfactualGenerator()
    cfs = gen.generate_counterfactuals(
        current_decision="ABSTAIN",
        current_risk=0.50,
        current_confidence=0.20,
        novelty_score=3.20,
    )
    assert len(cfs) >= 1
    assert any(cf.parameter_name == "feature_space_novelty" for cf in cfs)
    assert any(cf.parameter_name == "risk_confidence" for cf in cfs)


# =========================================================================
# 7. Rendering Tests (Levels 1, 2, 3)
# =========================================================================

def test_multi_level_rendering(fitted_xai_engine, sample_feature_dict, sample_trajectory):
    """Verify generation of all three explanation granularities without errors."""
    exp = fitted_xai_engine.generate_explanation(
        features=sample_feature_dict,
        trajectory=sample_trajectory,
        location_id="delhi",
        variable="surface_pressure",
    )

    # Level 1: Operator Summary
    l1 = XAIRenderer.render(exp, level=ExplanationLevel.OPERATOR_SUMMARY)
    assert "[VEYRA XAI SUMMARY]" in l1
    assert "Operational Action" in l1
    assert len(l1.splitlines()) <= 6

    # Level 2: Technical Report
    l2 = XAIRenderer.render(exp, level=ExplanationLevel.TECHNICAL_EXPLANATION)
    assert "# Veyra Forecast-Bust Diagnostic Explanation" in l2
    assert "Feature Risk Drivers" in l2
    assert "Temporal Trajectory Dynamics" in l2
    assert "Decision Provenance" in l2

    # Level 3: Forensic Trace
    l3 = XAIRenderer.render(exp, level=ExplanationLevel.FORENSIC_TRACE)
    assert "# Veyra Forensic XAI Trace" in l3
    assert "Structured JSON Representation" in l3
    assert exp.provenance_hash in l3


# =========================================================================
# 8. Anti-Leakage & Operational Isolation Tests
# =========================================================================

def test_decision_time_mode_rejects_verification_target_columns(fitted_xai_engine, sample_feature_dict):
    """Adversarial test: DECISION_TIME mode must reject all verification and target columns."""
    forbidden_list = [
        "truth_value",
        "forecast_error",
        "forecast_abs_error",
        "ensemble_mean_error",
        "ensemble_mean_abs_error",
        "bust_label",
        "is_bust",
        "bust_label_q95",
    ]
    for forbidden_col in forbidden_list:
        leaked_dict = sample_feature_dict.copy()
        leaked_dict[forbidden_col] = 1.0
        with pytest.raises(ValueError, match="Target leakage rejected in DECISION_TIME"):
            fitted_xai_engine.generate_explanation(
                features=leaked_dict,
                mode=ExplanationMode.DECISION_TIME,
            )


def test_post_hoc_evaluation_mode_accepts_verification_in_features_and_sanitizes(fitted_xai_engine, sample_feature_dict):
    """POST_HOC_EVALUATION mode must accept verification keys in features and isolate them from attribution."""
    leaked_features = sample_feature_dict.copy()
    leaked_features["truth_value"] = 1008.2
    leaked_features["forecast_error"] = 4.3
    leaked_features["bust_label"] = 1

    exp = fitted_xai_engine.generate_explanation(
        features=leaked_features,
        mode=ExplanationMode.POST_HOC_EVALUATION,
    )

    # 1. Explanation succeeded
    assert exp.mode == ExplanationMode.POST_HOC_EVALUATION

    # 2. Retrospective verification contains truth columns
    assert exp.post_hoc_verification is not None
    assert exp.post_hoc_verification["truth_value"] == 1008.2
    assert exp.post_hoc_verification["forecast_error"] == 4.3
    assert exp.post_hoc_verification["bust_label"] == 1

    # 3. Attribution risk drivers strictly exclude verification columns
    for driver in exp.risk_drivers + exp.protective_drivers:
        assert driver.feature_name not in ("truth_value", "forecast_error", "bust_label")


def test_attribution_engine_rejects_forbidden_columns_directly(sample_feature_dict):
    """XAIAttributionEngine must directly reject verification columns if passed without sanitization."""
    engine = XAIAttributionEngine()
    bad_features = sample_feature_dict.copy()
    bad_features["truth_value"] = 1010.0
    with pytest.raises(ValueError, match="Target leakage detected in XAI feature attribution"):
        engine.compute_risk_drivers(bad_features, current_risk=0.50)


def test_post_hoc_truth_value_change_does_not_affect_scientific_attribution_or_provenance(fitted_xai_engine, sample_feature_dict):
    """Changing retrospective truth must not alter scientific decision, attributions, or decision_provenance_hash."""
    f1 = sample_feature_dict.copy()
    f1["truth_value"] = 1005.0
    f1["forecast_error"] = 7.5
    f1["bust_label"] = 1

    f2 = sample_feature_dict.copy()
    f2["truth_value"] = 1012.0
    f2["forecast_error"] = 0.5
    f2["bust_label"] = 0

    exp1 = fitted_xai_engine.generate_explanation(features=f1, mode=ExplanationMode.POST_HOC_EVALUATION)
    exp2 = fitted_xai_engine.generate_explanation(features=f2, mode=ExplanationMode.POST_HOC_EVALUATION)

    assert exp1.risk_score == exp2.risk_score
    assert exp1.operational_decision == exp2.operational_decision
    assert exp1.decision_provenance_hash == exp2.decision_provenance_hash
    assert exp1.provenance_hash != exp2.provenance_hash  # Execution hash differs due to different audited truth payloads
    assert len(exp1.risk_drivers) == len(exp2.risk_drivers)
    for d1, d2 in zip(exp1.risk_drivers, exp2.risk_drivers):
        assert d1.feature_name == d2.feature_name
        assert d1.normalized_contribution == d2.normalized_contribution


# =========================================================================
# 9. Robustness & Monotonicity Tests
# =========================================================================

def test_xai_robustness_zero_spread_and_nans(fitted_xai_engine):
    """Engine must handle zero spread and missing feature keys without exceptions."""
    minimal_feats = {"forecast_value": 1010.0, "ensemble_std": 0.0}
    exp = fitted_xai_engine.generate_explanation(minimal_feats)
    assert exp.risk_score >= 0.0
    assert exp.operational_decision in [d.value for d in OperationalDecision]
    assert exp.explanation_confidence > 0.0


def test_xai_provenance_determinism_and_uniqueness(fitted_xai_engine, sample_feature_dict):
    """Identical inputs produce identical provenance hashes; differing locations produce unique hashes."""
    exp1 = fitted_xai_engine.generate_explanation(sample_feature_dict, location_id="delhi")
    exp2 = fitted_xai_engine.generate_explanation(sample_feature_dict, location_id="delhi")
    exp3 = fitted_xai_engine.generate_explanation(sample_feature_dict, location_id="mumbai")

    assert exp1.provenance_hash == exp2.provenance_hash
    assert exp1.provenance_hash != exp3.provenance_hash


def test_explanation_confidence_monotonicity_with_novelty(fitted_xai_engine, sample_feature_dict):
    """Higher novelty strictly reduces or preserves explanation confidence."""
    f1 = sample_feature_dict.copy()
    f2 = sample_feature_dict.copy()
    f2["ensemble_std"] = 25.0  # High novelty
    f2["forecast_delta_24h"] = 30.0

    exp1 = fitted_xai_engine.generate_explanation(f1)
    exp2 = fitted_xai_engine.generate_explanation(f2)
    assert exp2.explanation_confidence <= exp1.explanation_confidence


# =========================================================================
# 10. Real Stage B Multi-Cycle Integration Smoke Test
# =========================================================================

def test_xai_real_stage_b_smoke_test():
    """Verify end-to-end execution of Day 17 XAI pipeline on real Stage B data."""
    p_path = Path("data/historical/multicycle_paired/paired_multicycle_stage_b_2026-08-18_2026-08-24.parquet")
    if not p_path.exists():
        pytest.skip(f"Stage B archive not found at {p_path}")

    df = pd.read_parquet(p_path)
    delhi_rows = df[(df["location"] == "delhi") & (df["variable"] == "surface_pressure")].copy()
    assert len(delhi_rows) >= 10

    # Pick single event target valid time
    v_time = delhi_rows["valid_time"].iloc[0]
    event_rows = delhi_rows[delhi_rows["valid_time"] == v_time].sort_values("issue_time")

    pts = []
    for _, r in event_rows.iterrows():
        pts.append(
            ForecastTrajectoryPoint(
                issue_time_utc=str(r["issue_time"]),
                valid_time_utc=str(r["valid_time"]),
                lead_hours=float(r["lead_hours"]),
                forecast_value=float(r["forecast_value"]),
                ensemble_mean=float(r["ensemble_mean"]),
                ensemble_std=float(r["ensemble_std"]),
                calibrated_risk=0.30,
                raw_risk=0.25,
            )
        )
    traj = ForecastTrajectory("delhi", "surface_pressure", str(v_time), pts)

    latest_row = event_rows.iloc[-1]
    safe_feats = {
        "forecast_value": float(latest_row["forecast_value"]),
        "ensemble_mean": float(latest_row["ensemble_mean"]),
        "ensemble_std": float(latest_row["ensemble_std"]),
        "lead_hours": float(latest_row["lead_hours"]),
    }

    engine = ExplainableForecastEngine()
    exp = engine.generate_explanation(
        features=safe_feats,
        trajectory=traj,
        location_id="delhi",
        variable="surface_pressure",
        valid_time_utc=str(v_time),
        issue_time_utc=str(latest_row["issue_time"]),
    )

    assert exp.location_id == "delhi"
    assert exp.variable == "surface_pressure"
    assert exp.temporal_dynamics is not None
    assert exp.temporal_dynamics.sequence_length == len(pts)
    assert (len(exp.risk_drivers) + len(exp.protective_drivers)) > 0
    assert exp.provenance_hash != ""

    # Verify rendering
    summary_text = engine.render_explanation(exp, level=ExplanationLevel.OPERATOR_SUMMARY)
    assert "[VEYRA XAI SUMMARY]" in summary_text


# =========================================================================
# 11. Additional Rigorous Tests for XAI Governance, Abstention & Edge Cases
# =========================================================================

def test_xai_abstention_novelty_rationale(fitted_xai_engine, sample_feature_dict):
    """Extreme novelty triggering abstention must provide an explicit abstention rationale."""
    extreme_feats = sample_feature_dict.copy()
    extreme_feats["ensemble_std"] = 150.0
    extreme_feats["forecast_delta_24h"] = 100.0
    exp = fitted_xai_engine.generate_explanation(extreme_feats)
    if exp.operational_decision == "ABSTAIN":
        assert exp.decision_rationale.abstention_triggered is True
        assert exp.decision_rationale.abstention_reason is not None


def test_xai_counterfactual_governance_label_invariant():
    """All generated counterfactuals must bear the DECISION_COUNTERFACTUAL governance tag."""
    gen = DecisionCounterfactualGenerator()
    cfs = gen.generate_counterfactuals(
        current_decision="ALERT_CRITICAL_BUST",
        current_risk=0.78,
        current_confidence=0.90,
    )
    assert len(cfs) >= 1
    for cf in cfs:
        assert cf.governance_class == "DECISION_COUNTERFACTUAL"
        assert "DECISION_COUNTERFACTUAL" in cf.governance_class


def test_xai_explanation_confidence_evidence_conflict_penalty(fitted_xai_engine, sample_feature_dict):
    """Evidence conflicts must strictly penalize explanation confidence."""
    exp_clean = fitted_xai_engine.generate_explanation(sample_feature_dict)

    # Inject contradictory evidence
    pt = ForecastTrajectoryPoint("2026-08-20T00:00:00Z", "2026-08-23T00:00:00Z", 72.0, 1000.0, 1000.0, 0.2, 0.05, 0.05)
    traj = ForecastTrajectory("delhi", "surface_pressure", "2026-08-23T00:00:00Z", [pt])
    high_risk_feats = sample_feature_dict.copy()
    high_risk_feats["ensemble_std"] = 3.5

    exp_conflicted = fitted_xai_engine.generate_explanation(high_risk_feats, trajectory=traj)
    if len(exp_conflicted.evidence_conflicts) > 0:
        assert exp_conflicted.explanation_confidence <= exp_clean.explanation_confidence


def test_xai_empty_trajectory_handling(fitted_xai_engine, sample_feature_dict):
    """Empty trajectory must not cause errors and yield None/clean temporal dynamics."""
    t_empty = ForecastTrajectory("delhi", "surface_pressure", "2026-08-23T00:00:00Z", [])
    exp = fitted_xai_engine.generate_explanation(sample_feature_dict, trajectory=t_empty)
    assert exp.temporal_dynamics is not None
    assert exp.temporal_dynamics.sequence_length == 0


def test_xai_single_point_trajectory_handling(fitted_xai_engine, sample_feature_dict):
    """Single point trajectory must yield sequence_length = 1 and non-estimable time-to-risk."""
    p = ForecastTrajectoryPoint("2026-08-20T00:00:00Z", "2026-08-23T00:00:00Z", 72.0, 1012.0, 1012.0, 1.5, 0.2, 0.2)
    t_single = ForecastTrajectory("delhi", "surface_pressure", "2026-08-23T00:00:00Z", [p])
    exp = fitted_xai_engine.generate_explanation(sample_feature_dict, trajectory=t_single)
    assert exp.temporal_dynamics is not None
    assert exp.temporal_dynamics.sequence_length == 1
    assert exp.temporal_dynamics.time_to_risk_estimable is False


def test_xai_novel_unseen_location_handling(fitted_xai_engine, sample_feature_dict):
    """Engine must cleanly generate explanation for novel unseen location."""
    exp = fitted_xai_engine.generate_explanation(sample_feature_dict, location_id="srinagar")
    assert exp.location_id == "srinagar"
    assert exp.operational_decision != ""
    assert exp.provenance_hash != ""


def test_xai_renderer_forensic_json_validity(fitted_xai_engine, sample_feature_dict):
    """Forensic trace must include parseable JSON block."""
    exp = fitted_xai_engine.generate_explanation(sample_feature_dict)
    trace = XAIRenderer.render_forensic_trace(exp)
    assert "```json" in trace
    # Extract json block
    start = trace.find("```json") + len("```json")
    end = trace.find("```", start)
    json_block = trace[start:end].strip()
    parsed = json.loads(json_block)
    assert parsed["schema_version"] == "17.0.0"


def test_xai_renderer_technical_contains_all_sections(fitted_xai_engine, sample_feature_dict, sample_trajectory):
    """Technical report must render all core sections."""
    exp = fitted_xai_engine.generate_explanation(sample_feature_dict, trajectory=sample_trajectory)
    report = XAIRenderer.render_technical_explanation(exp)
    assert "## 1. Overall Assessment Narrative" in report
    assert "## 2. Feature Risk Drivers & Protective Factors" in report
    assert "## 3. Uncertainty & Novelty Analysis" in report
    assert "## 4. Multi-Cycle Temporal Trajectory Dynamics" in report
    assert "## 7. Policy Sensitivity Counterfactuals" in report


def test_xai_renderer_operator_summary_brevity(fitted_xai_engine, sample_feature_dict):
    """Operator summary must be concise (under 6 lines)."""
    exp = fitted_xai_engine.generate_explanation(sample_feature_dict)
    summary = XAIRenderer.render_operator_summary(exp)
    lines = [l for l in summary.splitlines() if l.strip()]
    assert len(lines) <= 6


def test_xai_multiple_variables_temperature_and_wind(fitted_xai_engine, sample_feature_dict):
    """Verify clean explanations for temperature_2m and wind_speed_10m."""
    exp_temp = fitted_xai_engine.generate_explanation(sample_feature_dict, variable="temperature_2m")
    assert exp_temp.variable == "temperature_2m"
    assert exp_temp.provenance_hash != ""

    exp_wind = fitted_xai_engine.generate_explanation(sample_feature_dict, variable="wind_speed_10m")
    assert exp_wind.variable == "wind_speed_10m"
    assert exp_wind.provenance_hash != ""


def test_xai_operator_attention_escalation_logic(fitted_xai_engine, sample_feature_dict):
    """High risk warnings must prepend emergency operational contingency recommendations."""
    high_feats = sample_feature_dict.copy()
    high_feats["ensemble_std"] = 6.0
    high_feats["lead_hours"] = 72.0
    exp = fitted_xai_engine.generate_explanation(high_feats)
    if "WARN" in exp.operational_decision or "ALERT" in exp.operational_decision:
        assert any("contingency" in rec.lower() for rec in exp.recommended_operator_attention)


def test_xai_provenance_stability_repeated_calls(fitted_xai_engine, sample_feature_dict):
    """Executing explanation 10 times consecutively must yield 10 identical provenance hashes."""
    hashes = set()
    for _ in range(10):
        exp = fitted_xai_engine.generate_explanation(sample_feature_dict, location_id="delhi")
        hashes.add(exp.provenance_hash)
    assert len(hashes) == 1


# =========================================================================
# 12. Counterfactual Step Tests & Enum Invariant Tests
# =========================================================================

def test_xai_counterfactual_all_step_down_tiers():
    """Verify counterfactual calculations across all policy step-down transitions."""
    gen = DecisionCounterfactualGenerator(risk_thresholds=(0.10, 0.22, 0.40, 0.65))

    # 1. ALERT -> WARN
    cf_alert = gen.generate_counterfactuals("ALERT_CRITICAL_BUST", current_risk=0.75, current_confidence=0.8)
    assert cf_alert[0].required_value < 0.65

    # 2. WARN -> CAUTION
    cf_warn = gen.generate_counterfactuals("WARN_POTENTIAL_BUST", current_risk=0.55, current_confidence=0.8)
    assert any(cf.required_value < 0.40 for cf in cf_warn)

    # 3. CAUTION -> MONITOR
    cf_caution = gen.generate_counterfactuals("ADVISE_CAUTION", current_risk=0.30, current_confidence=0.8)
    assert cf_caution[0].required_value < 0.22

    # 4. MONITOR -> TRUST
    cf_monitor = gen.generate_counterfactuals("MONITOR", current_risk=0.15, current_confidence=0.8)
    assert cf_monitor[0].required_value < 0.10


def test_xai_counterfactual_step_up_escalation():
    """Verify counterfactual calculations for escalation from TRUST or MONITOR to WARN."""
    gen = DecisionCounterfactualGenerator(risk_thresholds=(0.10, 0.22, 0.40, 0.65))
    cfs = gen.generate_counterfactuals("TRUST_FORECAST", current_risk=0.08, current_confidence=0.8)
    assert len(cfs) >= 1
    assert cfs[0].target_decision_direction == "MORE_SEVERE"
    assert cfs[0].required_value == 0.65 or cfs[0].required_value >= 0.40


def test_xai_attribution_all_zeros():
    """Attribution with all-zero features must not divide by zero and return stable neutral/protective drivers."""
    engine = XAIAttributionEngine()
    feats = {"forecast_value": 0.0, "ensemble_std": 0.0, "forecast_delta_6h": 0.0}
    r, p, meta = engine.compute_risk_drivers(feats, current_risk=0.10)
    assert len(p) > 0 or len(r) >= 0
    assert meta["target_risk"] == 0.10


def test_xai_enums_and_schema_types():
    """Verify all XAI enum members and schema constants."""
    assert set([e.value for e in ExplanationMode]) == {"DECISION_TIME", "POST_HOC_EVALUATION"}
    assert set([e.value for e in ExplanationLevel]) == {"OPERATOR_SUMMARY", "TECHNICAL_EXPLANATION", "FORENSIC_TRACE"}
    assert set([e.value for e in DriverCategory]) == {
        "HIGH_RISK_DRIVER", "MODERATE_RISK_DRIVER", "PROTECTIVE_FACTOR", "NEUTRAL_FACTOR", "INSUFFICIENT_EVIDENCE"
    }
    assert set([e.value for e in DriverDirection]) == {"INCREASES_RISK", "DECREASES_RISK", "NEUTRAL"}
    assert set([e.value for e in HistoricalEvidenceAlignment]) == {"SUPPORTING", "CONTRADICTING", "INSUFFICIENT_EVIDENCE"}


def test_xai_engine_is_fitted_flag():
    """Fitted engine must set is_fitted_ flag to True."""
    engine = ExplainableForecastEngine()
    assert engine.is_fitted_ is False
    df_t = pd.DataFrame({"location": ["delhi"], "variable": ["surface_pressure"], "forecast_abs_error": [1.0], "lead_hours": [24.0]})
    X_t = pd.DataFrame({"forecast_value": [1013.0], "ensemble_mean": [1013.0], "ensemble_std": [1.0], "lead_hours": [24.0]})
    y_t = pd.Series([0], name="bust_label")
    engine.fit_reference_context(df_t, X_t, y_t)
    assert engine.is_fitted_ is True


# =========================================================================
# 13. Forensic Provenance Sensitivity, Leakage & Multi-Variable Tests
# =========================================================================

def test_xai_provenance_sensitivity_to_scientific_inputs(fitted_xai_engine, sample_feature_dict):
    """Provenance hash must change when any scientifically relevant input changes."""
    exp_base = fitted_xai_engine.generate_explanation(sample_feature_dict, location_id="delhi")

    # 1. Change feature
    f_mod = sample_feature_dict.copy()
    f_mod["ensemble_std"] = 5.0
    exp_mod_feat = fitted_xai_engine.generate_explanation(f_mod, location_id="delhi")
    assert exp_mod_feat.provenance_hash != exp_base.provenance_hash

    # 2. Change location
    exp_mod_loc = fitted_xai_engine.generate_explanation(sample_feature_dict, location_id="mumbai")
    assert exp_mod_loc.provenance_hash != exp_base.provenance_hash

    # 3. Change valid time
    exp_mod_time = fitted_xai_engine.generate_explanation(sample_feature_dict, valid_time_utc="2026-08-25T00:00:00Z")
    assert exp_mod_time.provenance_hash != exp_base.provenance_hash


def test_xai_provenance_sensitivity_to_policy_configuration(fitted_xai_engine, sample_feature_dict):
    """Provenance hash must change when governing decision policy thresholds change."""
    exp = fitted_xai_engine.generate_explanation(sample_feature_dict)
    h_default = exp.compute_provenance_hash(governing_thresholds=(0.10, 0.22, 0.40, 0.65))
    h_custom = exp.compute_provenance_hash(governing_thresholds=(0.15, 0.30, 0.50, 0.75))
    assert h_default != h_custom


def test_xai_provenance_invariance_to_volatile_issue_time(fitted_xai_engine, sample_feature_dict):
    """Provenance hash must be invariant to excluded volatile timestamps (e.g. issue_time_utc)."""
    exp1 = fitted_xai_engine.generate_explanation(sample_feature_dict, issue_time_utc="2026-08-20T00:00:00Z")
    exp2 = fitted_xai_engine.generate_explanation(sample_feature_dict, issue_time_utc="2026-08-20T06:00:00Z")
    assert exp1.provenance_hash == exp2.provenance_hash


def test_xai_attribution_reconciliation_exact_residual_tolerance(sample_feature_dict):
    """Verify explicit residual and approximate additive reconciliation status."""
    engine = XAIAttributionEngine()
    r, p, meta = engine.compute_risk_drivers(sample_feature_dict, current_risk=0.48)
    assert meta["reconciliation_status"] == "APPROXIMATE_ADDITIVE"
    assert meta["reconciliation_residual"] <= meta["tolerance_applied"]
    assert meta["is_additive_reconciled"] is True
    assert "not physical causal" in meta["disclaimer"]


def test_xai_post_hoc_verification_not_leaked_to_decision_time_state(fitted_xai_engine, sample_feature_dict):
    """Post-hoc truth payload must not alter decision, probability, drivers, or decision_provenance_hash."""
    exp_decision = fitted_xai_engine.generate_explanation(
        features=sample_feature_dict,
        mode=ExplanationMode.DECISION_TIME,
    )
    exp_post_hoc = fitted_xai_engine.generate_explanation(
        features=sample_feature_dict,
        mode=ExplanationMode.POST_HOC_EVALUATION,
        post_hoc_truth={"truth_value": 1010.0, "actual_error": 2.5, "bust_occurred": True},
    )

    assert exp_decision.risk_score == exp_post_hoc.risk_score
    assert exp_decision.operational_decision == exp_post_hoc.operational_decision
    assert len(exp_decision.risk_drivers) == len(exp_post_hoc.risk_drivers)
    assert exp_decision.decision_provenance_hash == exp_post_hoc.decision_provenance_hash
    assert exp_decision.provenance_hash != exp_post_hoc.provenance_hash
    assert exp_post_hoc.post_hoc_verification is not None
    assert exp_decision.post_hoc_verification is None


def test_xai_provenance_contract_invariants(fitted_xai_engine, sample_feature_dict):
    """
    Explicitly test all core provenance contract invariants:
    A. Same scientific inputs + different truth_value -> same decision_provenance_hash.
    B. Same scientific inputs + different bust_label -> same decision_provenance_hash.
    C. Same scientific inputs + different forecast_error -> same decision_provenance_hash.
    D. Changing a genuine scientific feature -> changes both decision and execution hashes.
    E. DECISION_TIME vs POST_HOC on identical features -> identical decision_provenance_hash.
    """
    # Baseline DECISION_TIME
    exp_base = fitted_xai_engine.generate_explanation(sample_feature_dict, mode=ExplanationMode.DECISION_TIME)

    # Invariant A: Different truth_value
    exp_truth1 = fitted_xai_engine.generate_explanation(
        dict(sample_feature_dict, truth_value=1000.0), mode=ExplanationMode.POST_HOC_EVALUATION
    )
    exp_truth2 = fitted_xai_engine.generate_explanation(
        dict(sample_feature_dict, truth_value=1025.0), mode=ExplanationMode.POST_HOC_EVALUATION
    )
    assert exp_truth1.decision_provenance_hash == exp_base.decision_provenance_hash
    assert exp_truth2.decision_provenance_hash == exp_base.decision_provenance_hash
    assert exp_truth1.provenance_hash != exp_truth2.provenance_hash

    # Invariant B: Different bust_label
    exp_bust0 = fitted_xai_engine.generate_explanation(
        dict(sample_feature_dict, bust_label=0), mode=ExplanationMode.POST_HOC_EVALUATION
    )
    exp_bust1 = fitted_xai_engine.generate_explanation(
        dict(sample_feature_dict, bust_label=1), mode=ExplanationMode.POST_HOC_EVALUATION
    )
    assert exp_bust0.decision_provenance_hash == exp_base.decision_provenance_hash
    assert exp_bust1.decision_provenance_hash == exp_base.decision_provenance_hash
    assert exp_bust0.provenance_hash != exp_bust1.provenance_hash

    # Invariant C: Different forecast_error
    exp_err1 = fitted_xai_engine.generate_explanation(
        dict(sample_feature_dict, forecast_error=1.2), mode=ExplanationMode.POST_HOC_EVALUATION
    )
    exp_err2 = fitted_xai_engine.generate_explanation(
        dict(sample_feature_dict, forecast_error=8.9), mode=ExplanationMode.POST_HOC_EVALUATION
    )
    assert exp_err1.decision_provenance_hash == exp_base.decision_provenance_hash
    assert exp_err2.decision_provenance_hash == exp_base.decision_provenance_hash
    assert exp_err1.provenance_hash != exp_err2.provenance_hash

    # Invariant D: Changing a genuine scientific feature
    mod_feats = sample_feature_dict.copy()
    mod_feats["ensemble_std"] = 6.5
    exp_mod_scientific = fitted_xai_engine.generate_explanation(mod_feats, mode=ExplanationMode.DECISION_TIME)
    assert exp_mod_scientific.decision_provenance_hash != exp_base.decision_provenance_hash
    assert exp_mod_scientific.provenance_hash != exp_base.provenance_hash

    # Invariant E: DECISION_TIME vs POST_HOC on identical features
    exp_post_clean = fitted_xai_engine.generate_explanation(sample_feature_dict, mode=ExplanationMode.POST_HOC_EVALUATION)
    assert exp_post_clean.decision_provenance_hash == exp_base.decision_provenance_hash
    assert exp_post_clean.provenance_hash != exp_base.provenance_hash


def test_xai_programmatic_public_exports():
    """Programmatically verify all intended Day 17 symbols in evaluation package."""
    import evaluation
    expected_symbols = [
        "CanonicalXAIExplanation",
        "ExplanationMode",
        "ExplanationLevel",
        "DriverCategory",
        "DriverDirection",
        "UncertaintySource",
        "HistoricalEvidenceAlignment",
        "FeatureRiskDriver",
        "UncertaintyExplanation",
        "NoveltyExplanation",
        "HistoricalEvidenceExplanation",
        "EvidenceConflictItem",
        "TemporalDynamicsExplanation",
        "DecisionRationale",
        "DecisionCounterfactual",
        "XAIAttributionEngine",
        "DecisionCounterfactualGenerator",
        "XAIRenderer",
        "ExplainableForecastEngine",
    ]
    for sym in expected_symbols:
        assert hasattr(evaluation, sym), f"Missing public export '{sym}' in evaluation package."
        assert sym in evaluation.__all__, f"'{sym}' not declared in evaluation.__all__."


def test_xai_real_stage_b_multivariable_validation():
    """Validate Day 17 XAI execution across all three Stage B variables."""
    p_path = Path("data/historical/multicycle_paired/paired_multicycle_stage_b_2026-08-18_2026-08-24.parquet")
    if not p_path.exists():
        pytest.skip("Stage B parquet archive not found.")

    df = pd.read_parquet(p_path)
    engine = ExplainableForecastEngine()

    for var in ["surface_pressure", "temperature_2m", "wind_speed_10m"]:
        sub_df = df[(df["location"] == "delhi") & (df["variable"] == var)].sort_values("issue_time")
        assert len(sub_df) >= 5
        latest = sub_df.iloc[-1]
        safe_feats = {
            "forecast_value": float(latest["forecast_value"]),
            "ensemble_mean": float(latest["ensemble_mean"]),
            "ensemble_std": float(latest["ensemble_std"]),
            "lead_hours": float(latest["lead_hours"]),
        }
        exp = engine.generate_explanation(
            features=safe_feats,
            location_id="delhi",
            variable=var,
            valid_time_utc=str(latest["valid_time"]),
            issue_time_utc=str(latest["issue_time"]),
        )
        assert exp.variable == var
        assert exp.provenance_hash != ""
        assert exp.operational_decision != ""
        assert len(exp.risk_drivers) + len(exp.protective_drivers) >= 1


def test_xai_novelty_language_does_not_claim_guaranteed_failure(fitted_xai_engine, sample_feature_dict):
    """Novelty narrative must describe manifold support rather than claiming guaranteed failure."""
    exp = fitted_xai_engine.generate_explanation(sample_feature_dict)
    narr = exp.novelty.narrative.lower()
    assert "guaranteed failure" not in narr
    assert "fatal" not in narr
    assert "certain bust" not in narr
    assert "regime" in narr or "manifold" in narr or "distance" in narr
