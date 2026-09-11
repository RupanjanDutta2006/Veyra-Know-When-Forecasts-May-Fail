"""
Forecast Data Ingestion & Standardization Pipeline Runner.

Executes end-to-end:
Location (Delhi) -> Real NOAA GEFS Ingestion (Medium-Range 10-day) ->
Raw Preservation & Provenance Manifest -> Standardization (with Explicit Issue Time) ->
7-Rule QC -> Parquet/CSV Output
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.collector import GEFSCollector
from data_pipeline.standardize import GEFSStandardizer
from data_pipeline.qc import QualityControl


def run_pipeline(
    location_name: str = "delhi",
    latitude: float = 28.6139,
    longitude: float = 77.2090,
    forecast_days: int = 10,  # Medium-range horizon (240 hours)
    issue_time: str = None,
    use_cache: bool = False,
) -> int:
    print("=" * 70)
    print(" FORECAST-BUST SENTINEL — BUILDER 2 DAY 1 PIPELINE")
    print("=" * 70)
    print(f"Target Location  : {location_name.upper()} (Lat: {latitude:.4f}, Lon: {longitude:.4f})")
    print(f"Data Source      : NOAA GEFS (Global Ensemble Forecast System 0.25 deg)")
    print(f"Forecast Horizon : {forecast_days} days (Medium-Range: {forecast_days*24} hours)")
    print(f"Cache Mode       : {'Reusing local cache if available' if use_cache else 'Live download from NOAA endpoint'}")
    print("-" * 70)

    # 1. Ingestion
    print("\n[STEP 1/4] INGESTION — Fetching Real GEFS Forecast Data...")
    collector = GEFSCollector()
    try:
        raw_data, raw_file_path, manifest_path, manifest = collector.fetch_forecast(
            latitude=latitude,
            longitude=longitude,
            location_name=location_name,
            forecast_days=forecast_days,
            issue_time=issue_time,
            use_cache=use_cache,
        )
    except Exception as e:
        print(f"[ERROR] Failed to ingest GEFS data: {e}", file=sys.stderr)
        return 1

    explicit_issue_time = manifest.get("explicit_issue_time_utc")
    print(f"  [OK] Raw GEFS data preserved : {raw_file_path}")
    print(f"  [OK] Provenance manifest saved: {manifest_path}")
    print(f"  [OK] Explicit Issue Time     : {explicit_issue_time} (source: {manifest.get('issue_time_source')})")
    raw_size_kb = raw_file_path.stat().st_size / 1024.0
    print(f"  [OK] Raw payload size        : {raw_size_kb:.2f} KB")

    # 2. Standardization
    print("\n[STEP 2/4] STANDARDIZATION — Converting to Canonical Schema with Explicit Issue Time...")
    standardizer = GEFSStandardizer()
    try:
        df_std = standardizer.standardize(
            raw_data,
            issue_time=explicit_issue_time,
            location_name=location_name,
        )
    except Exception as e:
        print(f"[ERROR] Standardization failed: {e}", file=sys.stderr)
        return 1

    print(f"  [OK] Standardized rows       : {len(df_std)}")
    print(f"  [OK] Variables included      : {df_std['variable'].unique().tolist()}")
    print(f"  [OK] Ensemble members parsed : {df_std['member_count'].iloc[0] if len(df_std) > 0 else 0}")
    print(f"  [OK] Lead hours span         : {df_std['lead_hours'].min()} to {df_std['lead_hours'].max()} hrs ({len(df_std['lead_hours'].unique())} steps)")

    # 3. Quality Control
    print("\n[STEP 3/4] QUALITY CONTROL — Executing 7 QC Validation Rules...")
    qc = QualityControl()
    df_qc, qc_report = qc.run_qc(df_std)

    print(f"  [OK] Total records checked   : {qc_report['total_records']}")
    print(f"  [OK] Passed records          : {qc_report['passed_records']} ({qc_report['pass_rate_pct']}%)")
    print(f"  [OK] Failed records          : {qc_report['failed_records']}")
    print("  [OK] QC Rule Breakdown:")
    for rule, failures in qc_report["rule_breakdown"].items():
        status = "PASS (0 failures)" if failures == 0 else f"FLAGGED ({failures} records)"
        print(f"      - {rule.ljust(22)}: {status}")

    # 4. Storage
    print("\n[STEP 4/4] STORAGE — Persisting Processed Artifacts...")
    parquet_path = standardizer.save_processed(df_qc, location_name=location_name)
    csv_path = parquet_path.with_suffix(".csv")
    print(f"  [OK] Parquet output saved    : {parquet_path} ({parquet_path.stat().st_size / 1024.0:.2f} KB)")
    print(f"  [OK] CSV inspection saved    : {csv_path} ({csv_path.stat().st_size / 1024.0:.2f} KB)")

    # Print Sample Output
    print("\n" + "=" * 70)
    print(" SAMPLE STANDARDIZED & QC-CHECKED RECORDS (FIRST 3 ROWS)")
    print("=" * 70)
    sample_cols = ["variable", "issue_time", "valid_time", "lead_hours", "value", "unit", "ensemble_mean", "ensemble_std", "q10", "q90", "qc_passed"]
    print(df_qc[sample_cols].head(3).to_string(index=False))

    print("\n" + "=" * 70)
    print(f" DAY 1 PIPELINE EXECUTION COMPLETED (HORIZON: {df_std['lead_hours'].max()} HOURS)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Forecast-Bust Sentinel Day 1 Pipeline")
    parser.add_argument("--location", default="delhi", help="Location name")
    parser.add_argument("--lat", type=float, default=28.6139, help="Latitude")
    parser.add_argument("--lon", type=float, default=77.2090, help="Longitude")
    parser.add_argument("--days", type=int, default=10, help="Forecast days (default: 10 for medium-range)")
    parser.add_argument("--issue-time", default=None, help="Explicit issue time (ISO8601 UTC)")
    parser.add_argument("--use-cache", action="store_true", help="Reuse local raw cached file if present")
    args = parser.parse_args()

    sys.exit(run_pipeline(
        location_name=args.location,
        latitude=args.lat,
        longitude=args.lon,
        forecast_days=args.days,
        issue_time=args.issue_time,
        use_cache=args.use_cache,
    ))
