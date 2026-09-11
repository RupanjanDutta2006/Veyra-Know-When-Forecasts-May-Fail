"""
Veyra Research — Track 5: Probabilistic Calibration & Verification Metrics
Implements Brier Score, Brier Skill Score, ECE, PR-AUC, ROC-AUC, CRPS, PICP, Pinball Loss,
and Block-Bootstrap Confidence Intervals.
"""
from __future__ import annotations
import math
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from sklearn.metrics import roc_auc_score, precision_recall_curve, auc, brier_score_loss


def calculate_brier_skill_score(probs: np.ndarray, labels: np.ndarray, ref_probs: np.ndarray) -> float:
    """
    Computes Brier Skill Score: BSS = 1 - (BS_model / BS_ref)
    Positive BSS indicates skill superior to reference.
    """
    valid = (~np.isnan(probs)) & (~np.isnan(labels)) & (~np.isnan(ref_probs))
    p, y, p_ref = probs[valid], labels[valid], ref_probs[valid]
    if len(p) == 0:
        return np.nan

    bs_model = float(np.mean((p - y) ** 2))
    bs_ref = float(np.mean((p_ref - y) ** 2))
    if bs_ref <= 0.0:
        return 0.0
    return float(1.0 - (bs_model / bs_ref))


def calculate_ece(probs: np.ndarray, labels: np.ndarray, n_bins: int = 10) -> Dict[str, Any]:
    """
    Computes Expected Calibration Error (ECE) and returns reliability diagram knot points.
    """
    valid = (~np.isnan(probs)) & (~np.isnan(labels))
    p, y = probs[valid], labels[valid]
    if len(p) == 0:
        return {"ece": np.nan, "bin_centers": [], "bin_accuracies": [], "bin_confidences": [], "bin_counts": []}

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    centers, accs, confs, counts = [], [], [], []

    for i in range(n_bins):
        b_low, b_high = bin_edges[i], bin_edges[i + 1]
        in_bin = (p >= b_low) & (p <= b_high if i == n_bins - 1 else p < b_high)
        n_k = int(np.sum(in_bin))
        if n_k > 0:
            avg_conf = float(np.mean(p[in_bin]))
            avg_acc = float(np.mean(y[in_bin]))
            ece += (n_k / len(p)) * abs(avg_acc - avg_conf)
            centers.append(float((b_low + b_high) / 2.0))
            accs.append(avg_acc)
            confs.append(avg_conf)
            counts.append(n_k)

    return {
        "ece": float(ece),
        "bin_centers": centers,
        "bin_accuracies": accs,
        "bin_confidences": confs,
        "bin_counts": counts
    }


def calculate_pr_auc(probs: np.ndarray, labels: np.ndarray) -> float:
    """Computes Area Under Precision-Recall Curve."""
    valid = (~np.isnan(probs)) & (~np.isnan(labels))
    p, y = probs[valid], labels[valid]
    if len(p) == 0 or len(np.unique(y)) < 2:
        return np.nan
    precision, recall, _ = precision_recall_curve(y, p)
    return float(auc(recall, precision))


def calculate_roc_auc(probs: np.ndarray, labels: np.ndarray) -> float:
    """Computes Area Under ROC Curve."""
    valid = (~np.isnan(probs)) & (~np.isnan(labels))
    p, y = probs[valid], labels[valid]
    if len(p) == 0 or len(np.unique(y)) < 2:
        return np.nan
    return float(roc_auc_score(y, p))


def calculate_pinball_loss(quantiles: np.ndarray, true_errors: np.ndarray, quantile_levels: np.ndarray) -> float:
    """
    Computes mean pinball loss for quantile predictions:
    L_q(y, q_hat) = max(q * (y - q_hat), (1-q) * (q_hat - y))
    """
    losses = []
    for i, q in enumerate(quantile_levels):
        diff = true_errors - quantiles[..., i]
        loss_q = np.maximum(q * diff, (q - 1.0) * diff)
        losses.append(np.nanmean(loss_q))
    return float(np.nanmean(losses))


def calculate_crps_empirical(error_knots: np.ndarray, quantile_levels: np.ndarray, true_error: float) -> float:
    """
    Approximates Continuous Ranked Probability Score (CRPS) from quantile knots.
    """
    if np.isnan(true_error) or np.any(np.isnan(error_knots)):
        return np.nan
    # Numerical integration of pinball loss across quantile levels
    diffs = true_error - error_knots
    pinballs = np.maximum(quantile_levels * diffs, (quantile_levels - 1.0) * diffs)
    return float(2.0 * np.mean(pinballs))


def calculate_picp(lower_knots: np.ndarray, upper_knots: np.ndarray, true_errors: np.ndarray) -> float:
    """
    Prediction Interval Coverage Probability (PICP):
    Fraction of true values falling within [lower, upper] prediction interval.
    """
    valid = (~np.isnan(lower_knots)) & (~np.isnan(upper_knots)) & (~np.isnan(true_errors))
    if np.sum(valid) == 0:
        return np.nan
    inside = (true_errors[valid] >= lower_knots[valid]) & (true_errors[valid] <= upper_knots[valid])
    return float(np.mean(inside))


def bootstrap_metric_ci(probs: np.ndarray, labels: np.ndarray, metric_fn, n_bootstraps: int = 500, alpha: float = 0.05) -> Tuple[float, float, float]:
    """
    Computes empirical bootstrap confidence interval (lower, point_estimate, upper) for a metric.
    """
    valid = (~np.isnan(probs)) & (~np.isnan(labels))
    p, y = probs[valid], labels[valid]
    if len(p) < 10:
        return (np.nan, np.nan, np.nan)

    point_est = float(metric_fn(p, y))
    n = len(p)
    boot_vals = []
    np.random.seed(42)

    for _ in range(n_bootstraps):
        idx = np.random.randint(0, n, size=n)
        val = metric_fn(p[idx], y[idx])
        if not np.isnan(val):
            boot_vals.append(val)

    if len(boot_vals) < 10:
        return (point_est, point_est, point_est)

    lower = float(np.percentile(boot_vals, 100.0 * (alpha / 2.0)))
    upper = float(np.percentile(boot_vals, 100.0 * (1.0 - alpha / 2.0)))
    return (lower, point_est, upper)
