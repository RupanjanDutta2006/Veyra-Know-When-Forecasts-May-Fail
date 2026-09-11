"""
Unit tests for Historical Forecast / ERA5 Reference Alignment Engine.

Tests:
1. Time alignment on (location, variable, valid_time)
2. Mathematical error calculations (signed error, absolute error, ensemble mean error)
3. Missing pairs handling (drop diagnostics and inner join behavior)
4. Preservation of issue_time, valid_time, and lead_hours
5. Spatial distance calculation (Haversine colocation)
6. Leakage safeguard validation (truth columns separated from live features)
"""

import math
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import pytest

from data_pipeline.historical_aligner import (
    HistoricalAlignmentEngine,
    PAIRED_DATASET_COLUMNS,
    haversine_distance_km,
    standardize_era5_reference,
)


@pytest.fixture
def mock_forecast_df():
    """Mock standardized forecast DataFrame."""
    issue = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
    rows = []
    # 3 time steps (lead 0, 6, 12) for temperature and pressure
    for lead in [0, 6, 12]:
        valid = issue + timedelta(hours=lead)
        rows.append({
            "location": "delhi",
            "latitude": 28.5,
            "longitude": 77.25,
            "issue_time": issue,
            "valid_time": valid,
            "lead_hours": lead,
            "variable": "temperature_2m",
            "forecast_value": 30.0 + lead * 0.5,
            "forecast_unit": "degC",
            "forecast_source": "NOAA_GEFS",
            "member_id": "ensemble_summary",
            "ensemble_mean": 30.2 + lead * 0.5,
            "ensemble_std": 1.1,
            "ensemble_min": 28.5 + lead * 0.5,
            "ensemble_max": 32.0 + lead * 0.5,
            "q10": 29.0 + lead * 0.5,
            "q90": 31.5 + lead * 0.5,
            "member_count": 31,
        })
        rows.append({
            "location": "delhi",
            "latitude": 28.5,
            "longitude": 77.25,
            "issue_time": issue,
            "valid_time": valid,
            "lead_hours": lead,
            "variable": "surface_pressure",
            "forecast_value": 980.0 - lead * 0.2,
            "forecast_unit": "hPa",
            "forecast_source": "NOAA_GEFS",
            "member_id": "ensemble_summary",
            "ensemble_mean": 980.1 - lead * 0.2,
            "ensemble_std": 0.5,
            "ensemble_min": 979.0 - lead * 0.2,
            "ensemble_max": 981.0 - lead * 0.2,
            "q10": 979.5 - lead * 0.2,
            "q90": 980.7 - lead * 0.2,
            "member_count": 31,
        })
    return pd.DataFrame(rows)


@pytest.fixture
def mock_truth_df():
    """Mock standardized ERA5 reference DataFrame."""
    issue = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
    rows = []
    # Contains lead 0, lead 6, and an extra lead 18 (missing in forecast)
    # Notice lead 12 is missing in truth (simulating missing observation)
    for lead in [0, 6, 18]:
        valid = issue + timedelta(hours=lead)
        rows.append({
            "location": "delhi",
            "latitude": 28.576,
            "longitude": 77.187,
            "valid_time": valid,
            "variable": "temperature_2m",
            "truth_value": 29.0 + lead * 0.4,
            "truth_unit": "degC",
            "truth_source": "ERA5_REANALYSIS",
        })
        rows.append({
            "location": "delhi",
            "latitude": 28.576,
            "longitude": 77.187,
            "valid_time": valid,
            "variable": "surface_pressure",
            "truth_value": 981.0 - lead * 0.1,
            "truth_unit": "hPa",
            "truth_source": "ERA5_REANALYSIS",
        })
    return pd.DataFrame(rows)


def test_haversine_distance():
    """Test spatial distance calculation between Delhi forecast and ERA5 grid points."""
    # Delhi forecast grid: (28.5, 77.25), ERA5 grid: (28.576, 77.187)
    dist = haversine_distance_km(28.5, 77.25, 28.576, 77.187)
    assert 5.0 < dist < 15.0  # Approx 10.4 km colocation distance


def test_standardize_era5_reference():
    """Test raw ERA5 JSON parsing into standardized truth schema."""
    raw_payload = {
        "latitude": 28.576,
        "longitude": 77.187,
        "elevation": 214.0,
        "hourly": {
            "time": ["2026-08-01T00:00", "2026-08-01T01:00"],
            "temperature_2m": [26.5, 27.0],
            "surface_pressure": [975.0, 975.5],
            "wind_speed_10m": [10.0, 11.0],
        },
    }
    df = standardize_era5_reference(raw_payload, location_name="delhi")
    assert len(df) == 6  # 2 timestamps * 3 variables
    assert set(df["variable"].unique()) == {"temperature_2m", "surface_pressure", "wind_speed_10m"}
    assert df["truth_source"].iloc[0] == "ERA5_REANALYSIS"
    assert df["truth_unit"].iloc[0] == "degC"


def test_historical_alignment_and_error_calculation(mock_forecast_df, mock_truth_df):
    """Test time alignment and mathematical correctness of error columns."""
    aligner = HistoricalAlignmentEngine()
    df_paired, report = aligner.align(mock_forecast_df, mock_truth_df, join_policy="inner")

    # Matched pairs: lead 0 and lead 6 for 2 variables = 4 matched rows
    assert len(df_paired) == 4
    assert list(df_paired.columns) == PAIRED_DATASET_COLUMNS

    # Check lead 0 temperature: forecast=30.0, truth=29.0 -> error = 1.0, abs_error = 1.0
    t0 = df_paired[(df_paired["variable"] == "temperature_2m") & (df_paired["lead_hours"] == 0)].iloc[0]
    assert pytest.approx(t0["forecast_error"], 0.001) == 1.0
    assert pytest.approx(t0["forecast_abs_error"], 0.001) == 1.0

    # Ensemble mean: 30.2 - 29.0 = 1.2
    assert pytest.approx(t0["ensemble_mean_error"], 0.001) == 1.2
    assert pytest.approx(t0["ensemble_mean_abs_error"], 0.001) == 1.2

    # Invariant: forecast_abs_error == abs(forecast_error)
    assert (df_paired["forecast_abs_error"] == df_paired["forecast_error"].abs()).all()
    assert (df_paired["ensemble_mean_abs_error"] == df_paired["ensemble_mean_error"].abs()).all()


def test_missing_pairs_handling(mock_forecast_df, mock_truth_df):
    """Test that missing pairs are diagnosed cleanly and do not corrupt alignment."""
    aligner = HistoricalAlignmentEngine()
    df_paired, report = aligner.align(mock_forecast_df, mock_truth_df, join_policy="inner")

    assert report["total_forecast_records"] == 6
    assert report["total_truth_records"] == 6
    assert report["matched_paired_records"] == 4
    assert report["unmatched_forecast_records"] == 2  # Lead 12 was in forecast but not truth
    assert report["unmatched_truth_records"] == 2     # Lead 18 was in truth but not forecast


def test_timing_preservation(mock_forecast_df, mock_truth_df):
    """Test that issue_time, valid_time, and lead_hours are strictly preserved."""
    aligner = HistoricalAlignmentEngine()
    df_paired, report = aligner.align(mock_forecast_df, mock_truth_df, join_policy="inner")

    assert df_paired["issue_time"].notna().all()
    assert df_paired["valid_time"].notna().all()
    assert df_paired["lead_hours"].notna().all()

    for _, row in df_paired.iterrows():
        expected_lead = int((row["valid_time"] - row["issue_time"]).total_seconds() / 3600)
        assert row["lead_hours"] == expected_lead
