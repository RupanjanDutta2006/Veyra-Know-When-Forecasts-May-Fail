"""
Unit tests for standardization layer.
Tests:
- Schema validation
- Explicit issue_time requirement (fails if missing; proven not derived from valid_times[0])
- Lead-hour calculation accuracy (lead_hours = valid_time - explicit_issue_time)
- Unit preservation & mapping
- Ensemble statistics calculation (mean, std, min, max, q10, q90, count)
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from data_pipeline.standardize import GEFSStandardizer, REQUIRED_COLUMNS


@pytest.fixture
def mock_gefs_payload():
    """Provides a deterministic GEFS payload structure for offline unit testing."""
    times = [
        "2026-08-26T06:00",
        "2026-08-26T12:00",
        "2026-08-26T18:00",
        "2026-08-27T00:00",
    ]
    # 5 members for temperature
    temp_ctrl = [30.0, 32.0, 35.0, 28.0]
    temp_m1 = [29.0, 31.0, 34.0, 27.0]
    temp_m2 = [31.0, 33.0, 36.0, 29.0]
    temp_m3 = [30.5, 32.5, 35.5, 28.5]
    temp_m4 = [29.5, 31.5, 34.5, 27.5]

    # Pressure
    pres_ctrl = [1005.0, 1004.0, 1002.0, 1006.0]
    pres_m1 = [1006.0, 1005.0, 1003.0, 1007.0]

    # Wind
    wind_ctrl = [12.0, 15.0, 20.0, 10.0]
    wind_m1 = [14.0, 16.0, 22.0, 11.0]

    return {
        "latitude": 28.61,
        "longitude": 77.21,
        "elevation": 217.0,
        "generationtime_ms": 1.25,
        "hourly_units": {
            "time": "iso8601",
            "temperature_2m": "°C",
            "surface_pressure": "hPa",
            "wind_speed_10m": "km/h",
        },
        "hourly": {
            "time": times,
            "temperature_2m": temp_ctrl,
            "temperature_2m_member01": temp_m1,
            "temperature_2m_member02": temp_m2,
            "temperature_2m_member03": temp_m3,
            "temperature_2m_member04": temp_m4,
            "surface_pressure": pres_ctrl,
            "surface_pressure_member01": pres_m1,
            "wind_speed_10m": wind_ctrl,
            "wind_speed_10m_member01": wind_m1,
        },
    }


def test_explicit_issue_time_required(mock_gefs_payload):
    """Proves that standardizer strictly rejects implicit derivation and requires explicit issue_time."""
    standardizer = GEFSStandardizer()
    with pytest.raises(ValueError, match="Explicit issue_time must be provided"):
        standardizer.standardize(mock_gefs_payload, issue_time=None)


def test_schema_compliance(mock_gefs_payload):
    standardizer = GEFSStandardizer()
    df = standardizer.standardize(
        mock_gefs_payload,
        issue_time="2026-08-26T00:00:00Z",
        location_name="delhi",
    )

    # Assert all required columns are present and in exact order
    assert list(df.columns) == REQUIRED_COLUMNS
    assert len(df) == 4 * 3  # 4 time steps * 3 variables = 12 rows
    assert df["location"].iloc[0] == "delhi"
    assert df["source"].iloc[0] == "NOAA_GEFS"


def test_timestamp_and_lead_hours_from_explicit_issue_time(mock_gefs_payload):
    """
    Proves that issue_time is sourced from explicit metadata and NOT inferred from valid_times[0].
    Here, valid_times starts at 06:00, but explicit issue_time is 00:00.
    Thus, first lead_hours must be 6, NOT 0.
    """
    standardizer = GEFSStandardizer()
    explicit_issue = "2026-08-26T00:00:00Z"
    df = standardizer.standardize(mock_gefs_payload, issue_time=explicit_issue)

    expected_issue = pd.Timestamp("2026-08-26 00:00:00", tz="UTC")
    for val in df["issue_time"]:
        assert val == expected_issue

    # Check lead hours for each step: valid_times are 06:00, 12:00, 18:00, 24:00 (next day)
    # Expected lead_hours: 6, 12, 18, 24
    t_df = df[df["variable"] == "temperature_2m"].sort_values("valid_time")
    assert list(t_df["lead_hours"]) == [6, 12, 18, 24]

    # Verify mathematical invariant: lead_hours = (valid_time - explicit_issue_time) in hours
    for _, row in df.iterrows():
        expected_lead = int((row["valid_time"] - expected_issue).total_seconds() / 3600)
        assert row["lead_hours"] == expected_lead


def test_ensemble_statistics_computation(mock_gefs_payload):
    standardizer = GEFSStandardizer()
    df = standardizer.standardize(mock_gefs_payload, issue_time="2026-08-26T06:00:00Z")

    t_df = df[df["variable"] == "temperature_2m"].sort_values("valid_time")
    # For first time step: members are 30.0, 29.0, 31.0, 30.5, 29.5
    step0 = t_df.iloc[0]
    expected_members = [30.0, 29.0, 31.0, 30.5, 29.5]

    assert step0["member_count"] == 5
    assert pytest.approx(step0["ensemble_mean"], 0.01) == np.mean(expected_members)
    assert pytest.approx(step0["ensemble_std"], 0.01) == np.std(expected_members, ddof=1)
    assert pytest.approx(step0["ensemble_min"], 0.01) == 29.0
    assert pytest.approx(step0["ensemble_max"], 0.01) == 31.0
    assert step0["q10"] <= step0["ensemble_mean"] <= step0["q90"]


def test_unit_mapping(mock_gefs_payload):
    standardizer = GEFSStandardizer()
    df = standardizer.standardize(mock_gefs_payload, issue_time="2026-08-26T00:00:00Z")

    units_by_var = df.groupby("variable")["unit"].unique().to_dict()
    assert units_by_var["temperature_2m"][0] == "degC"
    assert units_by_var["surface_pressure"][0] == "hPa"
    assert units_by_var["wind_speed_10m"][0] == "km/h"
