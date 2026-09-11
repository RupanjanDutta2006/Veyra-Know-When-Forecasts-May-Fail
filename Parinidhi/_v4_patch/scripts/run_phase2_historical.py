"""
Historical Forecast/Reference Alignment & Error Engine Runner.

Executes end-to-end:
1. Ingest Genuine Historical GEFS Forecasts (Delhi) from NOAA AWS S3 via ecCodes byte-range extraction
2. Ingest Historical ERA5 Reanalysis Verification Reference for matching valid times
3. Align by Location, Variable, and Valid Time under Spatial Colocation Policy
4. Compute Forecast Error, Absolute Error, and Ensemble Mean Errors
5. Persist Paired Historical Dataset to data/historical/delhi/
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.historical_gefs_collector import HistoricalGEFSCollector
from ingestion.era5_collector import ERA5ReferenceCollector
from data_pipeline.historical_aligner import HistoricalAlignmentEngine, standardize_era5_reference


def run_historical_alignment(
    location_name: str = "delhi",
    latitude: float = 28.6139,
    longitude: float = 77.2090,
    start_date: str = "2026-08-18",
    end_date: str = "2026-08-24",
    cycle: str = "00",
    horizon_hours: int = 72,
    step_hours: int = 3,
    use_cache: bool = True,
) -> int:
    print("=" * 80)
    print(" FORECAST-BUST SENTINEL — PHASE 2: HISTORICAL NOAA S3 ALIGNMENT & ERROR ENGINE")
    print("=" * 80)
    print(f"Target Location  : {location_name.upper()} (Lat: {latitude:.4f}, Lon: {longitude:.4f})")
    print(f"Historical Window: {start_date} to {end_date} (00z cycle, 0-{horizon_hours}h at {step_hours}h steps)")
    print(f"Forecast Model   : NOAA GEFSv12 reforecast (00Z; 5 members normally, 11 on weekly extended runs)")
    print(f"Truth Reference  : ERA5 reanalysis verification reference (Open-Meteo Historical Archive)")
    print("-" * 80)

    # 1. Ingest Genuine Historical GEFS Forecasts from NOAA AWS S3
    print("\n[STEP 1/4] INGESTION — Fetching Genuine NOAA GEFS S3 Byte Slices & ecCodes Decoding...")
    hist_collector = HistoricalGEFSCollector()
    try:
        df_forecast, gefs_manifest, raw_gefs_path, gefs_manifest_path = hist_collector.collect_range(
            start_date=start_date,
            end_date=end_date,
            cycle=cycle,
            horizon_hours=horizon_hours,
            step_hours=step_hours,
            latitude=latitude,
            longitude=longitude,
            location_name=location_name,
            use_cache=use_cache,
        )
        print(f"  [OK] Preserved raw S3 slice json    : {raw_gefs_path}")
        print(f"  [OK] Standardized Forecast Records : {len(df_forecast)}")
        print(f"  [OK] Total Distinct Cycles         : {gefs_manifest.get('total_distinct_cycles')}")
        print(f"  [OK] Spatial Colocation Distance   : {gefs_manifest.get('spatial_distance_km')} km")
    except Exception as e:
        print(f"[ERROR] Failed to ingest historical GEFS data from NOAA S3: {e}", file=sys.stderr)
        return 1

    # 2. Ingest ERA5 verification reference.  Query through the forecast horizon so
    # every requested valid time can be verified when the archive contains it.
    d_end = datetime.strptime(end_date.replace("-", "")[:8], "%Y%m%d")
    desired_end = d_end + timedelta(hours=horizon_hours)
    era5_end_str = desired_end.strftime("%Y-%m-%d")

    print(f"\n[STEP 2/4] INGESTION — Fetching ERA5 Verification Reference ({start_date} to {era5_end_str})...")
    era5_collector = ERA5ReferenceCollector()
    try:
        raw_era5, raw_era5_path, era5_manifest_path, era5_manifest = era5_collector.fetch_historical_reference(
            start_date=start_date,
            end_date=era5_end_str,
            latitude=latitude,
            longitude=longitude,
            location_name=location_name,
            use_cache=use_cache,
        )
        df_truth = standardize_era5_reference(raw_era5, location_name=location_name)
        print(f"  [OK] Preserved raw ERA5 json       : {raw_era5_path}")
        print(f"  [OK] Standardized Truth Records    : {len(df_truth)}")
    except Exception as e:
        print(f"[ERROR] Failed to ingest ERA5 reference data: {e}", file=sys.stderr)
        return 1

    # 3. Alignment & Error Calculation
    print("\n[STEP 3/4] ALIGNMENT & ERROR CALCULATION — Matching on (location, variable, valid_time)...")
    aligner = HistoricalAlignmentEngine()
    try:
        df_paired, alignment_report = aligner.align(df_forecast, df_truth, join_policy="inner")
        print(f"  [OK] Matched Paired Records       : {alignment_report['matched_paired_records']} ({alignment_report['match_rate_pct']}%)")
        print(f"  [OK] Mean Spatial Colocation Dist : {alignment_report['mean_spatial_distance_km']} km")
        print("  [OK] Error Metrics Summary by Variable:")
        for var, metrics in alignment_report["variable_error_metrics"].items():
            print(f"      - {var.ljust(20)}: Mean Bias={metrics['mean_error_bias']:+.2f}, MAE={metrics['mae']:.2f}, RMSE={metrics['rmse']:.2f}, Ens_MAE={metrics['ensemble_mae']:.2f}")
    except Exception as e:
        print(f"[ERROR] Alignment failed: {e}", file=sys.stderr)
        return 1

    # 4. Persist Paired Dataset
    print("\n[STEP 4/4] STORAGE — Persisting Paired Historical Dataset...")
    parquet_p, csv_p, manifest_p = aligner.save_paired_dataset(df_paired, alignment_report, location_name=location_name)
    print(f"  [OK] Paired Parquet saved : {parquet_p} ({parquet_p.stat().st_size / 1024.0:.2f} KB)")
    print(f"  [OK] Paired CSV saved     : {csv_p} ({csv_p.stat().st_size / 1024.0:.2f} KB)")
    print(f"  [OK] Alignment manifest   : {manifest_p}")

    # Print Sample Paired Row
    print("\n" + "=" * 80)
    print(" SAMPLE HISTORICAL PAIRED RECORD (GENUINE NOAA S3 + ERA5)")
    print("=" * 80)
    sample_row = df_paired.iloc[0].to_dict()
    for col, val in sample_row.items():
        print(f"  {col.ljust(26)} : {val}")

    print("\n" + "=" * 80)
    print(" PHASE 2 HISTORICAL ALIGNMENT COMPLETED SUCCESSFULLY")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Forecast-Bust Sentinel Phase 2 Historical Pipeline")
    parser.add_argument("--location", default="delhi", help="Location name")
    parser.add_argument("--lat", type=float, default=28.6139, help="Latitude")
    parser.add_argument("--lon", type=float, default=77.2090, help="Longitude")
    parser.add_argument("--start-date", default="2026-08-18", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default="2026-08-24", help="End date (YYYY-MM-DD)")
    parser.add_argument("--cycle", default="00", help="Cycle hour (00, 06, 12, 18)")
    parser.add_argument("--horizon-hours", type=int, default=72, help="Forecast horizon hours (default: 72)")
    parser.add_argument("--step-hours", type=int, default=3, help="Forecast step hours (default: 3)")
    parser.add_argument("--use-cache", action="store_true", default=True, help="Reuse local raw cache if available")
    args = parser.parse_args()

    sys.exit(run_historical_alignment(
        location_name=args.location,
        latitude=args.lat,
        longitude=args.lon,
        start_date=args.start_date,
        end_date=args.end_date,
        cycle=args.cycle,
        horizon_hours=args.horizon_hours,
        step_hours=args.step_hours,
        use_cache=args.use_cache,
    ))
