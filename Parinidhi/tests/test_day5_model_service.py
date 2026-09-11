"""
Comprehensive Unit and Integration Tests for Model Service (ForecastBustModelService).

Tests:
1. Model service loads artifacts cleanly
2. Metadata version and configuration correctness
3. Valid 26-feature DataFrame prediction succeeds
4. Missing required feature raises ValueError naming missing columns
5. Extra unexpected features are safely ignored and selected
6. Non-numeric or uncoercible types raise TypeError
7. Empty DataFrame raises ValueError
8. Revision NaNs are accepted without raising errors
9. Probabilities are strictly bounded in [0.0, 1.0]
10. Repeated predictions in the same process are strictly deterministic
11. Predictions after fresh reload from disk are strictly identical
12. Threshold behavior correctly sets bust_alert = (probability >= 0.280)
13. predict_single() works seamlessly with dict input
14. Missing or corrupted artifact directory raises clear FileNotFoundError / RuntimeError
15. Exact preprocessing and numerical parity with direct Day 4 LightGBM + Platt Calibrator
"""

import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest

from features.feature_pipeline import FEATURE_COLUMN_NAMES
from models.model_service import ForecastBustModelService


@pytest.fixture
def model_service():
    """Fixture returning initialized ForecastBustModelService."""
    return ForecastBustModelService(model_dir="models/day4")


@pytest.fixture
def sample_features_df():
    """Fixture returning a genuine 1-row feature DataFrame from verified dataset."""
    df_path = Path("data/features/training_dataset.parquet")
    if df_path.exists():
        df = pd.read_parquet(df_path)
        return df[FEATURE_COLUMN_NAMES].iloc[[0]].copy()

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
    return pd.DataFrame([row_dict])


def test_1_model_service_loads_artifacts(model_service):
    """Test 1: Service successfully loads LightGBM, calibrator, and metadata."""
    assert model_service.model is not None
    assert model_service.calibrator is not None
    assert isinstance(model_service.metadata, dict)
    assert len(model_service.feature_names) == 26


def test_2_metadata_version(model_service):
    """Test 2: Metadata contains model_version 'prototype-gbm-v1' and decision_threshold 0.280."""
    meta = model_service.get_metadata()
    assert meta["model_version"] == "prototype-gbm-v1"
    assert meta["model_type"] == "lightgbm_binary_classifier"
    assert meta["calibration_method"] == "platt_sigmoid"
    assert meta["decision_threshold"] == 0.28
    assert model_service.threshold == 0.28


def test_3_valid_26_feature_input(model_service, sample_features_df):
    """Test 3: Valid 26-feature DataFrame returns structured prediction response."""
    preds = model_service.predict(sample_features_df)
    assert isinstance(preds, list)
    assert len(preds) == 1
    p = preds[0]
    assert "probability" in p
    assert "bust_alert" in p
    assert "model_version" in p
    assert p["model_version"] == "prototype-gbm-v1"
    assert isinstance(p["probability"], float)
    assert isinstance(p["bust_alert"], bool)


def test_4_missing_feature_rejection(model_service, sample_features_df):
    """Test 4: Missing required feature column raises ValueError naming missing columns."""
    df_missing = sample_features_df.drop(columns=["lead_hours", "ensemble_std"])
    with pytest.raises(ValueError) as excinfo:
        model_service.predict(df_missing)
    err_msg = str(excinfo.value)
    assert "Missing required feature columns" in err_msg
    assert "lead_hours" in err_msg
    assert "ensemble_std" in err_msg


def test_5_extra_feature_handling(model_service, sample_features_df):
    """Test 5: Extra unexpected columns (e.g. metadata or location) are safely ignored."""
    df_extra = sample_features_df.copy()
    df_extra["extra_column_1"] = "test_metadata"
    df_extra["extra_column_2"] = 999.9

    preds = model_service.predict(df_extra)
    assert len(preds) == 1
    assert 0.0 <= preds[0]["probability"] <= 1.0


def test_6_wrong_type_rejection(model_service, sample_features_df):
    """Test 6: Non-numeric uncoercible value raises TypeError."""
    df_bad_type = sample_features_df.copy()
    df_bad_type["forecast_value"] = "uncoercible_string_value"
    with pytest.raises(TypeError) as excinfo:
        model_service.predict(df_bad_type)
    assert "forecast_value" in str(excinfo.value)


