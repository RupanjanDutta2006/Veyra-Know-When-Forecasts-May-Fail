"""
Day 12 Scalable Data Foundation & Empirical Batch Ingestion Test Suite (Corrective Forensic Standard).

Verifies:
1. Dataset manifest generation with full schema completeness, QC status, and dual sample-size accounting.
2. Deterministic provenance & dataset-content SHA-256 calculation (row-order independent).
3. Canonical schema completeness (all 32 canonical columns).
4. Location coverage (20 operational locations, 8 benchmark completeness).
5. Temporal coverage & chronological sequence consistency.
6. Cycle derivation: auto-derivation, explicit preservation, invalid cycle rejection, determinism.
7. Variable coverage (temperature_2m, surface_pressure, wind_speed_10m).
8. Duplicate forecast key detection and rejection on (location, variable, issue_time, valid_time).
9. Forecast/truth alignment and signed/absolute error arithmetic.
10. Spatial mismatch detection and distance threshold auditing.
11. Issue-time leakage prevention (feature matrix X does not contain ground truth).
12. Target/feature segregation (canonical feature vs target columns).
13. Row-count vs forecast-run initialization unit count distinction (35,040 rows vs 1,200 runs).
14. Bit-for-bit reproducibility across repeated executions.
15. Incomplete-data handling (missing required columns raise ValueError).
16. Missing-cycle handling and detection in DatasetCoverageValidator.
17. Missing / unregistered location handling.
18. Graceful failure handling on corrupted or empty payloads.
19. Scalability behavior: Chunking 0, 1, 49, 50, 51, 100, 500, 1000, 1001+ locations & invalid chunk rejection.
20. Expected Calibration Error (ECE) and probabilistic metric edge case resilience.
21. Protection against accidental git tracking of local data files.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
import pandas as pd
import pytest

from api.location_service import LocationInfo, LocationRegistry
from data_pipeline.batch_processor import DatasetCoverageReport, DatasetCoverageValidator, HistoricalBatchManager
from data_pipeline.historical_aligner import (
    CANONICAL_HISTORICAL_COLUMNS,
    CANONICAL_TARGET_COLUMNS,
    MultiClimateDatasetBuilder,
    VALID_CANONICAL_CYCLES,
    derive_canonical_cycle,
)
from evaluation.metrics import GeneralizationMetrics
from features.feature_pipeline import FEATURE_COLUMN_NAMES, IssueTimeSafeFeaturePipeline
from features.leakage_audit import DataLeakageError, LeakageAuditor


@pytest.fixture
def sample_20_station_df() -> pd.DataFrame:
    """Creates a deterministic multi-location dataset across 20 Indian stations."""
    registry = LocationRegistry()
    all_locs = registry.get_all_location_ids()
    base_time = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    rows = []
    np.random.seed(42)

    for loc in all_locs:
        info = registry.get_location(loc)
        for day in range(2):
            for cycle_h in [0, 6, 12, 18]:
                issue_t = base_time + timedelta(days=day, hours=cycle_h)
                for lead in [0, 6, 12, 24, 48, 72]:
                    valid_t = issue_t + timedelta(hours=lead)
                    for var, mean_val, std_val in [
                        ("temperature_2m", 28.0, 2.0),
                        ("surface_pressure", 1005.0, 5.0),
                        ("wind_speed_10m", 15.0, 4.0),
                    ]:
                        f_val = round(float(mean_val + np.random.normal(0, std_val)), 2)
                        ens_std = round(float(np.random.uniform(0.5, 2.5)), 2)
                        err = round(float(np.random.normal(0, ens_std)), 2)
                        truth_val = round(f_val - err, 2)

                        rows.append({
                            "location": loc,
                            "latitude": info.requested_coordinates.latitude,
                            "longitude": info.requested_coordinates.longitude,
                            "spatial_distance_km": 5.0,
                            "issue_time": issue_t,
                            "valid_time": valid_t,
                            "lead_hours": lead,
                            "variable": var,
                            "forecast_value": f_val,
                            "forecast_unit": "degC" if "temp" in var else ("hPa" if "press" in var else "km/h"),
                            "forecast_source": "NOAA_GEFS",
                            "ensemble_mean": f_val,
                            "ensemble_std": ens_std,
                            "ensemble_min": f_val - 2 * ens_std,
                            "ensemble_max": f_val + 2 * ens_std,
                            "q10": f_val - 1.28 * ens_std,
                            "q90": f_val + 1.28 * ens_std,
                            "member_count": 31,
                            "truth_value": truth_val,
                            "truth_unit": "degC" if "temp" in var else ("hPa" if "press" in var else "km/h"),
                            "truth_source": "ERA5_REANALYSIS",
                            "forecast_error": err,
                            "forecast_abs_error": abs(err),
                            "ensemble_mean_error": err,
                            "ensemble_mean_abs_error": abs(err),
                        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Test 1: Dataset Manifest Generation & Dual Accounting
# ---------------------------------------------------------------------------
def test_1_dataset_manifest_generation(sample_20_station_df, tmp_path):
    mgr = HistoricalBatchManager(output_dir=str(tmp_path))
    std_df, manifest = mgr.process_batch(
        sample_20_station_df,
        dataset_id="test_batch_manifest_01",
        save_local_files=True,
    )

    assert manifest["dataset_id"] == "test_batch_manifest_01"
    assert manifest["total_records"] == len(std_df)
    assert manifest["column_count"] == 32
    assert manifest["forecast_run_count"] == 480
    assert manifest["records_per_run_avg"] == 6.0
    assert manifest["qc_validation"]["is_valid"] is True
    assert (tmp_path / "test_batch_manifest_01" / "test_batch_manifest_01.parquet").exists()
    assert (tmp_path / "test_batch_manifest_01" / "test_batch_manifest_01_manifest.json").exists()


# ---------------------------------------------------------------------------
# Test 2: Deterministic Provenance & Order-Independent Content Hash
# ---------------------------------------------------------------------------
def test_2_deterministic_provenance_and_hash(sample_20_station_df, tmp_path):
    mgr = HistoricalBatchManager(output_dir=str(tmp_path))
    _, m1 = mgr.process_batch(sample_20_station_df, dataset_id="run_1", save_local_files=False)

    # Shuffle dataframe rows
    shuffled_df = sample_20_station_df.sample(frac=1.0, random_state=123).reset_index(drop=True)
    _, m2 = mgr.process_batch(shuffled_df, dataset_id="run_2", save_local_files=False)

    # Hashes must be identical regardless of row ordering
    assert m1["content_sha256"] == m2["content_sha256"]
    assert len(m1["content_sha256"]) == 64

    # Modifying one float value must alter the hash
    altered_df = sample_20_station_df.copy()
    altered_df.loc[0, "forecast_value"] += 0.05
    _, m3 = mgr.process_batch(altered_df, dataset_id="run_3", save_local_files=False)
    assert m1["content_sha256"] != m3["content_sha256"]


# ---------------------------------------------------------------------------
# Test 3: Canonical Schema Completeness
# ---------------------------------------------------------------------------
def test_3_canonical_schema_completeness(sample_20_station_df):
    builder = MultiClimateDatasetBuilder()
    std_df = builder.standardize_paired_slice(sample_20_station_df)

    assert list(std_df.columns) == CANONICAL_HISTORICAL_COLUMNS
    assert "cycle" in std_df.columns
    assert "location_id" in std_df.columns
    assert "climate_zone" in std_df.columns
    assert "meteorological_regime" in std_df.columns
    assert "elevation_m" in std_df.columns


# ---------------------------------------------------------------------------
# Test 4: Location Coverage & Benchmark Completeness
# ---------------------------------------------------------------------------
def test_4_location_coverage_and_benchmarks(sample_20_station_df):
    validator = DatasetCoverageValidator()
    builder = MultiClimateDatasetBuilder()
    std_df = builder.standardize_paired_slice(sample_20_station_df)

    cov = validator.audit_coverage(std_df)

    assert cov.distinct_locations == 20
    assert cov.benchmark_completeness_pct == 100.0
    assert len(cov.benchmark_locations_present) == 8


# ---------------------------------------------------------------------------
# Test 5: Temporal Coverage & Ordering Consistency
# ---------------------------------------------------------------------------
def test_5_temporal_coverage_and_consistency(sample_20_station_df):
    builder = MultiClimateDatasetBuilder()
    std_df = builder.standardize_paired_slice(sample_20_station_df)

    assert (std_df["valid_time_utc"] >= std_df["issue_time_utc"]).all()
    assert (std_df["lead_hours"] >= 0).all()


# ---------------------------------------------------------------------------
# Test 6: Canonical Cycle Derivation & Validation
# ---------------------------------------------------------------------------
def test_6_canonical_cycle_derivation():
    # 1. Missing cycle is automatically derived from issue_time
    issue_t = datetime(2026, 8, 20, 6, 0, 0, tzinfo=timezone.utc)
    assert derive_canonical_cycle(issue_t) == "06z"

    # 2. Explicit valid cycle is preserved
    assert derive_canonical_cycle(issue_t, cycle="12Z ") == "12z"

    # 3. Invalid explicit cycle is rejected with ValueError
    with pytest.raises(ValueError) as exc1:
        derive_canonical_cycle(issue_t, cycle="invalid_cycle")
    assert "Invalid forecast cycle 'invalid_cycle'" in str(exc1.value)

    # 4. Invalid issue time hour (non-synoptic) raises ValueError
    non_synoptic_t = datetime(2026, 8, 20, 3, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError) as exc2:
        derive_canonical_cycle(non_synoptic_t)
    assert "not a valid synoptic cycle" in str(exc2.value)

    # 5. Series derivation is deterministic
    s_times = pd.Series([
        datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 20, 18, 0, 0, tzinfo=timezone.utc),
    ])
    derived_s = derive_canonical_cycle(s_times)
    assert list(derived_s) == ["00z", "18z"]


# ---------------------------------------------------------------------------
# Test 7: Variable Coverage
# ---------------------------------------------------------------------------
def test_7_variable_coverage(sample_20_station_df):
    validator = DatasetCoverageValidator()
    builder = MultiClimateDatasetBuilder()
    std_df = builder.standardize_paired_slice(sample_20_station_df)

    cov = validator.audit_coverage(std_df)
    assert set(cov.variables_present) == {"temperature_2m", "surface_pressure", "wind_speed_10m"}


# ---------------------------------------------------------------------------
# Test 8: Duplicate Forecast Key Detection
# ---------------------------------------------------------------------------
def test_8_duplicate_detection(sample_20_station_df):
    builder = MultiClimateDatasetBuilder()
    std_df = builder.standardize_paired_slice(sample_20_station_df)

    # Inject duplicate row
    dup_df = pd.concat([std_df, std_df.iloc[[0]]], ignore_index=True)
    report = builder.validate_dataset(dup_df, strict=False)

    assert report["is_valid"] is False
    assert any("Duplicate forecast keys detected" in issue for issue in report["audit_issues"])


# ---------------------------------------------------------------------------
# Test 9: Forecast/Truth Alignment & Error Computation
# ---------------------------------------------------------------------------
def test_9_forecast_truth_alignment_and_errors(sample_20_station_df):
    builder = MultiClimateDatasetBuilder()
    std_df = builder.standardize_paired_slice(sample_20_station_df)

    expected_signed = std_df["forecast_value"] - std_df["truth_value"]
    np.testing.assert_allclose(std_df["forecast_error"].values, expected_signed.values, atol=1e-3)
    np.testing.assert_allclose(std_df["forecast_abs_error"].values, np.abs(expected_signed.values), atol=1e-3)


# ---------------------------------------------------------------------------
# Test 10: Spatial Mismatch Threshold Auditing
# ---------------------------------------------------------------------------
def test_10_spatial_mismatch_detection(sample_20_station_df):
    builder = MultiClimateDatasetBuilder(max_spatial_distance_km=25.0)
    std_df = builder.standardize_paired_slice(sample_20_station_df)

    # Inject an excessive spatial offset of 100km
    std_df.loc[0, "spatial_distance_km"] = 100.0
    report = builder.validate_dataset(std_df, strict=False)

    assert report["is_valid"] is False
    assert any("Spatial mismatch" in issue for issue in report["audit_issues"])


# ---------------------------------------------------------------------------
# Test 11: Issue-Time Leakage Prevention
# ---------------------------------------------------------------------------
def test_11_issue_time_leakage_prevention(sample_20_station_df):
    fp = IssueTimeSafeFeaturePipeline()
    X, meta = fp.extract_features(sample_20_station_df)

    auditor = LeakageAuditor()
    audit_rep = auditor.audit_feature_matrix(X, meta)

    assert audit_rep["status"] == "PASSED"
    for col in CANONICAL_TARGET_COLUMNS:
        assert col not in X.columns


# ---------------------------------------------------------------------------
# Test 12: Target / Feature Segregation
# ---------------------------------------------------------------------------
def test_12_target_feature_segregation():
    assert set(FEATURE_COLUMN_NAMES).isdisjoint(set(CANONICAL_TARGET_COLUMNS))


# ---------------------------------------------------------------------------
# Test 13: Row-Count vs Forecast-Run-Count Distinction
# ---------------------------------------------------------------------------
def test_13_row_count_vs_forecast_run_count_distinction(sample_20_station_df):
    validator = DatasetCoverageValidator()
    builder = MultiClimateDatasetBuilder()
    std_df = builder.standardize_paired_slice(sample_20_station_df)

    cov = validator.audit_coverage(std_df)

    assert cov.total_records == 2880
    assert cov.forecast_run_count == 480
    assert cov.records_per_run_avg == 6.0


# ---------------------------------------------------------------------------
# Test 14: Reproducibility Across Repeated Executions
# ---------------------------------------------------------------------------
def test_14_reproducibility(sample_20_station_df, tmp_path):
    mgr = HistoricalBatchManager(output_dir=str(tmp_path))
    _, m1 = mgr.process_batch(sample_20_station_df, dataset_id="repro_run", save_local_files=False)
    _, m2 = mgr.process_batch(sample_20_station_df, dataset_id="repro_run", save_local_files=False)

    assert m1["content_sha256"] == m2["content_sha256"]
    assert m1["total_records"] == m2["total_records"]
    assert m1["forecast_run_count"] == m2["forecast_run_count"]
    assert m1["qc_validation"]["is_valid"] == m2["qc_validation"]["is_valid"]
    assert m1["qc_validation"]["distinct_locations"] == m2["qc_validation"]["distinct_locations"]


# ---------------------------------------------------------------------------
# Test 15: Incomplete Data Handling (Missing Required Columns)
# ---------------------------------------------------------------------------
def test_15_incomplete_data_handling(sample_20_station_df):
    builder = MultiClimateDatasetBuilder()
    corrupted_df = sample_20_station_df.drop(columns=["forecast_value"])

    with pytest.raises(ValueError) as exc:
        builder.standardize_paired_slice(corrupted_df)
    assert "missing required canonical columns" in str(exc.value)


# ---------------------------------------------------------------------------
# Test 16: Missing-Cycle Detection in Coverage Validator
# ---------------------------------------------------------------------------
def test_16_missing_cycle_handling(sample_20_station_df):
    validator = DatasetCoverageValidator()
    builder = MultiClimateDatasetBuilder()
    std_df = builder.standardize_paired_slice(sample_20_station_df)

    # Drop 18z cycle
    no_18z = std_df[std_df["cycle"] != "18z"].copy()
    cov = validator.audit_coverage(no_18z)

    assert cov.is_coverage_complete is False
    assert any("Missing required forecast cycles" in issue for issue in cov.coverage_issues)


# ---------------------------------------------------------------------------
# Test 17: Missing / Unregistered Location Handling
# ---------------------------------------------------------------------------
def test_17_missing_location_handling(sample_20_station_df):
    builder = MultiClimateDatasetBuilder()
    custom_df = sample_20_station_df.copy()
    custom_df["location"] = "unknown_city_xyz"
    custom_df["latitude"] = 15.5
    custom_df["longitude"] = 75.5

    std_df = builder.standardize_paired_slice(custom_df)
    assert (std_df["location_id"] == "unknown_city_xyz").all()
    assert builder.location_registry.has_location("unknown_city_xyz")


# ---------------------------------------------------------------------------
# Test 18: Graceful Empty Payload Handling
# ---------------------------------------------------------------------------
def test_18_graceful_empty_payload():
    builder = MultiClimateDatasetBuilder()
    with pytest.raises(ValueError) as exc:
        builder.standardize_paired_slice(pd.DataFrame())
    assert "Input paired DataFrame is empty" in str(exc.value)


# ---------------------------------------------------------------------------
# Test 19: Scalability Behavior (0, 1, 49, 50, 51, 100, 500, 1000, 1001 Locations)
# ---------------------------------------------------------------------------
def test_19_scalability_chunking():
    mgr = HistoricalBatchManager()

    # Invalid chunk size <= 0
    with pytest.raises(ValueError):
        list(mgr.create_batch_chunks(["delhi"], chunk_size=0))
    with pytest.raises(ValueError):
        list(mgr.create_batch_chunks(["delhi"], chunk_size=-5))

    # Test variable coordinate list sizes
    for n_locs in [0, 1, 49, 50, 51, 100, 500, 1000, 1001]:
        loc_list = [
            {"location_id": f"station_{i}", "latitude": 20.0 + (i % 20) * 0.25, "longitude": 75.0 + (i // 20) * 0.25}
            for i in range(n_locs)
        ]
        chunks = list(mgr.create_batch_chunks(loc_list, chunk_size=50))
        expected_chunks = (n_locs + 49) // 50 if n_locs > 0 else 0
        assert len(chunks) == expected_chunks
        assert sum(len(c) for c in chunks) == n_locs


# ---------------------------------------------------------------------------
# Test 20: Expected Calibration Error & Metrics Edge Cases
# ---------------------------------------------------------------------------
def test_20_ece_and_metrics_edge_cases():
    # Empty dataset
    res_empty = GeneralizationMetrics.evaluate_predictions([], [])
    assert res_empty["sample_count"] == 0

    # Single-class test sets (no positive busts)
    y_true_zeros = np.zeros(100, dtype=int)
    y_prob = np.random.uniform(0.1, 0.4, size=100)
    res_zeros = GeneralizationMetrics.evaluate_predictions(y_true_zeros, y_prob)
    assert res_zeros["positive_count"] == 0
    assert "single class" in str(res_zeros["classification"]["roc_auc"])
    assert res_zeros["probabilistic"]["expected_calibration_error"] >= 0.0

    # Perfect probabilities (0 and 1 boundaries)
    y_true_perf = np.array([0, 0, 1, 1])
    y_prob_perf = np.array([0.0, 0.0, 1.0, 1.0])
    res_perf = GeneralizationMetrics.evaluate_predictions(y_true_perf, y_prob_perf)
    assert res_perf["probabilistic"]["brier_score"] == 0.0
    assert res_perf["probabilistic"]["expected_calibration_error"] == 0.0


# ---------------------------------------------------------------------------
# Test 21: Protection Against Accidental Git Artifact Tracking
# ---------------------------------------------------------------------------
def test_21_git_ignore_rules():
    gitignore_path = Path(".gitignore")
    assert gitignore_path.exists()

    content = gitignore_path.read_text(encoding="utf-8")
    assert "*.parquet" in content
    assert "*.joblib" in content
    assert "*.grib" in content
    assert "*.grib2" in content
    assert "data/historical/*" in content
