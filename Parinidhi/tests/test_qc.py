"""
Unit tests for Quality Control (QC) module.
Validates all 7 rules:
1. Missing value detection
2. Duplicate row detection
3. Invalid timestamp detection
4. Unit mismatch detection
5. Missing ensemble members detection
6. Stale data detection
7. Out-of-range value detection
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from data_pipeline.qc import QualityControl


@pytest.fixture
def clean_forecast_df():
    """Returns a pristine standardized forecast DataFrame for testing."""
    now = datetime.now(timezone.utc)
    return pd.DataFrame([
        {
            "location": "delhi",
            "latitude": 28.61,
            "longitude": 77.21,
            "issue_time": now,
            "valid_time": now + timedelta(hours=6),
            "lead_hours": 6,
            "variable": "temperature_2m",
            "value": 32.5,
            "unit": "degC",
            "source": "NOAA_GEFS",
            "member_id": "ensemble_summary",
            "ensemble_mean": 32.5,
            "ensemble_std": 1.2,
            "ensemble_min": 30.1,
            "ensemble_max": 34.8,
            "q10": 31.0,
            "q90": 34.0,
            "member_count": 31,
        },
        {
            "location": "delhi",
            "latitude": 28.61,
            "longitude": 77.21,
            "issue_time": now,
            "valid_time": now + timedelta(hours=6),
            "lead_hours": 6,
            "variable": "surface_pressure",
            "value": 1005.0,
            "unit": "hPa",
            "source": "NOAA_GEFS",
            "member_id": "ensemble_summary",
            "ensemble_mean": 1005.0,
            "ensemble_std": 0.8,
            "ensemble_min": 1003.0,
            "ensemble_max": 1007.0,
            "q10": 1004.0,
            "q90": 1006.0,
            "member_count": 31,
        },
        {
            "location": "delhi",
            "latitude": 28.61,
            "longitude": 77.21,
            "issue_time": now,
            "valid_time": now + timedelta(hours=6),
            "lead_hours": 6,
            "variable": "wind_speed_10m",
            "value": 15.0,
            "unit": "km/h",
            "source": "NOAA_GEFS",
            "member_id": "ensemble_summary",
            "ensemble_mean": 15.0,
            "ensemble_std": 2.5,
            "ensemble_min": 10.0,
            "ensemble_max": 20.0,
            "q10": 12.0,
            "q90": 18.0,
            "member_count": 31,
        },
    ])


def test_qc_clean_pass(clean_forecast_df):
    qc = QualityControl()
    df_qc, report = qc.run_qc(clean_forecast_df)

    assert report["total_records"] == 3
    assert report["passed_records"] == 3
    assert report["failed_records"] == 0
    assert report["pass_rate_pct"] == 100.0
    assert df_qc["qc_passed"].all()


def test_qc_missing_value_detection(clean_forecast_df):
    df_dirty = clean_forecast_df.copy()
    df_dirty.loc[0, "value"] = np.nan

    qc = QualityControl()
    df_qc, report = qc.run_qc(df_dirty)

    assert report["rule_breakdown"]["missing_value"] == 1
    assert df_qc.loc[0, "qc_flag_missing_value"] == True
    assert df_qc.loc[0, "qc_passed"] == False


def test_qc_duplicate_detection(clean_forecast_df):
    # Duplicate first row
    df_dirty = pd.concat([clean_forecast_df, clean_forecast_df.iloc[[0]]], ignore_index=True)

    qc = QualityControl()
    df_qc, report = qc.run_qc(df_dirty)

    assert report["rule_breakdown"]["duplicate"] == 2
    assert df_qc["qc_flag_duplicate"].sum() == 2


def test_qc_invalid_timestamp(clean_forecast_df):
    df_dirty = clean_forecast_df.copy()
    # Set valid_time BEFORE issue_time and negative lead
    df_dirty.loc[0, "valid_time"] = df_dirty.loc[0, "issue_time"] - timedelta(hours=3)
    df_dirty.loc[0, "lead_hours"] = -3

    qc = QualityControl()
    df_qc, report = qc.run_qc(df_dirty)

    assert report["rule_breakdown"]["invalid_timestamp"] == 1
    assert df_qc.loc[0, "qc_flag_invalid_timestamp"] == True
    assert df_qc.loc[0, "qc_passed"] == False


def test_qc_unit_mismatch(clean_forecast_df):
    df_dirty = clean_forecast_df.copy()
    df_dirty.loc[0, "unit"] = "Kelvin"  # Should be degC

    qc = QualityControl()
    df_qc, report = qc.run_qc(df_dirty)

    assert report["rule_breakdown"]["unit_mismatch"] == 1
    assert df_qc.loc[0, "qc_flag_unit_mismatch"] == True


def test_qc_missing_members(clean_forecast_df):
    df_dirty = clean_forecast_df.copy()
    df_dirty.loc[0, "member_count"] = 3  # Less than min 10

    qc = QualityControl(min_ensemble_members=10)
    df_qc, report = qc.run_qc(df_dirty)

    assert report["rule_breakdown"]["missing_members"] == 1
    assert df_qc.loc[0, "qc_flag_missing_members"] == True


def test_qc_stale_data(clean_forecast_df):
    df_dirty = clean_forecast_df.copy()
    # Make issue time 5 days old
    old_time = datetime.now(timezone.utc) - timedelta(days=5)
    df_dirty["issue_time"] = old_time

    qc = QualityControl(max_stale_hours=72.0)
    df_qc, report = qc.run_qc(df_dirty)

    assert report["rule_breakdown"]["stale_data"] == 3
    assert df_qc["qc_flag_stale_data"].all()


def test_qc_out_of_range(clean_forecast_df):
    df_dirty = clean_forecast_df.copy()
    df_dirty.loc[0, "value"] = 150.0  # 150°C is physically impossible

    qc = QualityControl()
    df_qc, report = qc.run_qc(df_dirty)

    assert report["rule_breakdown"]["out_of_range"] == 1
    assert df_qc.loc[0, "qc_flag_out_of_range"] == True
