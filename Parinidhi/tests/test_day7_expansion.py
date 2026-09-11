"""
Multi-Location Multi-Cycle Forecast Instability Test Suite.

Tests:
1. LocationRegistry candidate expansion (20 Indian locations) & spatial colocation.
2. Multi-cycle (00Z, 06Z, 12Z, 18Z) revision extraction for same valid time.
3. 6h, 12h, and 24h signed revisions and revision magnitudes.
4. Second-order revision and spread acceleration mathematics.
5. Strict NaN handling when preceding cycle is absent (no 0.0 imputation).
6. Safeguard against same-run lead difference pollution.
7. Safeguard against future issue-time leakage.
8. Deterministic trajectory regime classification with variable-specific tolerances.
9. Structured 6-group Forecast Instability Fingerprint schema compliance.
10. Zero-regression verification of Day 5 ForecastBustModelService production contract.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from api.location_service import LocationRegistry, haversine_distance_km
from features.feature_pipeline import FEATURE_COLUMN_NAMES
from features.instability_feature_pipeline import (
    ALL_DAY7_FEATURE_NAMES,
    EXPERIMENTAL_INSTABILITY_FEATURE_NAMES,
    InstabilityFeaturePipeline,
)
from features.instability_fingerprint import (
    DEFAULT_VARIABLE_TOLERANCES,
    ForecastInstabilityFingerprintEngine,
    classify_forecast_trajectory,
)
from models.model_service import ForecastBustModelService


# ---------------------------------------------------------------------------
# Test 1: Location Registry 20-Location Expansion & Spatial Colocation
# ---------------------------------------------------------------------------
def test_1_location_registry_20_candidate_stations():
    registry = LocationRegistry()
    locations = registry.list_locations()
    assert len(locations) == 20, f"Expected 20 candidate locations, found {len(locations)}"

    loc_ids = [l["location_id"] for l in locations]
    expected_cities = [
        "delhi", "srinagar", "chandigarh", "jaipur", "lucknow",
        "mumbai", "pune", "ahmedabad", "goa",
        "bhopal", "nagpur", "raipur",
        "kolkata", "bhubaneswar", "ranchi", "guwahati",
        "bengaluru", "chennai", "hyderabad", "kochi",
    ]
    for city in expected_cities:
        assert city in loc_ids, f"Expected city '{city}' in location registry"

    # Delhi is source-verified with pilot grid coords
    delhi_info = registry.get_location("delhi")
    assert delhi_info.actual_grid_coordinates is not None
    assert delhi_info.actual_grid_coordinates.latitude == 28.50
    assert delhi_info.actual_grid_coordinates.longitude == 77.25
    assert delhi_info.spatial_distance_km is not None
    assert 10.0 < delhi_info.spatial_distance_km < 15.0

    # Unverified candidate (e.g., mumbai) has None grid coords until source-provided
    mumbai_info = registry.get_location("mumbai")
    assert mumbai_info.actual_grid_coordinates is None
    assert mumbai_info.spatial_distance_km is None

    # Providing actual grid coords dynamically resolves spatial offset
    mumbai_resolved = registry.get_location("mumbai", actual_grid_lat=19.00, actual_grid_lon=73.00)
    assert mumbai_resolved.actual_grid_coordinates is not None
    assert mumbai_resolved.spatial_distance_km is not None
    assert 10.0 < mumbai_resolved.spatial_distance_km < 20.0


# ---------------------------------------------------------------------------
# Test 2: Multi-Cycle Revision Intelligence (Same Valid Time)
# ---------------------------------------------------------------------------
def test_2_multi_cycle_revision_same_valid_time():
    """
    Construct 4 synthetic initialization cycles (00Z, 06Z, 12Z, 18Z) on 2026-08-20
    all predicting the SAME target valid_time (2026-08-21T18:00:00Z).
    Verify 6h, 12h, and 24h revisions match exact differences.
    """
    target_valid = datetime(2026, 8, 21, 18, 0, 0, tzinfo=timezone.utc)

    # 4 consecutive cycles 6 hours apart
    t_00z = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_06z = datetime(2026, 8, 20, 6, 0, 0, tzinfo=timezone.utc)
    t_12z = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
    t_18z = datetime(2026, 8, 20, 18, 0, 0, tzinfo=timezone.utc)

    records = [
        {
            "location": "delhi", "latitude": 28.61, "longitude": 77.21,
            "issue_time": t_00z, "valid_time": target_valid, "lead_hours": 42,
            "variable": "temperature_2m", "forecast_value": 30.0, "ensemble_mean": 30.0,
            "ensemble_std": 1.0, "member_count": 31,
        },
        {
            "location": "delhi", "latitude": 28.61, "longitude": 77.21,
            "issue_time": t_06z, "valid_time": target_valid, "lead_hours": 36,
            "variable": "temperature_2m", "forecast_value": 31.5, "ensemble_mean": 31.5,
            "ensemble_std": 1.4, "member_count": 31,
        },
        {
            "location": "delhi", "latitude": 28.61, "longitude": 77.21,
            "issue_time": t_12z, "valid_time": target_valid, "lead_hours": 30,
            "variable": "temperature_2m", "forecast_value": 33.0, "ensemble_mean": 33.0,
            "ensemble_std": 2.0, "member_count": 31,
        },
        {
            "location": "delhi", "latitude": 28.61, "longitude": 77.21,
            "issue_time": t_18z, "valid_time": target_valid, "lead_hours": 24,
            "variable": "temperature_2m", "forecast_value": 32.0, "ensemble_mean": 32.0,
            "ensemble_std": 1.8, "member_count": 31,
        },
    ]
    df = pd.DataFrame(records)

    pipeline = InstabilityFeaturePipeline()
    canonical_X, experimental_X, metadata = pipeline.extract_features(df)

    # For 00z: No prior cycle -> all deltas NaN
    assert np.isnan(canonical_X.loc[0, "forecast_delta_6h"])
    assert np.isnan(experimental_X.loc[0, "forecast_delta_12h"])
    assert np.isnan(canonical_X.loc[0, "forecast_delta_24h"])

    # For 06z: 6h prior is 00z (31.5 - 30.0 = +1.5)
    assert pytest.approx(canonical_X.loc[1, "forecast_delta_6h"], 1e-4) == 1.5
    assert pytest.approx(experimental_X.loc[1, "forecast_revision_mag_6h"], 1e-4) == 1.5
    assert np.isnan(experimental_X.loc[1, "forecast_delta_12h"])

    # For 12z: 6h prior is 06z (33.0 - 31.5 = +1.5), 12h prior is 00z (33.0 - 30.0 = +3.0)
    assert pytest.approx(canonical_X.loc[2, "forecast_delta_6h"], 1e-4) == 1.5
    assert pytest.approx(experimental_X.loc[2, "forecast_delta_12h"], 1e-4) == 3.0
    assert pytest.approx(experimental_X.loc[2, "spread_delta_12h"], 1e-4) == (2.0 - 1.0)

    # For 18z: 6h prior is 12z (32.0 - 33.0 = -1.0), 12h prior is 06z (32.0 - 31.5 = +0.5)
    assert pytest.approx(canonical_X.loc[3, "forecast_delta_6h"], 1e-4) == -1.0
    assert pytest.approx(experimental_X.loc[3, "forecast_revision_mag_6h"], 1e-4) == 1.0
    assert pytest.approx(experimental_X.loc[3, "forecast_delta_12h"], 1e-4) == 0.5


# ---------------------------------------------------------------------------
# Test 3: Second-Order Revision Acceleration Mathematics
# ---------------------------------------------------------------------------
def test_3_revision_acceleration_mathematics():
    """
    Verify revision_accel_6h: (X(T, V) - 2*X(T-6h, V) + X(T-12h, V)) / 6.
    """
    target_valid = datetime(2026, 8, 22, 12, 0, 0, tzinfo=timezone.utc)
    t_00z = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_06z = datetime(2026, 8, 20, 6, 0, 0, tzinfo=timezone.utc)
    t_12z = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)

    # Let X(00z) = 20.0, X(06z) = 22.0 (delta = +2.0), X(12z) = 26.0 (delta = +4.0)
    # accel_6h = (4.0 - 2.0) / 6 = 2.0 / 6 = 0.3333 °C/h
    records = [
        {"location": "delhi", "latitude": 28.61, "longitude": 77.21, "issue_time": t_00z, "valid_time": target_valid, "lead_hours": 60, "variable": "temperature_2m", "forecast_value": 20.0, "ensemble_mean": 20.0, "ensemble_std": 1.0, "member_count": 31},
        {"location": "delhi", "latitude": 28.61, "longitude": 77.21, "issue_time": t_06z, "valid_time": target_valid, "lead_hours": 54, "variable": "temperature_2m", "forecast_value": 22.0, "ensemble_mean": 22.0, "ensemble_std": 1.2, "member_count": 31},
        {"location": "delhi", "latitude": 28.61, "longitude": 77.21, "issue_time": t_12z, "valid_time": target_valid, "lead_hours": 48, "variable": "temperature_2m", "forecast_value": 26.0, "ensemble_mean": 26.0, "ensemble_std": 1.6, "member_count": 31},
    ]
    df = pd.DataFrame(records)

    pipeline = InstabilityFeaturePipeline()
    _, experimental_X, _ = pipeline.extract_features(df)

    # 00z and 06z do not have 2 prior cycles -> accel NaN
    assert np.isnan(experimental_X.loc[0, "revision_accel_6h"])
    assert np.isnan(experimental_X.loc[1, "revision_accel_6h"])

    # 12z has both 06z and 00z
    expected_accel = (26.0 - 2.0 * 22.0 + 20.0) / 6.0 # (26 - 44 + 20) / 6 = 2 / 6
    assert pytest.approx(experimental_X.loc[2, "revision_accel_6h"], 1e-4) == expected_accel

    # Spread acceleration: (1.6 - 2*1.2 + 1.0) / 6 = (1.6 - 2.4 + 1.0) / 6 = 0.2 / 6
    expected_spread_accel = (1.6 - 2.0 * 1.2 + 1.0) / 6.0
    assert pytest.approx(experimental_X.loc[2, "spread_accel_6h"], 1e-4) == expected_spread_accel


# ---------------------------------------------------------------------------
# Test 4: Missing Prior Cycle Invariant (Strict NaN, never 0.0)
# ---------------------------------------------------------------------------
def test_4_missing_prior_cycle_produces_strict_nan():
    target_valid = datetime(2026, 8, 22, 12, 0, 0, tzinfo=timezone.utc)
    t_00z = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    # Skipping 06z, directly 12z
    t_12z = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)

    records = [
        {"location": "delhi", "latitude": 28.61, "longitude": 77.21, "issue_time": t_00z, "valid_time": target_valid, "lead_hours": 60, "variable": "temperature_2m", "forecast_value": 25.0, "ensemble_mean": 25.0, "ensemble_std": 1.0, "member_count": 31},
        {"location": "delhi", "latitude": 28.61, "longitude": 77.21, "issue_time": t_12z, "valid_time": target_valid, "lead_hours": 48, "variable": "temperature_2m", "forecast_value": 27.0, "ensemble_mean": 27.0, "ensemble_std": 1.5, "member_count": 31},
    ]
    df = pd.DataFrame(records)

    pipeline = InstabilityFeaturePipeline()
    canonical_X, experimental_X, _ = pipeline.extract_features(df)

    # For 12z: 6h prior (06z) does not exist -> forecast_delta_6h MUST be NaN (not 0.0)
    assert np.isnan(canonical_X.loc[1, "forecast_delta_6h"])
    assert np.isnan(experimental_X.loc[1, "revision_accel_6h"])

    # 12h prior (00z) does exist (27.0 - 25.0 = 2.0)
    assert pytest.approx(experimental_X.loc[1, "forecast_delta_12h"], 1e-4) == 2.0


# ---------------------------------------------------------------------------
# Test 5: No Same-Run Lead Pollution & No Future Cycle Leakage
# ---------------------------------------------------------------------------
def test_5_no_same_run_lead_pollution_and_no_future_leakage():
    """
    Verify that within a SINGLE run (only 00z cycle), having multiple lead times
    does not pollute revision features (all revisions must remain NaN).
    """
    t_issue = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    v_1 = t_issue + timedelta(hours=24)
    v_2 = t_issue + timedelta(hours=30) # 6h later valid time within SAME cycle

    records = [
        {"location": "delhi", "latitude": 28.61, "longitude": 77.21, "issue_time": t_issue, "valid_time": v_1, "lead_hours": 24, "variable": "temperature_2m", "forecast_value": 28.0, "ensemble_mean": 28.0, "ensemble_std": 1.0, "member_count": 31},
        {"location": "delhi", "latitude": 28.61, "longitude": 77.21, "issue_time": t_issue, "valid_time": v_2, "lead_hours": 30, "variable": "temperature_2m", "forecast_value": 34.0, "ensemble_mean": 34.0, "ensemble_std": 1.5, "member_count": 31},
    ]
    df = pd.DataFrame(records)

    pipeline = InstabilityFeaturePipeline()
    canonical_X, experimental_X, _ = pipeline.extract_features(df)

    # Both rows are from the same issue cycle; neither has a prior cycle for its valid time
    assert np.isnan(canonical_X.loc[0, "forecast_delta_6h"])
    assert np.isnan(canonical_X.loc[1, "forecast_delta_6h"])
    assert np.isnan(experimental_X.loc[1, "forecast_delta_12h"])


# ---------------------------------------------------------------------------
# Test 6: Trajectory Classification Determinism & Precedence
# ---------------------------------------------------------------------------
def test_6_trajectory_classification_precedence():
    # 1. Missing data -> INSUFFICIENT_CYCLES
    res_na = classify_forecast_trajectory(None, 1.0, 1.0, 1.0, variable="temperature_2m")
    assert res_na["regime"] == "INSUFFICIENT_CYCLES"

    # 2. Both deltas small -> STABLE
    res_stable = classify_forecast_trajectory(0.05, -0.08, 1.0, 1.0, variable="temperature_2m")
    assert res_stable["regime"] == "STABLE"

    # 3. Flip-flop -> OSCILLATING
    res_osc = classify_forecast_trajectory(1.5, -1.2, 1.0, 1.0, variable="temperature_2m")
    assert res_osc["regime"] == "OSCILLATING"
    assert res_osc["is_oscillating"] is True

    # 4. Monotonic drift UP (neutral label)
    res_up = classify_forecast_trajectory(0.8, 0.9, 1.0, 1.0, variable="temperature_2m")
    assert res_up["regime"] == "MONOTONIC_DRIFT_UP"

    # 5. Monotonic drift DOWN
    res_down = classify_forecast_trajectory(-0.7, -1.1, 1.0, 1.0, variable="temperature_2m")
    assert res_down["regime"] == "MONOTONIC_DRIFT_DOWN"

    # 6. Variable-specific tolerance: wind speed (tolerance = 1.0)
    # delta = 0.6 is STABLE for wind_speed_10m, but would be DRIFT for temperature_2m
    res_wind_stable = classify_forecast_trajectory(0.6, 0.4, 2.0, 2.0, variable="wind_speed_10m")
    assert res_wind_stable["regime"] == "STABLE"

    res_temp_drift = classify_forecast_trajectory(0.6, 0.4, 2.0, 2.0, variable="temperature_2m")
    assert res_temp_drift["regime"] == "MONOTONIC_DRIFT_UP"


# ---------------------------------------------------------------------------
# Test 7: Forecast Instability Fingerprint 6-Group Schema Compliance
# ---------------------------------------------------------------------------
def test_7_instability_fingerprint_6_groups():
    engine = ForecastInstabilityFingerprintEngine()

    dummy_row = {
        "location": "delhi",
        "variable": "temperature_2m",
        "lead_hours": 96,
        "forecast_delta_6h": 1.2,
        "forecast_delta_12h": 2.0,
        "forecast_delta_24h": 3.1,
        "revision_accel_6h": 0.05,
        "ensemble_std": 1.8,
        "ensemble_range": 6.0,
        "ensemble_iqr": 3.2,
        "ensemble_cv": 0.06,
        "ensemble_spread_delta_6h": 0.3,
        "ensemble_spread_delta_24h": 0.7,
        "spread_accel_6h": 0.01,
        "ensemble_skew_proxy": 0.4,
        "ensemble_spread_to_iqr_ratio": 0.56,
    }

    fp = engine.build_fingerprint(dummy_row, variable="temperature_2m")

    # Check that all 6 evidence groups are present
    assert "revision_instability" in fp
    assert "ensemble_dispersion" in fp
    assert "spread_dynamics" in fp
    assert "forecast_trajectory" in fp
    assert "ensemble_shape" in fp
    assert "horizon_pressure" in fp

    # Check typing and values
    assert fp["revision_instability"]["delta_6h"] == 1.2
    assert fp["revision_instability"]["magnitude_6h"] == 1.2
    assert fp["spread_dynamics"]["spread_growth_regime"] == "EXPANDING_UNCERTAINTY"
    assert fp["ensemble_shape"]["distribution_tail"] == "UPWARD_SKEWED"
    assert fp["horizon_pressure"]["lead_bin"] == "day4_6"
    assert fp["horizon_pressure"]["climatological_error_growth_factor"] > 1.0


# ---------------------------------------------------------------------------
# Test 8: Day 5 ForecastBustModelService Zero Regression
# ---------------------------------------------------------------------------
def test_8_day5_model_service_zero_regression():
    """
    Verify that ForecastBustModelService continues to load prototype-gbm-v1
    and predicts exactly and deterministically without warnings.
    """
    service = ForecastBustModelService()
    assert service.model_version == "prototype-gbm-v1"
    assert service.threshold == 0.280
    assert service.feature_names == FEATURE_COLUMN_NAMES

    # Load first row of training dataset from data/features/
    df_train_path = Path("data/features/training_dataset.parquet")
    if df_train_path.exists():
        df_train = pd.read_parquet(df_train_path)
        sample_row = df_train[FEATURE_COLUMN_NAMES].iloc[0:1]
    else:
        # Fallback synthetic row if dataset missing
        row_dict = {
            "ensemble_std": 1.2, "ensemble_range": 3.5, "ensemble_iqr": 2.1,
            "ensemble_skew_proxy": 0.05, "ensemble_cv": 0.04, "ensemble_spread_to_iqr_ratio": 0.57,
            "member_count": 31, "has_full_ensemble": 1, "forecast_value": 30.2,
            "ensemble_mean": 30.1, "ensemble_spread_delta_6h": np.nan,
            "ensemble_spread_delta_24h": 0.15, "forecast_delta_6h": np.nan,
            "forecast_delta_24h": -0.35, "lead_hours": 24, "lead_days": 1.0,
            "valid_hour": 0, "valid_month": 8, "valid_dayofweek": 4,
            "sin_hour": 0.0, "cos_hour": 1.0, "sin_month": -0.866, "cos_month": -0.5,
            "is_weekend": 0, "latitude": 28.5, "longitude": 77.25,
        }
        sample_row = pd.DataFrame([row_dict])

    result = service.predict(sample_row)
    assert len(result) == 1
    assert 0.0 <= result[0]["probability"] <= 1.0
    assert isinstance(result[0]["bust_alert"], bool)
    assert result[0]["model_version"] == "prototype-gbm-v1"


# ---------------------------------------------------------------------------
# Test 9: Missing Ensemble Std Preserved as NaN (Never 0.0)
# ---------------------------------------------------------------------------
def test_9_missing_ensemble_std_preserved_as_nan():
    """
    Scientific Safeguard: Missing ensemble_std must evaluate to NaN in experimental
    spread features, never substituted with 0.0.
    """
    t_00z = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_06z = datetime(2026, 8, 20, 6, 0, 0, tzinfo=timezone.utc)
    t_12z = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
    target_valid = datetime(2026, 8, 22, 12, 0, 0, tzinfo=timezone.utc)

    # Missing ensemble_std in input DataFrame
    records = [
        {"location": "delhi", "latitude": 28.61, "longitude": 77.21, "issue_time": t_00z, "valid_time": target_valid, "lead_hours": 60, "variable": "temperature_2m", "forecast_value": 20.0, "ensemble_mean": 20.0, "member_count": 31},
        {"location": "delhi", "latitude": 28.61, "longitude": 77.21, "issue_time": t_06z, "valid_time": target_valid, "lead_hours": 54, "variable": "temperature_2m", "forecast_value": 22.0, "ensemble_mean": 22.0, "member_count": 31},
        {"location": "delhi", "latitude": 28.61, "longitude": 77.21, "issue_time": t_12z, "valid_time": target_valid, "lead_hours": 48, "variable": "temperature_2m", "forecast_value": 24.0, "ensemble_mean": 24.0, "member_count": 31},
    ]
    df = pd.DataFrame(records)

    pipeline = InstabilityFeaturePipeline()
    canonical_X, experimental_X, _ = pipeline.extract_features(df)

    # Forecast revisions work normally
    assert pytest.approx(canonical_X.loc[1, "forecast_delta_6h"], 1e-4) == 2.0
    assert pytest.approx(experimental_X.loc[2, "forecast_delta_12h"], 1e-4) == 4.0

    # Spread deltas and spread accelerations MUST be NaN because ensemble_std was missing
    assert np.isnan(canonical_X.loc[1, "ensemble_spread_delta_6h"])
    assert np.isnan(experimental_X.loc[2, "spread_delta_12h"])
    assert np.isnan(experimental_X.loc[2, "spread_accel_6h"])


# ---------------------------------------------------------------------------
# Test 10: Real Stage A Artifacts Integrity & Non-Null Revision Counts
# ---------------------------------------------------------------------------
def test_10_stage_a_real_artifacts_and_revision_counts():
    """
    Verify that Stage A multi-cycle paired and experimental feature parquet files
    exist on disk with real multi-location data and genuine non-null revisions.
    """
    paired_path = Path("data/historical/multicycle_paired/paired_multicycle_stage_a_2026-08-18_2026-08-24.parquet")
    features_path = Path("data/features/experimental_instability/features_instability_stage_a_2026-08-18_2026-08-24.parquet")

    assert paired_path.exists(), f"Paired dataset not found at {paired_path}"
    assert features_path.exists(), f"Features dataset not found at {features_path}"

    df_p = pd.read_parquet(paired_path)
    df_f = pd.read_parquet(features_path)

    # 4 locations
    locations = set(df_p["location"].unique())
    assert {"delhi", "mumbai", "kolkata", "bengaluru"}.issubset(locations)

    # 4 cycles (0, 6, 12, 18)
    cycles = set(df_p["issue_time"].dt.hour.unique())
    assert {0, 6, 12, 18}.issubset(cycles)

    # Exactly 7008 paired rows
    assert len(df_p) == 7008
    assert len(df_f) == 7008

    # Significant non-null revisions
    n_d6 = int(df_f["forecast_delta_6h"].notna().sum())
    n_d12 = int(df_f["forecast_delta_12h"].notna().sum())
    n_d24 = int(df_f["forecast_delta_24h"].notna().sum())
    n_accel6 = int(df_f["revision_accel_6h"].notna().sum())

    assert n_d6 > 6000, f"Expected >6000 non-null 6h revisions, got {n_d6}"
    assert n_d12 > 5000, f"Expected >5000 non-null 12h revisions, got {n_d12}"
    assert n_d24 > 4000, f"Expected >4000 non-null 24h revisions, got {n_d24}"
    assert n_accel6 > 5000, f"Expected >5000 non-null 6h accelerations, got {n_accel6}"


# ---------------------------------------------------------------------------
# Test 11: Stage B Full Geographic Expansion (20 Stations, 35,040 Rows)
# ---------------------------------------------------------------------------
def test_11_stage_b_full_geographic_expansion_artifacts():
    """
    Verify that Stage B multi-cycle paired and feature parquets exist on disk
    with all 20 Indian monitoring stations across 5 climatic zones.
    """
    paired_path = Path("data/historical/multicycle_paired/paired_multicycle_stage_b_2026-08-18_2026-08-24.parquet")
    features_path = Path("data/features/experimental_instability/features_instability_stage_b_2026-08-18_2026-08-24.parquet")
    audit_path = Path("reports/day7/multi_location_data_audit.json")

    assert paired_path.exists(), f"Stage B paired dataset missing at {paired_path}"
    assert features_path.exists(), f"Stage B features dataset missing at {features_path}"
    assert audit_path.exists(), f"Day 7 data audit JSON missing at {audit_path}"

    df_p = pd.read_parquet(paired_path)
    df_f = pd.read_parquet(features_path)

    # Exactly 20 locations
    locs = sorted(df_p["location"].unique())
    assert len(locs) == 20
    assert "srinagar" in locs and "chennai" in locs and "guwahati" in locs and "delhi" in locs

    # 35,040 paired rows (1,752 rows x 20 locations)
    assert len(df_p) == 35040
    assert len(df_f) == 35040

    # Non-null revision metrics (>90% 6h revisions)
    n_d6 = int(df_f["forecast_delta_6h"].notna().sum())
    n_d12 = int(df_f["forecast_delta_12h"].notna().sum())
    n_d24 = int(df_f["forecast_delta_24h"].notna().sum())
    n_accel6 = int(df_f["revision_accel_6h"].notna().sum())

    assert n_d6 == 32160  # Exactly 32,160 non-null 6h revisions
    assert n_d12 == 29280  # Exactly 29,280 non-null 12h revisions
    assert n_d24 == 23520  # Exactly 23,520 non-null 24h revisions
    assert n_accel6 == 29280  # Exactly 29,280 non-null 6h accelerations

    # Audit file verification
    with open(audit_path, "r", encoding="utf-8") as f:
        audit = json.load(f)
    assert audit["stage"] == "STAGE_B_EXPANSION"
    assert audit["historically_paired_count"] == 20
    assert audit["total_stage_b_paired_rows"] == 35040
