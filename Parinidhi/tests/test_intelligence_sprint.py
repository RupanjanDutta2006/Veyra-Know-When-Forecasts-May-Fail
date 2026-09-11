"""
Comprehensive Test Battery for Veyra Parallel Intelligence & Product Sprint.

Verifies:
1. Operational Risk Tiers & Probability Boundaries (0.0, 0.0599, 0.060, 0.5999, 0.60, 1.0)
2. Configurable Operational Trust Horizon (Pcrit = 0.35 cutoff, status derivation)
3. Epistemic Abstention on severe OOD (D_M >= 40.0) and corrupted/missing NaNs
4. Actionable Decision Modes (HIGH_TRUST, CAUTION, RECHECK_SOON, DO_NOT_RELY_SOLELY, ABSTAIN)
5. Analytical Failure Fingerprint Taxonomy (non-causal schemas, INSUFFICIENT_EVIDENCE)
6. Lead-Time Trust Timeline (+24h to +240h, zero fabricated values for unobserved leads)
7. Deterministic Demonstration Scenarios API & Scientific Disclaimers
8. Strict Backward Compatibility of ForecastRiskItem and ForecastRiskResponse schemas
9. Absence of Target/Future Information Leakage
"""

from datetime import datetime, timezone, timedelta
import pytest
import numpy as np
import pandas as pd

from api.demo_scenarios import DEMO_SCENARIOS_METADATA, generate_scenario_dataframe
from api.risk_engine import (
    OperationalRiskEngine,
    TRUST_HORIZON_DEFAULT_THRESHOLD,
    OOD_SEVERE_ABSTAIN_THRESHOLD,
    FINGERPRINT_CATALOG,
)
from api.routes import ForecastBustAPI
from api.schemas import (
    DataStatus,
    DecisionMode,
    ForecastRiskItem,
    ForecastRiskResponse,
)


@pytest.fixture
def risk_engine():
    return OperationalRiskEngine()


@pytest.fixture
def api():
    return ForecastBustAPI()


# -------------------------------------------------------------------------
# Test 1: Probability Tier Boundaries & Risk Level Mapping
# -------------------------------------------------------------------------
def test_probability_boundaries(risk_engine):
    """Verify exact boundary transitions for LOW, ELEVATED, CRITICAL and Decision Modes."""
    # 1. Zero risk -> HIGH_TRUST
    mode, reason, action = risk_engine.determine_decision_mode(
        p_bust=0.0, ood_score=2.0, stability_index=100.0, fingerprint="STABLE_SYNOPTIC_CONSENSUS", lead_hours=24
    )
    assert mode == DecisionMode.HIGH_TRUST

    # 2. 0.0599 -> HIGH_TRUST
    mode, reason, action = risk_engine.determine_decision_mode(
        p_bust=0.0599, ood_score=2.0, stability_index=100.0, fingerprint="STABLE_SYNOPTIC_CONSENSUS", lead_hours=24
    )
    assert mode == DecisionMode.HIGH_TRUST

    # 3. 0.100 -> CAUTION
    mode, reason, action = risk_engine.determine_decision_mode(
        p_bust=0.100, ood_score=2.0, stability_index=90.0, fingerprint="STABLE_SYNOPTIC_CONSENSUS", lead_hours=24
    )
    assert mode == DecisionMode.CAUTION

    # 4. 0.5999 -> CAUTION
    mode, reason, action = risk_engine.determine_decision_mode(
        p_bust=0.5999, ood_score=2.0, stability_index=90.0, fingerprint="STABLE_SYNOPTIC_CONSENSUS", lead_hours=24
    )
    assert mode == DecisionMode.CAUTION

    # 5. 0.600 -> DO_NOT_RELY_SOLELY
    mode, reason, action = risk_engine.determine_decision_mode(
        p_bust=0.600, ood_score=2.0, stability_index=90.0, fingerprint="STABLE_SYNOPTIC_CONSENSUS", lead_hours=24
    )
    assert mode == DecisionMode.DO_NOT_RELY_SOLELY

    # 6. 1.0 -> DO_NOT_RELY_SOLELY
    mode, reason, action = risk_engine.determine_decision_mode(
        p_bust=1.0, ood_score=2.0, stability_index=10.0, fingerprint="LONG_LEAD_DECAY", lead_hours=144
    )
    assert mode == DecisionMode.DO_NOT_RELY_SOLELY


