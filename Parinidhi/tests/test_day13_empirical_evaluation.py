"""
Day 13 Empirical Forecast-Bust Evaluation, Calibration & Evidence Engine Test Suite.

Verifies:
1. Issue-time feature availability contract enforcement.
2. Target column leakage rejection during feature selection.
3. Train-only label threshold fitting and test label isolation.
4. Pre-computed label provenance verification and rejection if unverified.
5. Baseline correctness (MajorityClass, Climatology, Persistence, SpreadHeuristic).
6. ProbabilityCalibrator: Platt scaling (sigmoid) fit and transform.
7. ProbabilityCalibrator: Isotonic regression fit and transform.
8. ProbabilityCalibrator: Train/test isolation (calibrator strictly fits on train only).
9. ReliabilityAnalyzer: Reliability table, ECE, MCE, and Brier Skill Score.
10. ReliabilityAnalyzer: Edge cases (single-class, boundary probabilities 0.0/1.0, empty bins).
11. Lead-time degradation stratification (Short 0-24h, Medium 25-48h, Extended 49-72h).
12. Location-wise granular evaluation & inter-location spread reporting.
13. Full evidence engine split evaluation with calibration & baseline deltas.
14. Location-held-out (LOLO) generalization integrity.
15. Climate-held-out (LOCO) generalization integrity.
16. Ensemble spread vs absolute error association (Pearson r & Spearman rho).
17. Spread tertile stratification (Low, Medium, High spread bins).
18. Bootstrap confidence intervals for PR-AUC, Brier score, and F1 with deterministic seed.
19. Failure mode attribution (False Negatives vs False Positives).
20. Statistical data sufficiency gating (insufficient samples return INSUFFICIENT_DATA).
21. Reproducible empirical experiment manifest & content SHA-256 hashing.
22. Git protection against accidental tracking of historical/model binaries.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
import pandas as pd
import pytest

from api.location_service import LocationRegistry
from data_pipeline.historical_aligner import MultiClimateDatasetBuilder
from evaluation.calibration import ProbabilityCalibrator, ReliabilityAnalyzer
from evaluation.empirical_engine import EmpiricalEvidenceEngine, EmpiricalExperimentManifest
from evaluation.generalization import GeneralizationEvaluator, GeneralizationResult, compute_dataset_content_hash
from evaluation.metrics import GeneralizationMetrics
from evaluation.splits import ClimateHeldOutSplitter, HeldOutSplit, LocationHeldOutSplitter
from features.contract import AVAILABLE_AT_ISSUE_TIME, UNAVAILABLE_UNTIL_VERIFICATION, validate_feature_contract
from features.feature_pipeline import FEATURE_COLUMN_NAMES, IssueTimeSafeFeaturePipeline
from features.leakage_audit import DataLeakageError, LeakageAuditor
from labels.label_engine import BustLabelEngine
from models.baselines import ClimatologyBaseline, MajorityClassBaseline, PersistenceBaseline, SpreadHeuristicBaseline
from models.logistic_classifier import RegularizedLogisticClassifier


@pytest.fixture
def multi_station_empirical_df() -> pd.DataFrame:
    """Creates a deterministic multi-location dataset across 20 Indian stations for empirical tests."""
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
                        ens_std = round(float(np.random.uniform(0.5, 3.5)), 2)
                        # Induce correlation between spread and error
                        err = round(float(np.random.normal(0, 0.8 * ens_std + 0.2)), 2)
                        truth_val = round(f_val - err, 2)

                        rows.append({
                            "location_id": loc,
                            "location": loc,
                            "latitude": info.requested_coordinates.latitude,
                            "longitude": info.requested_coordinates.longitude,
                            "spatial_distance_km": 5.0,
                            "issue_time": issue_t,
                            "issue_time_utc": issue_t,
                            "valid_time": valid_t,
                            "valid_time_utc": valid_t,
                            "lead_hours": lead,
                            "lead_days": lead // 24,
                            "cycle": f"{cycle_h:02d}z",
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
                            "has_full_ensemble": True,
                            "truth_value": truth_val,
                            "truth_unit": "degC" if "temp" in var else ("hPa" if "press" in var else "km/h"),
                            "truth_source": "ERA5_REANALYSIS",
                            "forecast_error": err,
                            "forecast_abs_error": abs(err),
                            "ensemble_mean_error": err,
                            "ensemble_mean_abs_error": abs(err),
                            "climate_zone": info.climate_zone,
                            "meteorological_regime": info.meteorological_regime,
                            "region": info.state_region,
                            "elevation_m": info.elevation_m if info.elevation_m is not None else 100.0,
                        })

    raw_df = pd.DataFrame(rows)
    builder = MultiClimateDatasetBuilder()
    std_df = builder.standardize_paired_slice(raw_df)

    # Extract features using IssueTimeSafeFeaturePipeline and merge
    fp = IssueTimeSafeFeaturePipeline()
    X, _ = fp.extract_features(std_df)
    for col in X.columns:
        if col not in std_df.columns:
            std_df[col] = X[col].values

    return std_df


# ---------------------------------------------------------------------------
# Test 1: Issue-Time Feature Availability Contract Enforcement
# ---------------------------------------------------------------------------
def test_1_feature_contract_enforcement():
    valid_features = list(FEATURE_COLUMN_NAMES)
    violations = validate_feature_contract(valid_features)
    assert len(violations) == 0

    # Inject forbidden verification columns
    for forbidden in UNAVAILABLE_UNTIL_VERIFICATION:
        bad_features = valid_features + [forbidden]
        v = validate_feature_contract(bad_features)
        assert len(v) > 0
        assert any(forbidden in msg for msg in v)


# ---------------------------------------------------------------------------
# Test 2: Target Column Leakage Rejection in Evidence Engine
# ---------------------------------------------------------------------------
def test_2_leakage_rejection_in_evidence_engine():
    engine = EmpiricalEvidenceEngine()
    audit = engine.audit_feature_contract(list(FEATURE_COLUMN_NAMES))
    assert audit["is_valid"] is True

    # Attempt to audit feature set containing truth_value
    leaked_audit = engine.audit_feature_contract(list(FEATURE_COLUMN_NAMES) + ["truth_value"])
    assert leaked_audit["is_valid"] is False
    assert any("truth_value" in err for err in leaked_audit["violations"])


# ---------------------------------------------------------------------------
# Test 3: Train-Only Label Threshold Fitting & Test Isolation
# ---------------------------------------------------------------------------
def test_3_train_only_label_threshold_fitting(multi_station_empirical_df):
    splitter = LocationHeldOutSplitter()
    split = splitter.split(multi_station_empirical_df, held_out_locations=["delhi"])

    label_engine = BustLabelEngine(primary_quantile=0.95)
    # Fit strictly on df_train
    label_engine.fit(split.df_train)
    fitted_thresh = label_engine.thresholds_

    # Transform both partitions using frozen train thresholds
    train_labeled = label_engine.transform(split.df_train)
    test_labeled = label_engine.transform(split.df_test)

    assert "bust_label" in train_labeled.columns
    assert "bust_label" in test_labeled.columns
    assert label_engine.is_fitted_ is True
    assert "training_sample_count" in fitted_thresh["meta"]
    assert fitted_thresh["meta"]["training_sample_count"] == len(split.df_train)


# ---------------------------------------------------------------------------
# Test 4: Pre-Computed Label Provenance Enforcement
# ---------------------------------------------------------------------------
def test_4_label_provenance_enforcement(multi_station_empirical_df):
    splitter = LocationHeldOutSplitter()
    split = splitter.split(multi_station_empirical_df, held_out_locations=["mumbai"])

    evaluator = GeneralizationEvaluator()

    # Create unverified labeled dataframes
    unverified_train = split.df_train.copy()
    unverified_test = split.df_test.copy()
    unverified_train["bust_label"] = 0
    unverified_test["bust_label"] = 0

    bad_split = HeldOutSplit(
        df_train=unverified_train,
        df_test=unverified_test,
        train_locations=split.train_locations,
        held_out_locations=split.held_out_locations,
        train_climates=split.train_climates,
        held_out_climates=split.held_out_climates,
        split_type="location_held_out",
    )

    # force_refit_labels=False without valid provenance metadata must raise ValueError
    with pytest.raises(ValueError) as exc:
        evaluator.evaluate_split(bad_split, force_refit_labels=False)
    assert "Unverifiable label provenance" in str(exc.value)


# ---------------------------------------------------------------------------
# Test 5: Baseline Suite Correctness
# ---------------------------------------------------------------------------
def test_5_baseline_suite_correctness(multi_station_empirical_df):
    feat_cols = [c for c in FEATURE_COLUMN_NAMES if c in multi_station_empirical_df.columns]
    X = multi_station_empirical_df[feat_cols]
    y = pd.Series(np.random.binomial(1, 0.1, size=len(X)))

    # 1. Majority Class
    b_maj = MajorityClassBaseline().fit(X, y)
    p_maj = b_maj.predict_proba(X)
    assert (p_maj[:, 1] == 0.0).all()

    # 2. Climatology
    b_clim = ClimatologyBaseline().fit(X, y)
    p_clim = b_clim.predict_proba(X)
    np.testing.assert_allclose(p_clim[:, 1], y.mean(), atol=1e-4)

    # 3. Persistence
    b_pers = PersistenceBaseline().fit(X, y)
    p_pers = b_pers.predict_proba(X)
    assert (p_pers[:, 1] >= 0.0).all() and (p_pers[:, 1] <= 1.0).all()

    # 4. Spread Heuristic
    b_spread = SpreadHeuristicBaseline().fit(X, y)
    p_spread = b_spread.predict_proba(X)
    assert (p_spread[:, 1] >= 0.0).all() and (p_spread[:, 1] <= 1.0).all()


# ---------------------------------------------------------------------------
# Test 6: ProbabilityCalibrator - Platt Scaling (Sigmoid)
# ---------------------------------------------------------------------------
def test_6_platt_scaling_calibration():
    np.random.seed(42)
    y_true = np.random.binomial(1, 0.2, size=500)
    # Uncalibrated overconfident probabilities
    y_prob_uncal = np.clip(y_true * 0.8 + np.random.normal(0.2, 0.1, size=500), 0.01, 0.99)

    calibrator = ProbabilityCalibrator(method="platt")
    calibrator.fit(y_true, y_prob_uncal)
    calibrated_probs = calibrator.predict_proba(y_prob_uncal)

    assert calibrator.is_fitted_ is True
    assert len(calibrated_probs) == len(y_prob_uncal)
    assert (calibrated_probs >= 0.0).all() and (calibrated_probs <= 1.0).all()


# ---------------------------------------------------------------------------
# Test 7: ProbabilityCalibrator - Isotonic Regression
# ---------------------------------------------------------------------------
def test_7_isotonic_regression_calibration():
    np.random.seed(42)
    y_true = np.random.binomial(1, 0.15, size=400)
    y_prob = np.clip(np.random.uniform(0.0, 1.0, size=400), 0.01, 0.99)

    calibrator = ProbabilityCalibrator(method="isotonic")
    calibrator.fit(y_true, y_prob)
    calibrated_probs = calibrator.predict_proba(y_prob)

    assert calibrator.is_fitted_ is True
    assert len(calibrated_probs) == 400
    assert (calibrated_probs >= 0.0).all() and (calibrated_probs <= 1.0).all()


# ---------------------------------------------------------------------------
# Test 8: ProbabilityCalibrator Train/Test Isolation
# ---------------------------------------------------------------------------
def test_8_calibration_train_test_isolation():
    y_train = np.array([0, 0, 0, 1, 0, 1, 0, 0, 1, 0] * 10)
    p_train = np.linspace(0.1, 0.9, 100)

    calibrator = ProbabilityCalibrator(method="platt")
    calibrator.fit(y_train, p_train)
    params_before = (calibrator.a_, calibrator.b_)

    # Evaluating test predictions must not modify learned parameters
    p_test = np.array([0.2, 0.5, 0.8])
    _ = calibrator.predict_proba(p_test)
    params_after = (calibrator.a_, calibrator.b_)

    assert params_before == params_after


# ---------------------------------------------------------------------------
# Test 9: ReliabilityAnalyzer & Expected Calibration Error (ECE)
# ---------------------------------------------------------------------------
def test_9_reliability_analyzer_and_ece():
    y_true = np.array([0, 0, 0, 0, 1, 0, 1, 1, 1, 1])
    y_prob = np.array([0.1, 0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9, 0.9])

    rel = ReliabilityAnalyzer.compute_reliability_curve(y_true, y_prob, n_bins=5)

    assert rel["sample_count"] == 10
    assert rel["positive_count"] == 5
    assert rel["expected_calibration_error"] >= 0.0
    assert rel["maximum_calibration_error"] >= 0.0
    assert len(rel["bins"]) == 5
    assert "brier_skill_score" in rel


# ---------------------------------------------------------------------------
# Test 10: ReliabilityAnalyzer Edge Cases (Single-Class, Boundaries)
# ---------------------------------------------------------------------------
def test_10_reliability_analyzer_edge_cases():
    # Empty
    empty_rel = ReliabilityAnalyzer.compute_reliability_curve([], [])
    assert empty_rel["status"] == "INSUFFICIENT_DATA"

    # All zeros (no busts)
    all_zeros_rel = ReliabilityAnalyzer.compute_reliability_curve(np.zeros(50), np.linspace(0.1, 0.3, 50))
    assert all_zeros_rel["positive_count"] == 0
    assert all_zeros_rel["expected_calibration_error"] >= 0.0

    # Perfect probability boundaries 0.0 and 1.0
    perf_rel = ReliabilityAnalyzer.compute_reliability_curve(np.array([0, 0, 1, 1]), np.array([0.0, 0.0, 1.0, 1.0]))
    assert perf_rel["brier_score"] == 0.0
    assert perf_rel["expected_calibration_error"] == 0.0


# ---------------------------------------------------------------------------
# Test 11: Lead-Time Degradation Stratification
# ---------------------------------------------------------------------------
def test_11_lead_time_stratification(multi_station_empirical_df):
    engine = EmpiricalEvidenceEngine()
    results = engine.run_lead_time_stratification(multi_station_empirical_df)

    assert "short_00_24h" in results
    assert "medium_25_48h" in results
    assert "extended_49_72h" in results
    assert results["short_00_24h"]["sample_count"] > 0
    assert results["medium_25_48h"]["sample_count"] > 0
    assert results["extended_49_72h"]["sample_count"] > 0


# ---------------------------------------------------------------------------
# Test 12: Location-Wise Granular Evaluation
# ---------------------------------------------------------------------------
def test_12_location_wise_evaluation(multi_station_empirical_df):
    engine = EmpiricalEvidenceEngine()
    loc_eval = engine.run_location_wise_evaluation(multi_station_empirical_df)

    assert loc_eval["summary"]["evaluated_locations_count"] == 20
    assert "delhi" in loc_eval["locations"]
    assert "mumbai" in loc_eval["locations"]
    assert "median_brier" in loc_eval["summary"]


# ---------------------------------------------------------------------------
# Test 13: Full Evidence Engine Split Evaluation with Calibration & Deltas
# ---------------------------------------------------------------------------
def test_13_full_evidence_engine_split_evaluation(multi_station_empirical_df):
    engine = EmpiricalEvidenceEngine(calibration_method="platt", bootstrap_iterations=50)
    splitter = LocationHeldOutSplitter()
    split = splitter.split(multi_station_empirical_df, held_out_locations=["bengaluru"])

    res = engine.evaluate_split_with_calibration(split)

    assert res["split_type"] == "location_held_out"
    assert res["held_out_locations"] == ["bengaluru"]
    assert "metrics_uncalibrated" in res
    assert "metrics_calibrated" in res
    assert "reliability_curve" in res
    assert "baseline_deltas" in res
    assert "bootstrap_confidence_intervals" in res
    assert "failure_analysis" in res
    assert "climatology" in res["baseline_deltas"]


# ---------------------------------------------------------------------------
# Test 14: Location-Held-Out (LOLO) Generalization Protocol
# ---------------------------------------------------------------------------
def test_14_location_held_out_generalization_protocol(multi_station_empirical_df):
    splitter = LocationHeldOutSplitter()
    split = splitter.split(multi_station_empirical_df, held_out_locations=["chennai", "kolkata"])

    # Guarantee disjoint sets
    assert set(split.train_locations).isdisjoint(set(split.held_out_locations))
    assert len(split.held_out_locations) == 2


# ---------------------------------------------------------------------------
# Test 15: Climate-Held-Out (LOCO) Generalization Protocol
# ---------------------------------------------------------------------------
def test_15_climate_held_out_generalization_protocol(multi_station_empirical_df):
    splitter = ClimateHeldOutSplitter()
    split = splitter.split(multi_station_empirical_df, held_out_climates=["Aw"], match_mode="exact")

    assert set(split.train_climates).isdisjoint(set(split.held_out_climates))
    assert "Aw" in split.held_out_climates


# ---------------------------------------------------------------------------
# Test 16: Ensemble Spread vs Error Association Hypothesis
# ---------------------------------------------------------------------------
def test_16_spread_error_association_hypothesis(multi_station_empirical_df):
    engine = EmpiricalEvidenceEngine()
    spread_res = engine.evaluate_spread_hypothesis(multi_station_empirical_df)

    assert spread_res["status"] == "VALID"
    assert "pearson_correlation" in spread_res
    assert "spearman_rank_correlation" in spread_res
    assert "strata_analysis" in spread_res
    assert "low_spread" in spread_res["strata_analysis"]
    assert "high_spread" in spread_res["strata_analysis"]


# ---------------------------------------------------------------------------
# Test 17: Spread Tertile Stratification
# ---------------------------------------------------------------------------
def test_17_spread_tertile_stratification(multi_station_empirical_df):
    engine = EmpiricalEvidenceEngine()
    res = engine.evaluate_spread_hypothesis(multi_station_empirical_df)

    low_mae = res["strata_analysis"]["low_spread"]["mean_absolute_error"]
    high_mae = res["strata_analysis"]["high_spread"]["mean_absolute_error"]
    assert high_mae >= low_mae


# ---------------------------------------------------------------------------
# Test 18: Bootstrap Confidence Intervals Reproducibility
# ---------------------------------------------------------------------------
def test_18_bootstrap_confidence_intervals_reproducibility():
    np.random.seed(42)
    yt = np.random.binomial(1, 0.1, size=300)
    yp = np.random.uniform(0.05, 0.35, size=300)

    engine1 = EmpiricalEvidenceEngine(random_seed=123, bootstrap_iterations=50)
    engine2 = EmpiricalEvidenceEngine(random_seed=123, bootstrap_iterations=50)

    ci1 = engine1.compute_bootstrap_ci(yt, yp)
    ci2 = engine2.compute_bootstrap_ci(yt, yp)

    assert ci1["pr_auc"]["ci_lower"] == ci2["pr_auc"]["ci_lower"]
    assert ci1["brier_score"]["mean"] == ci2["brier_score"]["mean"]


# ---------------------------------------------------------------------------
# Test 19: Failure Mode Attribution
# ---------------------------------------------------------------------------
def test_19_failure_mode_attribution(multi_station_empirical_df):
    engine = EmpiricalEvidenceEngine(bootstrap_iterations=20)
    splitter = LocationHeldOutSplitter()
    split = splitter.split(multi_station_empirical_df, held_out_locations=["srinagar"])

    res = engine.evaluate_split_with_calibration(split)
    fails = res["failure_analysis"]

    assert "false_negative_unwarned_busts" in fails
    assert "false_positive_overconfident_alarms" in fails
    assert fails["total_test_samples"] == len(split.df_test)


# ---------------------------------------------------------------------------
# Test 20: Statistical Data Sufficiency Gating
# ---------------------------------------------------------------------------
def test_20_data_sufficiency_gating():
    engine = EmpiricalEvidenceEngine(min_total_samples=50, min_positive_samples=5)

    # Insufficient samples (10 < 50)
    ci_small = engine.compute_bootstrap_ci(np.array([0, 1] * 5), np.array([0.1, 0.9] * 5))
    assert ci_small["status"] == "INSUFFICIENT_DATA"

    # Insufficient positives (0 < 5)
    ci_no_pos = engine.compute_bootstrap_ci(np.zeros(100), np.random.uniform(0.1, 0.4, 100))
    assert ci_no_pos["status"] == "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# Test 21: Reproducible Empirical Manifest & Hash Sensitivity
# ---------------------------------------------------------------------------
def test_21_empirical_manifest_and_hash_sensitivity(multi_station_empirical_df):
    engine = EmpiricalEvidenceEngine()
    m1 = engine.generate_manifest(
        experiment_id="exp_01",
        df=multi_station_empirical_df,
        results_dict={"lolo_bengaluru": 0.85},
    )

    assert m1.experiment_id == "exp_01"
    assert m1.total_records == len(multi_station_empirical_df)
    assert len(m1.dataset_content_sha256) == 64

    # Alter data float and verify hash change in manifest
    altered_df = multi_station_empirical_df.copy()
    altered_df.loc[0, "forecast_value"] += 0.1
    m2 = engine.generate_manifest(
        experiment_id="exp_02",
        df=altered_df,
        results_dict={"lolo_bengaluru": 0.85},
    )
    assert m1.dataset_content_sha256 != m2.dataset_content_sha256


# ---------------------------------------------------------------------------
# Test 22: Git Protection Against Scientific Binaries
# ---------------------------------------------------------------------------
def test_22_git_ignore_rules():
    gitignore_path = Path(".gitignore")
    assert gitignore_path.exists()
    content = gitignore_path.read_text(encoding="utf-8")
    assert "*.parquet" in content
    assert "*.joblib" in content
    assert "*.grib2" in content
    assert "data/historical/*" in content
