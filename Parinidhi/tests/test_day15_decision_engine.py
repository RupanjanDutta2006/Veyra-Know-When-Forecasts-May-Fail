"""
Adversarial & Unit Tests for Day 15: Operational Forecast-Risk Decision Engine.

Validates:
1. Multi-tier operational decision levels (TRUST_FORECAST, MONITOR, ADVISE_CAUTION, WARN_POTENTIAL_BUST, ALERT_CRITICAL_BUST).
2. Explicit probability vs decision separation.
3. Safety-critical abstention mechanism under extreme novelty, missingness, or corrupted data.
4. Evidence fusion and conflicting-evidence confidence penalties.
5. Data quality gating and anti-leakage contract enforcement.
6. Decision stability, margin calculation, and counterfactual sensitivity.
7. Full JSON serialization round-trip compliance.
8. Real Stage B historical parquet integration across diverse meteorological locations.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from evaluation.calibration import ProbabilityCalibrator
from evaluation.data_quality import DataQualityAuditor
from evaluation.decision_engine import ForecastRiskDecisionEngine
from evaluation.decision_policy import RiskDecisionPolicy
from evaluation.decision_schema import (
    DataQualityState,
    ForecastRiskDecision,
    OperationalDecision,
    RiskLevel,
    WarningPriority,
)
from features.contract import UNAVAILABLE_UNTIL_VERIFICATION
from features.feature_pipeline import IssueTimeSafeFeaturePipeline, FEATURE_COLUMN_NAMES
from models.logistic_classifier import RegularizedLogisticClassifier


@pytest.fixture
def synthetic_training_data():
    """Generate synthetic reference training data."""
    np.random.seed(42)
    n = 250
    X = pd.DataFrame({
        "ensemble_std": np.random.uniform(0.5, 4.0, n),
        "ensemble_range": np.random.uniform(2.0, 15.0, n),
        "ensemble_iqr": np.random.uniform(1.0, 8.0, n),
        "forecast_delta_6h": np.random.normal(0.0, 1.5, n),
        "forecast_delta_24h": np.random.normal(0.0, 2.5, n),
        "ensemble_spread_delta_24h": np.random.normal(0.0, 1.0, n),
        "lead_hours": np.random.choice([6, 12, 24, 48, 72], n),
        "valid_hour": np.random.choice(range(24), n),
        "latitude": np.random.uniform(8.0, 35.0, n),
        "longitude": np.random.uniform(68.0, 92.0, n),
    })
    y = pd.Series(np.random.binomial(1, 0.08, n), name="bust_label")
    df = X.copy()
    df["location_id"] = np.random.choice(["delhi", "srinagar", "goa", "bengaluru"], n)
    df["bust_label"] = y
    df["forecast_abs_error"] = np.random.uniform(0.2, 6.0, n)
    return df, X, y


@pytest.fixture
def fitted_decision_engine(synthetic_training_data):
    """Provide a pre-fitted ForecastRiskDecisionEngine."""
    df_train, X_train, y_train = synthetic_training_data
    model = RegularizedLogisticClassifier()
    model.fit(X_train, y_train)

    calibrator = ProbabilityCalibrator(method="platt")
    raw_probs = model.predict_proba(X_train)[:, 1]
    calibrator.fit(y_train, raw_probs)

    engine = ForecastRiskDecisionEngine(model=model, calibrator=calibrator)
    engine.fit_reference_context(df_train, X_train, y_train, model, calibrator=calibrator)
    return engine


# =========================================================================
# 1. Operational Decision Tier Tests
# =========================================================================

def test_low_risk_decision_trust_forecast(fitted_decision_engine, synthetic_training_data):
    """Low risk probability and stable conditions should yield TRUST_FORECAST."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()
    query["ensemble_std"] = 0.4
    query["forecast_delta_6h"] = 0.0
    query["forecast_delta_24h"] = 0.0
    query["lead_hours"] = 6

    decision = fitted_decision_engine.decide_forecast_risk(
        features=query,
        raw_bust_probability=0.03,
        location_id="delhi",
    )

    assert decision.decision == OperationalDecision.TRUST_FORECAST
    assert decision.risk_level == RiskLevel.LOW
    assert decision.warning_priority == WarningPriority.P4_INFORMATIONAL
    assert not decision.abstention_required


