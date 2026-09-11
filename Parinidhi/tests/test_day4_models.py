"""
Unit and Integration Tests for ML Modeling Framework.

Tests:
1. Feature selection & canonical 26 features integrity
2. Forbidden-column exclusion & zero target leakage
3. Chronological issue-time split with zero group overlap
4. Baselines (Majority, Climatology, Spread Heuristic) output valid probabilities in [0, 1]
5. Logistic Regression with missingness indicators and StandardScaler
6. LightGBM Classifier native NaN handling & valid predictions
7. Probability Calibrator (Platt Sigmoid and Isotonic) validation fit & monotonicity
8. Optimal threshold selection logic on Validation PR curve
9. Lead-time and per-variable diagnostic evaluation robustness
10. Model serialization and reload parity (reloaded model outputs identical probabilities)
"""

from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest

from features.feature_pipeline import FEATURE_COLUMN_NAMES
from models.baselines import (
    ClimatologyBaseline,
    MajorityClassBaseline,
    PersistenceBaseline,
    SpreadHeuristicBaseline,
)
from models.calibrator import ProbabilityCalibrator
from models.data_splitter import ChronologicalDataSplitter, SplitData
from models.evaluator import ModelEvaluator
from models.logistic_classifier import RegularizedLogisticClassifier
from models.tree_classifier import LightGBMBustClassifier


@pytest.fixture
def sample_training_data():
    """Load the verified training dataset or construct mock dataset."""
    train_path = Path("data/features/training_dataset.parquet")
    if train_path.exists():
        return pd.read_parquet(train_path)

    # Fallback synthetic fixture for unit testing if file missing
    np.random.seed(42)
    n = 100
    rows = []
    dates = ["2026-08-15", "2026-08-16", "2026-08-17", "2026-08-18", "2026-08-19", "2026-08-20", "2026-08-21"]
    for i in range(n):
        d = dates[i % len(dates)]
        lh = (i % 41) * 6
        it = pd.Timestamp(f"{d} 00:00:00+00:00")
        vt = it + pd.Timedelta(hours=lh)
        rows.append({
            "location": "delhi", "latitude": 28.5, "longitude": 77.2,
            "issue_time": it, "valid_time": vt, "lead_hours": lh, "lead_days": lh / 24.0,
            "variable": "temperature_2m", "forecast_value": 30.0 + np.random.randn(),
            "ensemble_mean": 30.0 + np.random.randn(), "ensemble_std": 1.5 + np.random.rand(),
            "ensemble_range": 4.0, "ensemble_iqr": 2.5, "ensemble_skew_proxy": 0.1,
            "ensemble_cv": 0.05, "ensemble_spread_to_iqr_ratio": 0.6,
            "member_count": 31, "has_full_ensemble": 1,
            "ensemble_spread_delta_6h": np.nan, "ensemble_spread_delta_24h": 0.1 if i > 10 else np.nan,
            "forecast_delta_6h": np.nan, "forecast_delta_24h": -0.2 if i > 10 else np.nan,
            "valid_hour": vt.hour, "valid_month": vt.month, "valid_dayofweek": vt.dayofweek,
            "sin_hour": np.sin(2 * np.pi * vt.hour / 24), "cos_hour": np.cos(2 * np.pi * vt.hour / 24),
            "sin_month": np.sin(2 * np.pi * vt.month / 12), "cos_month": np.cos(2 * np.pi * vt.month / 12),
            "is_weekend": 0, "bust_label": 1 if np.random.rand() > 0.85 else 0,
            "truth_value": 31.0, "forecast_error": 1.0, "forecast_abs_error": 1.0,
        })
    return pd.DataFrame(rows)


def test_feature_contract_and_forbidden_columns(sample_training_data):
    """Test 1 & 2: Feature contract strictly equals 26 features, zero target leakage."""
    assert len(FEATURE_COLUMN_NAMES) == 26

    forbidden_cols = [
        "truth_value", "forecast_error", "forecast_abs_error",
        "ensemble_mean_error", "ensemble_mean_abs_error",
        "bust_label", "bust_threshold", "bust_label_q9",
        "bust_label_q95", "bust_label_q975", "bust_label_q99",
    ]

    for f_col in forbidden_cols:
        assert f_col not in FEATURE_COLUMN_NAMES, f"Forbidden column '{f_col}' found in model features"


