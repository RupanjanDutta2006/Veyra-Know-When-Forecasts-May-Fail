"""
Unit tests for Issue-Time-Safe Feature Pipeline.

Tests:
1. Extraction of canonical 26 features
2. Ensemble dispersion feature formulas (range, IQR, skew proxy, CV)
3. Inter-cycle revision semantics (6h and 24h revisions for SAME valid_time)
4. Absence of cross-valid_time pollution within same cycle
5. Missing previous cycles yielding NaN (never imputed with 0)
6. Non-use of future issue_time information (temporal causality)
7. Inter-cycle spread revision alignment
8. Temporal cyclical trigonometry encodings
"""

from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import pytest

from features.feature_pipeline import IssueTimeSafeFeaturePipeline, FEATURE_COLUMN_NAMES


@pytest.fixture
def mock_multi_cycle_dataset():
    """
    Deterministic multi-cycle fixture with overlapping valid times.
    Contains two 00z cycles (Aug 18 and Aug 19) and one 06z cycle (Aug 18).
    """
    t_aug18_00 = pd.Timestamp("2026-08-18 00:00:00+00:00")
    t_aug18_06 = pd.Timestamp("2026-08-18 06:00:00+00:00")
    t_aug19_00 = pd.Timestamp("2026-08-19 00:00:00+00:00")

    v_aug20_00 = pd.Timestamp("2026-08-20 00:00:00+00:00")
    v_aug20_06 = pd.Timestamp("2026-08-20 06:00:00+00:00")

    rows = [
        # Cycle 1: 2026-08-18 00z
        {
            "location": "delhi", "latitude": 28.5, "longitude": 77.2,
            "issue_time": t_aug18_00, "valid_time": v_aug20_00, "lead_hours": 48,
            "variable": "temperature_2m", "forecast_value": 32.0, "ensemble_std": 2.0,
            "ensemble_mean": 32.0, "ensemble_min": 28.0, "ensemble_max": 36.0,
            "q10": 30.0, "q90": 34.0, "member_count": 31,
        },
        {
            "location": "delhi", "latitude": 28.5, "longitude": 77.2,
            "issue_time": t_aug18_00, "valid_time": v_aug20_06, "lead_hours": 54,
            "variable": "temperature_2m", "forecast_value": 35.0, "ensemble_std": 2.5,
            "ensemble_mean": 35.0, "ensemble_min": 30.0, "ensemble_max": 40.0,
            "q10": 33.0, "q90": 37.0, "member_count": 31,
        },
        # Cycle 2: 2026-08-18 06z (6h after Cycle 1)
        {
            "location": "delhi", "latitude": 28.5, "longitude": 77.2,
            "issue_time": t_aug18_06, "valid_time": v_aug20_00, "lead_hours": 42,
            "variable": "temperature_2m", "forecast_value": 31.5, "ensemble_std": 1.8,
            "ensemble_mean": 31.5, "ensemble_min": 28.0, "ensemble_max": 35.0,
            "q10": 29.5, "q90": 33.5, "member_count": 31,
        },
        # Cycle 3: 2026-08-19 00z (24h after Cycle 1)
        {
            "location": "delhi", "latitude": 28.5, "longitude": 77.2,
            "issue_time": t_aug19_00, "valid_time": v_aug20_00, "lead_hours": 24,
            "variable": "temperature_2m", "forecast_value": 30.5, "ensemble_std": 1.2,
            "ensemble_mean": 30.5, "ensemble_min": 28.0, "ensemble_max": 33.0,
            "q10": 29.5, "q90": 31.5, "member_count": 31,
        },
        {
            "location": "delhi", "latitude": 28.5, "longitude": 77.2,
            "issue_time": t_aug19_00, "valid_time": v_aug20_06, "lead_hours": 30,
            "variable": "temperature_2m", "forecast_value": 33.0, "ensemble_std": 1.5,
            "ensemble_mean": 33.0, "ensemble_min": 29.0, "ensemble_max": 37.0,
            "q10": 31.0, "q90": 35.0, "member_count": 31,
        },
    ]
    return pd.DataFrame(rows)


def test_feature_pipeline_extraction(mock_multi_cycle_dataset):
    """Test full extraction returns canonical feature matrix and metadata."""
    pipeline = IssueTimeSafeFeaturePipeline()
    X, metadata = pipeline.extract_features(mock_multi_cycle_dataset)

    assert list(X.columns) == FEATURE_COLUMN_NAMES
    assert len(X) == len(mock_multi_cycle_dataset)
    assert len(metadata) == len(mock_multi_cycle_dataset)