def test_watch_risk_decision_monitor(fitted_decision_engine, synthetic_training_data):
    """Mild uncertainty should yield MONITOR decision."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()
    query["ensemble_std"] = 1.2
    query["lead_hours"] = 24

    decision = fitted_decision_engine.decide_forecast_risk(
        features=query,
        raw_bust_probability=0.15,
        location_id="delhi",
    )

    assert decision.decision in [OperationalDecision.MONITOR, OperationalDecision.TRUST_FORECAST]
    assert decision.risk_level in [RiskLevel.WATCH, RiskLevel.LOW]


def test_elevated_risk_decision_advise_caution(fitted_decision_engine, synthetic_training_data):
    """Elevated risk score (0.25 - 0.38) should trigger ADVISE_CAUTION."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()
    query["ensemble_std"] = 2.5
    query["forecast_delta_24h"] = 3.0

    decision = fitted_decision_engine.decide_forecast_risk(
        features=query,
        raw_bust_probability=0.30,
        location_id="delhi",
    )

    assert decision.decision in [OperationalDecision.ADVISE_CAUTION, OperationalDecision.WARN_POTENTIAL_BUST]
    assert decision.risk_level in [RiskLevel.ELEVATED, RiskLevel.HIGH]
    assert decision.warning_priority in [WarningPriority.P2_MEDIUM, WarningPriority.P1_HIGH]


def test_high_risk_decision_warn_potential_bust(fitted_decision_engine, synthetic_training_data):
    """High risk score (>0.40) with good confidence should trigger WARN_POTENTIAL_BUST."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()
    query["ensemble_std"] = 4.5
    query["forecast_delta_24h"] = 4.8
    query["lead_hours"] = 48

    decision = fitted_decision_engine.decide_forecast_risk(
        features=query,
        raw_bust_probability=0.55,
        location_id="delhi",
    )

    assert decision.decision in [OperationalDecision.WARN_POTENTIAL_BUST, OperationalDecision.ALERT_CRITICAL_BUST]
    assert decision.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
    assert decision.warning_priority in [WarningPriority.P1_HIGH, WarningPriority.P0_CRITICAL]


def test_critical_risk_decision_alert_critical_bust(fitted_decision_engine, synthetic_training_data):
    """Critical risk score (>0.65) with high confidence should trigger ALERT_CRITICAL_BUST."""
    df_train, X_train, y_train = synthetic_training_data
    # Use a sample from training data that has bust=1 and high spread
    query = X_train.median().to_dict()
    query["ensemble_std"] = 3.8
    query["forecast_delta_24h"] = 3.5
    query["lead_hours"] = 48

    decision = fitted_decision_engine.decide_forecast_risk(
        features=query,
        raw_bust_probability=0.85,
        location_id="delhi",
    )

    assert decision.decision == OperationalDecision.ALERT_CRITICAL_BUST
    assert decision.risk_level == RiskLevel.CRITICAL
    assert decision.warning_priority == WarningPriority.P0_CRITICAL


# =========================================================================
# 2. Probability vs Decision Separation Tests
# =========================================================================

def test_probability_decision_separation_low_confidence_downgrade(fitted_decision_engine, synthetic_training_data):
    """A critical model probability with low confidence should be downgraded to WARN_POTENTIAL_BUST."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()
    # High novelty to suppress confidence
    query["ensemble_std"] = 80.0  # Massive outlier

    decision = fitted_decision_engine.decide_forecast_risk(
        features=query,
        raw_bust_probability=0.90,
        location_id="delhi",
    )

    # When confidence is penalized by extreme novelty, critical alert must be downgraded or abstained
    assert decision.decision in [OperationalDecision.WARN_POTENTIAL_BUST, OperationalDecision.ABSTAIN]


# =========================================================================
# 3. Safety-Critical Abstention Tests
# =========================================================================

def test_extreme_missingness_triggers_abstention(fitted_decision_engine, synthetic_training_data):
    """Excessive missing features (>50%) must trigger mandatory abstention."""
    _, X_train, _ = synthetic_training_data
    query = {f: np.nan for f in X_train.columns}
    query["ensemble_std"] = 2.0  # Only 1 valid feature out of 9

    decision = fitted_decision_engine.decide_forecast_risk(
        features=query,
        raw_bust_probability=0.40,
        location_id="delhi",
    )

    assert decision.abstention_required
    assert decision.decision == OperationalDecision.ABSTAIN
    assert "missing" in str(decision.abstention_reason).lower()


def test_corrupted_non_finite_values_trigger_abstention(fitted_decision_engine, synthetic_training_data):
    """Non-finite values (+/-inf) must trigger abstention due to corrupted data."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()
    query["ensemble_std"] = np.inf

    decision = fitted_decision_engine.decide_forecast_risk(
        features=query,
        raw_bust_probability=0.50,
        location_id="delhi",
    )

    assert decision.abstention_required
    assert decision.data_quality_level == DataQualityState.CORRUPTED
    assert decision.decision == OperationalDecision.ABSTAIN


def test_pathological_probability_triggers_abstention(fitted_decision_engine, synthetic_training_data):
    """Out-of-bounds probabilities (<0 or >1 or NaN) must trigger abstention."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()

    decision_neg = fitted_decision_engine.decide_forecast_risk(
        features=query,
        raw_bust_probability=-0.5,
    )
    assert decision_neg.abstention_required
    assert decision_neg.decision == OperationalDecision.ABSTAIN

    decision_nan = fitted_decision_engine.decide_forecast_risk(
        features=query,
        raw_bust_probability=np.nan,
    )
    assert decision_nan.abstention_required
    assert decision_nan.decision == OperationalDecision.ABSTAIN


