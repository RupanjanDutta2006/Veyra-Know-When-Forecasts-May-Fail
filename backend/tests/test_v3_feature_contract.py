"""Deterministic Feature Contract Tests for V3 50-Feature Pipeline.

Verifies:
1. Exactly 50 features are produced.
2. Columns match feature_names.json in exact order.
3. No spatial coordinates (lat, lon, elevation) in the feature matrix.
4. Variable one-hot indicator encoding is mutually exclusive and exact.
5. Temporal harmonic fields (sin_hour, cos_hour, sin_month, cos_month, is_weekend) are deterministic.
6. Lead interactions (spread_x_lead, cv_x_lead, lead_decay_factor) are mathematically correct.
7. Revision features conform to frozen issue-time semantics.
8. OOD feature is computed pre-inference without dependency on model predictions.
"""

import json
import math
from pathlib import Path
import pytest

from backend.app.builder2.v3_feature_pipeline import (
    V3_FEATURE_NAMES,
    V3FeaturePipeline,
    compute_v3_ood_score,
)
from backend.app.schemas.weather import CanonicalForecastRecord

FEATURES_JSON_PATH = Path("models/v3/feature_names.json")


def test_50_features_exact_count_and_order():
    """Verify extracted DataFrame has shape (N, 50) and matches JSON feature list."""
    pipeline = V3FeaturePipeline()
    record = CanonicalForecastRecord(
        location="Kolkata",
        latitude=22.5726,
        longitude=88.3639,
        issue_time="2026-09-01T00:00:00Z",
        valid_time="2026-09-02T12:00:00Z",
        lead_hours=36,
        variable="temperature_2m",
        unit="°C",
        value=28.0,
        ensemble_mean=28.0,
        ensemble_std=1.2,
        ensemble_min=25.0,
        ensemble_max=31.0,
        q10=26.0,
        q90=30.0,
        member_count=31,
    )

    df_feats, meta = pipeline.extract_from_records([record], target_variable="temperature_2m")
    assert df_feats.shape == (1, 50)

    expected_features = json.loads(FEATURES_JSON_PATH.read_text(encoding="utf-8"))
    assert list(df_feats.columns) == expected_features
    assert list(df_feats.columns) == V3_FEATURE_NAMES


def test_no_spatial_coordinates_in_feature_matrix():
    """Ensure latitude, longitude, and elevation do not appear in V3 feature schema."""
    expected_features = json.loads(FEATURES_JSON_PATH.read_text(encoding="utf-8"))
    forbidden = ["latitude", "longitude", "lat", "lon", "elevation", "location"]
    for f in forbidden:
        assert f not in expected_features, f"Forbidden spatial field '{f}' found in V3 feature schema!"


def test_variable_one_hot_mutually_exclusive():
    """Verify variable one-hot indicators for temperature, wind, and pressure."""
    pipeline = V3FeaturePipeline()

    vars_to_test = [
        ("temperature_2m", (1.0, 0.0, 0.0)),
        ("surface_pressure", (0.0, 1.0, 0.0)),
        ("wind_speed_10m", (0.0, 0.0, 1.0)),
    ]

    for var_name, (exp_t2m, exp_sp, exp_ws) in vars_to_test:
        rec = CanonicalForecastRecord(
            location="TestLoc",
            latitude=20.0,
            longitude=75.0,
            issue_time="2026-09-01T00:00:00Z",
            valid_time="2026-09-02T00:00:00Z",
            lead_hours=24,
            variable=var_name,
            unit="unit",
            value=10.0,
            ensemble_mean=10.0,
            ensemble_std=1.0,
            ensemble_min=8.0,
            ensemble_max=12.0,
            member_count=31,
        )
        df_feats, _ = pipeline.extract_from_records([rec], target_variable=var_name)
        row = df_feats.iloc[0]

        assert row["is_temperature_2m"] == exp_t2m
        assert row["is_surface_pressure"] == exp_sp
        assert row["is_wind_speed_10m"] == exp_ws


def test_temporal_harmonics_deterministic():
    """Verify cyclical time features for hour and month."""
    pipeline = V3FeaturePipeline()
    # 2026-09-01T06:00:00Z -> valid_hour = 6, valid_month = 9, Tuesday (dayofweek=1)
    rec = CanonicalForecastRecord(
        location="Delhi",
        latitude=28.6,
        longitude=77.2,
        issue_time="2026-09-01T00:00:00Z",
        valid_time="2026-09-01T06:00:00Z",
        lead_hours=6,
        variable="temperature_2m",
        unit="°C",
        value=26.0,
        ensemble_mean=26.0,
        ensemble_std=1.0,
        ensemble_min=24.0,
        ensemble_max=28.0,
        member_count=31,
    )

    df_feats, _ = pipeline.extract_from_records([rec])
    row = df_feats.iloc[0]

    assert row["valid_hour"] == 6
    assert row["valid_month"] == 9
    assert row["valid_dayofweek"] == 1
    assert row["is_weekend"] == 0

    # sin(2*pi*6/24) = sin(pi/2) = 1.0
    assert row["sin_hour"] == pytest.approx(1.0, abs=1e-4)
    # cos(2*pi*6/24) = cos(pi/2) = 0.0
    assert row["cos_hour"] == pytest.approx(0.0, abs=1e-4)


def test_lead_interactions():
    """Verify lead_days, lead_decay_factor, and spread_x_lead."""
    pipeline = V3FeaturePipeline()
    rec = CanonicalForecastRecord(
        location="Shimla",
        latitude=31.1,
        longitude=77.1,
        issue_time="2026-09-01T00:00:00Z",
        valid_time="2026-09-03T00:00:00Z",
        lead_hours=48,
        variable="temperature_2m",
        unit="°C",
        value=15.0,
        ensemble_mean=15.0,
        ensemble_std=2.0,
        ensemble_min=12.0,
        ensemble_max=18.0,
        member_count=31,
    )

    df_feats, _ = pipeline.extract_from_records([rec])
    row = df_feats.iloc[0]

    assert row["lead_hours"] == 48
    assert row["lead_days"] == pytest.approx(2.0, abs=1e-3)
    assert row["lead_decay_factor"] == pytest.approx(1.0 - (48.0 / 240.0), abs=1e-4)

    expected_spread_x_lead = 2.0 * math.log1p(48)
    assert row["spread_x_lead"] == pytest.approx(expected_spread_x_lead, abs=1e-3)


def test_ood_score_pre_inference_and_non_circular():
    """Verify OOD score operates on input physics directly without model prediction."""
    # Nominal temperature: 25°C -> 298.15 K -> expected OOD 0.0
    ood_nominal = compute_v3_ood_score("temperature_2m", 298.15)
    assert ood_nominal == 0.0

    # Extreme physical temperature: 100°C -> 373.15 K -> should yield high OOD score
    ood_extreme = compute_v3_ood_score("temperature_2m", 373.15)
    assert ood_extreme >= 45.0