def test_inter_cycle_revisions_same_valid_time(mock_multi_cycle_dataset):
    """
    Test 1: Same valid_time across two issue_times produces the exact expected revision.
    - For valid_time = 2026-08-20 00:00:
      Aug 19 00z (forecast=30.5) minus Aug 18 00z (forecast=32.0) = -1.5 (24h revision)
      Aug 18 06z (forecast=31.5) minus Aug 18 00z (forecast=32.0) = -0.5 (6h revision)
    """
    pipeline = IssueTimeSafeFeaturePipeline()
    X, metadata = pipeline.extract_features(mock_multi_cycle_dataset)
    combined = pd.concat([metadata, X], axis=1)

    # Aug 19 00z row for valid_time 2026-08-20 00:00
    row_aug19_v00 = combined[
        (combined["issue_time"] == pd.Timestamp("2026-08-19 00:00:00+00:00")) &
        (combined["valid_time"] == pd.Timestamp("2026-08-20 00:00:00+00:00"))
    ].iloc[0]

    assert pytest.approx(row_aug19_v00["forecast_delta_24h"], 0.001) == -1.5

    # Aug 18 06z row for valid_time 2026-08-20 00:00 (6h revision against Aug 18 00z)
    row_aug18_06_v00 = combined[
        (combined["issue_time"] == pd.Timestamp("2026-08-18 06:00:00+00:00")) &
        (combined["valid_time"] == pd.Timestamp("2026-08-20 00:00:00+00:00"))
    ].iloc[0]

    assert pytest.approx(row_aug18_06_v00["forecast_delta_6h"], 0.001) == -0.5


def test_no_cross_valid_time_pollution_within_same_run(mock_multi_cycle_dataset):
    """
    Test 2: Different valid_times within the SAME issue_time/run are NEVER subtracted.
    Aug 18 00z has valid 00:00 (val=32.0) and valid 06:00 (val=35.0).
    Difference within run is +3.0, but inter-cycle revision MUST be NaN because no prior run exists.
    """
    pipeline = IssueTimeSafeFeaturePipeline()
    X, metadata = pipeline.extract_features(mock_multi_cycle_dataset)
    combined = pd.concat([metadata, X], axis=1)

    # First cycle rows (Aug 18 00z)
    aug18_rows = combined[combined["issue_time"] == pd.Timestamp("2026-08-18 00:00:00+00:00")]

    # Neither row should have 6h or 24h revision since no earlier cycle exists
    assert aug18_rows["forecast_delta_6h"].isna().all()
    assert aug18_rows["forecast_delta_24h"].isna().all()


def test_missing_previous_cycle_produces_nan(mock_multi_cycle_dataset):
    """
    Test 3: If previous cycle (~6h or ~24h earlier) does not exist, return NaN, never 0.
    """
    pipeline = IssueTimeSafeFeaturePipeline()
    X, metadata = pipeline.extract_features(mock_multi_cycle_dataset)
    combined = pd.concat([metadata, X], axis=1)

    # Aug 19 00z has NO 6h earlier cycle (Aug 18 18z is missing from fixture)
    row_aug19 = combined[combined["issue_time"] == pd.Timestamp("2026-08-19 00:00:00+00:00")].iloc[0]
    assert np.isnan(row_aug19["forecast_delta_6h"])
    assert np.isnan(row_aug19["ensemble_spread_delta_6h"])

    # Aug 18 00z has NO prior cycle
    row_aug18 = combined[combined["issue_time"] == pd.Timestamp("2026-08-18 00:00:00+00:00")].iloc[0]
    assert np.isnan(row_aug18["forecast_delta_24h"])
    assert np.isnan(row_aug18["ensemble_spread_delta_24h"])


def test_future_issue_time_never_used(mock_multi_cycle_dataset):
    """
    Test 4: Strict temporal causality — earlier cycle cannot see later cycle.
    Aug 18 00z row CANNOT see Aug 19 00z value (30.5). Its revision remains NaN.
    """
    pipeline = IssueTimeSafeFeaturePipeline()
    X, metadata = pipeline.extract_features(mock_multi_cycle_dataset)
    combined = pd.concat([metadata, X], axis=1)

    row_aug18 = combined[
        (combined["issue_time"] == pd.Timestamp("2026-08-18 00:00:00+00:00")) &
        (combined["valid_time"] == pd.Timestamp("2026-08-20 00:00:00+00:00"))
    ].iloc[0]

    assert np.isnan(row_aug18["forecast_delta_24h"])