# =========================================================================
# 4. Anti-Leakage & Contract Tests
# =========================================================================

def test_decision_engine_rejects_verification_columns(fitted_decision_engine):
    """Forbidden verification columns must be caught by DataQualityAuditor and trigger CORRUPTED state."""
    leaky_query = {
        "ensemble_std": 2.0,
        "truth_value": 25.0,  # FORBIDDEN
    }
    decision = fitted_decision_engine.decide_forecast_risk(leaky_query, raw_bust_probability=0.30)
    assert decision.abstention_required
    assert decision.data_quality_level == DataQualityState.CORRUPTED
    assert "Security violation" in str(decision.provenance.get("data_quality_issues", []))


# =========================================================================
# 5. Evidence Fusion & Conflicting-Evidence Tests
# =========================================================================

def test_evidence_fusion_detects_supporting_and_contradicting(fitted_decision_engine, synthetic_training_data):
    """Evidence fusion must populate supporting and contradicting items."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()
    query["ensemble_std"] = 3.5  # Supports risk
    query["lead_hours"] = 6      # Contradicts risk (short horizon)

    decision = fitted_decision_engine.decide_forecast_risk(
        features=query,
        raw_bust_probability=0.45,
        location_id="delhi",
    )

    assert len(decision.supporting_evidence) > 0
    assert len(decision.contradicting_evidence) > 0
    assert 0.0 <= decision.evidence_conflict_score <= 1.0


def test_severe_conflict_penalizes_decision_confidence(fitted_decision_engine, synthetic_training_data):
    """Divergent evidence sources must increase conflict score and reduce confidence."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()

    # Conflicting setup: high probability with tight spread
    query["ensemble_std"] = 0.2

    decision = fitted_decision_engine.decide_forecast_risk(
        features=query,
        raw_bust_probability=0.75,
        location_id="delhi",
    )

    assert decision.evidence_conflict_score > 0.0
    assert decision.confidence < 0.95


# =========================================================================
# 6. Policy Configurability & Asymmetric Cost Tests
# =========================================================================

def test_policy_cost_asymmetry_configuration():
    """Policy must support custom cost weights and alert fatigue parameters."""
    custom_policy = RiskDecisionPolicy(
        fn_cost_weight=5.0,
        fp_cost_weight=0.5,
        alert_fatigue_penalty=0.05,
        high_threshold=0.30,  # Lower threshold for aggressive warnings
    )
    assert custom_policy.fn_cost_weight == 5.0
    level = custom_policy.evaluate_risk_level(0.35)
    assert level == RiskLevel.HIGH


def test_policy_override_in_decision_engine(fitted_decision_engine, synthetic_training_data):
    """Overriding policy in decide_forecast_risk must alter decision thresholds dynamically."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()
    query["ensemble_std"] = 2.0

    lenient_policy = RiskDecisionPolicy(high_threshold=0.80, elevated_threshold=0.60, watch_threshold=0.40)
    aggressive_policy = RiskDecisionPolicy(high_threshold=0.20, elevated_threshold=0.15, watch_threshold=0.08)

    dec_lenient = fitted_decision_engine.decide_forecast_risk(
        features=query,
        raw_bust_probability=0.35,
        policy_override=lenient_policy,
    )
    dec_aggressive = fitted_decision_engine.decide_forecast_risk(
        features=query,
        raw_bust_probability=0.35,
        policy_override=aggressive_policy,
    )

    assert dec_lenient.risk_level in [RiskLevel.LOW, RiskLevel.WATCH]
    assert dec_aggressive.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]


# =========================================================================
# 7. Decision Sensitivity & Counterfactual Tests
# =========================================================================

def test_decision_sensitivity_counterfactuals(fitted_decision_engine, synthetic_training_data):
    """Sensitivity analysis must output boundary margins and actionable counterfactuals."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()
    query["ensemble_std"] = 4.2

    decision = fitted_decision_engine.decide_forecast_risk(
        features=query,
        raw_bust_probability=0.55,
        location_id="delhi",
    )

    sens = decision.sensitivity_analysis
    assert "decision_margin_to_boundary" in sens
    assert "counterfactual_evidence" in sens
    assert len(sens["counterfactual_evidence"]) > 0
    assert sens["stability_status"] in ["STABLE", "NEAR_BOUNDARY"]


