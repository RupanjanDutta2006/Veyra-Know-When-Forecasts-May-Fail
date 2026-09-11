"""
Veyra Research — Model Comparison Framework
Unified benchmark runner comparing baselines (E0, E1a, E1b, E2), production V2 (E3),
and challengers (E4 Quantile Mesh, E5 Parametric Student-t).

SCIENTIFIC PRINCIPLES:
- Evaluates on identical held-out partitions.
- Zero data leakage between train/val and test.
- Reports comprehensive deterministic & probabilistic metrics.
- Computes empirical BSS against both Climatology (E0) and Fair Ensemble (E1b).
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional, Any, Callable
import numpy as np
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

from research.evaluation.metrics import (
    calculate_brier_skill_score,
    calculate_ece,
    calculate_pr_auc,
    calculate_roc_auc,
    calculate_pinball_loss,
    calculate_crps_empirical,
    calculate_picp,
)


@dataclass
class ModelEvaluationMetrics:
    """Standardized evaluation metrics for a single model."""
    model_id: str
    model_name: str
    model_type: str  # 'baseline' | 'production_v2' | 'error_distribution' | 'parametric'
    n_samples: int
    pr_auc: float
    roc_auc: float
    brier_score: float
    bss_vs_climatology: float
    bss_vs_fair_ensemble: float
    ece: float
    precision: float
    recall: float
    f1: float
    specificity: float
    false_positive_rate: float
    confusion_matrix: List[List[int]]
    reliability_knot_centers: List[float] = field(default_factory=list)
    reliability_knot_accuracies: List[float] = field(default_factory=list)
    # Probabilistic / Error distribution specific metrics
    crps: Optional[float] = None
    pinball_loss: Optional[float] = None
    picp_90: Optional[float] = None
    mean_interval_width: Optional[float] = None
    tail_exceedance_error: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ModelComparisonFramework:
    """
    Executes standardized multi-model benchmarking on a shared dataset split.
    """

    def __init__(self, operational_threshold: float = 0.060):
        self.operational_threshold = operational_threshold

    def evaluate_predictions(
        self,
        model_id: str,
        model_name: str,
        model_type: str,
        probs: np.ndarray,
        labels: np.ndarray,
        ref_clim_probs: np.ndarray,
        ref_fair_probs: np.ndarray,
        quantiles: Optional[np.ndarray] = None,
        true_errors: Optional[np.ndarray] = None,
        quantile_levels: Optional[np.ndarray] = None,
    ) -> ModelEvaluationMetrics:
        """
        Compute standard verification metrics for predicted bust probabilities.
        """
        valid_mask = (~np.isnan(probs)) & (~np.isnan(labels))
        p = np.clip(probs[valid_mask], 0.0, 1.0)
        y = labels[valid_mask].astype(int)
        p_clim = ref_clim_probs[valid_mask] if ref_clim_probs is not None else np.full_like(p, np.mean(y))
        p_fair = ref_fair_probs[valid_mask] if ref_fair_probs is not None else p_clim

        n_samples = int(len(p))
        if n_samples == 0:
            return ModelEvaluationMetrics(
                model_id=model_id,
                model_name=model_name,
                model_type=model_type,
                n_samples=0,
                pr_auc=np.nan,
                roc_auc=np.nan,
                brier_score=np.nan,
                bss_vs_climatology=np.nan,
                bss_vs_fair_ensemble=np.nan,
                ece=np.nan,
                precision=np.nan,
                recall=np.nan,
                f1=np.nan,
                specificity=np.nan,
                false_positive_rate=np.nan,
                confusion_matrix=[[0, 0], [0, 0]],
            )

        # Binary decision classifications at operational threshold
        y_pred = (p >= self.operational_threshold).astype(int)

        pr_auc_val = calculate_pr_auc(p, y)
        roc_auc_val = calculate_roc_auc(p, y)
        brier_val = float(np.mean((p - y) ** 2))
        bss_clim = calculate_brier_skill_score(p, y, p_clim)
        bss_fair = calculate_brier_skill_score(p, y, p_fair)
        ece_dict = calculate_ece(p, y, n_bins=10)

        # Confusion Matrix metrics
        cm = confusion_matrix(y, y_pred, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1_val = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        spec = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
        fpr = float(fp / (tn + fp)) if (tn + fp) > 0 else 0.0

        # Distribution / Quantile metrics if available
        crps_val = None
        pinball_val = None
        picp_val = None
        interval_width = None
        tail_err = None

        if quantiles is not None and true_errors is not None and quantile_levels is not None:
            q_valid = quantiles[valid_mask]
            te_valid = true_errors[valid_mask]
            pinball_val = calculate_pinball_loss(q_valid, te_valid, quantile_levels)

            # Approximation of CRPS across samples
            crps_list = [
                calculate_crps_empirical(q_valid[i], quantile_levels, float(te_valid[i]))
                for i in range(min(1000, len(q_valid)))
            ]
            crps_val = float(np.nanmean(crps_list))

            # 90% Prediction interval (e.g. index 1 (q0.05) to index -2 (q0.95))
            if q_valid.shape[-1] >= 5:
                lower_q = q_valid[..., 1]
                upper_q = q_valid[..., -2]
                picp_val = calculate_picp(lower_q, upper_q, te_valid)
                interval_width = float(np.nanmean(upper_q - lower_q))
                tail_exceed = np.mean(te_valid > upper_q)
                tail_err = float(abs(tail_exceed - 0.05))

        return ModelEvaluationMetrics(
            model_id=model_id,
            model_name=model_name,
            model_type=model_type,
            n_samples=n_samples,
            pr_auc=round(pr_auc_val, 4) if not np.isnan(pr_auc_val) else np.nan,
            roc_auc=round(roc_auc_val, 4) if not np.isnan(roc_auc_val) else np.nan,
            brier_score=round(brier_val, 4),
            bss_vs_climatology=round(bss_clim, 4) if not np.isnan(bss_clim) else np.nan,
            bss_vs_fair_ensemble=round(bss_fair, 4) if not np.isnan(bss_fair) else np.nan,
            ece=round(ece_dict["ece"], 4) if not np.isnan(ece_dict["ece"]) else np.nan,
            precision=round(prec, 4),
            recall=round(rec, 4),
            f1=round(f1_val, 4),
            specificity=round(spec, 4),
            false_positive_rate=round(fpr, 4),
            confusion_matrix=cm.tolist(),
            reliability_knot_centers=ece_dict["bin_centers"],
            reliability_knot_accuracies=ece_dict["bin_accuracies"],
            crps=round(crps_val, 4) if crps_val is not None and not np.isnan(crps_val) else None,
            pinball_loss=round(pinball_val, 4) if pinball_val is not None and not np.isnan(pinball_val) else None,
            picp_90=round(picp_val, 4) if picp_val is not None and not np.isnan(picp_val) else None,
            mean_interval_width=round(interval_width, 4) if interval_width is not None and not np.isnan(interval_width) else None,
            tail_exceedance_error=round(tail_err, 4) if tail_err is not None and not np.isnan(tail_err) else None,
        )

    def run_benchmark_suite(
        self,
        model_predictions: Dict[str, Dict[str, Any]],
        labels: np.ndarray,
        true_errors: Optional[np.ndarray] = None,
        quantile_levels: Optional[np.ndarray] = None,
    ) -> Dict[str, ModelEvaluationMetrics]:
        """
        Evaluates an entire suite of model predictions against labels.

        Expected model_predictions keys:
            'E0': {'name': 'Climatology Baseline', 'type': 'baseline', 'probs': ...}
            'E1a': {'name': 'Spread-Only Baseline', 'type': 'baseline', 'probs': ...}
            'E1b': {'name': 'Fair Ensemble Baseline', 'type': 'baseline', 'probs': ...}
            'E2': {'name': 'Logistic Baseline', 'type': 'baseline', 'probs': ...}
            'E3': {'name': 'Frozen V2 Champion', 'type': 'production_v2', 'probs': ...}
            'E4': {'name': 'Quantile Mesh Model', 'type': 'error_distribution', 'probs': ..., 'quantiles': ...}
            'E5': {'name': 'Parametric Challenger', 'type': 'parametric', 'probs': ...}
        """
        ref_clim = model_predictions.get("E0", {}).get("probs", np.full_like(labels, np.mean(labels), dtype=float))
        ref_fair = model_predictions.get("E1b", {}).get("probs", ref_clim)

        results: Dict[str, ModelEvaluationMetrics] = {}

        for m_id, m_dict in model_predictions.items():
            res = self.evaluate_predictions(
                model_id=m_id,
                model_name=m_dict.get("name", m_id),
                model_type=m_dict.get("type", "baseline"),
                probs=m_dict["probs"],
                labels=labels,
                ref_clim_probs=ref_clim,
                ref_fair_probs=ref_fair,
                quantiles=m_dict.get("quantiles"),
                true_errors=true_errors,
                quantile_levels=quantile_levels,
            )
            results[m_id] = res

        return results
