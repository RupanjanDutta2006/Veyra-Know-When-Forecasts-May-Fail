"""
Generalization Evaluation Framework for Out-of-Location and Out-of-Climate Forecast Risk.

Orchestrates:
1. Location-Held-Out Evaluation Protocol.
2. Climate-Held-Out (Köppen) and Meteorological-Regime-Held-Out Evaluation Protocols.
3. Cross-Location & Cross-Climate Leave-One-Out Cross-Validation.
4. Comparative Benchmarking against Climatology, Persistence, and Spread Heuristics.
5. Strict anti-leakage auditing, verifiable label provenance, and reproducible dataset-content hashing.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, Type, Union
import numpy as np
import pandas as pd

from api.location_service import LocationRegistry
from evaluation.metrics import GeneralizationMetrics
from evaluation.splits import ClimateHeldOutSplitter, HeldOutSplit, LocationHeldOutSplitter
from features.feature_pipeline import FEATURE_COLUMN_NAMES
from features.leakage_audit import DataLeakageError, LeakageAuditor
from labels.label_engine import BustLabelEngine
from models.baselines import ClimatologyBaseline, MajorityClassBaseline, PersistenceBaseline, SpreadHeuristicBaseline
from models.logistic_classifier import RegularizedLogisticClassifier


def compute_dataset_content_hash(df: pd.DataFrame) -> str:
    """
    Compute a deterministic SHA-256 hash over sorted core content columns of a DataFrame.
    Ensures dataset-content provenance is bit-for-bit verifiable across environments.
    """
    if df.empty:
        return "empty"
    sort_cols = [c for c in ["location_id", "variable", "issue_time_utc", "valid_time_utc"] if c in df.columns]
    content_cols = [
        c for c in ["location_id", "variable", "issue_time_utc", "valid_time_utc", "forecast_value", "truth_value", "forecast_error"]
        if c in df.columns
    ]
    if not content_cols:
        content_cols = list(df.columns[:10])

    df_sorted = df.sort_values(by=sort_cols).reset_index(drop=True) if sort_cols else df.reset_index(drop=True)
    csv_bytes = df_sorted[content_cols].to_csv(index=False, float_format="%.4f").encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


@dataclass
class GeneralizationResult:
    """Structured report container for generalization evaluation runs."""
    evaluation_type: str
    train_locations: List[str]
    held_out_locations: List[str]
    train_climate_regimes: List[str]
    held_out_climate_regimes: List[str]
    sample_count: int
    forecast_run_count: int
    positive_count: int
    negative_count: int
    metrics: Dict[str, Any]
    train_metrics: Dict[str, Any]
    baseline_metrics: Dict[str, Dict[str, Any]]
    generalization_gap: Dict[str, Any]
    feature_columns: List[str]
    model_version: str
    split_definition: Dict[str, Any]
    provenance: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to a clean dictionary."""
        return asdict(self)

    def summary(self) -> str:
        """Human-readable scientific summary string."""
        roc = self.metrics.get("classification", {}).get("roc_auc", "N/A")
        pr = self.metrics.get("classification", {}).get("pr_auc", "N/A")
        brier = self.metrics.get("probabilistic", {}).get("brier_score", "N/A")
        ece = self.metrics.get("probabilistic", {}).get("expected_calibration_error", "N/A")
        frr = self.metrics.get("forecast_risk_utility", {}).get("false_reassurance_rate", "N/A")

        return (
            f"=== Generalization Evaluation [{self.evaluation_type}] ===\n"
            f"Train Locations ({len(self.train_locations)}): {self.train_locations}\n"
            f"Held-Out Locations ({len(self.held_out_locations)}): {self.held_out_locations}\n"
            f"Train Climates: {self.train_climate_regimes}\n"
            f"Held-Out Climates: {self.held_out_climate_regimes}\n"
            f"Test Samples: {self.sample_count} (Busts: {self.positive_count}, Non-Busts: {self.negative_count})\n"
            f"--- Performance on Held-Out Test Set ---\n"
            f"  ROC-AUC: {roc} | PR-AUC: {pr} | Brier Score: {brier} | ECE: {ece}\n"
            f"  False Reassurance Rate: {frr}\n"
        )


