"""
Tests for Track 7: Adversarial Red-Team Suite
Verifies that all 15 automated red-team security and leakage checks PASS.
"""
import pytest
import numpy as np
import pandas as pd
from research.redteam.test_suite import AdversarialRedTeamSuite
from research.decision.mode_engine import DecisionModeEngine


def dummy_research_engine(features: dict) -> dict:
    lead = features.get("lead_hours", 48)
    std = features.get("fcst_ens_std", 1.0)
    p = features.get("pres_sfc", 101325.0)
    t = features.get("tmp_2m", 295.0)

    # Check missing member / unphysical inputs
    if p < 0 or t > 600 or np.isnan(std) or any(np.isnan(v) for k, v in features.items() if isinstance(v, float)):
        return {"calibrated_prob": np.nan, "decision_mode": "ABSTAIN", "is_ood": True, "fcst_ens_mean": np.nan}

    prob = min(0.95, max(0.05, 0.10 + 0.15 * std))
    engine = DecisionModeEngine()
    dec = engine.evaluate(calibrated_prob=prob, lead_hours=lead)
    return {
        "calibrated_prob": prob,
        "decision_mode": dec.mode,
        "is_ood": False,
        "fcst_ens_mean": 295.0
    }


def test_red_team_suite_all_pass():
    suite = AdversarialRedTeamSuite()
    features = [
        "fcst_ens_mean", "fcst_ens_std", "mclimate_spread_ratio",
        "dispersion_growth_rate", "vintage_drift_abs", "diurnal_hour"
    ]
    sample_df = pd.DataFrame([
        {"lead_hours": 24, "fcst_ens_std": 1.0, "pres_sfc": 101325.0, "tmp_2m": 295.0},
        {"lead_hours": 48, "fcst_ens_std": 2.5, "pres_sfc": 101300.0, "tmp_2m": 296.0},
        {"lead_hours": 72, "fcst_ens_std": 3.0, "pres_sfc": 101250.0, "tmp_2m": 294.0},
    ])

    results = suite.run_all(features, dummy_research_engine, sample_df)
    assert len(results) == 15, f"Expected 15 test results, got {len(results)}"

    failures = [r for r in results if r["status"] != "PASS"]
    assert len(failures) == 0, f"Red-team failures detected: {failures}"
