"""
Veyra Research — Grouped Block-Bootstrap Uncertainty Framework
Computes non-parametric empirical confidence intervals for verification metrics
using forecast-cycle grouping to respect temporal dependencies.

SCIENTIFIC PRINCIPLE:
Standard i.i.d. row bootstrap severely underestimates uncertainty in meteorological data
due to spatial and lead-time dependencies across the same forecast run.
Grouped bootstrap samples entire weekly forecast cycles (cycle_idx) as atomic blocks.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional, Any, Callable
import numpy as np
import pandas as pd
from sklearn.metrics import recall_score

from research.evaluation.metrics import (
    calculate_pr_auc,
    calculate_roc_auc,
    calculate_ece,
)


@dataclass
class MetricConfidenceInterval:
    """Confidence interval for a single metric."""
    metric_name: str
    point_estimate: float
    ci_lower_95: float
    ci_upper_95: float
    std_error: float
    n_resamples: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GroupedBootstrapReport:
    """Complete block-bootstrap uncertainty report across standard verification metrics."""
    model_name: str
    total_samples: int
    total_cycle_blocks: int
    n_resamples: int
    metrics_ci: Dict[str, MetricConfidenceInterval]
    scientific_disclaimer: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GroupedBootstrapEvaluator:
    """
    Executes cluster/block bootstrap resampling across unique forecast cycles.
    """

    def __init__(self, n_resamples: int = 500, alpha: float = 0.05, random_seed: int = 42):
        self.n_resamples = n_resamples
        self.alpha = alpha
        self.random_seed = random_seed

    def evaluate_bootstrap_ci(
        self,
        df_eval: pd.DataFrame,
        model_name: str,
        prob_col: str = "pred_prob",
        label_col: str = "bust_label",
        cycle_col: str = "cycle_idx",
        operational_threshold: float = 0.060,
    ) -> GroupedBootstrapReport:
        """
        Resamples cycle clusters and computes 95% CIs for PR-AUC, ROC-AUC, Brier, Recall, Specificity, ECE.
        """
        if df_eval.empty:
            return GroupedBootstrapReport(
                model_name=model_name,
                total_samples=0,
                total_cycle_blocks=0,
                n_resamples=self.n_resamples,
                metrics_ci={},
                scientific_disclaimer="UNVALIDATED: No samples available for bootstrap.",
            )

        unique_cycles = np.array(sorted(df_eval[cycle_col].unique()))
        n_cycles = len(unique_cycles)

        # Pre-group DataFrame rows by cycle for fast block-sampling
        cycle_groups = {c: df_eval[df_eval[cycle_col] == c] for c in unique_cycles}

        # 1. Point Estimates on full data
        p_full = df_eval[prob_col].values.astype(float)
        y_full = df_eval[label_col].values.astype(int)
        y_pred_full = (p_full >= operational_threshold).astype(int)

        point_pr_auc = calculate_pr_auc(p_full, y_full)
        point_roc_auc = calculate_roc_auc(p_full, y_full)
        point_brier = float(np.mean((p_full - y_full) ** 2))
        point_ece = calculate_ece(p_full, y_full)["ece"]

        # Confusion metrics
        tp = np.sum((y_pred_full == 1) & (y_full == 1))
        fn = np.sum((y_pred_full == 0) & (y_full == 1))
        tn = np.sum((y_pred_full == 0) & (y_full == 0))
        fp = np.sum((y_pred_full == 1) & (y_full == 0))

        point_recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        point_spec = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0

        # 2. Block Bootstrap Resampling
        rng = np.random.RandomState(self.random_seed)

        boot_pr_auc: List[float] = []
        boot_roc_auc: List[float] = []
        boot_brier: List[float] = []
        boot_ece: List[float] = []
        boot_recall: List[float] = []
        boot_spec: List[float] = []

        for _ in range(self.n_resamples):
            sampled_cycles = rng.choice(unique_cycles, size=n_cycles, replace=True)
            sampled_dfs = [cycle_groups[c] for c in sampled_cycles]
            boot_df = pd.concat(sampled_dfs, axis=0, ignore_index=True)

            p_boot = boot_df[prob_col].values.astype(float)
            y_boot = boot_df[label_col].values.astype(int)
            y_pred_b = (p_boot >= operational_threshold).astype(int)

            # Avoid single-class resamples
            if len(np.unique(y_boot)) < 2:
                continue

            pr_val = calculate_pr_auc(p_boot, y_boot)
            roc_val = calculate_roc_auc(p_boot, y_boot)
            br_val = float(np.mean((p_boot - y_boot) ** 2))
            ec_val = calculate_ece(p_boot, y_boot)["ece"]

            tp_b = np.sum((y_pred_b == 1) & (y_boot == 1))
            fn_b = np.sum((y_pred_b == 0) & (y_boot == 1))
            tn_b = np.sum((y_pred_b == 0) & (y_boot == 0))
            fp_b = np.sum((y_pred_b == 1) & (y_boot == 0))

            rec_val = float(tp_b / (tp_b + fn_b)) if (tp_b + fn_b) > 0 else 0.0
            spec_val = float(tn_b / (tn_b + fp_b)) if (tn_b + fp_b) > 0 else 0.0

            if not np.isnan(pr_val): boot_pr_auc.append(pr_val)
            if not np.isnan(roc_val): boot_roc_auc.append(roc_val)
            boot_brier.append(br_val)
            if not np.isnan(ec_val): boot_ece.append(ec_val)
            boot_recall.append(rec_val)
            boot_spec.append(spec_val)

        def _make_ci(name: str, point: float, values: List[float]) -> MetricConfidenceInterval:
            if len(values) < 10:
                return MetricConfidenceInterval(name, round(point, 4), round(point, 4), round(point, 4), 0.0, len(values))
            arr = np.array(values)
            low = float(np.percentile(arr, 100.0 * (self.alpha / 2.0)))
            high = float(np.percentile(arr, 100.0 * (1.0 - self.alpha / 2.0)))
            se = float(np.std(arr))
            return MetricConfidenceInterval(
                metric_name=name,
                point_estimate=round(point, 4),
                ci_lower_95=round(low, 4),
                ci_upper_95=round(high, 4),
                std_error=round(se, 4),
                n_resamples=len(values),
            )

        cis: Dict[str, MetricConfidenceInterval] = {
            "pr_auc": _make_ci("PR-AUC", point_pr_auc, boot_pr_auc),
            "roc_auc": _make_ci("ROC-AUC", point_roc_auc, boot_roc_auc),
            "brier_score": _make_ci("Brier Score", point_brier, boot_brier),
            "ece": _make_ci("Expected Calibration Error (ECE)", point_ece, boot_ece),
            "recall": _make_ci("Recall (@ Operational Threshold)", point_recall, boot_recall),
            "specificity": _make_ci("Specificity (@ Operational Threshold)", point_spec, boot_spec),
        }

        return GroupedBootstrapReport(
            model_name=model_name,
            total_samples=len(df_eval),
            total_cycle_blocks=n_cycles,
            n_resamples=self.n_resamples,
            metrics_ci=cis,
            scientific_disclaimer=(
                "Confidence intervals computed using 500 block-bootstrap resamples clustered on forecast cycles. "
                "Preserves spatial and lead-time dependency structure."
            ),
        )
