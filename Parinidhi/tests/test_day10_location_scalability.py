"""
Day 10 Location-Scalable Historical Data Engine Test Suite.

Verifies:
1. Multi-location processing through the exact same historical pipeline (Delhi, Mumbai, Srinagar, Pune).
2. Multi-climate regime representation and stratification metadata preservation.
3. Runtime-configured arbitrary/new location processing without source code changes.
4. Multi-cycle identity preservation across 00Z, 06Z, 12Z, 18Z cycles.
5. Canonical schema completeness (CANONICAL_HISTORICAL_COLUMNS).
6. Duplicate forecast record detection on (location_id, variable, issue_time, valid_time).
7. Temporal consistency enforcement (valid_time >= issue_time, lead_hours >= 0).
8. Spatial mismatch distance validation (>50 km limit).
9. Physical QC bounds validation (temperature, pressure, wind).
10. Strict issue-time leakage boundary enforcement.
11. Provenance manifests with SHA-256 hashes and multi-location breakdowns.
12. Full preservation of the existing 20-location registry.
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
from features.leakage_audit import DataLeakageError, LeakageAuditor
# ---------------------------------------------------------------------------
# Test A & B: Multi-Location & Multi-Climate Historical Processing
# ---------------------------------------------------------------------------
def test_a_b_multi_location_and_multi_climate_processing():
    """
    Verifies that multiple existing benchmark and non-benchmark locations
    (Delhi, Mumbai, Srinagar, and Pune) are processed through the exact same
    historical pipeline, preserving distinct climate regimes.
    """
    registry = LocationRegistry()
    builder = MultiClimateDatasetBuilder(location_registry=registry)
    test_locations = ["delhi", "mumbai", "srinagar", "pune"]
    t_issue = datetime(2026, 8, 22, 0, 0, 0, tzinfo=timezone.utc)
    t_valid = datetime(2026, 8, 22, 12, 0, 0, tzinfo=timezone.utc)
    slices = []
    for loc_id in test_locations:
        info = registry.get_location(loc_id)
        slices.append(pd.DataFrame([{
            "location": loc_id,
            "latitude": info.requested_coordinates.latitude,
            "longitude": info.requested_coordinates.longitude,
            "spatial_distance_km": 12.0,
            "issue_time": t_issue,
            "valid_time": t_valid,
            "lead_hours": 12,
            "variable": "temperature_2m",
            "forecast_value": 28.0,
            "forecast_unit": "degC",
            "forecast_source": "NOAA_GEFS",
            "ensemble_mean": 27.8,
            "ensemble_std": 1.1,
            "ensemble_min": 25.5,
            "ensemble_max": 30.2,
            "q10": 26.5,
            "q90": 29.1,
            "member_count": 31,
            "truth_value": 27.5,
            "truth_unit": "degC",
            "truth_source": "ERA5_REANALYSIS",
            "forecast_error": 0.5,
            "forecast_abs_error": 0.5,
            "ensemble_mean_error": 0.3,
            "ensemble_mean_abs_error": 0.3,
        }]))
    canonical_df, report = builder.build_canonical_dataset(slices)
    assert len(canonical_df) == 4
    assert set(canonical_df["location_id"]) == {"delhi", "mumbai", "srinagar", "pune"}
    assert report["distinct_locations"] == 4
    assert report["is_valid"] is True
    # Verify climate regimes are accurately attached
    delhi_row = canonical_df[canonical_df["location_id"] == "delhi"].iloc[0]
    assert delhi_row["climate_zone"] == "Cwa/BSh"
    assert delhi_row["elevation_m"] == 214.0
    mumbai_row = canonical_df[canonical_df["location_id"] == "mumbai"].iloc[0]
    assert mumbai_row["climate_zone"] == "Am/Aw"
    assert mumbai_row["elevation_m"] == 14.0
    srinagar_row = canonical_df[canonical_df["location_id"] == "srinagar"].iloc[0]
    assert srinagar_row["climate_zone"] == "Cfb/Dfb"
    assert srinagar_row["elevation_m"] == 1585.0
    pune_row = canonical_df[canonical_df["location_id"] == "pune"].iloc[0]
    assert pune_row["climate_zone"] == "BSh/Aw"
    assert pune_row["elevation_m"] == 560.0
# ---------------------------------------------------------------------------
# Test C: Runtime-Configured New Location (Arbitrary Coordinates)
# ---------------------------------------------------------------------------
def test_c_runtime_configured_new_location_extensibility():
    """
    Demonstrates that a completely new location (e.g. 'shimla' or 'leh') can be
    introduced at runtime through configuration without modifying production code.
    """
    registry = LocationRegistry()
    # Verify 'shimla' does not exist initially
    assert registry.has_location("shimla") is False
    # 1. Register 'shimla' dynamically at runtime
    shimla_info = registry.register_location(
        location_id="shimla",
        requested_latitude=31.1048,
        requested_longitude=77.1734,
        country="India",
        state_region="Himachal Pradesh",
        city="Shimla",
        climate_zone="Cwb",
        meteorological_regime="Subtropical Highland / Alpine Valley",
        elevation_m=2276.0,
        is_benchmark=False,
        rationale="High-altitude Himalayan hill station with complex orographic and snow dynamics.",
    )
    assert registry.has_location("shimla") is True
    assert shimla_info.elevation_m == 2276.0
    assert shimla_info.climate_zone == "Cwb"
    # 2. Process a historical slice for 'shimla' through the pipeline
    builder = MultiClimateDatasetBuilder(location_registry=registry)
    t_issue = datetime(2026, 8, 22, 0, 0, 0, tzinfo=timezone.utc)
    t_valid = datetime(2026, 8, 22, 6, 0, 0, tzinfo=timezone.utc)
    shimla_slice = pd.DataFrame([{
        "location": "shimla",
        "latitude": 31.1048,
        "longitude": 77.1734,
        "spatial_distance_km": 14.5,
        "issue_time": t_issue,
        "valid_time": t_valid,
        "lead_hours": 6,
        "variable": "temperature_2m",
        "forecast_value": 18.0,
        "forecast_unit": "degC",
        "forecast_source": "NOAA_GEFS",
        "ensemble_mean": 17.5,
        "ensemble_std": 0.9,
        "ensemble_min": 16.0,
        "ensemble_max": 19.5,
        "q10": 16.8,
        "q90": 18.4,
        "member_count": 31,
        "truth_value": 17.2,
        "truth_unit": "degC",
        "truth_source": "ERA5_REANALYSIS",
        "forecast_error": 0.8,
        "forecast_abs_error": 0.8,
        "ensemble_mean_error": 0.3,
        "ensemble_mean_abs_error": 0.3,
    }])
    canonical_df = builder.standardize_paired_slice(shimla_slice)
    assert len(canonical_df) == 1
    row = canonical_df.iloc[0]
    assert row["location_id"] == "shimla"
    assert row["region"] == "Himachal Pradesh"
    assert row["climate_zone"] == "Cwb"
    assert row["elevation_m"] == 2276.0
    assert row["has_full_ensemble"] == True
# ---------------------------------------------------------------------------
# Test D: Multi-Cycle Forecast Identity Preservation (00Z, 06Z, 12Z, 18Z)
# ---------------------------------------------------------------------------
def test_d_multi_cycle_forecast_identity():
    """
    Verifies that all 4 NWP cycles predicting overlapping valid times
    preserve their individual initialization timestamps and lead hours.
    """
    builder = MultiClimateDatasetBuilder()
    target_time = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)
    cycle_offsets = [("00", 36), ("06", 30), ("12", 24), ("18", 18)]
    slices = []
    for c_str, lead_h in cycle_offsets:
        issue_t = target_time - timedelta(hours=lead_h)
        slices.append(pd.DataFrame([{
            "location_id": "jaipur",
            "latitude": 26.9124,
            "longitude": 75.7873,
            "spatial_distance_km": 10.0,
            "issue_time_utc": issue_t,
            "valid_time_utc": target_time,
            "lead_hours": lead_h,
            "lead_days": lead_h // 24,
            "cycle": f"{c_str}z",
            "variable": "surface_pressure",
            "forecast_value": 965.0 + float(c_str),
            "forecast_unit": "hPa",
            "forecast_source": "NOAA_GEFS",
            "ensemble_mean": 965.2 + float(c_str),
            "ensemble_std": 0.8,
            "ensemble_min": 963.0,
            "ensemble_max": 967.0,
            "q10": 964.0,
            "q90": 966.0,
            "member_count": 31,
            "has_full_ensemble": True,
            "truth_value": 964.8,
            "truth_unit": "hPa",
            "truth_source": "ERA5_REANALYSIS",
            "forecast_error": 0.2 + float(c_str),
            "forecast_abs_error": abs(0.2 + float(c_str)),
            "ensemble_mean_error": 0.4 + float(c_str),
            "ensemble_mean_abs_error": abs(0.4 + float(c_str)),
        }]))
    canonical_df, report = builder.build_canonical_dataset(slices)
    assert len(canonical_df) == 4
    assert set(canonical_df["cycle"]) == {"00z", "06z", "12z", "18z"}
    assert list(canonical_df["lead_hours"].sort_values(ascending=False)) == [36, 30, 24, 18]
    assert canonical_df["valid_time_utc"].nunique() == 1
# ---------------------------------------------------------------------------
# Test E: Canonical Schema Completeness
# ---------------------------------------------------------------------------
def test_e_canonical_schema_preservation():
    builder = MultiClimateDatasetBuilder()
    t_issue = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_valid = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
    raw_slice = pd.DataFrame([{
        "location": "chennai",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "spatial_distance_km": 7.2,
        "issue_time": t_issue,
        "valid_time": t_valid,
        "lead_hours": 12,
        "variable": "wind_speed_10m",
        "forecast_value": 22.5,
        "forecast_unit": "km/h",
        "forecast_source": "NOAA_GEFS",
        "ensemble_mean": 22.0,
        "ensemble_std": 1.5,
        "ensemble_min": 19.0,
        "ensemble_max": 25.0,
        "q10": 20.5,
        "q90": 23.8,
        "member_count": 31,
        "truth_value": 21.0,
        "truth_unit": "km/h",
        "truth_source": "ERA5_REANALYSIS",
        "forecast_error": 1.5,
        "forecast_abs_error": 1.5,
        "ensemble_mean_error": 1.0,
        "ensemble_mean_abs_error": 1.0,
    }])
    canonical_df = builder.standardize_paired_slice(raw_slice)
    assert list(canonical_df.columns) == CANONICAL_HISTORICAL_COLUMNS
# ---------------------------------------------------------------------------
# Test F: Duplicate Record Detection
# ---------------------------------------------------------------------------
def test_f_duplicate_record_detection():
    builder = MultiClimateDatasetBuilder()
    t_issue = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_valid = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
    row = {
        "location_id": "kolkata", "region": "West Bengal", "climate_zone": "Aw/Cwa",
        "meteorological_regime": "Tropical Deltaic", "elevation_m": 9.0,
        "latitude": 22.57, "longitude": 88.36, "spatial_distance_km": 8.0,
        "issue_time_utc": t_issue, "valid_time_utc": t_valid, "lead_hours": 12, "lead_days": 0,
        "cycle": "00z", "variable": "temperature_2m", "forecast_value": 31.0,
        "forecast_unit": "degC", "forecast_source": "NOAA_GEFS", "ensemble_mean": 31.0,
        "ensemble_std": 1.0, "ensemble_min": 29.0, "ensemble_max": 33.0,
        "q10": 30.0, "q90": 32.0, "member_count": 31, "has_full_ensemble": True,
        "truth_value": 30.5, "truth_unit": "degC", "truth_source": "ERA5",
        "forecast_error": 0.5, "forecast_abs_error": 0.5, "ensemble_mean_error": 0.5, "ensemble_mean_abs_error": 0.5,
    }
    dup_df = pd.DataFrame([row, row])
    with pytest.raises(ValueError) as exc_info:
        builder.validate_dataset(dup_df, strict=True)
    assert "Duplicate forecast keys detected" in str(exc_info.value)
# ---------------------------------------------------------------------------
# Test G: Temporal Consistency (valid_time >= issue_time, lead_hours >= 0)
# ---------------------------------------------------------------------------
def test_g_temporal_consistency():
    builder = MultiClimateDatasetBuilder()
    t_issue = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
    t_invalid_valid = datetime(2026, 8, 20, 6, 0, 0, tzinfo=timezone.utc)  # Inverted
    inverted_row = {
        "location_id": "guwahati", "region": "Assam", "climate_zone": "Cwa",
        "meteorological_regime": "Subtropical Valley", "elevation_m": 55.0,
        "latitude": 26.14, "longitude": 91.73, "spatial_distance_km": 6.0,
        "issue_time_utc": t_issue, "valid_time_utc": t_invalid_valid, "lead_hours": -6, "lead_days": 0,
        "cycle": "12z", "variable": "temperature_2m", "forecast_value": 28.0,
        "forecast_unit": "degC", "forecast_source": "NOAA_GEFS", "ensemble_mean": 28.0,
        "ensemble_std": 1.0, "ensemble_min": 26.0, "ensemble_max": 30.0,
        "q10": 27.0, "q90": 29.0, "member_count": 31, "has_full_ensemble": True,
        "truth_value": 28.0, "truth_unit": "degC", "truth_source": "ERA5",
        "forecast_error": 0.0, "forecast_abs_error": 0.0, "ensemble_mean_error": 0.0, "ensemble_mean_abs_error": 0.0,
    }
    bad_df = pd.DataFrame([inverted_row])
    with pytest.raises(ValueError) as exc_info:
        builder.validate_dataset(bad_df, strict=True)
    assert "Temporal violation" in str(exc_info.value)
# ---------------------------------------------------------------------------
# Test H: Spatial Mismatch Distance Validation
# ---------------------------------------------------------------------------
def test_h_spatial_mismatch_threshold():
    builder = MultiClimateDatasetBuilder(max_spatial_distance_km=50.0)
    t_issue = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_valid = datetime(2026, 8, 20, 6, 0, 0, tzinfo=timezone.utc)
    excess_row = {
        "location_id": "bengaluru", "region": "Karnataka", "climate_zone": "Aw",
        "meteorological_regime": "Elevated Plateau", "elevation_m": 920.0,
        "latitude": 12.97, "longitude": 77.59, "spatial_distance_km": 78.5,  # Exceeds 50km
        "issue_time_utc": t_issue, "valid_time_utc": t_valid, "lead_hours": 6, "lead_days": 0,
        "cycle": "00z", "variable": "temperature_2m", "forecast_value": 24.0,
        "forecast_unit": "degC", "forecast_source": "NOAA_GEFS", "ensemble_mean": 24.0,
        "ensemble_std": 1.0, "ensemble_min": 22.0, "ensemble_max": 26.0,
        "q10": 23.0, "q90": 25.0, "member_count": 31, "has_full_ensemble": True,
        "truth_value": 23.5, "truth_unit": "degC", "truth_source": "ERA5",
        "forecast_error": 0.5, "forecast_abs_error": 0.5, "ensemble_mean_error": 0.5, "ensemble_mean_abs_error": 0.5,
    }
    bad_df = pd.DataFrame([excess_row])
    with pytest.raises(ValueError) as exc_info:
        builder.validate_dataset(bad_df, strict=True)
    assert "Spatial mismatch" in str(exc_info.value)
# ---------------------------------------------------------------------------
# Test I: Physical QC Bounds Validation
# ---------------------------------------------------------------------------
def test_i_physical_qc_bounds():
    builder = MultiClimateDatasetBuilder()
    t_issue = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_valid = datetime(2026, 8, 20, 6, 0, 0, tzinfo=timezone.utc)
    # Impossible wind speed (450 km/h)
    unphysical_wind = {
        "location_id": "mumbai", "region": "Maharashtra", "climate_zone": "Am/Aw",
        "meteorological_regime": "Tropical Coastal", "elevation_m": 14.0,
        "latitude": 19.07, "longitude": 72.87, "spatial_distance_km": 10.0,
        "issue_time_utc": t_issue, "valid_time_utc": t_valid, "lead_hours": 6, "lead_days": 0,
        "cycle": "00z", "variable": "wind_speed_10m", "forecast_value": 450.0,
        "forecast_unit": "km/h", "forecast_source": "NOAA_GEFS", "ensemble_mean": 450.0,
        "ensemble_std": 10.0, "ensemble_min": 430.0, "ensemble_max": 470.0,
        "q10": 440.0, "q90": 460.0, "member_count": 31, "has_full_ensemble": True,
        "truth_value": 20.0, "truth_unit": "km/h", "truth_source": "ERA5",
        "forecast_error": 430.0, "forecast_abs_error": 430.0, "ensemble_mean_error": 430.0, "ensemble_mean_abs_error": 430.0,
    }
    bad_df = pd.DataFrame([unphysical_wind])
    with pytest.raises(ValueError) as exc_info:
        builder.validate_dataset(bad_df, strict=True)
    assert "Physical bounds violation" in str(exc_info.value)
# ---------------------------------------------------------------------------
# Test J: Strict Issue-Time Anti-Leakage Boundary
# ---------------------------------------------------------------------------
def test_j_issue_time_anti_leakage_boundary():
    auditor = LeakageAuditor()
    # Features must pass cleanly
    feat_violations = auditor.audit_feature_names(CANONICAL_FEATURE_COLUMNS)
    assert len(feat_violations) == 0
    # Target/Verification fields must fail loudly if passed as features
    target_violations = auditor.audit_feature_names(CANONICAL_TARGET_COLUMNS)
    assert len(target_violations) > 0
    assert any("truth" in v for v in target_violations)
# ---------------------------------------------------------------------------
# Test K: Provenance Manifest & SHA-256 Reproducibility
# ---------------------------------------------------------------------------
def test_k_provenance_and_sha256(tmp_path):
    builder = MultiClimateDatasetBuilder(historical_dir=str(tmp_path))
    t_issue = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_valid = datetime(2026, 8, 20, 6, 0, 0, tzinfo=timezone.utc)
    sample_df = pd.DataFrame([{
        "location": "nagpur", "latitude": 21.14, "longitude": 79.08, "spatial_distance_km": 11.2,
        "issue_time": t_issue, "valid_time": t_valid, "lead_hours": 6, "variable": "temperature_2m",
        "forecast_value": 30.5, "forecast_unit": "degC", "forecast_source": "NOAA_GEFS",
        "ensemble_mean": 30.2, "ensemble_std": 1.0, "ensemble_min": 28.0, "ensemble_max": 32.0,
        "q10": 29.0, "q90": 31.0, "member_count": 31,
        "truth_value": 29.8, "truth_unit": "degC", "truth_source": "ERA5_REANALYSIS",
        "forecast_error": 0.7, "forecast_abs_error": 0.7,
        "ensemble_mean_error": 0.4, "ensemble_mean_abs_error": 0.4,
    }])
    canonical_df, report = builder.build_canonical_dataset([sample_df])
    parquet_p, csv_p, manifest_p = builder.save_canonical_dataset(
        canonical_df, report, dest_dir=str(tmp_path / "canonical")
    )
    assert parquet_p.exists()
    assert manifest_p.exists()
    import json
    with open(manifest_p, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["schema_version"] == "2.0.0-multi-climate"
    assert "parquet_sha256" in manifest
    assert len(manifest["parquet_sha256"]) == 64
    assert manifest["total_records"] == 1
# ---------------------------------------------------------------------------
# Test L: Preservation of 20-Location Registry
# ---------------------------------------------------------------------------
def test_l_all_20_registered_locations_intact():
    registry = LocationRegistry()
    locations = registry.list_locations()
    assert len(locations) == 20
    expected_20 = [
        "delhi", "srinagar", "chandigarh", "jaipur", "lucknow",
        "mumbai", "pune", "ahmedabad", "goa",
        "bhopal", "nagpur", "raipur",
        "kolkata", "bhubaneswar", "ranchi", "guwahati",
        "bengaluru", "chennai", "hyderabad", "kochi",
    ]
    loc_ids = [l["location_id"] for l in locations]
    for exp_id in expected_20:
        assert exp_id in loc_ids
        assert registry.has_location(exp_id) is True
# ---------------------------------------------------------------------------
# Test M: Location ID Validation (Empty & Whitespace-Only Rejection)
# ---------------------------------------------------------------------------
def test_m_location_id_validation():
    registry = LocationRegistry()
    # Empty string
    with pytest.raises(ValueError) as exc:
        registry.register_location(location_id="", requested_latitude=20.0, requested_longitude=75.0)
    assert "non-empty string" in str(exc.value)
    # Whitespace-only string
    with pytest.raises(ValueError) as exc:
        registry.register_location(location_id="   ", requested_latitude=20.0, requested_longitude=75.0)
    assert "non-empty string" in str(exc.value)
    with pytest.raises(ValueError) as exc:
        registry.resolve_location(location_id_or_name="", latitude=20.0, longitude=75.0)
    assert "non-empty string" in str(exc.value)
# ---------------------------------------------------------------------------
# Test N: Coordinate Range & Non-Finite Checks (NaN / Inf / Out-of-Bounds)
# ---------------------------------------------------------------------------
def test_n_coordinate_range_and_finite_checks():
    registry = LocationRegistry()
    # Latitude out of bounds
    with pytest.raises(ValueError) as exc:
        registry.register_location(location_id="bad_lat_high", requested_latitude=95.0, requested_longitude=75.0)
    assert "[-90.0, 90.0]" in str(exc.value)
    with pytest.raises(ValueError) as exc:
        registry.register_location(location_id="bad_lat_low", requested_latitude=-90.5, requested_longitude=75.0)
    assert "[-90.0, 90.0]" in str(exc.value)
    # Longitude out of bounds
    with pytest.raises(ValueError) as exc:
        registry.register_location(location_id="bad_lon_high", requested_latitude=20.0, requested_longitude=185.0)
    assert "[-180.0, 180.0]" in str(exc.value)
    with pytest.raises(ValueError) as exc:
        registry.register_location(location_id="bad_lon_low", requested_latitude=20.0, requested_longitude=-185.0)
    assert "[-180.0, 180.0]" in str(exc.value)
    # NaN / Inf coordinates
    with pytest.raises(ValueError) as exc:
        registry.register_location(location_id="nan_lat", requested_latitude=float("nan"), requested_longitude=75.0)
    assert "Must be finite" in str(exc.value)
    with pytest.raises(ValueError) as exc:
        registry.register_location(location_id="inf_lon", requested_latitude=20.0, requested_longitude=float("inf"))
    assert "Must be finite" in str(exc.value)
# ---------------------------------------------------------------------------
# Test O: Exact NWP Coordinate -> Zero Spatial Distance (No False Mismatch)
# ---------------------------------------------------------------------------
def test_o_exact_coordinates_zero_spatial_distance():
    registry = LocationRegistry()
    # Register station with verified NWP grid coordinates matching requested coordinates
    loc_info = registry.register_location(
        location_id="grid_aligned_station",
        requested_latitude=25.0,
        requested_longitude=80.0,
        verified_grid_latitude=25.0,
        verified_grid_longitude=80.0,
    )
    assert loc_info.spatial_distance_km is not None
    assert loc_info.spatial_distance_km == pytest.approx(0.0, abs=1e-6)
    # Run through MultiClimateDatasetBuilder QC with 0.0 spatial distance
    builder = MultiClimateDatasetBuilder(max_spatial_distance_km=50.0)
    t_issue = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_valid = datetime(2026, 8, 20, 6, 0, 0, tzinfo=timezone.utc)
    slice_df = pd.DataFrame([{
        "location_id": "grid_aligned_station", "region": "Central", "climate_zone": "Aw",
        "meteorological_regime": "Plains", "elevation_m": 150.0,
        "latitude": 25.0, "longitude": 80.0, "spatial_distance_km": 0.0,
        "issue_time_utc": t_issue, "valid_time_utc": t_valid, "lead_hours": 6, "lead_days": 0,
        "cycle": "00z", "variable": "temperature_2m", "forecast_value": 30.0,
        "forecast_unit": "degC", "forecast_source": "NOAA_GEFS", "ensemble_mean": 30.0,
        "ensemble_std": 1.0, "ensemble_min": 28.0, "ensemble_max": 32.0,
        "q10": 29.0, "q90": 31.0, "member_count": 31, "has_full_ensemble": True,
        "truth_value": 29.5, "truth_unit": "degC", "truth_source": "ERA5",
        "forecast_error": 0.5, "forecast_abs_error": 0.5, "ensemble_mean_error": 0.5, "ensemble_mean_abs_error": 0.5,
    }])
    report = builder.validate_dataset(slice_df, strict=True)
    assert report["is_valid"] is True
# ---------------------------------------------------------------------------
# Test P: Benchmark Overwrite Protection & Idempotency
# ---------------------------------------------------------------------------
def test_p_benchmark_overwrite_protection_and_idempotency():
    registry = LocationRegistry()
    # 1. Idempotent registration of existing benchmark with matching coordinates
    delhi_info = registry.get_location("delhi")
    idempotent_info = registry.register_location(
        location_id="delhi",
        requested_latitude=delhi_info.requested_coordinates.latitude,
        requested_longitude=delhi_info.requested_coordinates.longitude,
    )
    assert idempotent_info.location_id == "delhi"
    assert idempotent_info.is_benchmark is True
    # 2. Attempting to overwrite benchmark with differing coordinates MUST raise ValueError
    with pytest.raises(ValueError) as exc:
        registry.register_location(
            location_id="delhi",
            requested_latitude=19.0760,  # Mumbai lat instead of Delhi
            requested_longitude=72.8777,
        )
    assert "Cannot overwrite protected benchmark location 'delhi'" in str(exc.value)
    with pytest.raises(ValueError) as exc:
        registry.register_location(
            location_id="mumbai",
            requested_latitude=34.0837,  # Srinagar lat
            requested_longitude=74.7973,
        )
    assert "Cannot overwrite protected benchmark location 'mumbai'" in str(exc.value)
