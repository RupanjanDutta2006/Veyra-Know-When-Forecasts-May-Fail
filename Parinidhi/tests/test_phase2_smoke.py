"""
Real-Data Smoke Test — Historical Forecast & ERA5 Verification Alignment.

Tests the full historical chain on real data:
Historical GEFS Ingestion -> Historical ERA5 Ingestion -> Dual Standardization -> Alignment & Error Calculation -> Parquet Persistence.

Marked with @pytest.mark.smoke.
"""

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
import pandas as pd

from ingestion.collector import GEFSCollector
from ingestion.era5_collector import ERA5ReferenceCollector
from data_pipeline.standardize import GEFSStandardizer
from data_pipeline.historical_aligner import HistoricalAlignmentEngine, standardize_era5_reference, PAIRED_DATASET_COLUMNS


@pytest.mark.smoke
def test_real_historical_alignment_smoke(tmp_path):
    """End-to-end smoke test for historical forecast/reference alignment using real data."""
    # Dynamically select a recent valid window supported by the live GEFS/ERA5 endpoints
    now_utc = datetime.now(timezone.utc)
    start_date = (now_utc - timedelta(days=3)).strftime("%Y-%m-%d")
    end_date = (now_utc - timedelta(days=1)).strftime("%Y-%m-%d")
    location = "delhi"

    # 1. Ingest/Load Historical GEFS Forecast with authoritative registry verification
    gefs_collector = GEFSCollector(raw_dir=str(tmp_path / "raw_gefs"))
    raw_gefs, raw_gefs_p, gefs_manifest_p, gefs_manifest = gefs_collector.fetch_forecast(
        latitude=28.6139,
        longitude=77.2090,
        location_name=location,
        start_date=start_date,
        end_date=end_date,
        use_cache=False,  # Re-verify and re-download fresh to prove registry check
    )
    assert raw_gefs_p.exists()
    assert gefs_manifest_p.exists()
    assert gefs_manifest["issue_time_source"] == "NOAA NCEP GEFS AWS S3 Open Data Registry"
    assert "authoritative_cycle_details" in gefs_manifest
    assert gefs_manifest["authoritative_cycle_details"]["selected_cycle"] in ("00z", "06z", "12z", "18z")

    # 2. Ingest/Load Historical ERA5 Truth Reference
    era5_collector = ERA5ReferenceCollector(raw_dir=str(tmp_path / "raw_era5"))
    raw_era5, raw_era5_p, era5_manifest_p, era5_manifest = era5_collector.fetch_historical_reference(
        start_date=start_date,
        end_date=end_date,
        latitude=28.6139,
        longitude=77.2090,
        location_name=location,
        use_cache=False,
    )
    assert raw_era5_p.exists()
    assert era5_manifest_p.exists()

    # 3. Standardize Both
    standardizer = GEFSStandardizer(processed_dir=str(tmp_path / "processed_gefs"))
    df_forecast = standardizer.standardize(
        raw_gefs,
        issue_time=gefs_manifest["explicit_issue_time_utc"],
        location_name=location,
        filter_future_only=True,
    )
    df_truth = standardize_era5_reference(raw_era5, location_name=location)

    assert len(df_forecast) > 0
    assert len(df_truth) > 0

    # 4. Align & Compute Error
    aligner = HistoricalAlignmentEngine(historical_dir=str(tmp_path / "historical"))
    df_paired, report = aligner.align(df_forecast, df_truth, join_policy="inner")

    # Invariants
    assert list(df_paired.columns) == PAIRED_DATASET_COLUMNS
    assert len(df_paired) > 0
    assert report["matched_paired_records"] == len(df_paired)
    assert report["match_rate_pct"] > 90.0

    # Verify mathematical accuracy of error
    assert (df_paired["forecast_abs_error"] == df_paired["forecast_error"].abs()).all()
    assert (df_paired["ensemble_mean_abs_error"] == df_paired["ensemble_mean_error"].abs()).all()

    # Verify timing invariants
    assert (df_paired["valid_time"] >= df_paired["issue_time"]).all()
    assert (df_paired["lead_hours"] >= 0).all()

    # 5. Storage
    parquet_p, csv_p, manifest_p = aligner.save_paired_dataset(df_paired, report, location_name=location)
    assert parquet_p.exists()
    assert csv_p.exists()
    assert manifest_p.exists()
    assert parquet_p.stat().st_size > 0

    df_loaded = pd.read_parquet(parquet_p)
    assert len(df_loaded) == len(df_paired)