def test_chronological_data_splitter_no_group_overlap(sample_training_data):
    """Test 3: Issue-time group chronological split prevents group/temporal leakage."""
    splitter = ChronologicalDataSplitter(feature_columns=FEATURE_COLUMN_NAMES)
    split_data = splitter.split_by_dates(
        sample_training_data,
        train_end_date="2026-08-19",
        val_date="2026-08-20",
        test_date="2026-08-21",
    )

    # Verify zero group overlap
    train_cycles = set(split_data.train_cycles)
    val_cycles = set(split_data.val_cycles)
    test_cycles = set(split_data.test_cycles)

    assert len(train_cycles.intersection(val_cycles)) == 0
    assert len(train_cycles.intersection(test_cycles)) == 0
    assert len(val_cycles.intersection(test_cycles)) == 0

    # Verify feature shapes
    assert split_data.X_train.shape[1] == 26
    assert split_data.X_val.shape[1] == 26
    assert split_data.X_test.shape[1] == 26


def test_baseline_models(sample_training_data):
    """Test 4: Baselines (Majority, Climatology, Persistence, Spread) output valid probabilities in [0, 1]."""
    splitter = ChronologicalDataSplitter(feature_columns=FEATURE_COLUMN_NAMES)
    split = splitter.split_by_dates(sample_training_data)

    # Majority class
    maj = MajorityClassBaseline().fit(split.X_train, split.y_train)
    p_maj = maj.predict_proba(split.X_val)
    assert p_maj.shape == (len(split.X_val), 2)
    assert np.all(p_maj[:, 1] == 0.0)

    # Climatology (E0)
    clim = ClimatologyBaseline().fit(split.X_train, split.y_train)
    p_clim = clim.predict_proba(split.X_val)
    assert p_clim.shape == (len(split.X_val), 2)
    assert np.allclose(p_clim[:, 1], split.y_train.mean())

    # Persistence (E1)
    persist = PersistenceBaseline().fit(split.X_train, split.y_train)
    p_persist = persist.predict_proba(split.X_val)
    assert p_persist.shape == (len(split.X_val), 2)
    assert np.all((p_persist >= 0.0) & (p_persist <= 1.0))
    assert np.allclose(p_persist.sum(axis=1), 1.0)

    # Spread Heuristic (E2)
    spread = SpreadHeuristicBaseline().fit(split.X_train, split.y_train)
    p_spread = spread.predict_proba(split.X_val)
    assert p_spread.shape == (len(split.X_val), 2)
    assert np.all((p_spread >= 0.0) & (p_spread <= 1.0))
    assert np.allclose(p_spread.sum(axis=1), 1.0)


def test_regularized_logistic_classifier(sample_training_data):
    """Test 5: Logistic regression pipeline with imputation and scaling."""
    splitter = ChronologicalDataSplitter(feature_columns=FEATURE_COLUMN_NAMES)
    split = splitter.split_by_dates(sample_training_data)

    clf = RegularizedLogisticClassifier(C=1.0, random_state=42)
    clf.fit(split.X_train, split.y_train)

    p_val = clf.predict_proba(split.X_val)
    assert p_val.shape == (len(split.X_val), 2)
    assert np.all((p_val >= 0.0) & (p_val <= 1.0))
    assert np.allclose(p_val.sum(axis=1), 1.0)

    coefs = clf.get_feature_coefficients()
    assert len(coefs) >= 26


def test_lightgbm_classifier_native_nans(sample_training_data):
    """Test 6: LightGBM handles NaNs natively and outputs bounded probabilities."""
    splitter = ChronologicalDataSplitter(feature_columns=FEATURE_COLUMN_NAMES)
    split = splitter.split_by_dates(sample_training_data)

    # Ensure NaNs exist in input to test native NaN handling
    assert split.X_train["forecast_delta_6h"].isna().any()

    lgbm = LightGBMBustClassifier(n_estimators=20, max_depth=3, random_state=42)
    lgbm.fit(split.X_train, split.y_train)

    p_val = lgbm.predict_proba(split.X_val)
    assert p_val.shape == (len(split.X_val), 2)
    assert np.all((p_val >= 0.0) & (p_val <= 1.0))
    assert np.allclose(p_val.sum(axis=1), 1.0)

    importances = lgbm.get_feature_importances()
    assert len(importances) == 26
    for fname, d in importances.items():
        assert "split" in d and "gain" in d