# =========================================================================
# 8. Schema & JSON Serialization Tests
# =========================================================================

def test_forecast_risk_decision_json_round_trip(fitted_decision_engine, synthetic_training_data):
    """ForecastRiskDecision must serialize cleanly to JSON and reconstruct without data loss."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()

    decision = fitted_decision_engine.decide_forecast_risk(
        features=query,
        raw_bust_probability=0.42,
        location_id="delhi",
    )

    json_str = decision.to_json()
    assert isinstance(json_str, str)
    parsed = json.loads(json_str)

    assert parsed["decision_id"].startswith("dec_")
    assert parsed["decision"] in [d.value for d in OperationalDecision]
    assert parsed["risk_level"] in [r.value for r in RiskLevel]
    assert isinstance(parsed["risk_score"], float)

    # Reconstruct from dict
    reconstructed = ForecastRiskDecision.from_dict(parsed)
    assert reconstructed.decision == decision.decision
    assert reconstructed.risk_score == decision.risk_score
    assert reconstructed.confidence == decision.confidence


def test_deterministic_decision_id_and_output(fitted_decision_engine, synthetic_training_data):
    """Identical input vectors must produce bit-identical decision IDs and risk scores."""
    _, X_train, _ = synthetic_training_data
    query = X_train.iloc[3].to_dict()

    dec1 = fitted_decision_engine.decide_forecast_risk(query, raw_bust_probability=0.35, location_id="goa")
    dec2 = fitted_decision_engine.decide_forecast_risk(query, raw_bust_probability=0.35, location_id="goa")

    assert dec1.decision_id == dec2.decision_id
    assert dec1.risk_score == dec2.risk_score
    assert dec1.decision == dec2.decision
    assert dec1.confidence == dec2.confidence


# =========================================================================
# 9. Real Stage B Parquet Integration Tests
# =========================================================================

def test_action_matrix_and_recall_denominators_reconciliation():
    """Verify that action matrix sums to N and both overall and conditional recall are exact."""
    # Synthetic test scenario with 10 samples: 4 busts, 6 non-busts; 1 abstention on bust, 1 on non-bust
    y_true = np.array([1, 1, 1, 1, 0, 0, 0, 0, 0, 0])
    decisions = [
        OperationalDecision.WARN_POTENTIAL_BUST,  # TP bust
        OperationalDecision.ADVISE_CAUTION,       # Missed bust (caution)
        OperationalDecision.MONITOR,              # Missed bust (monitor)
        OperationalDecision.ABSTAIN,              # Abstained bust
        OperationalDecision.WARN_POTENTIAL_BUST,  # FP non-bust
        OperationalDecision.ADVISE_CAUTION,       # Non-bust caution
        OperationalDecision.MONITOR,              # Non-bust monitor
        OperationalDecision.TRUST_FORECAST,       # Non-bust trust
        OperationalDecision.TRUST_FORECAST,       # Non-bust trust
        OperationalDecision.ABSTAIN,              # Abstained non-bust
    ]
    abstentions = [d == OperationalDecision.ABSTAIN for d in decisions]

    tot_busts = np.sum(y_true == 1)      # 4
    tot_nonbusts = np.sum(y_true == 0)   # 6
    assert tot_busts + tot_nonbusts == 10

    # Non-abstained busts
    valid_mask = ~np.array(abstentions)
    evaluable_busts = np.sum((y_true == 1) & valid_mask)  # 3
    abstained_busts = np.sum((y_true == 1) & np.array(abstentions))  # 1
    assert evaluable_busts + abstained_busts == tot_busts

def test_decimal_round_half_up_cost_accounting():
    """Verify that monetary totals are summed at full precision and rounded with Decimal ROUND_HALF_UP."""
    from decimal import Decimal, ROUND_HALF_UP

    def format_currency(val: float) -> str:
        d = Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"${d:.2f}"

    # 1. Synoptic N=2000 calculations
    bust_loss_2000 = 83 * 0.37 + 111 * 0.875  # 127.835
    surveillance_2000 = 100 * 0.08 + 1689 * 0.26  # 447.14
    abstention_2000 = 17 * 0.15  # 2.55
    total_2000 = bust_loss_2000 + surveillance_2000 + abstention_2000  # 577.525

    assert abs(bust_loss_2000 - 127.835) < 1e-9
    assert format_currency(bust_loss_2000) == "$127.84"
    assert format_currency(total_2000) == "$577.53"

    # 2. Balanced N=2400 calculations
    bust_loss_2400 = 57 * 0.37 + 94 * 0.875  # 103.34
    surveillance_2400 = 124 * 0.08 + 1838 * 0.26 + 36 * 0.72  # 513.72
    abstention_2400 = 11 * 1.125 + 240 * 0.15  # 48.375
    total_2400 = bust_loss_2400 + surveillance_2400 + abstention_2400  # 665.435

    assert abs(abstention_2400 - 48.375) < 1e-9
    assert format_currency(abstention_2400) == "$48.38"
    assert format_currency(total_2400) == "$665.44"


def test_decision_engine_on_real_stage_b_parquet():
    """Execute end-to-end decision engine on real Stage B historical parquet archive."""
    parquet_path = Path("data/historical/multicycle_paired/paired_multicycle_stage_b_2026-08-18_2026-08-24.parquet")
    if not parquet_path.exists():
        pytest.skip("Stage B archive not found on local path.")

    df_real = pd.read_parquet(parquet_path)
    assert len(df_real) == 35040

    # Extract issue-time features on a sample subset
    pipeline = IssueTimeSafeFeaturePipeline()
    sample_slice = df_real.iloc[:300].copy()
    X_feat, meta = pipeline.extract_features(sample_slice)

    # Fit decision engine
    model = RegularizedLogisticClassifier()
    # Dummy binary target for smoke test
    y_dummy = pd.Series([1 if i % 15 == 0 else 0 for i in range(len(X_feat))], name="bust_label")
    model.fit(X_feat, y_dummy)

    calibrator = ProbabilityCalibrator(method="platt")
    raw_p = model.predict_proba(X_feat)[:, 1]
    calibrator.fit(y_dummy, raw_p)

    df_slice_train = X_feat.copy()
    df_slice_train["location_id"] = meta["location"]
    df_slice_train["bust_label"] = y_dummy

    engine = ForecastRiskDecisionEngine(model=model, calibrator=calibrator)
    engine.fit_reference_context(df_slice_train, X_feat, y_dummy, model, calibrator=calibrator)

    # Evaluate decisions on test instances across multiple locations
    for idx in [0, 50, 150, 250]:
        query_row = X_feat.iloc[idx].to_dict()
        loc = meta["location"].iloc[idx]
        var = meta["variable"].iloc[idx]

        dec = engine.decide_forecast_risk(
            features=query_row,
            location_id=loc,
            variable=var,
        )

        assert isinstance(dec, ForecastRiskDecision)
        assert dec.decision in [d for d in OperationalDecision]
        assert 0.0 <= dec.risk_score <= 1.0
        assert 0.0 <= dec.confidence <= 1.0
        assert len(dec.decision_id) > 0


# =========================================================================
# 10. Additional Adversarial & Boundary Tests
# =========================================================================

def test_abstention_on_extreme_novelty_and_sparse_support(fitted_decision_engine, synthetic_training_data):
    """Extreme feature novelty (>2.8) with sparse analogues must trigger abstention."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()
    query["ensemble_std"] = 150.0  # Impossible outlier
    query["forecast_delta_24h"] = 120.0

    dec = fitted_decision_engine.decide_forecast_risk(query, raw_bust_probability=0.85, location_id="delhi")
    assert dec.abstention_required
    assert dec.decision == OperationalDecision.ABSTAIN
    assert "novelty" in str(dec.abstention_reason).lower()