class GeneralizationEvaluator:
    """
    Evaluates out-of-domain generalization across locations, Köppen zones, and meteorological regimes.
    """

    def __init__(
        self,
        location_registry: Optional[LocationRegistry] = None,
        leakage_auditor: Optional[LeakageAuditor] = None,
        default_feature_columns: Optional[List[str]] = None,
        model_version: str = "2.0.0-research-eval",
    ):
        self.location_registry = location_registry or LocationRegistry()
        self.leakage_auditor = leakage_auditor or LeakageAuditor()
        self.default_feature_columns = default_feature_columns or FEATURE_COLUMN_NAMES
        self.model_version = model_version
        self.loc_splitter = LocationHeldOutSplitter(self.location_registry)
        self.clim_splitter = ClimateHeldOutSplitter(self.location_registry)

    def evaluate_split(
        self,
        split: HeldOutSplit,
        feature_columns: Optional[List[str]] = None,
        model_factory: Optional[Callable[[], Any]] = None,
        target_column: str = "bust_label",
        primary_quantile: float = 0.95,
        threshold: float = 0.5,
        force_refit_labels: bool = True,
        label_provenance: Optional[Dict[str, Any]] = None,
    ) -> GeneralizationResult:
        """
        Train a research model on df_train and evaluate generalization performance on df_test.

        Args:
            split: HeldOutSplit partition.
            feature_columns: Feature subset (defaults to issue-time safe FEATURE_COLUMN_NAMES).
            model_factory: Callable returning an unfitted model instance.
            target_column: Name of bust label column.
            primary_quantile: Bust definition quantile for BustLabelEngine.
            threshold: Probability threshold for binary decision metrics.
            force_refit_labels: If True, refits BustLabelEngine strictly on df_train.
            label_provenance: Verification dictionary if using pre-computed labels.

        Returns:
            GeneralizationResult with complete provenance and metrics.
        """
        # 1. Feature selection & Anti-Leakage Audit
        feat_cols = feature_columns or [c for c in self.default_feature_columns if c in split.df_train.columns]
        if not feat_cols:
            raise ValueError("No valid feature columns available in training DataFrame.")

        # Assert no target/future leakage in feature columns
        violations = self.leakage_auditor.audit_feature_names(feat_cols)
        if violations:
            raise DataLeakageError(f"Data Leakage Audit FAILED in feature list: {violations}")

        # 2. Label Preparation with Verifiable Provenance:
        df_train_work = split.df_train.copy()
        df_test_work = split.df_test.copy()
        fitted_thresholds: Dict[str, Any] = {}

        has_labels = target_column in df_train_work.columns and target_column in df_test_work.columns

        if not has_labels or force_refit_labels:
            # Fit BustLabelEngine strictly on training data
            label_engine = BustLabelEngine(primary_quantile=primary_quantile)
            label_engine.fit(df_train_work)
            df_train_work = label_engine.transform(df_train_work)
            df_test_work = label_engine.transform(df_test_work)
            fitted_thresholds = label_engine.thresholds_
            label_provenance_meta = {
                "source": "train_fitted_bust_label_engine",
                "fit_partition": "df_train_only",
                "primary_quantile": primary_quantile,
                "thresholds": fitted_thresholds,
            }
        else:
            # Pre-existing labels supplied: require verifiable provenance
            if label_provenance is None or label_provenance.get("fit_partition") != "train_only":
                raise ValueError(
                    "Unverifiable label provenance! Pre-computed labels cannot be trusted without explicit "
                    "proof of train-only threshold fitting. Set force_refit_labels=True to fit safely."
                )
            label_provenance_meta = label_provenance

        X_train = df_train_work[feat_cols].copy()
        y_train = df_train_work[target_column].astype(int)

        X_test = df_test_work[feat_cols].copy()
        y_test = df_test_work[target_column].astype(int)

        # 3. Fit Research Model on Training Set
        model = model_factory() if model_factory is not None else RegularizedLogisticClassifier()
        if hasattr(model, "fit"):
            model.fit(X_train, y_train)

        # Predict probabilities
        if hasattr(model, "predict_proba"):
            p_train = model.predict_proba(X_train)
            p_test = model.predict_proba(X_test)
        else:
            p_train = model.predict(X_train)
            p_test = model.predict(X_test)

        # Extract run IDs and lead hours for dependence-aware grouped diagnostics
        run_cols = [c for c in ["location_id", "variable", "issue_time_utc", "cycle"] if c in df_test_work.columns]
        test_run_ids = df_test_work[run_cols].astype(str).agg("_".join, axis=1) if len(run_cols) >= 2 else None
        test_leads = df_test_work["lead_hours"].values if "lead_hours" in df_test_work.columns else None

        train_run_cols = [c for c in ["location_id", "variable", "issue_time_utc", "cycle"] if c in df_train_work.columns]
        train_run_ids = df_train_work[train_run_cols].astype(str).agg("_".join, axis=1) if len(train_run_cols) >= 2 else None
        train_leads = df_train_work["lead_hours"].values if "lead_hours" in df_train_work.columns else None

        # 4. Compute Test and In-Sample Metrics
        test_metrics = GeneralizationMetrics.evaluate_predictions(
            y_test, p_test, threshold=threshold, run_ids=test_run_ids, lead_hours=test_leads
        )
        train_metrics = GeneralizationMetrics.evaluate_predictions(
            y_train, p_train, threshold=threshold, run_ids=train_run_ids, lead_hours=train_leads
        )

        # 5. Fit & Evaluate Standard Baselines on Test Set
        baseline_metrics = self._evaluate_baselines(X_train, y_train, X_test, y_test, threshold=threshold)

        # 6. Generalization Gap Calculation
        gap = self._compute_generalization_gap(train_metrics, test_metrics)

        # 7. Dataset-Content Provenance & Checksums
        train_content_hash = compute_dataset_content_hash(df_train_work)
        test_content_hash = compute_dataset_content_hash(df_test_work)

        forecast_run_cnt = int(test_run_ids.nunique()) if test_run_ids is not None else len(df_test_work)
        records_per_run = round(len(df_test_work) / max(forecast_run_cnt, 1), 2)

        provenance = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "train_row_count": len(df_train_work),
            "test_row_count": len(df_test_work),
            "test_forecast_run_count": forecast_run_cnt,
            "records_per_run_avg": records_per_run,
            "train_content_sha256": train_content_hash,
            "test_content_sha256": test_content_hash,
            "feature_hash_sha256": hashlib.sha256(",".join(feat_cols).encode("utf-8")).hexdigest(),
            "train_locations_hash": hashlib.sha256(",".join(sorted(split.train_locations)).encode("utf-8")).hexdigest(),
            "held_out_locations_hash": hashlib.sha256(",".join(sorted(split.held_out_locations)).encode("utf-8")).hexdigest(),
            "label_provenance": label_provenance_meta,
        }

        return GeneralizationResult(
            evaluation_type=split.split_type,
            train_locations=split.train_locations,
            held_out_locations=split.held_out_locations,
            train_climate_regimes=split.train_climates,
            held_out_climate_regimes=split.held_out_climates,
            sample_count=len(y_test),
            forecast_run_count=forecast_run_cnt,
            positive_count=int(y_test.sum()),
            negative_count=int(len(y_test) - y_test.sum()),
            metrics=test_metrics,
            train_metrics=train_metrics,
            baseline_metrics=baseline_metrics,
            generalization_gap=gap,
            feature_columns=feat_cols,
            model_version=self.model_version,
            split_definition=split.split_metadata,
            provenance=provenance,
        )

    def evaluate_location_held_out(
        self,
        df: pd.DataFrame,
        held_out_locations: Union[str, List[str]],
        feature_columns: Optional[List[str]] = None,
        model_factory: Optional[Callable[[], Any]] = None,
        temporal_train_cutoff: Optional[str] = None,
        threshold: float = 0.5,
    ) -> GeneralizationResult:
        """Run Location-Held-Out Generalization Evaluation with optional two-sided temporal cutoff."""
        split = self.loc_splitter.split(
            df,
            held_out_locations=held_out_locations,
            temporal_train_cutoff=temporal_train_cutoff,
        )
        return self.evaluate_split(
            split,
            feature_columns=feature_columns,
            model_factory=model_factory,
            threshold=threshold,
        )

    def evaluate_climate_held_out(
        self,
        df: pd.DataFrame,
        held_out_climates: Union[str, List[str]],
        climate_column: str = "climate_zone",
        match_mode: str = "exact",
        feature_columns: Optional[List[str]] = None,
        model_factory: Optional[Callable[[], Any]] = None,
        threshold: float = 0.5,
    ) -> GeneralizationResult:
        """Run Köppen Climate Zone Holdout Evaluation."""
        split = self.clim_splitter.split(
            df,
            held_out_climates=held_out_climates,
            climate_column=climate_column,
            match_mode=match_mode,
        )
        return self.evaluate_split(
            split,
            feature_columns=feature_columns,
            model_factory=model_factory,
            threshold=threshold,
        )

    def evaluate_meteorological_regime_held_out(
        self,
        df: pd.DataFrame,
        held_out_regimes: Union[str, List[str]],
        match_mode: str = "contains",
        feature_columns: Optional[List[str]] = None,
        model_factory: Optional[Callable[[], Any]] = None,
        threshold: float = 0.5,
    ) -> GeneralizationResult:
        """Run Physical Meteorological Regime Holdout Evaluation (e.g. 'Semi-Arid', 'Himalayan', 'Coastal')."""
        return self.evaluate_climate_held_out(
            df,
            held_out_climates=held_out_regimes,
            climate_column="meteorological_regime",
            match_mode=match_mode,
            feature_columns=feature_columns,
            model_factory=model_factory,
            threshold=threshold,
        )

    def run_leave_one_location_out(
        self,
        df: pd.DataFrame,
        feature_columns: Optional[List[str]] = None,
        model_factory: Optional[Callable[[], Any]] = None,
    ) -> List[GeneralizationResult]:
        """Run full Leave-One-Location-Out cross-validation across all locations in df."""
        results = []
        for split in self.loc_splitter.generate_leave_one_location_out(df):
            res = self.evaluate_split(
                split,
                feature_columns=feature_columns,
                model_factory=model_factory,
            )
            results.append(res)
        return results

    def run_leave_one_climate_out(
        self,
        df: pd.DataFrame,
        climate_column: str = "climate_zone",
        feature_columns: Optional[List[str]] = None,
        model_factory: Optional[Callable[[], Any]] = None,
    ) -> List[GeneralizationResult]:
        """Run full Leave-One-Climate-Out cross-validation across all climate zones in df."""
        results = []
        for split in self.clim_splitter.generate_leave_one_climate_out(df, climate_column=climate_column):
            res = self.evaluate_split(
                split,
                feature_columns=feature_columns,
                model_factory=model_factory,
            )
            results.append(res)
        return results

    def _evaluate_baselines(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        threshold: float = 0.5,
    ) -> Dict[str, Dict[str, Any]]:
        """Fit and evaluate baseline models strictly on train set and test on held-out set."""
        baselines = {
            "climatology": ClimatologyBaseline().fit(X_train, y_train),
            "persistence": PersistenceBaseline().fit(X_train, y_train),
            "spread_heuristic": SpreadHeuristicBaseline().fit(X_train, y_train),
            "majority_class": MajorityClassBaseline().fit(X_train, y_train),
        }

        results = {}
        for name, bl in baselines.items():
            p_test = bl.predict_proba(X_test)
            metrics = GeneralizationMetrics.evaluate_predictions(y_test, p_test, threshold=threshold)
            results[name] = {
                "brier_score": metrics["probabilistic"]["brier_score"],
                "roc_auc": metrics["classification"]["roc_auc"],
                "pr_auc": metrics["classification"]["pr_auc"],
                "false_reassurance_rate": metrics["forecast_risk_utility"]["false_reassurance_rate"],
            }
        return results

    def _compute_generalization_gap(
        self,
        train_metrics: Dict[str, Any],
        test_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculate in-sample vs out-of-domain generalization performance delta."""
        train_brier = train_metrics.get("probabilistic", {}).get("brier_score", 0.0)
        test_brier = test_metrics.get("probabilistic", {}).get("brier_score", 0.0)
        delta_brier = round(float(test_brier - train_brier), 4)

        train_pr = train_metrics.get("classification", {}).get("pr_auc")
        test_pr = test_metrics.get("classification", {}).get("pr_auc")
        delta_pr = round(float(train_pr - test_pr), 4) if isinstance(train_pr, (int, float)) and isinstance(test_pr, (int, float)) else None

        train_roc = train_metrics.get("classification", {}).get("roc_auc")
        test_roc = test_metrics.get("classification", {}).get("roc_auc")
        delta_roc = round(float(train_roc - test_roc), 4) if isinstance(train_roc, (int, float)) and isinstance(test_roc, (int, float)) else None

        return {
            "brier_score_degradation": delta_brier,
            "pr_auc_degradation": delta_pr,
            "roc_auc_degradation": delta_roc,
            "transfer_status": "STRONG" if delta_brier <= 0.05 else ("MODERATE" if delta_brier <= 0.15 else "DEGRADED"),
        }
