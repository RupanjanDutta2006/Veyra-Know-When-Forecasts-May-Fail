"""
Day 9 Scientific Multi-Location Multi-Climate Data Foundation Test Suite.

Verifies:
1. Benchmark climate metadata & preservation of all 20 registered locations.
2. LocationRegistry climate query helpers and benchmark indicators.
3. Multi-cycle forecast identity preservation (00Z, 06Z, 12Z, 18Z distinct issue times).
4. Canonical multi-climate historical dataset schema completeness.
5. Forecast vs truth temporal alignment and signed/absolute error calculations.
6. Spatial mismatch distance calculation and >50km threshold validation.
7. Missing member detection and has_full_ensemble boolean tagging.
8. Duplicate record detection on (location_id, variable, issue_time_utc, valid_time_utc).
9. Physical atmospheric QC bounds validation.
10. Strict anti-leakage audit (verification target fields cannot contaminate feature matrices).
11. Reproducibility, manifest generation, and SHA-256 hashing.
12. Deterministic multi-station multi-climate dataset assembly.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from api.location_service import LocationRegistry, haversine_distance_km
from data_pipeline.historical_aligner import (
    CANONICAL_FEATURE_COLUMNS,
    CANONICAL_HISTORICAL_COLUMNS,
    CANONICAL_TARGET_COLUMNS,
    HistoricalAlignmentEngine,
    MultiClimateDatasetBuilder,
    standardize_era5_reference,
)
from data_pipeline.standardize import GEFSStandardizer
from features.leakage_audit import DataLeakageError, LeakageAuditor


# ---------------------------------------------------------------------------
# Test 1: Preservation of 20 Locations & 8 Benchmark Climate Annotations
# ---------------------------------------------------------------------------
def test_1_location_registry_20_locations_and_8_benchmarks():
    registry = LocationRegistry()
    all_locations = registry.list_locations()
    assert len(all_locations) == 20, f"Expected 20 registered locations, got {len(all_locations)}"

    benchmark_locations = registry.list_benchmark_locations()
    assert len(benchmark_locations) == 8, f"Expected 8 benchmark locations, got {len(benchmark_locations)}"

    expected_benchmarks = {
        "delhi": ("North", "Cwa/BSh", "Subtropical Semi-Arid / Continental", 214.0),
        "jaipur": ("Rajasthan", "BSh/BWh", "Hot Semi-Arid / Desert Margin", 431.0),
        "mumbai": ("Maharashtra", "Am/Aw", "Tropical Coastal / Maritime", 14.0),
        "kolkata": ("West Bengal", "Aw/Cwa", "Tropical Wet-and-Dry / Deltaic", 9.0),
        "bengaluru": ("Karnataka", "Aw", "Elevated Interior Plateau", 920.0),
        "chennai": ("Tamil Nadu", "As/Aw", "Tropical Maritime / Coromandel Coast", 7.0),
        "srinagar": ("Jammu and Kashmir", "Cfb/Dfb", "Himalayan Mountain & Valley", 1585.0),
        "guwahati": ("Assam", "Cwa", "Subtropical Valley / Monsoonal", 55.0),
    }

    for loc_id, (expected_region, expected_cz, expected_regime, expected_elev) in expected_benchmarks.items():
        assert registry.is_benchmark_location(loc_id) is True
        info = registry.get_location(loc_id)
        assert info.is_benchmark is True
        assert info.climate_zone == expected_cz
        assert info.meteorological_regime == expected_regime
        assert info.elevation_m == expected_elev
        assert info.rationale is not None and len(info.rationale) > 10

    # Test a non-benchmark location
    assert registry.is_benchmark_location("pune") is False
    pune_info = registry.get_location("pune")
    assert pune_info.is_benchmark is False
    assert pune_info.climate_zone == "BSh/Aw"


# ---------------------------------------------------------------------------
# Test 2: Location Registry Climate & Region Queries
# ---------------------------------------------------------------------------
def test_2_location_registry_query_helpers():
    registry = LocationRegistry()

    # Climate queries
    cwa_locs = registry.get_locations_by_climate("Cwa")
    assert len(cwa_locs) >= 4  # Delhi, Chandigarh, Lucknow, Kolkata, Guwahati, Ranchi

    aw_locs = registry.get_locations_by_climate("Aw")
    assert len(aw_locs) >= 6  # Mumbai, Kolkata, Bengaluru, Chennai, Nagpur, Raipur, Bhopal, Bhubaneswar

    # Region queries
    south_locs = registry.get_locations_by_region("Karnataka")
    assert any(l["location_id"] == "bengaluru" for l in south_locs)

    assert registry.get_climate_zone("delhi") == "Cwa/BSh"
    assert registry.get_meteorological_regime("srinagar") == "Himalayan Mountain & Valley"

    with pytest.raises(KeyError):
        registry.get_climate_zone("nonexistent_loc_xyz")


# ---------------------------------------------------------------------------
# Test 3: Multi-Cycle Forecast Identity Preservation (00Z, 06Z, 12Z, 18Z)
# ---------------------------------------------------------------------------
def test_3_multi_cycle_forecast_identity():
    """
    Ensures that different NWP initialization cycles predicting the SAME valid_time
    maintain distinct issue_time_utc, lead_hours, and cycle labels.
    """
    target_valid = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)
    cycles = ["00", "06", "12", "18"]
    records = []

    for i, c_str in enumerate(cycles):
        issue_t = datetime(2026, 8, 24, int(c_str), 0, 0, tzinfo=timezone.utc)
        lead_h = int((target_valid - issue_t).total_seconds() / 3600)
        records.append({
            "location_id": "delhi",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "spatial_distance_km": 13.2,
            "issue_time_utc": issue_t,
            "valid_time_utc": target_valid,
            "lead_hours": lead_h,
            "lead_days": lead_h // 24,
            "cycle": f"{c_str}z",
            "variable": "temperature_2m",
            "forecast_value": 31.0 + i * 0.5,
            "forecast_unit": "degC",
            "forecast_source": "NOAA_GEFS",
            "ensemble_mean": 31.2 + i * 0.4,
            "ensemble_std": 1.1,
            "ensemble_min": 29.0,
            "ensemble_max": 33.5,
            "q10": 30.0,
            "q90": 32.5,
            "member_count": 31,
            "has_full_ensemble": True,
            "truth_value": 30.8,
            "truth_unit": "degC",
            "truth_source": "ERA5_REANALYSIS",
            "forecast_error": (31.0 + i * 0.5) - 30.8,
            "forecast_abs_error": abs((31.0 + i * 0.5) - 30.8),
            "ensemble_mean_error": (31.2 + i * 0.4) - 30.8,
            "ensemble_mean_abs_error": abs((31.2 + i * 0.4) - 30.8),
        })

    df = pd.DataFrame(records)
    builder = MultiClimateDatasetBuilder()
    standardized = builder.standardize_paired_slice(df)

    assert len(standardized) == 4
    assert list(standardized["cycle"]) == ["00z", "06z", "12z", "18z"]
    assert list(standardized["lead_hours"]) == [24, 18, 12, 6]
    assert standardized["valid_time_utc"].nunique() == 1  # Same target valid time
    assert standardized["issue_time_utc"].nunique() == 4  # 4 distinct initialization times


# ---------------------------------------------------------------------------
# Test 4: Canonical Historical Dataset Schema Completeness
# ---------------------------------------------------------------------------
def test_4_canonical_historical_schema_completeness():
    builder = MultiClimateDatasetBuilder()
    t_issue = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_valid = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)

    raw_slice = pd.DataFrame([{
        "location": "mumbai",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "spatial_distance_km": 8.5,
        "issue_time": t_issue,
        "valid_time": t_valid,
        "lead_hours": 12,
        "variable": "surface_pressure",
        "forecast_value": 1008.2,
        "forecast_unit": "hPa",
        "forecast_source": "NOAA_GEFS",
        "ensemble_mean": 1008.0,
        "ensemble_std": 0.6,
        "ensemble_min": 1006.5,
        "ensemble_max": 1009.5,
        "q10": 1007.2,
        "q90": 1008.8,
        "member_count": 31,
        "truth_value": 1007.9,
        "truth_unit": "hPa",
        "truth_source": "ERA5_REANALYSIS",
        "forecast_error": 0.3,
        "forecast_abs_error": 0.3,
        "ensemble_mean_error": 0.1,
        "ensemble_mean_abs_error": 0.1,
    }])

    canonical_df = builder.standardize_paired_slice(raw_slice)
    assert list(canonical_df.columns) == CANONICAL_HISTORICAL_COLUMNS

    row = canonical_df.iloc[0]
    assert row["location_id"] == "mumbai"
    assert row["region"] == "Maharashtra"
    assert row["climate_zone"] == "Am/Aw"
    assert row["meteorological_regime"] == "Tropical Coastal / Maritime"
    assert row["elevation_m"] == 14.0
    assert row["cycle"] == "00z"
    assert row["lead_days"] == 0
    assert row["has_full_ensemble"] == True


# ---------------------------------------------------------------------------
# Test 5: Forecast vs Truth Temporal Alignment & Signed Error Math
# ---------------------------------------------------------------------------
def test_5_forecast_truth_alignment_and_error_math():
    aligner = HistoricalAlignmentEngine()

    t1 = datetime(2026, 8, 20, 6, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)

    forecast_df = pd.DataFrame([
        {
            "location": "kolkata", "latitude": 22.57, "longitude": 88.36,
            "issue_time": datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc),
            "valid_time": t1, "lead_hours": 6, "variable": "temperature_2m",
            "value": 28.5, "unit": "degC", "source": "NOAA_GEFS",
            "ensemble_mean": 28.0, "ensemble_std": 1.0, "ensemble_min": 26.0,
            "ensemble_max": 30.0, "q10": 27.0, "q90": 29.0, "member_count": 31,
        },
        {
            "location": "kolkata", "latitude": 22.57, "longitude": 88.36,
            "issue_time": datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc),
            "valid_time": t2, "lead_hours": 12, "variable": "temperature_2m",
            "value": 33.0, "unit": "degC", "source": "NOAA_GEFS",
            "ensemble_mean": 32.5, "ensemble_std": 1.2, "ensemble_min": 30.0,
            "ensemble_max": 35.0, "q10": 31.0, "q90": 34.0, "member_count": 31,
        },
    ])

    truth_df = pd.DataFrame([
        {
            "location": "kolkata", "latitude": 22.57, "longitude": 88.36,
            "valid_time": t1, "variable": "temperature_2m",
            "truth_value": 27.0, "truth_unit": "degC", "truth_source": "ERA5_REANALYSIS",
        },
        {
            "location": "kolkata", "latitude": 22.57, "longitude": 88.36,
            "valid_time": t2, "variable": "temperature_2m",
            "truth_value": 35.0, "truth_unit": "degC", "truth_source": "ERA5_REANALYSIS",
        },
    ])

    paired_df, report = aligner.align(forecast_df, truth_df)

    assert len(paired_df) == 2
    # Row 0: Overprediction (28.5 - 27.0 = +1.5)
    assert paired_df.iloc[0]["forecast_error"] == 1.5
    assert paired_df.iloc[0]["forecast_abs_error"] == 1.5
    assert paired_df.iloc[0]["ensemble_mean_error"] == 1.0

    # Row 1: Underprediction (33.0 - 35.0 = -2.0)
    assert paired_df.iloc[1]["forecast_error"] == -2.0
    assert paired_df.iloc[1]["forecast_abs_error"] == 2.0
    assert paired_df.iloc[1]["ensemble_mean_error"] == -2.5


# ---------------------------------------------------------------------------
# Test 6: Spatial Mismatch Distance Calculation & Limit Enforcement
# ---------------------------------------------------------------------------
def test_6_spatial_mismatch_validation():
    builder = MultiClimateDatasetBuilder(max_spatial_distance_km=50.0)

    # Valid distance (~13.2 km)
    t_issue = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_valid = datetime(2026, 8, 20, 6, 0, 0, tzinfo=timezone.utc)

    valid_slice = pd.DataFrame([{
        "location_id": "delhi", "region": "NCR", "climate_zone": "Cwa/BSh",
        "meteorological_regime": "Continental", "elevation_m": 214.0,
        "latitude": 28.6139, "longitude": 77.2090, "spatial_distance_km": 13.2,
        "issue_time_utc": t_issue, "valid_time_utc": t_valid, "lead_hours": 6, "lead_days": 0,
        "cycle": "00z", "variable": "temperature_2m", "forecast_value": 30.0,
        "forecast_unit": "degC", "forecast_source": "NOAA_GEFS", "ensemble_mean": 30.0,
        "ensemble_std": 1.0, "ensemble_min": 28.0, "ensemble_max": 32.0,
        "q10": 29.0, "q90": 31.0, "member_count": 31, "has_full_ensemble": True,
        "truth_value": 29.5, "truth_unit": "degC", "truth_source": "ERA5",
        "forecast_error": 0.5, "forecast_abs_error": 0.5, "ensemble_mean_error": 0.5, "ensemble_mean_abs_error": 0.5,
    }])

    rep = builder.validate_dataset(valid_slice, strict=True)
    assert rep["is_valid"] is True

    # Excessive distance (65 km > 50 km)
    excessive_slice = valid_slice.copy()
    excessive_slice["spatial_distance_km"] = 65.0

    with pytest.raises(ValueError) as exc_info:
        builder.validate_dataset(excessive_slice, strict=True)
    assert "Spatial mismatch" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 7: Missing Member Detection & has_full_ensemble Tagging
# ---------------------------------------------------------------------------
def test_7_missing_ensemble_member_handling():
    builder = MultiClimateDatasetBuilder()
    t_issue = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_valid = datetime(2026, 8, 20, 6, 0, 0, tzinfo=timezone.utc)

    # 1. Full 31 members
    full_df = pd.DataFrame([{
        "location": "bengaluru", "latitude": 12.97, "longitude": 77.59, "spatial_distance_km": 5.0,
        "issue_time": t_issue, "valid_time": t_valid, "lead_hours": 6, "variable": "wind_speed_10m",
        "forecast_value": 15.0, "forecast_unit": "km/h", "forecast_source": "NOAA_GEFS",
        "ensemble_mean": 14.8, "ensemble_std": 2.0, "ensemble_min": 10.0, "ensemble_max": 20.0,
        "q10": 12.0, "q90": 18.0, "member_count": 31,
        "truth_value": 14.5, "truth_unit": "km/h", "truth_source": "ERA5",
        "forecast_error": 0.5, "forecast_abs_error": 0.5, "ensemble_mean_error": 0.3, "ensemble_mean_abs_error": 0.3,
    }])
    res_full = builder.standardize_paired_slice(full_df)
    assert res_full.iloc[0]["has_full_ensemble"] == True

    # 2. Degraded ensemble (only 20 members)
    degraded_df = full_df.copy()
    degraded_df["member_count"] = 20
    res_deg = builder.standardize_paired_slice(degraded_df)
    assert res_deg.iloc[0]["has_full_ensemble"] == False


# ---------------------------------------------------------------------------
# Test 8: Duplicate Record Detection on (location_id, variable, issue_time, valid_time)
# ---------------------------------------------------------------------------
def test_8_duplicate_record_detection():
    builder = MultiClimateDatasetBuilder()
    t_issue = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_valid = datetime(2026, 8, 20, 6, 0, 0, tzinfo=timezone.utc)

    row = {
        "location_id": "chennai", "region": "Tamil Nadu", "climate_zone": "As/Aw",
        "meteorological_regime": "Tropical Maritime", "elevation_m": 7.0,
        "latitude": 13.08, "longitude": 80.27, "spatial_distance_km": 4.2,
        "issue_time_utc": t_issue, "valid_time_utc": t_valid, "lead_hours": 6, "lead_days": 0,
        "cycle": "00z", "variable": "temperature_2m", "forecast_value": 32.0,
        "forecast_unit": "degC", "forecast_source": "NOAA_GEFS", "ensemble_mean": 32.0,
        "ensemble_std": 0.8, "ensemble_min": 30.0, "ensemble_max": 34.0,
        "q10": 31.0, "q90": 33.0, "member_count": 31, "has_full_ensemble": True,
        "truth_value": 31.5, "truth_unit": "degC", "truth_source": "ERA5",
        "forecast_error": 0.5, "forecast_abs_error": 0.5, "ensemble_mean_error": 0.5, "ensemble_mean_abs_error": 0.5,
    }

    # Dataset with intentional duplicates
    dup_df = pd.DataFrame([row, row])
    with pytest.raises(ValueError) as exc_info:
        builder.validate_dataset(dup_df, strict=True)
    assert "Duplicate forecast keys detected" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 9: Physical QC Bounds Enforcement
# ---------------------------------------------------------------------------
def test_9_physical_qc_bounds_validation():
    builder = MultiClimateDatasetBuilder()
    t_issue = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_valid = datetime(2026, 8, 20, 6, 0, 0, tzinfo=timezone.utc)

    # Impossible temperature (120 degC)
    unphysical_row = {
        "location_id": "jaipur", "region": "Rajasthan", "climate_zone": "BSh/BWh",
        "meteorological_regime": "Semi-Arid", "elevation_m": 431.0,
        "latitude": 26.91, "longitude": 75.78, "spatial_distance_km": 6.0,
        "issue_time_utc": t_issue, "valid_time_utc": t_valid, "lead_hours": 6, "lead_days": 0,
        "cycle": "00z", "variable": "temperature_2m", "forecast_value": 120.0,  # Physically impossible
        "forecast_unit": "degC", "forecast_source": "NOAA_GEFS", "ensemble_mean": 120.0,
        "ensemble_std": 1.0, "ensemble_min": 118.0, "ensemble_max": 122.0,
        "q10": 119.0, "q90": 121.0, "member_count": 31, "has_full_ensemble": True,
        "truth_value": 35.0, "truth_unit": "degC", "truth_source": "ERA5",
        "forecast_error": 85.0, "forecast_abs_error": 85.0, "ensemble_mean_error": 85.0, "ensemble_mean_abs_error": 85.0,
    }

    bad_df = pd.DataFrame([unphysical_row])
    with pytest.raises(ValueError) as exc_info:
        builder.validate_dataset(bad_df, strict=True)
    assert "Physical bounds violation" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 10: Anti-Leakage Audit on Canonical Columns
# ---------------------------------------------------------------------------
def test_10_anti_leakage_safety_audit():
    """
    Verifies that CANONICAL_FEATURE_COLUMNS passes the LeakageAuditor,
    while CANONICAL_TARGET_COLUMNS triggers DataLeakageError if leaked into features.
    """
    auditor = LeakageAuditor()

    # 1. Feature columns are safe
    feat_violations = auditor.audit_feature_names(CANONICAL_FEATURE_COLUMNS)
    assert len(feat_violations) == 0, f"Expected 0 violations in features, got: {feat_violations}"

    # 2. Target columns MUST trigger leakage violations
    target_violations = auditor.audit_feature_names(CANONICAL_TARGET_COLUMNS)
    assert len(target_violations) > 0, "Target columns must be flagged as forbidden in feature sets"
    assert any("truth" in v for v in target_violations)
    assert any("error" in v for v in target_violations)


# ---------------------------------------------------------------------------
# Test 11: Reproducibility, Manifest Generation & SHA-256 Hashing
# ---------------------------------------------------------------------------
def test_11_reproducible_manifest_and_sha256(tmp_path):
    builder = MultiClimateDatasetBuilder(historical_dir=str(tmp_path))
    t_issue = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_valid = datetime(2026, 8, 20, 6, 0, 0, tzinfo=timezone.utc)

    sample_slice = pd.DataFrame([{
        "location": "guwahati", "latitude": 26.14, "longitude": 91.73, "spatial_distance_km": 7.0,
        "issue_time": t_issue, "valid_time": t_valid, "lead_hours": 6, "variable": "temperature_2m",
        "value": 29.0, "unit": "degC", "source": "NOAA_GEFS",
        "ensemble_mean": 28.8, "ensemble_std": 1.0, "ensemble_min": 27.0, "ensemble_max": 31.0,
        "q10": 28.0, "q90": 30.0, "member_count": 31,
        "truth_value": 28.5, "truth_unit": "degC", "truth_source": "ERA5_REANALYSIS",
    }])

    aligner = HistoricalAlignmentEngine()
    truth_df = pd.DataFrame([{
        "location": "guwahati", "latitude": 26.14, "longitude": 91.73,
        "valid_time": t_valid, "variable": "temperature_2m",
        "truth_value": 28.5, "truth_unit": "degC", "truth_source": "ERA5_REANALYSIS",
    }])
    paired_df, _ = aligner.align(sample_slice, truth_df)

    canonical_df, report = builder.build_canonical_dataset([paired_df])
    parquet_p, csv_p, manifest_p = builder.save_canonical_dataset(
        canonical_df, report, dest_dir=str(tmp_path / "canonical")
    )

    assert parquet_p.exists()
    assert csv_p.exists()
    assert manifest_p.exists()

    import json
    with open(manifest_p, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["schema_version"] == "2.0.0-multi-climate"
    assert "parquet_sha256" in manifest
    assert len(manifest["parquet_sha256"]) == 64  # Valid SHA-256 string
    assert manifest["total_records"] == 1
    assert "location_breakdown" in manifest["validation_report"]
    assert "guwahati" in manifest["validation_report"]["location_breakdown"]


# ---------------------------------------------------------------------------
# Test 12: Multi-Station Multi-Climate Canonical Assembly & Stratification
# ---------------------------------------------------------------------------
def test_12_multi_station_canonical_assembly_and_stratification():
    """
    Assembles a synthetic multi-station canonical dataset across 4 distinct climate regimes
    (Delhi: Cwa/BSh, Mumbai: Am/Aw, Srinagar: Cfb/Dfb, Bengaluru: Aw)
    and verifies evaluation stratification readiness.
    """
    builder = MultiClimateDatasetBuilder()
    stations = ["delhi", "mumbai", "srinagar", "bengaluru"]
    slices = []

    t_issue = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_valid = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)

    for loc in stations:
        slices.append(pd.DataFrame([{
            "location": loc, "latitude": 20.0, "longitude": 75.0, "spatial_distance_km": 10.0,
            "issue_time": t_issue, "valid_time": t_valid, "lead_hours": 12, "variable": "temperature_2m",
            "forecast_value": 25.0, "forecast_unit": "degC", "forecast_source": "NOAA_GEFS",
            "ensemble_mean": 25.0, "ensemble_std": 1.0, "ensemble_min": 23.0, "ensemble_max": 27.0,
            "q10": 24.0, "q90": 26.0, "member_count": 31,
            "truth_value": 24.5, "truth_unit": "degC", "truth_source": "ERA5",
            "forecast_error": 0.5, "forecast_abs_error": 0.5,
            "ensemble_mean_error": 0.5, "ensemble_mean_abs_error": 0.5,
        }]))

    combined_df, report = builder.build_canonical_dataset(slices)

    assert len(combined_df) == 4
    assert set(combined_df["location_id"]) == {"delhi", "mumbai", "srinagar", "bengaluru"}
    assert set(combined_df["climate_zone"]) == {"Cwa/BSh", "Am/Aw", "Cfb/Dfb", "Aw"}
    assert report["distinct_locations"] == 4
    assert report["distinct_cycles"] == 1
    assert report["is_valid"] is True

    # Check stratification ability
    by_climate = combined_df.groupby("climate_zone")["forecast_abs_error"].mean()
    assert len(by_climate) == 4