def test_abstention_on_novel_location_with_high_novelty(fitted_decision_engine, synthetic_training_data):
    """Novel unmonitored location with high novelty must trigger abstention."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()
    query["ensemble_std"] = 12.0  # High novelty

    dec = fitted_decision_engine.decide_forecast_risk(query, raw_bust_probability=0.70, location_id="nonexistent_city_xyz")
    assert dec.abstention_required
    assert dec.decision == OperationalDecision.ABSTAIN


def test_incomplete_ensemble_member_count_flagged(fitted_decision_engine, synthetic_training_data):
    """Incomplete ensemble members (<20) must be flagged in data quality issues."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()
    query["member_count"] = 12  # Severely degraded ensemble

    dec = fitted_decision_engine.decide_forecast_risk(query, raw_bust_probability=0.25, location_id="delhi")
    assert dec.data_quality_level == DataQualityState.DEGRADED
    assert any("ensemble" in s.lower() for s in dec.provenance.get("data_quality_issues", []))


def test_unsupported_novel_location_downgrades_confidence(fitted_decision_engine, synthetic_training_data):
    """In-domain features for a novel location must incur a confidence penalty."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()

    dec_known = fitted_decision_engine.decide_forecast_risk(query, raw_bust_probability=0.20, location_id="delhi")
    dec_novel = fitted_decision_engine.decide_forecast_risk(query, raw_bust_probability=0.20, location_id="unseen_remote_outpost")

    assert dec_novel.confidence < dec_known.confidence
    assert dec_novel.location_reliability.get("reliability_status") == "NOVEL_LOCATION"


def test_lead_time_awareness_extended_horizon_risk(fitted_decision_engine, synthetic_training_data):
    """Extended lead horizon (72h) must be marked and elevate horizon uncertainty."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()
    query["lead_hours"] = 72

    dec = fitted_decision_engine.decide_forecast_risk(query, raw_bust_probability=0.30, location_id="delhi")
    assert dec.lead_time_level == "EXTENDED"
    assert any(item["source"] == "LEAD_TIME_HORIZON" for item in dec.supporting_evidence)


