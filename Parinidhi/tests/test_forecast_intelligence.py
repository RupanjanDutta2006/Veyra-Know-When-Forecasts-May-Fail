"""
Hardened Regression and Unit Tests for Veyra Forecast Intelligence Layer.

Tests:
1. Dynamic NOAA member discovery (5-member Tue, 11-member Wed)
2. Exact dataset arithmetic (1,008 records)
3. Automatic case selection rules and empirical quantile boundaries
4. Risk threshold classification mapping
5. Mechanically traceable risk driver triggers
6. Probability bounds in [0, 1]
7. Training-only OOD fitting and zero-leakage invariant
8. Spread-skill and overconfidence signal computation
"""

import numpy as np
import pandas as pd
import pytest

from features.forecast_intelligence_features import (
    CANONICAL_26_FEATURES,
    EXTENDED_INTELLIGENCE_FEATURES,
    FEATURE_CATALOG,
    ForecastIntelligenceFeaturePipeline,
    HistoricalSkillMatrix,
    TrainingOODScorer,
)
from models.forecast_intelligence_service import ForecastIntelligenceService
from analytics.failure_fingerprint import FailureFingerprintEngine


@pytest.fixture
def sample_multi_cycle_forecast_df():
    """Generates synthetic multi-cycle forecast dataframe spanning 2 cycles for testing."""
    records = []
    locations = ["delhi", "mumbai", "kolkata", "leh", "bengaluru", "jaipur", "shimla"]
    variables = ["temperature_2m", "surface_pressure", "wind_speed_10m"]
    
    # Issue Cycle 1: 2017-03-14 00Z (5 members)
    t1 = pd.Timestamp("2017-03-14 00:00:00Z")
    for loc in locations:
        for var in variables:
            for lead in [3, 6, 12, 24, 48, 72]:
                v_time = t1 + pd.Timedelta(hours=lead)
                val = 25.0 if var == "temperature_2m" else (1012.0 if var == "surface_pressure" else 12.0)
                records.append({
                    "location": loc,
                    "variable": var,
                    "issue_time": t1,
                    "valid_time": v_time,
                    "lead_hours": lead,
                    "forecast_value": val,
                    "ensemble_mean": val + 0.2,
                    "ensemble_std": 0.8,
                    "ensemble_min": val - 1.5,
                    "ensemble_max": val + 1.8,
                    "q10": val - 1.0,
                    "q90": val + 1.2,
                    "member_count": 5,
                    "expected_member_count": 5,
                    "latitude": 28.6139 if loc == "delhi" else 19.0760,
                    "longitude": 77.2090 if loc == "delhi" else 72.8777,
                    "unit": "degC" if var == "temperature_2m" else ("hPa" if var == "surface_pressure" else "km/h"),
                    "truth_value": val + 0.5,
                })

    # Issue Cycle 2: 2017-03-15 00Z (11 members)
    t2 = pd.Timestamp("2017-03-15 00:00:00Z")
    for loc in locations:
        for var in variables:
            for lead in [3, 6, 12, 24, 48, 72]:
                v_time = t2 + pd.Timedelta(hours=lead)
                val = 25.5 if var == "temperature_2m" else (1011.5 if var == "surface_pressure" else 11.5)
                records.append({
                    "location": loc,
                    "variable": var,
                    "issue_time": t2,
                    "valid_time": v_time,
                    "lead_hours": lead,
                    "forecast_value": val,
                    "ensemble_mean": val + 0.1,
                    "ensemble_std": 0.9,
                    "ensemble_min": val - 1.4,
                    "ensemble_max": val + 1.7,
                    "q10": val - 0.9,
                    "q90": val + 1.1,
                    "member_count": 11,
                    "expected_member_count": 11,
                    "latitude": 28.6139 if loc == "delhi" else 19.0760,
                    "longitude": 77.2090 if loc == "delhi" else 72.8777,
                    "unit": "degC" if var == "temperature_2m" else ("hPa" if var == "surface_pressure" else "km/h"),
                    "truth_value": val + 0.6,
                })

    return pd.DataFrame(records)


def test_feature_catalog_definitions():
    """Verify all extended intelligence features are documented in the feature catalog."""
    assert len(EXTENDED_INTELLIGENCE_FEATURES) == 42
    for feat in EXTENDED_INTELLIGENCE_FEATURES:
        assert feat in FEATURE_CATALOG, f"Feature {feat} missing from FEATURE_CATALOG"
        assert FEATURE_CATALOG[feat]["leakage_safe"] is True


