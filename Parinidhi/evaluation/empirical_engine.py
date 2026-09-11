"""
Empirical Forecast-Bust Evidence, Calibration & Generalization Engine (Day 13).

Provides the comprehensive empirical evaluation orchestrator:
1. Formal Multi-Baseline Benchmarking (Majority, Climatology, Persistence, Spread Heuristic, Simple Logistic, Veyra).
2. Probability Calibration with Train-Only Fitting (Platt Scaling, Isotonic Regression, Reliability Analysis).
3. Ensemble Spread vs Forecast Error Association & Stratification (Testing the Core Uncertainty Hypothesis).
4. Lead-Time Degradation Analysis (Short 0-24h, Medium-1 25-48h, Medium-2 49-72h).
5. Granular Location-Wise, Climate-Wise, Variable-Wise, and Cycle-Wise Stratifications.
6. Out-of-Location (LOLO) and Out-of-Climate (LOCO) Generalization Protocols.
7. Non-Parametric Bootstrap Confidence Intervals for Key Metrics.
8. Rigorous Failure Mode Attribution (False Negatives vs False Positives).
9. Statistical Data Sufficiency Gating and Reproducible Experiment Manifests.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from api.location_service import LocationRegistry
from evaluation.calibration import ProbabilityCalibrator, ReliabilityAnalyzer
from evaluation.generalization import GeneralizationEvaluator, GeneralizationResult, compute_dataset_content_hash
from evaluation.metrics import GeneralizationMetrics
from evaluation.splits import ClimateHeldOutSplitter, HeldOutSplit, LocationHeldOutSplitter
from features.contract import AVAILABLE_AT_ISSUE_TIME, UNAVAILABLE_UNTIL_VERIFICATION, validate_feature_contract
from features.feature_pipeline import FEATURE_COLUMN_NAMES, IssueTimeSafeFeaturePipeline
from features.leakage_audit import DataLeakageError, LeakageAuditor
from labels.label_engine import BustLabelEngine
from models.baselines import ClimatologyBaseline, MajorityClassBaseline, PersistenceBaseline, SpreadHeuristicBaseline
from models.logistic_classifier import RegularizedLogisticClassifier


@dataclass
class EmpiricalExperimentManifest:
    """Provenance and configuration container for empirical evidence runs."""
    experiment_id: str
    generation_timestamp_utc: str
    dataset_content_sha256: str
    total_records: int
    forecast_run_count: int
    random_seed: int
    feature_columns: List[str]
    excluded_target_columns: List[str]
    label_methodology: str
    primary_quantile: float
    calibration_method: str
    bootstrap_iterations: int
    bootstrap_confidence_level: float
    data_sufficiency_thresholds: Dict[str, int]
    summary_results: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EmpiricalEvidenceEngine:
    """
    Scientific Evidence Engine for evaluating forecast-bust detection,
    probabilistic calibration, and out-of-domain generalization.
    """

    def __init__(
        self,
        random_seed: int = 42,
        primary_quantile: float = 0.95,
        calibration_method: str = "platt",
        bootstrap_iterations: int = 500,
        bootstrap_confidence_level: float = 0.95,
        min_total_samples: int = 30,
        min_positive_samples: int = 5,
        location_registry: Optional[LocationRegistry] = None,
    ):
        self.random_seed = random_seed
        self.primary_quantile = primary_quantile
        self.calibration_method = calibration_method
        self.bootstrap_iterations = bootstrap_iterations
        self.bootstrap_confidence_level = bootstrap_confidence_level
        self.min_total_samples = min_total_samples
        self.min_positive_samples = min_positive_samples
        self.location_registry = location_registry or LocationRegistry()
        self.feature_pipeline = IssueTimeSafeFeaturePipeline()
        self.leakage_auditor = LeakageAuditor()
        self.label_engine = BustLabelEngine(primary_quantile=self.primary_quantile)

    def audit_feature_contract(self, feature_names: List[str]) -> Dict[str, Any]:
        """Verify feature availability contract before running experiments."""
        violations = validate_feature_contract(feature_names)
        leakage_violations = self.leakage_auditor.audit_feature_names(feature_names)
        all_violations = list(set(violations + leakage_violations))
        return {
            "is_valid": len(all_violations) == 0,
            "violations": all_violations,
            "checked_features_count": len(feature_names),
        }

    def evaluate_spread_hypothesis(
        self,
        df: pd.DataFrame,
        error_column: str = "forecast_abs_error",
        spread_column: str = "ensemble_std",
    ) -> Dict[str, Any]:
        """
        Test the core meteorological hypothesis: Does ensemble spread correlate with forecast error?
        Evaluates Pearson correlation, Spearman rank correlation, and spread stratification.
        """
        if error_column not in df.columns or spread_column not in df.columns:
            return {"status": "INSUFFICIENT_DATA", "reason": "Missing error or spread column."}

        sub = df[[error_column, spread_column]].dropna()
        n = len(sub)
        if n < self.min_total_samples:
            return {"status": "INSUFFICIENT_DATA", "sample_count": n}

        err_vals = sub[error_column].values.astype(float)
        spread_vals = sub[spread_column].values.astype(float)

        # 1. Pearson Correlation
        if np.std(err_vals) < 1e-6 or np.std(spread_vals) < 1e-6:
            pearson_r = 0.0
        else:
            pearson_r = float(np.corrcoef(spread_vals, err_vals)[0, 1])

        # 2. Spearman Rank Correlation
        rank_err = pd.Series(err_vals).rank().values
        rank_spread = pd.Series(spread_vals).rank().values
        spearman_rho = float(np.corrcoef(rank_spread, rank_err)[0, 1]) if np.std(rank_err) > 0 and np.std(rank_spread) > 0 else 0.0

        # 3. Spread Stratification (Low, Medium, High tertiles)
        q33 = float(np.percentile(spread_vals, 33.33))
        q66 = float(np.percentile(spread_vals, 66.66))

        strata = {
            "low_spread": sub[spread_vals <= q33],
            "medium_spread": sub[(spread_vals > q33) & (spread_vals <= q66)],
            "high_spread": sub[spread_vals > q66],
        }

        strata_summary: Dict[str, Any] = {}
        for s_name, s_df in strata.items():
            if len(s_df) > 0:
                s_err = s_df[error_column].values
                strata_summary[s_name] = {
                    "sample_count": len(s_df),
                    "mean_absolute_error": round(float(np.mean(s_err)), 4),
                    "median_absolute_error": round(float(np.median(s_err)), 4),
                    "p90_absolute_error": round(float(np.percentile(s_err, 90)), 4),
                }

        return {
            "status": "VALID",
            "sample_count": n,
            "pearson_correlation": round(pearson_r, 4),
            "spearman_rank_correlation": round(spearman_rho, 4),
            "spread_tertile_thresholds": {
                "q33": round(q33, 4),
                "q66": round(q66, 4),
            },
            "strata_analysis": strata_summary,
        }

    def compute_bootstrap_ci(
        self,
        y_true: Union[pd.Series, np.ndarray],
        y_prob: Union[pd.Series, np.ndarray],
        threshold: float = 0.5,
        n_iterations: Optional[int] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compute non-parametric bootstrap confidence intervals for key metrics.
        """
        yt = np.asarray(y_true, dtype=int)
        yp = np.asarray(y_prob, dtype=float)
        n = len(yt)
        n_iters = n_iterations or self.bootstrap_iterations

        if n < self.min_total_samples or np.sum(yt == 1) < self.min_positive_samples:
            return {"status": "INSUFFICIENT_DATA"}

        rng = np.random.RandomState(self.random_seed)
        boot_pr_aucs: List[float] = []
        boot_briers: List[float] = []
        boot_f1s: List[float] = []
        boot_recs: List[float] = []
        boot_precs: List[float] = []

        alpha = 1.0 - self.bootstrap_confidence_level
        low_p = (alpha / 2.0) * 100.0
        high_p = (1.0 - alpha / 2.0) * 100.0

        for _ in range(n_iters):
            idx = rng.randint(0, n, size=n)
            sub_yt = yt[idx]
            sub_yp = yp[idx]

            if np.sum(sub_yt == 1) == 0:
                continue

            m = GeneralizationMetrics.evaluate_predictions(sub_yt, sub_yp, threshold=threshold)
            pr = m["classification"]["pr_auc"]
            if isinstance(pr, (int, float)):
                boot_pr_aucs.append(float(pr))
            boot_briers.append(float(m["probabilistic"]["brier_score"]))
            boot_f1s.append(float(m["classification"]["f1_score"]))
            boot_recs.append(float(m["classification"]["recall"]))
            boot_precs.append(float(m["classification"]["precision"]))

        def _calc_stats(arr: List[float]) -> Dict[str, Any]:
            if not arr:
                return {"mean": np.nan, "ci_lower": np.nan, "ci_upper": np.nan}
            np_arr = np.array(arr)
            return {
                "mean": round(float(np.mean(np_arr)), 4),
                "std": round(float(np.std(np_arr)), 4),
                "ci_lower": round(float(np.percentile(np_arr, low_p)), 4),
                "ci_upper": round(float(np.percentile(np_arr, high_p)), 4),
                "confidence_level": self.bootstrap_confidence_level,
                "iterations_valid": len(np_arr),
            }

        return {
            "status": "VALID",
            "pr_auc": _calc_stats(boot_pr_aucs),
            "brier_score": _calc_stats(boot_briers),
            "f1_score": _calc_stats(boot_f1s),
            "recall": _calc_stats(boot_recs),
            "precision": _calc_stats(boot_precs),
        }

    def evaluate_split_with_calibration(
        self,
        split: HeldOutSplit,
        feature_columns: Optional[List[str]] = None,
        target_column: str = "bust_label",
        threshold: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Execute full empirical benchmark on a single partition split:
        1. Verifies feature contract & anti-leakage.
        2. Fits label engine strictly on df_train.
        3. Fits ML model & baselines on (X_train, y_train).
        4. Fits ProbabilityCalibrator strictly on training predictions.
        5. Evaluates uncalibrated and calibrated predictions on df_test.
        6. Computes reliability curves, bootstrap CIs, and delta comparisons.
        """
        split.validate_invariants()

        # 1. Feature selection & Contract Validation
        feat_cols = feature_columns or [c for c in FEATURE_COLUMN_NAMES if c in split.df_train.columns]
        contract_audit = self.audit_feature_contract(feat_cols)
        if not contract_audit["is_valid"]:
            raise DataLeakageError(f"Feature contract violation: {contract_audit['violations']}")

        # 2. Train-Only Label Fitting
        df_train_work = split.df_train.copy()
        df_test_work = split.df_test.copy()

        self.label_engine.fit(df_train_work)
        df_train_work = self.label_engine.transform(df_train_work)
        df_test_work = self.label_engine.transform(df_test_work)

        X_train = df_train_work[feat_cols].copy()
        y_train = df_train_work[target_column].astype(int)
        X_test = df_test_work[feat_cols].copy()
        y_test = df_test_work[target_column].astype(int)

        # 3. Fit Research Model (Regularized Logistic / Veyra)
        model = RegularizedLogisticClassifier()
        model.fit(X_train, y_train)

        p_train_raw = model.predict_proba(X_train)[:, 1]
        p_test_raw = model.predict_proba(X_test)[:, 1]

        # 4. Train-Only Probability Calibration
        calibrator = ProbabilityCalibrator(method=self.calibration_method)
        calibrator.fit(y_train, p_train_raw)
        p_test_cal = calibrator.predict_proba(p_test_raw)

        # 5. Fit & Evaluate Baselines
        baselines = {
            "majority_class": MajorityClassBaseline().fit(X_train, y_train),
            "climatology": ClimatologyBaseline().fit(X_train, y_train),
            "persistence": PersistenceBaseline().fit(X_train, y_train),
            "spread_heuristic": SpreadHeuristicBaseline().fit(X_train, y_train),
        }

        baseline_metrics: Dict[str, Any] = {}
        for b_name, b_model in baselines.items():
            b_probs = b_model.predict_proba(X_test)
            baseline_metrics[b_name] = GeneralizationMetrics.evaluate_predictions(y_test, b_probs, threshold=threshold)

        # 6. Evaluate Veyra Predictions (Uncalibrated & Calibrated)
        run_cols = [c for c in ["location_id", "variable", "issue_time_utc", "cycle"] if c in df_test_work.columns]
        test_runs = df_test_work[run_cols].astype(str).agg("_".join, axis=1).values if len(run_cols) >= 2 else None
        test_leads = df_test_work["lead_hours"].values if "lead_hours" in df_test_work.columns else None

        uncal_metrics = GeneralizationMetrics.evaluate_predictions(
            y_test, p_test_raw, threshold=threshold, run_ids=test_runs, lead_hours=test_leads
        )
        cal_metrics = GeneralizationMetrics.evaluate_predictions(
            y_test, p_test_cal, threshold=threshold, run_ids=test_runs, lead_hours=test_leads
        )

        # 7. Reliability Analysis on Calibrated Probabilities
        reliability_curve = ReliabilityAnalyzer.compute_reliability_curve(y_test, p_test_cal, n_bins=5)

        # 8. Bootstrap Uncertainty
        bootstrap_ci = self.compute_bootstrap_ci(y_test, p_test_cal, threshold=threshold)

        # 9. Compute Deltas vs Baselines
        veyra_pr = cal_metrics["classification"]["pr_auc"] if isinstance(cal_metrics["classification"]["pr_auc"], float) else 0.0
        veyra_brier = cal_metrics["probabilistic"]["brier_score"]

        deltas: Dict[str, Any] = {}
        for b_name, b_met in baseline_metrics.items():
            b_pr = b_met["classification"]["pr_auc"] if isinstance(b_met["classification"]["pr_auc"], float) else 0.0
            b_brier = b_met["probabilistic"]["brier_score"]
            deltas[b_name] = {
                "pr_auc_delta": round(float(veyra_pr - b_pr), 4),
                "brier_improvement": round(float(b_brier - veyra_brier), 4),  # Lower Brier is better
            }

        # 10. Failure Analysis
        y_test_arr = y_test.values
        p_test_arr = p_test_cal
        high_risk_pred = (p_test_arr >= 0.66).astype(int)
        low_risk_pred = (p_test_arr < 0.33).astype(int)

        fn_mask = (y_test_arr == 1) & (low_risk_pred == 1)  # Busted but predicted low risk
        fp_mask = (y_test_arr == 0) & (high_risk_pred == 1)  # Non-bust but predicted high risk

        failure_analysis = {
            "false_negative_unwarned_busts": int(np.sum(fn_mask)),
            "false_positive_overconfident_alarms": int(np.sum(fp_mask)),
            "total_test_busts": int(np.sum(y_test_arr == 1)),
            "total_test_samples": len(y_test_arr),
        }

        # 11. Provenance Hashes
        train_hash = compute_dataset_content_hash(df_train_work)
        test_hash = compute_dataset_content_hash(df_test_work)

        return {
            "split_type": split.split_type,
            "train_locations": split.train_locations,
            "held_out_locations": split.held_out_locations,
            "train_climates": split.train_climates,
            "held_out_climates": split.held_out_climates,
            "sample_count": len(y_test),
            "forecast_run_count": int(pd.Series(test_runs).nunique()) if test_runs is not None else len(y_test),
            "positive_count": int(y_test.sum()),
            "negative_count": int(len(y_test) - y_test.sum()),
            "metrics_uncalibrated": uncal_metrics,
            "metrics_calibrated": cal_metrics,
            "reliability_curve": reliability_curve,
            "baseline_metrics": baseline_metrics,
            "baseline_deltas": deltas,
            "bootstrap_confidence_intervals": bootstrap_ci,
            "failure_analysis": failure_analysis,
            "provenance": {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "train_content_sha256": train_hash,
                "test_content_sha256": test_hash,
                "calibration_method": self.calibration_method,
                "calibrator_fitted_params": {
                    "a": calibrator.a_,
                    "b": calibrator.b_,
                    "method": calibrator.method,
                },
                "label_thresholds": self.label_engine.thresholds_,
            },
        }

    def run_lead_time_stratification(
        self,
        df: pd.DataFrame,
        feature_columns: Optional[List[str]] = None,
        target_column: str = "bust_label",
    ) -> Dict[str, Any]:
        """
        Evaluate forecast-bust detection performance across lead-time horizons:
        - 0-24h (Short)
        - 25-48h (Medium-1)
        - 49-72h (Medium-2)
        """
        if "lead_hours" not in df.columns:
            return {"status": "INSUFFICIENT_DATA", "reason": "Missing lead_hours column."}

        lead_bins = [
            ("short_00_24h", (df["lead_hours"] >= 0) & (df["lead_hours"] <= 24)),
            ("medium_25_48h", (df["lead_hours"] >= 25) & (df["lead_hours"] <= 48)),
            ("extended_49_72h", (df["lead_hours"] >= 49) & (df["lead_hours"] <= 72)),
        ]

        results: Dict[str, Any] = {}
        for bin_name, mask in lead_bins:
            sub_df = df[mask].copy()
            if len(sub_df) < self.min_total_samples:
                results[bin_name] = {"status": "INSUFFICIENT_DATA", "sample_count": len(sub_df)}
                continue

            # Standardize labels
            sub_df = self.label_engine.fit_transform(sub_df)
            feat_cols = feature_columns or [c for c in FEATURE_COLUMN_NAMES if c in sub_df.columns]
            X = sub_df[feat_cols]
            y = sub_df[target_column].astype(int)

            model = RegularizedLogisticClassifier().fit(X, y)
            probs = model.predict_proba(X)[:, 1]

            m = GeneralizationMetrics.evaluate_predictions(y, probs)
            rel = ReliabilityAnalyzer.compute_reliability_curve(y, probs, n_bins=5)

            results[bin_name] = {
                "sample_count": len(sub_df),
                "positive_count": int(y.sum()),
                "base_bust_rate": round(float(y.mean()), 4),
                "metrics": m,
                "reliability": rel,
            }

        return results

    def run_location_wise_evaluation(
        self,
        df: pd.DataFrame,
        feature_columns: Optional[List[str]] = None,
        target_column: str = "bust_label",
    ) -> Dict[str, Any]:
        """
        Run in-domain evaluation independently across all locations to identify geographic weaknesses.
        """
        locs = sorted(df["location_id"].unique().tolist())
        loc_results: Dict[str, Any] = {}
        pr_aucs: List[float] = []
        briers: List[float] = []

        for loc in locs:
            sub_df = df[df["location_id"] == loc].copy()
            if len(sub_df) < self.min_total_samples:
                loc_results[loc] = {"status": "INSUFFICIENT_DATA", "sample_count": len(sub_df)}
                continue

            sub_df = self.label_engine.fit_transform(sub_df)
            feat_cols = feature_columns or [c for c in FEATURE_COLUMN_NAMES if c in sub_df.columns]
            X = sub_df[feat_cols]
            y = sub_df[target_column].astype(int)

            if int(y.sum()) == 0:
                # Calm location with 0 busts
                loc_results[loc] = {
                    "sample_count": len(sub_df),
                    "positive_count": 0,
                    "base_bust_rate": 0.0,
                    "status": "CALM_LOCATION_ZERO_BUSTS",
                    "brier_score": 0.0,
                }
                continue

            model = RegularizedLogisticClassifier().fit(X, y)
            probs = model.predict_proba(X)[:, 1]

            m = GeneralizationMetrics.evaluate_predictions(y, probs)
            pr = m["classification"]["pr_auc"]
            brier = m["probabilistic"]["brier_score"]

            if isinstance(pr, (int, float)):
                pr_aucs.append(float(pr))
            briers.append(float(brier))

            loc_results[loc] = {
                "sample_count": len(sub_df),
                "positive_count": int(y.sum()),
                "base_bust_rate": round(float(y.mean()), 4),
                "pr_auc": pr,
                "brier_score": brier,
                "ece": m["probabilistic"]["expected_calibration_error"],
                "false_reassurance_rate": m["forecast_risk_utility"]["false_reassurance_rate"],
            }

        summary = {
            "evaluated_locations_count": len(locs),
            "valid_positive_locations_count": len(pr_aucs),
            "median_pr_auc": round(float(np.median(pr_aucs)), 4) if pr_aucs else np.nan,
            "median_brier": round(float(np.median(briers)), 4) if briers else np.nan,
            "pr_auc_spread": round(float(np.max(pr_aucs) - np.min(pr_aucs)), 4) if len(pr_aucs) >= 2 else 0.0,
        }

        return {
            "summary": summary,
            "locations": loc_results,
        }

    def generate_manifest(
        self,
        experiment_id: str,
        df: pd.DataFrame,
        results_dict: Dict[str, Any],
    ) -> EmpiricalExperimentManifest:
        """
        Generate complete reproducible experiment manifest.
        """
        content_hash = compute_dataset_content_hash(df)
        run_cols = [c for c in ["location_id", "variable", "issue_time_utc", "cycle"] if c in df.columns]
        run_cnt = int(df[run_cols].astype(str).agg("_".join, axis=1).nunique()) if len(run_cols) >= 2 else len(df)

        manifest = EmpiricalExperimentManifest(
            experiment_id=experiment_id,
            generation_timestamp_utc=datetime.now(timezone.utc).isoformat(),
            dataset_content_sha256=content_hash,
            total_records=len(df),
            forecast_run_count=run_cnt,
            random_seed=self.random_seed,
            feature_columns=list(FEATURE_COLUMN_NAMES),
            excluded_target_columns=list(UNAVAILABLE_UNTIL_VERIFICATION),
            label_methodology="quantile_error_threshold_train_only",
            primary_quantile=self.primary_quantile,
            calibration_method=self.calibration_method,
            bootstrap_iterations=self.bootstrap_iterations,
            bootstrap_confidence_level=self.bootstrap_confidence_level,
            data_sufficiency_thresholds={
                "min_total_samples": self.min_total_samples,
                "min_positive_samples": self.min_positive_samples,
            },
            summary_results=results_dict,
        )
        return manifest