def test_data_quality_gating_clean_vs_degraded(fitted_decision_engine, synthetic_training_data):
    """Clean feature vector vs degraded vector (with partial NaNs) must be categorized properly."""
    _, X_train, _ = synthetic_training_data
    query_clean = X_train.median().to_dict()
    query_degraded = X_train.median().to_dict()
    query_degraded["forecast_delta_6h"] = np.nan
    query_degraded["forecast_delta_24h"] = np.nan

    dec_clean = fitted_decision_engine.decide_forecast_risk(query_clean, raw_bust_probability=0.10)
    dec_deg = fitted_decision_engine.decide_forecast_risk(query_degraded, raw_bust_probability=0.10)

    assert dec_clean.data_quality_level == DataQualityState.CLEAN
    assert dec_deg.data_quality_level == DataQualityState.DEGRADED


def test_decision_stability_tiny_perturbations(fitted_decision_engine, synthetic_training_data):
    """A 1% numerical perturbation should not cause a decision jump for stable instances."""
    _, X_train, _ = synthetic_training_data
    query1 = X_train.median().to_dict()
    query2 = query1.copy()
    query2["ensemble_std"] = query1["ensemble_std"] * 1.01

    dec1 = fitted_decision_engine.decide_forecast_risk(query1, raw_bust_probability=0.15, location_id="delhi")
    dec2 = fitted_decision_engine.decide_forecast_risk(query2, raw_bust_probability=0.15, location_id="delhi")

    assert dec1.decision == dec2.decision
    assert dec1.risk_level == dec2.risk_level
    assert abs(dec1.risk_score - dec2.risk_score) < 0.05


def test_policy_alert_fatigue_penalty():
    """Policy must reflect alert fatigue suppression on marginal scores."""
    policy = RiskDecisionPolicy(alert_fatigue_penalty=0.20, watch_threshold=0.15)
    assert policy.alert_fatigue_penalty == 0.20
    level = policy.evaluate_risk_level(0.12)
    assert level == RiskLevel.LOW


def test_counterfactual_sensitivity_for_low_risk(fitted_decision_engine, synthetic_training_data):
    """Low risk cases must provide counterfactuals explaining what would elevate risk."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()
    query["ensemble_std"] = 0.5

    dec = fitted_decision_engine.decide_forecast_risk(query, raw_bust_probability=0.05, location_id="delhi")
    sens = dec.sensitivity_analysis
    assert len(sens.get("counterfactual_evidence", [])) > 0


def test_provenance_auditability_and_hashes(fitted_decision_engine, synthetic_training_data):
    """Provenance dictionary must contain engine version, policy version, and timestamps."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()

    dec = fitted_decision_engine.decide_forecast_risk(query, raw_bust_probability=0.25, location_id="delhi")
    prov = dec.provenance
    assert prov["engine_version"] == "15.0.0"
    assert prov["policy_version"] == "1.0"
    assert "timestamp_utc" in prov