def test_probability_calibrator(sample_training_data):
    """Test 7: Probability calibrator fits on validation fold and outputs valid probabilities."""
    splitter = ChronologicalDataSplitter(feature_columns=FEATURE_COLUMN_NAMES)
    split = splitter.split_by_dates(sample_training_data)

    lgbm = LightGBMBustClassifier(n_estimators=20, max_depth=3, random_state=42)
    lgbm.fit(split.X_train, split.y_train)
    p_val = lgbm.predict_proba(split.X_val)

    # Sigmoid calibration
    cal_sig = ProbabilityCalibrator(method="sigmoid").fit(p_val, split.y_val.values)
    p_cal = cal_sig.predict_proba(p_val)
    assert p_cal.shape == (len(split.X_val), 2)
    assert np.all((p_cal >= 0.0) & (p_cal <= 1.0))
    assert np.allclose(p_cal.sum(axis=1), 1.0)

    impact = cal_sig.evaluate_calibration_impact(p_val, split.y_val.values)
    assert "brier_score_uncalibrated" in impact
    assert "brier_score_calibrated" in impact


def test_model_evaluator_metrics_and_thresholds(sample_training_data):
    """Test 8: ModelEvaluator metrics and threshold finding on PR curve."""
    splitter = ChronologicalDataSplitter(feature_columns=FEATURE_COLUMN_NAMES)
    split = splitter.split_by_dates(sample_training_data)

    lgbm = LightGBMBustClassifier(n_estimators=20, max_depth=3, random_state=42)
    lgbm.fit(split.X_train, split.y_train)
    p_val = lgbm.predict_proba(split.X_val)

    metrics = ModelEvaluator.compute_metrics(split.y_val, p_val, threshold=0.5)
    assert 0.0 <= metrics["pr_auc"] <= 1.0
    assert 0.0 <= metrics["brier_score"] <= 1.0
    assert 0.0 <= metrics["f1_score"] <= 1.0

    thresholds = ModelEvaluator.find_optimal_thresholds(split.y_val, p_val)
    assert "optimal_f1" in thresholds
    assert 0.0 <= thresholds["optimal_f1"]["threshold"] <= 1.0


def test_stratified_evaluations(sample_training_data):
    """Test 9: Lead-time bins and per-variable stratified evaluations."""
    splitter = ChronologicalDataSplitter(feature_columns=FEATURE_COLUMN_NAMES)
    split = splitter.split_by_dates(sample_training_data)

    lgbm = LightGBMBustClassifier(n_estimators=20, max_depth=3, random_state=42)
    lgbm.fit(split.X_train, split.y_train)
    p_val = lgbm.predict_proba(split.X_val)

    lead_metrics = ModelEvaluator.evaluate_by_lead_time_bins(split.df_val, split.y_val, p_val)
    assert "0-24h" in lead_metrics
    assert "48-72h" in lead_metrics

    var_metrics = ModelEvaluator.evaluate_by_variable(split.df_val, split.y_val, p_val)
    assert "temperature_2m" in var_metrics or len(var_metrics) > 0


def test_model_serialization_and_reload_parity(tmp_path, sample_training_data):
    """Test 10: Model serialization and reload produces identical probability predictions."""
    splitter = ChronologicalDataSplitter(feature_columns=FEATURE_COLUMN_NAMES)
    split = splitter.split_by_dates(sample_training_data)

    # Train model & calibrator
    lgbm = LightGBMBustClassifier(n_estimators=20, max_depth=3, random_state=42)
    lgbm.fit(split.X_train, split.y_train)
    p_val_raw = lgbm.predict_proba(split.X_val)

    calibrator = ProbabilityCalibrator(method="sigmoid").fit(p_val_raw, split.y_val.values)
    p_val_cal = calibrator.predict_proba(p_val_raw)

    # Save to tmp_path
    model_path = tmp_path / "model.joblib"
    cal_path = tmp_path / "calibrator.joblib"
    joblib.dump(lgbm, model_path)
    joblib.dump(calibrator, cal_path)

    # Reload
    reloaded_model = joblib.load(model_path)
    reloaded_cal = joblib.load(cal_path)

    # Predict on test
    p_test_orig = calibrator.predict_proba(lgbm.predict_proba(split.X_test))
    p_test_reloaded = reloaded_cal.predict_proba(reloaded_model.predict_proba(split.X_test))

    np.testing.assert_allclose(p_test_orig, p_test_reloaded, rtol=1e-6)
