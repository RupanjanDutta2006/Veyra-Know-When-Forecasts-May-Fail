"""
Real-Data Smoke Test for GEFS Forecast Pipeline.

Validates the full medium-range chain with real NOAA GEFS data and verified issue time:
GEFS Source -> Authoritative Status Query -> Raw Preservation & Manifest -> Standardization -> QC -> Structured DataFrame.

Does not re-download on every run if cached raw data with sufficient horizon is present.
Marked with @pytest.mark.smoke for explicit invocation.
"""

import os
from pathlib import Path
import pytest
import pandas as pd

from ingestion.collector import GEFSCollector
from data_pipeline.standardize import GEFSStandardizer, REQUIRED_COLUMNS
from data_pipeline.qc import QualityControl


@pytest.mark.smoke
def test_real_gefs_pipeline_smoke():
    """End-to-end smoke test using real NOAA GEFS forecast data for Delhi across 10-day medium-range horizon."""
    # 1. Ingestion with authoritative status verification
    collector = GEFSCollector(raw_dir="data/raw/gefs")
    raw_data, raw_file_path, manifest_path, manifest = collector.fetch_forecast(
        latitude=28.6139,
        longitude=77.2090,
        location_name="delhi",
        forecast_days=11,  # 11 days ensures >= 240 hours of future lead time after cycle alignment
        use_cache=True,
    )

    # Invariant: Raw files and status payload must exist on disk
    assert raw_file_path.exists(), f"Raw file {raw_file_path} not found"
    assert manifest_path.exists(), f"Manifest {manifest_path} not found"
    assert "status_file_path" in manifest
    assert Path(manifest["status_file_path"]).exists()
    assert raw_file_path.stat().st_size > 0
    assert manifest_path.stat().st_size > 0

    # Invariant: Manifest must contain explicit verified issue time and authoritative provenance
    assert "explicit_issue_time_utc" in manifest
    assert "authoritative_cycle_details" in manifest
    assert manifest["model_identifier"] == "ncep_gefs025"
    assert manifest["actual_returned_horizon_hours"] >= 240

    # Invariant: Raw data must contain real geographic coordinates
    assert abs(raw_data.get("latitude", 0) - 28.5) < 0.5  # Delhi grid cell
    assert abs(raw_data.get("longitude", 0) - 77.25) < 0.5

    # 2. Standardization with explicit issue_time
    explicit_issue_time = manifest["explicit_issue_time_utc"]
    standardizer = GEFSStandardizer(processed_dir="data/processed/gefs")
    df_std = standardizer.standardize(
        raw_data,
        issue_time=explicit_issue_time,
        location_name="delhi",
        filter_future_only=True,
    )

    # Invariant: Schema compliance
    assert list(df_std.columns) == REQUIRED_COLUMNS
    assert len(df_std) >= 700  # 237 forecast steps * 3 variables = 711 records

    # Invariant: Timestamps & Medium-Range Lead Hours integrity
    assert df_std["issue_time"].notna().all()
    assert df_std["valid_time"].notna().all()
    assert (df_std["valid_time"] >= df_std["issue_time"]).all()
    assert (df_std["lead_hours"] >= 0).all()
    assert df_std["lead_hours"].min() == 0
    assert df_std["lead_hours"].max() >= 235, f"Expected >= 235h lead time (Day 10), got {df_std['lead_hours'].max()}"

    # Verify mathematical invariant: lead_hours == (valid_time - explicit_issue_time) in hours
    expected_issue_dt = pd.to_datetime(explicit_issue_time, utc=True)
    for _, row in df_std.head(20).iterrows():
        expected_lead = int((row["valid_time"] - expected_issue_dt).total_seconds() / 3600)
        assert row["lead_hours"] == expected_lead

    # Invariant: All 3 minimal variables must be present across all lead hours
    present_vars = set(df_std["variable"].unique())
    expected_vars = {"temperature_2m", "surface_pressure", "wind_speed_10m"}
    assert expected_vars.issubset(present_vars)

    # Invariant: Real ensemble members (GEFS has 31 members)
    assert df_std["member_count"].iloc[0] == 31
    assert df_std["ensemble_std"].notna().all()
    assert (df_std["q10"] <= df_std["q90"]).all()
    assert (df_std["ensemble_min"] <= df_std["ensemble_max"]).all()

    # 3. Quality Control
    qc = QualityControl()
    df_qc, qc_report = qc.run_qc(df_std)

    assert qc_report["total_records"] == len(df_std)
    assert "qc_passed" in df_qc.columns
    assert qc_report["pass_rate_pct"] == 100.0, f"Expected 100% QC pass on future forecast steps: {qc_report}"

    # 4. Storage round-trip
    parquet_path = standardizer.save_processed(df_qc, location_name="delhi")
    assert parquet_path.exists()
    assert parquet_path.stat().st_size > 0

    df_loaded = pd.read_parquet(parquet_path)
    assert len(df_loaded) == len(df_qc)