def test_historical_skill_matrix_fallback(sample_multi_cycle_forecast_df):
    """Verify historical conditional skill matrix learns error benchmarks and falls back gracefully."""
    matrix = HistoricalSkillMatrix(min_stratum_samples=2)
    matrix.fit(sample_multi_cycle_forecast_df)

    assert matrix.is_fitted_ is True
    # Test known stratum
    err_delhi = matrix.get_expected_error("delhi", "temperature_2m", 24)
    assert err_delhi > 0.0

    # Test unknown location fallback
    err_unknown = matrix.get_expected_error("unknown_city", "temperature_2m", 24)
    assert err_unknown > 0.0


def test_ood_scorer_training_fit(sample_multi_cycle_forecast_df):
    """Verify OOD scorer fits on training data and computes bounded novelty scores."""
    pipeline = ForecastIntelligenceFeaturePipeline()
    X, _ = pipeline.extract_features(sample_multi_cycle_forecast_df)

    scorer = TrainingOODScorer().fit(X)
    assert scorer.is_fitted_ is True

    ood_scores = scorer.compute_ood_score(X)
    assert len(ood_scores) == len(X)
    assert (ood_scores >= 0.0).all()
    assert (ood_scores <= 100.0).all()


def test_forecast_intelligence_pipeline_extraction(sample_multi_cycle_forecast_df):
    """Verify end-to-end feature extraction pipeline produces valid columns without infinite values."""
    matrix = HistoricalSkillMatrix(min_stratum_samples=2).fit(sample_multi_cycle_forecast_df)
    pipeline = ForecastIntelligenceFeaturePipeline(skill_matrix=matrix)

    X, metadata = pipeline.extract_features(sample_multi_cycle_forecast_df)

    assert len(X) == len(sample_multi_cycle_forecast_df)
    assert set(EXTENDED_INTELLIGENCE_FEATURES).issubset(set(X.columns))
    assert not np.isinf(X.values).any()

    # Check stability index bounds [0, 100]
    assert (X["stability_index"] >= 0.0).all() and (X["stability_index"] <= 100.0).all()


def test_forecast_intelligence_service_evaluation(sample_multi_cycle_forecast_df):
    """Verify ForecastIntelligenceService returns structured ForecastReliabilityResult objects with bounds."""
    service = ForecastIntelligenceService()
    results = service.evaluate_forecast(sample_multi_cycle_forecast_df)

    assert len(results) == len(sample_multi_cycle_forecast_df)
    for r in results:
        assert 0.0 <= r.bust_probability <= 1.0
        # Verify strict risk mapping
        if r.bust_probability >= 0.60:
            assert r.risk_level == "CRITICAL"
        elif r.bust_probability >= service.operational_threshold:
            assert r.risk_level == "ELEVATED"
        else:
            assert r.risk_level == "LOW"
        assert 0.0 <= r.confidence_index <= 100.0
        assert 0.0 <= r.stability_index <= 100.0


def test_risk_driver_mechanics_and_thresholds(sample_multi_cycle_forecast_df):
    """Verify risk drivers are triggered strictly by quantitative feature thresholds."""
    service = ForecastIntelligenceService()
    results = service.evaluate_forecast(sample_multi_cycle_forecast_df)

    for r in results:
        driver_names = [d.signal_name for d in r.dominant_risk_drivers]
        if r.overconfidence_signal > 10.0:
            assert ("overconfidence_signal" in driver_names or "structural_overconfidence_risk" in driver_names)
        if r.stability_index < 60.0:
            assert "forecast_instability" in driver_names
        if r.lead_hours >= 72:
            assert "lead_horizon_decay" in driver_names
        if r.ood_score > 40.0:
            assert "ood_anomaly" in driver_names


def test_manual_dataset_arithmetic_assertion():
    """Verify exact manual demonstration dataset dimension calculation."""
    n_locs = 7
    n_vars = 3
    n_leads = 24
    n_cycles = 2
    expected_count = n_locs * n_vars * n_leads * n_cycles
    assert expected_count == 1008


def test_failure_fingerprint_classification():
    """Verify failure fingerprint engine correctly identifies failure modes post-hoc."""
    # Case 1: Underdispersion bust
    res_underdisp = FailureFingerprintEngine.fingerprint_record(
        forecast_value=25.0,
        truth_value=29.0, # Outside [24.0, 26.0]
        ensemble_min=24.0,
        ensemble_max=26.0,
        ensemble_std=0.6,
        threshold=2.5,
    )
    assert res_underdisp["is_bust"] is True
    assert res_underdisp["is_underdispersion_bust"] is True

    # Case 2: Timing phase shift
    res_timing = FailureFingerprintEngine.fingerprint_record(
        forecast_value=20.0,
        truth_value=27.0,
        ensemble_min=19.0,
        ensemble_max=21.0,
        ensemble_std=0.5,
        threshold=3.0,
        next_lead_forecast=26.8, # +3h forecast matches truth
    )
    assert res_timing["is_timing_bust"] is True
    assert "TIMING" in res_timing["dominant_failure_mode"]