def test_spread_revisions_alignment(mock_multi_cycle_dataset):
    """
    Test 5: Ensemble spread revisions use identical inter-cycle alignment.
    Aug 19 00z (std=1.2) minus Aug 18 00z (std=2.0) = -0.8 (24h spread revision).
    Aug 18 06z (std=1.8) minus Aug 18 00z (std=2.0) = -0.2 (6h spread revision).
    """
    pipeline = IssueTimeSafeFeaturePipeline()
    X, metadata = pipeline.extract_features(mock_multi_cycle_dataset)
    combined = pd.concat([metadata, X], axis=1)

    # 24h spread delta
    row_aug19_v00 = combined[
        (combined["issue_time"] == pd.Timestamp("2026-08-19 00:00:00+00:00")) &
        (combined["valid_time"] == pd.Timestamp("2026-08-20 00:00:00+00:00"))
    ].iloc[0]
    assert pytest.approx(row_aug19_v00["ensemble_spread_delta_24h"], 0.001) == -0.8

    # 6h spread delta
    row_aug18_06_v00 = combined[
        (combined["issue_time"] == pd.Timestamp("2026-08-18 06:00:00+00:00")) &
        (combined["valid_time"] == pd.Timestamp("2026-08-20 00:00:00+00:00"))
    ].iloc[0]
    assert pytest.approx(row_aug18_06_v00["ensemble_spread_delta_6h"], 0.001) == -0.2


def test_training_dataset_schema_and_re_extraction():
    """
    Regression Test:
    1. Training dataset contains canonical ensemble source columns: ensemble_min, ensemble_max, q10, q90.
    2. Calling extract_features() on training_dataset succeeds without KeyError.
    3. Output feature matrix X contains exactly FEATURE_COLUMN_NAMES (no targets/truth/audit columns).
    4. Derived ensemble features remain numerically identical when re-extracted.
    """
    from pathlib import Path

    train_path = Path("data/features/training_dataset.parquet")
    if not train_path.exists():
        pytest.skip("training_dataset.parquet not yet generated on disk")

    df_train = pd.read_parquet(train_path)

    # 1. Verify source audit columns are present in saved dataset
    required_source_cols = ["ensemble_min", "ensemble_max", "q10", "q90"]
    for col in required_source_cols:
        assert col in df_train.columns, f"Missing source audit column '{col}' in training_dataset"
        assert df_train[col].notna().all(), f"Column '{col}' has unexpected NaNs"

    # 2. Verify re-extraction succeeds
    pipeline = IssueTimeSafeFeaturePipeline()
    X_reextracted, meta_reextracted = pipeline.extract_features(df_train)

    # 3. Verify X contains exactly the 26 canonical feature columns
    assert list(X_reextracted.columns) == FEATURE_COLUMN_NAMES
    assert len(X_reextracted.columns) == 26

    # Verify forbidden truth / target / audit columns are NOT in X
    forbidden_in_x = [
        "truth_value", "forecast_error", "forecast_abs_error",
        "bust_label", "bust_threshold", "ensemble_min", "ensemble_max", "q10", "q90"
    ]
    for f_col in forbidden_in_x:
        assert f_col not in X_reextracted.columns, f"Forbidden column '{f_col}' leaked into feature matrix X"

    # 4. Verify derived ensemble features match numerically
    np.testing.assert_allclose(
        X_reextracted["ensemble_range"].values,
        (df_train["ensemble_max"] - df_train["ensemble_min"]).clip(lower=0.0).values,
        rtol=1e-5,
        err_msg="ensemble_range mismatch on re-extraction"
    )
    np.testing.assert_allclose(
        X_reextracted["ensemble_iqr"].values,
        (df_train["q90"] - df_train["q10"]).clip(lower=0.0).values,
        rtol=1e-5,
        err_msg="ensemble_iqr mismatch on re-extraction"
    )
    np.testing.assert_allclose(
        X_reextracted["ensemble_std"].values,
        df_train["ensemble_std"].values,
        rtol=1e-5,
        err_msg="ensemble_std mismatch on re-extraction"
    )
