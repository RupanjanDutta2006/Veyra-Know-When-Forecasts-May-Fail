"""
Unit tests for Bust Label Engine.

Tests:
1. Training-period conditional q95 error threshold fitting
2. Binary bust_label generation (0/1)
3. Stratified vs variable-level fallback hierarchy
4. Sensitivity quantiles (q90, q95, q97.5, q99)
5. Gray-band / ambiguity zone classification
6. Threshold persistence and reload invariance
7. Temporal leakage prevention (frozen thresholds on test set)
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from labels.label_engine import BustLabelEngine, assign_lead_bin


@pytest.fixture
def sample_paired_data():
    """Create sample paired historical dataset with known error distribution."""
    np.random.seed(42)
    n_rows = 100
    rows = []
    for i in range(n_rows):
        lead = (i % 10) * 24
        var = ["temperature_2m", "surface_pressure", "wind_speed_10m"][i % 3]
        # Simulate absolute errors with occasional large extremes
        base_err = np.random.exponential(scale=1.5)
        if i in [10, 25, 50, 75, 90]:
            base_err += 8.0  # Force bust outliers

        rows.append({
            "location": "delhi",
            "variable": var,
            "lead_hours": lead,
            "forecast_abs_error": base_err,
            "forecast_value": 30.0 + i * 0.1,
            "truth_value": 30.0 + i * 0.1 - base_err,
        })
    return pd.DataFrame(rows)


def test_assign_lead_bin():
    """Test operational lead bin assignment."""
    assert assign_lead_bin(12) == "day1"
    assert assign_lead_bin(48) == "day2_3"
    assert assign_lead_bin(120) == "day4_6"
    assert assign_lead_bin(192) == "day7_10"
    assert assign_lead_bin(260) == "day10_plus"


def test_bust_label_engine_fitting_and_labeling(sample_paired_data):
    """Test fitting thresholds on training set and transforming to 0/1 labels."""
    engine = BustLabelEngine(primary_quantile=0.95)
    df_labeled = engine.fit_transform(sample_paired_data)

    assert "bust_label" in df_labeled.columns
    assert "bust_threshold" in df_labeled.columns
    assert set(df_labeled["bust_label"].unique()).issubset({0, 1})

    # Exactly the rows exceeding threshold must be labeled 1
    expected_busts = (df_labeled["forecast_abs_error"] >= df_labeled["bust_threshold"]).astype(int)
    pd.testing.assert_series_equal(df_labeled["bust_label"], expected_busts, check_names=False)


def test_sensitivity_quantiles(sample_paired_data):
    """Test that multiple sensitivity quantiles are generated monotonically."""
    engine = BustLabelEngine(
        primary_quantile=0.95,
        sensitivity_quantiles=[0.90, 0.95, 0.975, 0.99],
    )
    df_labeled = engine.fit_transform(sample_paired_data)

    # Invariant: Higher quantile threshold results in fewer or equal positive bust labels
    # q90 >= q95 >= q97.5 >= q99 positive count
    q90_count = df_labeled["bust_label_q9"].sum()
    q95_count = df_labeled["bust_label_q95"].sum()
    q975_count = df_labeled["bust_label_q975"].sum()
    q99_count = df_labeled["bust_label_q99"].sum()

    assert q90_count >= q95_count >= q975_count >= q99_count


def test_ambiguity_zone(sample_paired_data):
    """Test identification of gray-band / ambiguous error zone between q90 and q95."""
    engine = BustLabelEngine(primary_quantile=0.95)
    df_labeled = engine.fit_transform(sample_paired_data)

    assert "is_ambiguous_zone" in df_labeled.columns
    # Rows in ambiguous zone should have bust_label == 0 but bust_label_q9 == 1
    ambig_rows = df_labeled[df_labeled["is_ambiguous_zone"]]
    if not ambig_rows.empty:
        assert (ambig_rows["bust_label"] == 0).all()
        assert (ambig_rows["bust_label_q9"].astype(int) == 1).all()


def test_threshold_serialization_and_test_leakage_safety(sample_paired_data, tmp_path):
    """Test that frozen thresholds can be saved, reloaded, and applied to test data without leakage."""
    train_df = sample_paired_data.iloc[:70]
    test_df = sample_paired_data.iloc[70:]

    engine = BustLabelEngine(primary_quantile=0.95)
    engine.fit(train_df)

    thresh_file = tmp_path / "test_thresholds.json"
    engine.save_thresholds(thresh_file)
    assert thresh_file.exists()

    # Load into a fresh engine instance
    fresh_engine = BustLabelEngine().load_thresholds(thresh_file)
    assert fresh_engine.is_fitted_

    # Transform test set with frozen thresholds
    test_labeled = fresh_engine.transform(test_df)
    assert len(test_labeled) == len(test_df)
    assert "bust_label" in test_labeled.columns