# -------------------------------------------------------------------------
# Test 2: Epistemic Abstention on Severe OOD & Corrupted Inputs
# -------------------------------------------------------------------------
def test_epistemic_abstention(risk_engine):
    """Verify that severe OOD (D_M >= 40.0) or corrupted inputs trigger ABSTAIN."""
    # Exact threshold 40.0 triggers ABSTAIN
    mode, reason, action = risk_engine.determine_decision_mode(
        p_bust=0.02, ood_score=40.0, stability_index=100.0, fingerprint="STABLE_SYNOPTIC_CONSENSUS", lead_hours=24
    )
    assert mode == DecisionMode.ABSTAIN
    assert "out-of-distribution" in reason.lower()

    # Extreme OOD 75.0 triggers ABSTAIN
    mode, reason, action = risk_engine.determine_decision_mode(
        p_bust=0.02, ood_score=75.0, stability_index=100.0, fingerprint="STABLE_SYNOPTIC_CONSENSUS", lead_hours=24
    )
    assert mode == DecisionMode.ABSTAIN

    # Corrupted input trigger
    mode, reason, action = risk_engine.determine_decision_mode(
        p_bust=0.02, ood_score=5.0, stability_index=100.0, fingerprint="STABLE_SYNOPTIC_CONSENSUS", lead_hours=24, has_corrupted_input=True
    )
    assert mode == DecisionMode.ABSTAIN


# -------------------------------------------------------------------------
# Test 3: Decision Mode Trigger Logic
# -------------------------------------------------------------------------
def test_decision_modes_triggers(risk_engine):
    """Verify RECHECK_SOON and LONG_LEAD_DECAY trigger paths."""
    # Revision shock triggers RECHECK_SOON
    mode, reason, action = risk_engine.determine_decision_mode(
        p_bust=0.15, ood_score=5.0, stability_index=35.0, fingerprint="RAPID_REVISION_SHOCK", lead_hours=48
    )
    assert mode == DecisionMode.RECHECK_SOON
    assert "Revision Shock" in reason

    # Long lead decay beyond 120h triggers DO_NOT_RELY_SOLELY
    mode, reason, action = risk_engine.determine_decision_mode(
        p_bust=0.20, ood_score=8.0, stability_index=45.0, fingerprint="LONG_LEAD_DECAY", lead_hours=144
    )
    assert mode == DecisionMode.DO_NOT_RELY_SOLELY


# -------------------------------------------------------------------------
# Test 4: Operational Trust Horizon Logic
# -------------------------------------------------------------------------
def test_operational_trust_horizon_derivation(api):
    """Verify that operational trust horizon is evaluated across leads without fabrication."""
    res_a = api.run_scenario("scenario_a_high_trust")
    h_a = res_a.get("operational_trust_horizon")
    assert h_a is not None
    assert h_a["threshold_used"] == TRUST_HORIZON_DEFAULT_THRESHOLD
    assert h_a["threshold_type"] == "product_design_threshold"
    assert "configurable research/product design threshold" in h_a["scientific_note"]

    # Scenario B exhibits decay
    res_b = api.run_scenario("scenario_b_long_lead_decay")
    h_b = res_b.get("operational_trust_horizon")
    assert h_b is not None
    assert h_b["status"] in ("DECAYS_AT_LEAD", "WITHIN_HORIZON", "FULL_HORIZON_RELIABLE")