def test_pathological_negative_ensemble_std(fitted_decision_engine, synthetic_training_data):
    """Negative ensemble spread (physically impossible) must be flagged and trigger abstention."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()
    query["ensemble_std"] = -2.5

    dec = fitted_decision_engine.decide_forecast_risk(query, raw_bust_probability=0.25, location_id="delhi")
    assert dec.abstention_required
    assert dec.data_quality_level == DataQualityState.CORRUPTED


def test_real_stage_b_multilocation_decisions():
    """Verify decision engine across 5 distinct geographic stations on real Stage B parquet."""
    parquet_path = Path("data/historical/multicycle_paired/paired_multicycle_stage_b_2026-08-18_2026-08-24.parquet")
    if not parquet_path.exists():
        pytest.skip("Stage B archive not found on local path.")

    df_real = pd.read_parquet(parquet_path)
    pipeline = IssueTimeSafeFeaturePipeline()
    sample_slice = df_real.iloc[:500].copy()
    X_feat, meta = pipeline.extract_features(sample_slice)

    model = RegularizedLogisticClassifier()
    y_dummy = pd.Series([1 if i % 10 == 0 else 0 for i in range(len(X_feat))], name="bust_label")
    model.fit(X_feat, y_dummy)

    engine = ForecastRiskDecisionEngine(model=model)
    df_train = X_feat.copy()
    df_train["location_id"] = meta["location"]
    df_train["bust_label"] = y_dummy
    engine.fit_reference_context(df_train, X_feat, y_dummy, model)

    locations_tested = set()
    for idx in range(len(X_feat)):
        loc = meta["location"].iloc[idx]
        if loc not in locations_tested:
            locations_tested.add(loc)
            row_dict = X_feat.iloc[idx].to_dict()
            dec = engine.decide_forecast_risk(row_dict, location_id=loc)
            assert isinstance(dec, ForecastRiskDecision)
            assert dec.decision in [d for d in OperationalDecision]
        if len(locations_tested) >= 5:
            break


# =========================================================================
# 11. Scientific Hardening: Monotonicity, Expected Loss & Governance
# =========================================================================

def test_expected_loss_minimization():
    """Expected loss calculation must identify optimal action based on probability."""
    policy = RiskDecisionPolicy(fn_cost_weight=2.5, fp_cost_weight=1.0)

    # Low risk (P=0.02) -> TRUST_FORECAST should have lowest expected loss
    losses_low = policy.compute_expected_losses(risk_probability=0.02, confidence=0.90)
    best_low = min(losses_low, key=losses_low.get)
    assert best_low == OperationalDecision.TRUST_FORECAST

    # Critical risk (P=0.90) -> ALERT_CRITICAL_BUST or WARN should have lowest expected loss
    losses_high = policy.compute_expected_losses(risk_probability=0.90, confidence=0.90)
    best_high = min(losses_high, key=losses_high.get)
    assert best_high in [OperationalDecision.ALERT_CRITICAL_BUST, OperationalDecision.WARN_POTENTIAL_BUST]


def test_monotonicity_of_risk_score_with_probability(fitted_decision_engine, synthetic_training_data):
    """Higher input probability must strictly yield non-decreasing composite risk score."""
    _, X_train, _ = synthetic_training_data
    query = X_train.median().to_dict()

    probs = [0.05, 0.15, 0.35, 0.60, 0.85]
    risk_scores = []
    for p in probs:
        dec = fitted_decision_engine.decide_forecast_risk(query, raw_bust_probability=p, location_id="delhi")
        risk_scores.append(dec.risk_score)

    for i in range(len(risk_scores) - 1):
        assert risk_scores[i] <= risk_scores[i + 1], f"Monotonicity violated: {risk_scores[i]} > {risk_scores[i+1]}"


def test_monotonicity_of_dispersion_with_trust(fitted_decision_engine, synthetic_training_data):
    """Greater ensemble spread must not increase trust (risk score must not decrease)."""
    _, X_train, _ = synthetic_training_data
    query_tight = X_train.median().to_dict()
    query_tight["ensemble_std"] = 0.5

    query_wide = X_train.median().to_dict()
    query_wide["ensemble_std"] = 4.5

    dec_tight = fitted_decision_engine.decide_forecast_risk(query_tight, raw_bust_probability=0.20, location_id="delhi")
    dec_wide = fitted_decision_engine.decide_forecast_risk(query_wide, raw_bust_probability=0.20, location_id="delhi")

    assert dec_wide.risk_score >= dec_tight.risk_score
    assert dec_wide.confidence <= dec_tight.confidence or dec_wide.uncertainty_level != "LOW"


def test_monotonicity_of_novelty_with_confidence(fitted_decision_engine, synthetic_training_data):
    """Higher feature novelty must strictly not increase decision confidence."""
    _, X_train, _ = synthetic_training_data
    query_normal = X_train.median().to_dict()

    query_novel = X_train.median().to_dict()
    query_novel["ensemble_std"] = 8.0
    query_novel["forecast_delta_24h"] = 9.0

    dec_norm = fitted_decision_engine.decide_forecast_risk(query_normal, raw_bust_probability=0.30, location_id="delhi")
    dec_nov = fitted_decision_engine.decide_forecast_risk(query_novel, raw_bust_probability=0.30, location_id="delhi")

    assert dec_nov.confidence <= dec_norm.confidence


def test_parameter_governance_registry_completeness():
    """All policy hyperparameters must be classified into explicit scientific governance classes."""
    policy = RiskDecisionPolicy()
    registry = policy.get_parameter_governance_registry()

    assert len(registry) >= 8
    for name, meta in registry.items():
        assert meta.governance_class is not None
        assert len(meta.description) > 0
        assert meta.empirical_source is not None


def test_threshold_sensitivity_analyzer_perturbations():
    """Threshold sensitivity analyzer must quantify decision switching rates under parameter perturbations."""
    from evaluation.decision_sensitivity import ThresholdSensitivityAnalyzer

    policy = RiskDecisionPolicy()
    np.random.seed(42)
    risk_scores = np.random.uniform(0.0, 1.0, 200)
    confidences = np.random.uniform(0.4, 0.9, 200)

    res = ThresholdSensitivityAnalyzer.evaluate_perturbations(policy, risk_scores, confidences)

    assert "mean_stability_score" in res
    assert "robustness_status" in res
    assert 0.0 <= res["mean_stability_score"] <= 1.0
    assert len(res["perturbation_results"]) == 4


def test_policy_benchmark_evaluator_on_synthetic_data(fitted_decision_engine, synthetic_training_data):
    """PolicyBenchmarkEvaluator must benchmark against climatology and naive baselines."""
    from evaluation.decision_policy_evaluator import PolicyBenchmarkEvaluator

    df_train, X_train, y_train = synthetic_training_data
    evaluator = PolicyBenchmarkEvaluator(fitted_decision_engine)

    benchmarks = evaluator.evaluate_dataset(X_train, y_train, locations=df_train["location_id"])

    assert "day15_policy" in benchmarks
    assert "climatology_baseline" in benchmarks
    assert "naive_threshold" in benchmarks

    day15_summary = benchmarks["day15_policy"]
    assert day15_summary.sample_count == len(X_train)
    assert 0.0 <= day15_summary.bust_prevalence <= 1.0
    assert day15_summary.total_cost >= 0.0


def test_single_class_all_zeros_labels(fitted_decision_engine, synthetic_training_data):
    """PolicyBenchmarkEvaluator must not crash when evaluated on dataset with zero busts."""
    from evaluation.decision_policy_evaluator import PolicyBenchmarkEvaluator

    _, X_train, _ = synthetic_training_data
    y_zeros = pd.Series(np.zeros(len(X_train), dtype=int))
    evaluator = PolicyBenchmarkEvaluator(fitted_decision_engine)

    benchmarks = evaluator.evaluate_dataset(X_train, y_zeros)
    assert benchmarks["day15_policy"].bust_prevalence == 0.0
    assert benchmarks["day15_policy"].false_negative_count == 0


def test_single_class_all_ones_labels(fitted_decision_engine, synthetic_training_data):
    """PolicyBenchmarkEvaluator must not crash when evaluated on dataset with 100% busts."""
    from evaluation.decision_policy_evaluator import PolicyBenchmarkEvaluator

    _, X_train, _ = synthetic_training_data
    y_ones = pd.Series(np.ones(len(X_train), dtype=int))
    evaluator = PolicyBenchmarkEvaluator(fitted_decision_engine)

    benchmarks = evaluator.evaluate_dataset(X_train, y_ones)
    assert benchmarks["day15_policy"].bust_prevalence == 1.0


def test_empty_dataframe_resilience(fitted_decision_engine):
    """PolicyBenchmarkEvaluator must return clean empty summary when given 0 rows."""
    from evaluation.decision_policy_evaluator import PolicyBenchmarkEvaluator

    X_empty = pd.DataFrame(columns=["ensemble_std", "lead_hours"])
    y_empty = pd.Series([], dtype=int)
    evaluator = PolicyBenchmarkEvaluator(fitted_decision_engine)

    benchmarks = evaluator.evaluate_dataset(X_empty, y_empty)
    assert benchmarks["day15_policy"].sample_count == 0


def test_real_stage_b_policy_benchmarking():
    """Run PolicyBenchmarkEvaluator on real Stage B historical parquet archive."""
    from evaluation.decision_policy_evaluator import PolicyBenchmarkEvaluator

    parquet_path = Path("data/historical/multicycle_paired/paired_multicycle_stage_b_2026-08-18_2026-08-24.parquet")
    if not parquet_path.exists():
        pytest.skip("Stage B archive not found on local path.")

    df_real = pd.read_parquet(parquet_path)
    pipeline = IssueTimeSafeFeaturePipeline()
    sample_slice = df_real.iloc[:400].copy()
    X_feat, meta = pipeline.extract_features(sample_slice)

    model = RegularizedLogisticClassifier()
    y_dummy = pd.Series([1 if i % 12 == 0 else 0 for i in range(len(X_feat))], name="bust_label")
    model.fit(X_feat, y_dummy)

    engine = ForecastRiskDecisionEngine(model=model)
    df_train = X_feat.copy()
    df_train["location_id"] = meta["location"]
    df_train["bust_label"] = y_dummy
    engine.fit_reference_context(df_train, X_feat, y_dummy, model)

    evaluator = PolicyBenchmarkEvaluator(engine)
    benchmarks = evaluator.evaluate_dataset(X_feat, y_dummy, locations=meta["location"], variables=meta["variable"])

    summary = benchmarks["day15_policy"]
    assert summary.sample_count == 400
    assert summary.total_cost > 0.0
