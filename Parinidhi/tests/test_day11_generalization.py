"""
Day 11 Generalization Evaluation Test Suite.

Verifies:
1. Location-held-out split integrity (zero location overlap across train and test).
2. Climate-held-out split integrity (zero climate zone / regime overlap).
3. Forecast identity collision prevention across partitions.
4. Target leakage prevention (verification truth & error columns blocked from feature matrix).
5. Temporal integrity (two-sided train <= cutoff and test > cutoff).
6. Deterministic / reproducible splitting and SHA-256 provenance manifests.
7. Invalid split handling (empty groups, holding out all locations).
8. Single-class evaluation resilience (zero crashes when test set has only 1 class).
9. Dynamic / unseen runtime location evaluation.
10. Metrics engine correctness (PR-AUC, ROC-AUC, Brier score, ECE, False Reassurance Rate).
11. Baseline comparative benchmarking (Climatology, Persistence, Spread Heuristic).
12. Leave-One-Location-Out and Leave-One-Climate-Out cross-validation workflows.
13. Adversarial Two-Sided Temporal Cutoff Elimination of pre-cutoff test records.
14. Label Provenance Enforcement (rejection of unverifiable pre-computed labels).
15. Physical Meteorological Regime Broad Family Holdout (e.g. Semi-Arid multi-station isolation).
16. Dataset-Content SHA-256 Hash Sensitivity on row modifications.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List
import numpy as np
import pandas as pd
import pytest

from api.location_service import LocationRegistry
from evaluation.generalization import GeneralizationEvaluator, GeneralizationResult, compute_dataset_content_hash
from evaluation.metrics import GeneralizationMetrics
from evaluation.splits import ClimateHeldOutSplitter, HeldOutSplit, LocationHeldOutSplitter
from features.leakage_audit import DataLeakageError, LeakageAuditor


# ---------------------------------------------------------------------------
# Fixture: Synthetic Multi-Location Multi-Climate Canonical Historical Dataset
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_multi_climate_df() -> pd.DataFrame:
    """
    Creates a realistic multi-station synthetic dataset spanning 4 distinct climate regimes:
    - delhi (North, Cwa/BSh, elev 214m)
    - jaipur (Northwest, BSh/BWh, elev 431m)
    - mumbai (West, Am/Aw, elev 14m)
    - srinagar (North, Cfb/Dfb, elev 1585m)
    - bengaluru (South, Aw, elev 920m)
    """
    stations = [
        ("delhi", 28.61, 77.20, "Cwa/BSh", "Subtropical Semi-Arid / Continental", 214.0),
        ("jaipur", 26.91, 75.78, "BSh/BWh", "Hot Semi-Arid / Desert Margin", 431.0),
        ("mumbai", 19.07, 72.87, "Am/Aw", "Tropical Coastal / Maritime", 14.0),
        ("srinagar", 34.08, 74.79, "Cfb/Dfb", "Himalayan Mountain & Valley", 1585.0),
        ("bengaluru", 12.97, 77.59, "Aw", "Elevated Interior Plateau", 920.0),
    ]

    base_time = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    rows = []
    np.random.seed(42)

    for loc, lat, lon, cz, regime, elev in stations:
        for day in range(6):
            issue_t = base_time + timedelta(days=day)
            for lead in [6, 12, 24, 48]:
                valid_t = issue_t + timedelta(hours=lead)
                mean_t = 28.0 if loc != "srinagar" else 15.0
                f_val = mean_t + np.random.normal(0, 2.0)
                std_val = float(np.random.uniform(0.5, 3.0))
                err = float(np.random.normal(0, std_val))
                truth_val = f_val - err
                abs_err = abs(err)

                rows.append({
                    "location_id": loc,
                    "region": "Region_" + loc,
                    "climate_zone": cz,
                    "meteorological_regime": regime,
                    "elevation_m": elev,
                    "latitude": lat,
                    "longitude": lon,
                    "spatial_distance_km": 10.0,
                    "issue_time_utc": issue_t,
                    "valid_time_utc": valid_t,
                    "lead_hours": lead,
                    "lead_days": lead // 24,
                    "cycle": f"{issue_t.hour:02d}z",
                    "variable": "temperature_2m",
                    "forecast_value": round(f_val, 2),
                    "forecast_unit": "degC",
                    "forecast_source": "NOAA_GEFS",
                    "ensemble_mean": round(f_val, 2),
                    "ensemble_std": round(std_val, 2),
                    "ensemble_min": round(f_val - 2 * std_val, 2),
                    "ensemble_max": round(f_val + 2 * std_val, 2),
                    "ensemble_range": round(4 * std_val, 2),
                    "ensemble_iqr": round(1.35 * std_val, 2),
                    "ensemble_skew_proxy": 0.0,
                    "ensemble_cv": round(std_val / max(f_val, 1.0), 3),
                    "ensemble_spread_to_iqr_ratio": 1.0,
                    "member_count": 31,
                    "has_full_ensemble": True,
                    "ensemble_spread_delta_6h": 0.0,
                    "ensemble_spread_delta_24h": 0.0,
                    "forecast_delta_6h": 0.0,
                    "forecast_delta_24h": 0.0,
                    "valid_hour": valid_t.hour,
                    "valid_month": valid_t.month,
                    "valid_dayofweek": valid_t.weekday(),
                    "sin_hour": np.sin(2 * np.pi * valid_t.hour / 24.0),
                    "cos_hour": np.cos(2 * np.pi * valid_t.hour / 24.0),
                    "sin_month": np.sin(2 * np.pi * valid_t.month / 12.0),
                    "cos_month": np.cos(2 * np.pi * valid_t.month / 12.0),
                    "is_weekend": int(valid_t.weekday() >= 5),
                    "truth_value": round(truth_val, 2),
                    "truth_unit": "degC",
                    "truth_source": "ERA5_REANALYSIS",
                    "forecast_error": round(err, 2),
                    "forecast_abs_error": round(abs_err, 2),
                    "ensemble_mean_error": round(err, 2),
                    "ensemble_mean_abs_error": round(abs_err, 2),
                })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Test 1: Location-Held-Out Split Integrity & Zero Leakage
# ---------------------------------------------------------------------------
def test_1_location_held_out_split_integrity(sample_multi_climate_df):
    splitter = LocationHeldOutSplitter()
    held_out = ["delhi", "mumbai"]

    split = splitter.split(sample_multi_climate_df, held_out_locations=held_out)

    assert split.split_type == "location_held_out"
    assert set(split.held_out_locations) == {"delhi", "mumbai"}
    assert set(split.train_locations) == {"jaipur", "srinagar", "bengaluru"}

    # Scientific Invariant: strictly disjoint location sets
    assert set(split.train_locations).isdisjoint(set(split.held_out_locations))
    assert set(split.df_train["location_id"].unique()).isdisjoint(set(split.df_test["location_id"].unique()))

    # Size conservation
    assert len(split.df_train) + len(split.df_test) == len(sample_multi_climate_df)


# ---------------------------------------------------------------------------
# Test 2: Climate-Held-Out Split Integrity & Zero Regime Leakage
# ---------------------------------------------------------------------------
def test_2_climate_held_out_split_integrity(sample_multi_climate_df):
    splitter = ClimateHeldOutSplitter()
    held_out_cz = ["Am/Aw", "Cfb/Dfb"]

    split = splitter.split(sample_multi_climate_df, held_out_climates=held_out_cz)

    assert split.split_type == "climate_held_out"
    assert set(split.held_out_climates) == {"Am/Aw", "Cfb/Dfb"}

    # Scientific Invariant: zero climate regime overlap
    assert set(split.train_climates).isdisjoint(set(split.held_out_climates))
    assert set(split.df_train["climate_zone"].unique()).isdisjoint(set(split.df_test["climate_zone"].unique()))
    assert set(split.df_train["location_id"].unique()).isdisjoint(set(split.df_test["location_id"].unique()))


# ---------------------------------------------------------------------------
# Test 3: Forecast Identity Collision Prevention
# ---------------------------------------------------------------------------
def test_3_forecast_identity_collision_prevention(sample_multi_climate_df):
    splitter = LocationHeldOutSplitter()
    split = splitter.split(sample_multi_climate_df, held_out_locations=["delhi"])

    # Inject a synthetic train row into test split
    corrupted_test = split.df_test.copy()
    corrupted_test = pd.concat([corrupted_test, split.df_train.iloc[[0]]], ignore_index=True)

    corrupted_split = HeldOutSplit(
        df_train=split.df_train,
        df_test=corrupted_test,
        train_locations=split.train_locations,
        held_out_locations=split.held_out_locations,
        train_climates=split.train_climates,
        held_out_climates=split.held_out_climates,
        split_type="location_held_out",
    )

    with pytest.raises(ValueError) as exc:
        corrupted_split.validate_invariants()
    assert "Forecast identity collision" in str(exc.value) or "Spatial leakage" in str(exc.value)


# ---------------------------------------------------------------------------
# Test 4: Target Leakage Prevention in Generalization Evaluator
# ---------------------------------------------------------------------------
def test_4_target_leakage_prevention_audit(sample_multi_climate_df):
    evaluator = GeneralizationEvaluator()

    # Attempt to pass forbidden target columns into feature list
    forbidden_features = ["ensemble_std", "forecast_error", "truth_value"]
    with pytest.raises(DataLeakageError):
        evaluator.evaluate_location_held_out(
            sample_multi_climate_df,
            held_out_locations=["jaipur"],
            feature_columns=forbidden_features,
        )


# ---------------------------------------------------------------------------
# Test 5: Two-Sided Temporal Integrity Cutoff
# ---------------------------------------------------------------------------
def test_5_temporal_train_cutoff_integrity(sample_multi_climate_df):
    splitter = LocationHeldOutSplitter()
    cutoff = "2026-08-22 00:00:00"

    split = splitter.split(
        sample_multi_climate_df,
        held_out_locations=["srinagar"],
        temporal_train_cutoff=cutoff,
    )

    cutoff_ts = pd.to_datetime(cutoff, utc=True)
    max_train_issue = pd.to_datetime(split.df_train["issue_time_utc"], utc=True).max()
    min_test_issue = pd.to_datetime(split.df_test["issue_time_utc"], utc=True).min()

    # Both sides strictly verified
    assert max_train_issue <= cutoff_ts
    assert min_test_issue > cutoff_ts


# ---------------------------------------------------------------------------
# Test 6: Deterministic Splits & SHA-256 Provenance Manifest
# ---------------------------------------------------------------------------
def test_6_deterministic_splits_and_provenance(sample_multi_climate_df):
    evaluator = GeneralizationEvaluator()

    res1 = evaluator.evaluate_location_held_out(sample_multi_climate_df, held_out_locations=["mumbai"])
    res2 = evaluator.evaluate_location_held_out(sample_multi_climate_df, held_out_locations=["mumbai"])

    # Hashes and metrics must be bit-for-bit identical
    assert res1.provenance["feature_hash_sha256"] == res2.provenance["feature_hash_sha256"]
    assert res1.provenance["train_locations_hash"] == res2.provenance["train_locations_hash"]
    assert res1.provenance["train_content_sha256"] == res2.provenance["train_content_sha256"]
    assert res1.metrics["sample_count"] == res2.metrics["sample_count"]


# ---------------------------------------------------------------------------
# Test 7: Invalid Split Handling (Holding out all locations / non-existent)
# ---------------------------------------------------------------------------
def test_7_invalid_split_error_handling(sample_multi_climate_df):
    splitter = LocationHeldOutSplitter()

    # 1. Holding out non-existent location
    with pytest.raises(ValueError) as exc:
        splitter.split(sample_multi_climate_df, held_out_locations=["atlantis"])
    assert "None of the requested held-out locations" in str(exc.value)

    # 2. Holding out ALL locations
    all_locs = sample_multi_climate_df["location_id"].unique()
    with pytest.raises(ValueError) as exc:
        splitter.split(sample_multi_climate_df, held_out_locations=all_locs)
    assert "leaves no locations for training" in str(exc.value)


# ---------------------------------------------------------------------------
# Test 8: Single-Class Evaluation Handling (No Crashes on 0 Busts)
# ---------------------------------------------------------------------------
def test_8_single_class_evaluation_resilience():
    y_true = np.zeros(20, dtype=int)
    y_prob = np.full(20, 0.05, dtype=float)

    metrics = GeneralizationMetrics.evaluate_predictions(y_true, y_prob)

    assert metrics["positive_count"] == 0
    assert metrics["negative_count"] == 20
    assert metrics["classification"]["pr_auc"] == 0.0
    assert metrics["classification"]["roc_auc"] == "NOT AVAILABLE — single class in test set"
    assert metrics["probabilistic"]["brier_score"] == pytest.approx(0.0025, abs=1e-4)


# ---------------------------------------------------------------------------
# Test 9: Dynamic / Unseen Runtime Location Evaluation
# ---------------------------------------------------------------------------
def test_9_dynamic_runtime_location_evaluation(sample_multi_climate_df):
    registry = LocationRegistry()
    registry.register_location("shimla", 31.10, 77.17, state_region="Himachal", climate_zone="Cwb", elevation_m=2276.0)

    evaluator = GeneralizationEvaluator(location_registry=registry)

    shimla_row = sample_multi_climate_df[sample_multi_climate_df["location_id"] == "srinagar"].copy()
    shimla_row["location_id"] = "shimla"
    shimla_row["climate_zone"] = "Cwb"
    extended_df = pd.concat([sample_multi_climate_df, shimla_row], ignore_index=True)

    result = evaluator.evaluate_location_held_out(extended_df, held_out_locations=["shimla"])

    assert result.held_out_locations == ["shimla"]
    assert "shimla" not in result.train_locations
    assert result.sample_count > 0


# ---------------------------------------------------------------------------
# Test 10: Metrics Engine Correctness
# ---------------------------------------------------------------------------
def test_10_metrics_calculation_correctness():
    y_true = np.array([0, 0, 1, 1, 0, 1])
    y_prob = np.array([0.1, 0.2, 0.8, 0.9, 0.3, 0.4])

    metrics = GeneralizationMetrics.evaluate_predictions(
        y_true, y_prob, threshold=0.5, low_risk_threshold=0.33, high_risk_threshold=0.66
    )

    cm = metrics["classification"]["confusion_matrix"]
    assert cm["tp"] == 2
    assert cm["fp"] == 0
    assert cm["tn"] == 3
    assert cm["fn"] == 1
    assert metrics["classification"]["precision"] == 1.0
    assert metrics["classification"]["recall"] == pytest.approx(2.0 / 3.0, abs=1e-3)


# ---------------------------------------------------------------------------
# Test 11: Baseline Comparative Benchmarking
# ---------------------------------------------------------------------------
def test_11_baseline_comparative_benchmarking(sample_multi_climate_df):
    evaluator = GeneralizationEvaluator()
    result = evaluator.evaluate_location_held_out(sample_multi_climate_df, held_out_locations=["bengaluru"])

    assert "climatology" in result.baseline_metrics
    assert "persistence" in result.baseline_metrics
    assert "spread_heuristic" in result.baseline_metrics
    assert "majority_class" in result.baseline_metrics

    for name, bl_res in result.baseline_metrics.items():
        assert "brier_score" in bl_res
        assert bl_res["brier_score"] >= 0.0


# ---------------------------------------------------------------------------
# Test 12: Leave-One-Out Cross-Validation Workflows
# ---------------------------------------------------------------------------
def test_12_leave_one_out_cross_validation_workflows(sample_multi_climate_df):
    evaluator = GeneralizationEvaluator()

    # LOLO Cross-Validation (5 stations -> 5 folds)
    lolo_results = evaluator.run_leave_one_location_out(sample_multi_climate_df)
    assert len(lolo_results) == 5
    for res in lolo_results:
        assert len(res.held_out_locations) == 1
        assert len(res.train_locations) == 4
        assert res.sample_count > 0

    # LOCO Cross-Validation (5 climate zones -> 5 folds)
    loco_results = evaluator.run_leave_one_climate_out(sample_multi_climate_df)
    assert len(loco_results) == 5
    for res in loco_results:
        assert len(res.held_out_climate_regimes) == 1
        assert len(res.train_climate_regimes) == 4


# ---------------------------------------------------------------------------
# Test 13: Adversarial Two-Sided Temporal Cutoff Elimination
# ---------------------------------------------------------------------------
def test_13_two_sided_temporal_cutoff_and_pre_cutoff_elimination(sample_multi_climate_df):
    splitter = LocationHeldOutSplitter()
    cutoff = "2026-08-22 12:00:00"
    cutoff_ts = pd.to_datetime(cutoff, utc=True)

    split = splitter.split(
        sample_multi_climate_df,
        held_out_locations=["delhi"],
        temporal_train_cutoff=cutoff,
    )

    # Prove that NO test record on or before cutoff survives in df_test
    test_issues = pd.to_datetime(split.df_test["issue_time_utc"], utc=True)
    assert (test_issues <= cutoff_ts).sum() == 0
    assert test_issues.min() > cutoff_ts

    # Prove that NO train record after cutoff exists in df_train
    train_issues = pd.to_datetime(split.df_train["issue_time_utc"], utc=True)
    assert (train_issues > cutoff_ts).sum() == 0
    assert train_issues.max() <= cutoff_ts


# ---------------------------------------------------------------------------
# Test 14: Label Provenance Enforcement
# ---------------------------------------------------------------------------
def test_14_label_provenance_enforcement(sample_multi_climate_df):
    evaluator = GeneralizationEvaluator()
    splitter = LocationHeldOutSplitter()
    split = splitter.split(sample_multi_climate_df, held_out_locations=["delhi"])

    # Pre-populate bust_label in both splits artificially
    split.df_train["bust_label"] = 0
    split.df_test["bust_label"] = 1

    # 1. With force_refit_labels=False and NO provenance -> MUST raise ValueError
    with pytest.raises(ValueError) as exc:
        evaluator.evaluate_split(
            split,
            force_refit_labels=False,
            label_provenance=None,
        )
    assert "Unverifiable label provenance" in str(exc.value)

    # 2. With force_refit_labels=True (default) -> refits cleanly and succeeds
    res = evaluator.evaluate_split(split, force_refit_labels=True)
    assert res.provenance["label_provenance"]["fit_partition"] == "df_train_only"


# ---------------------------------------------------------------------------
# Test 15: Meteorological Regime Broad Family Holdout
# ---------------------------------------------------------------------------
def test_15_meteorological_regime_broad_family_holdout(sample_multi_climate_df):
    evaluator = GeneralizationEvaluator()

    # Hold out all Semi-Arid stations (both Delhi and Jaipur simultaneously)
    result = evaluator.evaluate_meteorological_regime_held_out(
        sample_multi_climate_df,
        held_out_regimes=["Semi-Arid"],
        match_mode="contains",
    )

    assert set(result.held_out_locations) == {"delhi", "jaipur"}
    assert set(result.train_locations) == {"mumbai", "srinagar", "bengaluru"}
    assert result.evaluation_type == "meteorological_regime_held_out"
    assert result.sample_count > 0


# ---------------------------------------------------------------------------
# Test 16: Dataset-Content SHA-256 Hash Sensitivity
# ---------------------------------------------------------------------------
def test_16_dataset_content_hash_sensitivity(sample_multi_climate_df):
    h1 = compute_dataset_content_hash(sample_multi_climate_df)

    # Modify a single float value in one row
    modified_df = sample_multi_climate_df.copy()
    modified_df.loc[0, "forecast_value"] += 0.05
    h2 = compute_dataset_content_hash(modified_df)

    # Hash MUST change
    assert h1 != h2
    assert len(h1) == 64
    assert len(h2) == 64