def test_7_empty_dataframe_rejection(model_service):
    """Test 7: Empty DataFrame raises ValueError."""
    empty_df = pd.DataFrame(columns=FEATURE_COLUMN_NAMES)
    with pytest.raises(ValueError) as excinfo:
        model_service.predict(empty_df)
    assert "empty" in str(excinfo.value).lower()


def test_8_revision_nans_accepted(model_service, sample_features_df):
    """Test 8: NaNs in revision features are accepted without raising errors."""
    df_nans = sample_features_df.copy()
    df_nans["ensemble_spread_delta_6h"] = np.nan
    df_nans["ensemble_spread_delta_24h"] = np.nan
    df_nans["forecast_delta_6h"] = np.nan
    df_nans["forecast_delta_24h"] = np.nan

    preds = model_service.predict(df_nans)
    assert len(preds) == 1
    assert 0.0 <= preds[0]["probability"] <= 1.0


def test_9_probability_bounds(model_service):
    """Test 9: All probabilities returned by service are strictly in [0.0, 1.0]."""
    df_path = Path("data/features/training_dataset.parquet")
    if df_path.exists():
        df = pd.read_parquet(df_path)
        preds = model_service.predict(df)
        for p in preds:
            assert 0.0 <= p["probability"] <= 1.0
            assert isinstance(p["bust_alert"], bool)


def test_10_deterministic_repeated_prediction(model_service, sample_features_df):
    """Test 10: Repeated calls on identical input produce identical probabilities."""
    res1 = model_service.predict(sample_features_df)
    res2 = model_service.predict(sample_features_df)
    assert res1[0]["probability"] == res2[0]["probability"]
    assert res1[0]["bust_alert"] == res2[0]["bust_alert"]


def test_11_deterministic_prediction_after_service_reload(sample_features_df):
    """Test 11: Service reloaded fresh from disk produces identical probability to first instance."""
    svc_a = ForecastBustModelService(model_dir="models/day4")
    svc_b = ForecastBustModelService(model_dir="models/day4")

    res_a = svc_a.predict(sample_features_df)
    res_b = svc_b.predict(sample_features_df)

    assert res_a[0]["probability"] == res_b[0]["probability"]
    assert res_a[0]["bust_alert"] == res_b[0]["bust_alert"]


def test_12_threshold_behavior(model_service, sample_features_df):
    """Test 12: Threshold behavior correctly maps probability >= 0.280 to True, else False."""
    preds = model_service.predict(sample_features_df)
    p = preds[0]["probability"]
    expected_alert = bool(p >= 0.28)
    assert preds[0]["bust_alert"] == expected_alert


def test_13_predict_single(model_service, sample_features_df):
    """Test 13: predict_single() accepts dict and returns single response dict."""
    row_dict = sample_features_df.iloc[0].to_dict()
    res = model_service.predict_single(row_dict)
    assert isinstance(res, dict)
    assert "probability" in res
    assert "bust_alert" in res
    assert "model_version" in res
    assert res["model_version"] == "prototype-gbm-v1"


def test_14_missing_or_corrupt_artifact_failure(tmp_path):
    """Test 14: Initializing service on invalid directory raises clear FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        ForecastBustModelService(model_dir=tmp_path)


def test_15_exact_preprocessing_and_model_parity_with_day4(model_service):
    """
    Test 15: Critical Preprocessing & Model Parity.
    Direct LightGBM + Platt Calibrator inference matches ForecastBustModelService exactly.
    """
    df_path = Path("data/features/training_dataset.parquet")
    if not df_path.exists():
        pytest.skip("Verified training dataset parquet required for parity test")

    df = pd.read_parquet(df_path)
    X = df[FEATURE_COLUMN_NAMES].copy()

    # 1. Direct evaluation using raw loaded models
    lgbm_direct = joblib.load("models/day4/lightgbm_bust_model.joblib")
    cal_direct = joblib.load("models/day4/probability_calibrator.joblib")

    raw_probs = lgbm_direct.predict_proba(X)
    cal_probs = cal_direct.predict_proba(raw_probs)[:, 1]

    # 2. Service evaluation
    service_preds = model_service.predict(df)
    service_probs = np.array([p["probability"] for p in service_preds])

    # 3. Assert exact floating-point parity
    np.testing.assert_allclose(
        service_probs,
        cal_probs,
        rtol=1e-7,
        atol=1e-7,
        err_msg="Discrepancy detected between direct Day 4 inference and ForecastBustModelService!",
    )