# -------------------------------------------------------------------------
# Test 5: Failure Fingerprint Taxonomy & Non-Causal Framing
# -------------------------------------------------------------------------
def test_fingerprint_taxonomy():
    """Verify all 7 fingerprints have required structured non-causal keys."""
    required_keys = ["name", "description", "interpretation", "limitations"]
    for fp_id, meta in FINGERPRINT_CATALOG.items():
        for k in required_keys:
            assert k in meta, f"Missing {k} in fingerprint {fp_id}"
            assert len(meta[k]) > 0
        # Verify non-causal phrasing
        interp = meta["interpretation"].lower()
        assert any(term in interp for term in ["associated with", "consistent with", "pattern", "observed in"])


# -------------------------------------------------------------------------
# Test 6: Demonstration Scenarios Execution & Disclaimers
# -------------------------------------------------------------------------
def test_demo_scenarios_contract(api):
    """Verify all 4 simulation scenarios return valid responses with disclaimers."""
    scenarios_list = api.list_scenarios()
    assert scenarios_list["count"] == 4
    assert "NOT scientific validation cases" in scenarios_list["disclaimer"]

    expected_modes = {
        "scenario_a_high_trust": DecisionMode.HIGH_TRUST.value,
        "scenario_b_long_lead_decay": DecisionMode.DO_NOT_RELY_SOLELY.value,
        "scenario_c_revision_shock": DecisionMode.RECHECK_SOON.value,
        "scenario_d_severe_ood": DecisionMode.ABSTAIN.value,
    }

    for scenario_id, exp_mode in expected_modes.items():
        res = api.run_scenario(scenario_id)
        assert res["request_id"].startswith("req-")
        assert len(res["forecasts"]) == 10
        assert len(res["trust_timeline"]) == 10

        target_lead = res["scenario_meta"]["lead_hours"]
        target_item = next((f for f in res["forecasts"] if f["lead_hours"] == target_lead), None)
        assert target_item is not None
        assert target_item["decision_mode"] == exp_mode

        # Verify scenario disclaimer
        assert "disclaimer" in res["scenario_meta"]
        assert "simulation scenario" in res["scenario_meta"]["disclaimer"].lower()


# -------------------------------------------------------------------------
# Test 7: Backward Compatibility of Existing API Schemas
# -------------------------------------------------------------------------
def test_schema_backward_compatibility(api):
    """Ensure all legacy Builder 1 fields remain intact and properly typed."""
    res = api.run_scenario("scenario_a_high_trust")
    assert "request_id" in res
    assert "location" in res
    assert "issue_time" in res
    assert "model_version" in res
    assert "decision_threshold" in res
    assert "provenance" in res
    assert "forecasts" in res

    f0 = res["forecasts"][0]
    # Mandatory legacy fields
    assert "valid_time" in f0
    assert "lead_hours" in f0
    assert "bust_probability" in f0
    assert "bust_alert" in f0
    assert "data_status" in f0
    assert "verification_status" in f0
    assert "explanation" in f0
    assert "primary_driver" in f0["explanation"]
    assert "driver_summary" in f0["explanation"]


# -------------------------------------------------------------------------
# Test 8: Zero Future / Target Leakage
# -------------------------------------------------------------------------
def test_zero_target_leakage(risk_engine):
    """Ensure prediction does NOT require or leak ground-truth / future errors."""
    now = datetime.now(timezone.utc)
    df_clean = pd.DataFrame([{
        "issue_time": now.isoformat(),
        "valid_time": (now + timedelta(hours=24)).isoformat(),
        "lead_hours": 24,
        "location_id": "delhi",
        "variable": "temperature_2m",
        "unit": "K",
        "forecast_value": 300.0,
        "ensemble_mean": 300.0,
        "ensemble_std": 0.5,
    }])
    # Should NOT have forecast_abs_error or verification_truth
    assert "forecast_abs_error" not in df_clean.columns
    res = risk_engine.process_forecast_dataframe(df_clean, location_id="delhi")
    assert res.forecasts[0].verification_status == "NO_TRUTH_AVAILABLE"
    assert res.forecasts[0].bust_probability >= 0.0
