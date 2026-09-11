"""
Generalization and Operational Forecast-Risk Metrics Engine.

Computes:
1. Classification Metrics (ROC-AUC, PR-AUC, Precision, Recall, F1, Accuracy, Confusion Matrix).
2. Probabilistic Quality (Brier Score, Expected Calibration Error).
3. Forecast-Risk Utility Metrics:
   - High-Risk Precision & Recall
   - Risk-Stratified Empirical Bust Rates (Low, Medium, High risk bins)
   - False Reassurance Rate (bust frequency given low predicted probability)
   - Uncertain / Ambiguous Region Fraction (0.4 <= P <= 0.6)
4. Correlated Run Structure & Horizon-Stratified Diagnostics (0-24h, 25-48h, 49-72h).
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


class GeneralizationMetrics:
    """Computes comprehensive classification, probabilistic calibration, and decision-risk metrics."""

    @staticmethod
    def evaluate_predictions(
        y_true: Union[pd.Series, np.ndarray, List[int]],
        y_prob: Union[pd.Series, np.ndarray, List[float]],
        threshold: float = 0.5,
        low_risk_threshold: float = 0.33,
        high_risk_threshold: float = 0.66,
        run_ids: Optional[Union[pd.Series, np.ndarray, List[str]]] = None,
        lead_hours: Optional[Union[pd.Series, np.ndarray, List[int]]] = None,
    ) -> Dict[str, Any]:
        """
        Compute full suite of generalization metrics for binary forecast bust risk predictions.

        Args:
            y_true: Ground truth binary labels (0 = no bust, 1 = forecast bust).
            y_prob: Predicted bust probabilities in [0.0, 1.0] or 2D probability array.
            threshold: Binary decision threshold.
            low_risk_threshold: Threshold below which forecasts are considered low risk.
            high_risk_threshold: Threshold above which forecasts are flagged as high bust risk.
            run_ids: Optional sequence of forecast-run identifiers (location_variable_issue_time).
            lead_hours: Optional sequence of forecast lead hours.

        Returns:
            Dictionary containing structured classification, probabilistic, and risk utility metrics.
        """
        y_t = np.asarray(y_true, dtype=int)
        y_p = np.asarray(y_prob, dtype=float)

        if y_p.ndim == 2:
            y_p = y_p[:, 1]

        y_p = np.clip(y_p, 0.0, 1.0)
        n_samples = len(y_t)

        if n_samples == 0:
            return {
                "sample_count": 0,
                "forecast_run_count": 0,
                "status": "NOT AVAILABLE — empty dataset",
            }

        n_pos = int(np.sum(y_t == 1))
        n_neg = int(np.sum(y_t == 0))
        base_rate = float(n_pos / n_samples)

        # 1. Brier Score
        brier = float(np.mean((y_t - y_p) ** 2))

        # 2. PR-AUC (Average Precision)
        if n_pos == 0:
            pr_auc: Union[float, str] = 0.0
        elif n_neg == 0:
            pr_auc = 1.0
        else:
            order = np.argsort(-y_p)
            y_sorted = y_t[order]
            tp_cumsum = np.cumsum(y_sorted)
            fp_cumsum = np.cumsum(1 - y_sorted)
            recalls = tp_cumsum / n_pos
            precisions = tp_cumsum / (tp_cumsum + fp_cumsum)
            recalls = np.concatenate([[0.0], recalls])
            precisions = np.concatenate([[precisions[0]], precisions])
            pr_auc = float(np.sum((recalls[1:] - recalls[:-1]) * precisions[1:]))

        # 3. ROC-AUC (Wilcoxon-Mann-Whitney rank statistic)
        if n_pos == 0 or n_neg == 0:
            roc_auc: Union[float, str] = "NOT AVAILABLE — single class in test set"
        else:
            ranks = pd.Series(y_p).rank(method="average").values
            rank_sum_pos = np.sum(ranks[y_t == 1])
            u = rank_sum_pos - (n_pos * (n_pos + 1)) / 2.0
            roc_auc = float(u / (n_pos * n_neg))

        # 4. Standard Binary Decision Metrics at threshold
        y_pred = (y_p >= threshold).astype(int)
        tp = int(np.sum((y_t == 1) & (y_pred == 1)))
        fp = int(np.sum((y_t == 0) & (y_pred == 1)))
        tn = int(np.sum((y_t == 0) & (y_pred == 0)))
        fn = int(np.sum((y_t == 1) & (y_pred == 0)))

        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        acc = float((tp + tn) / n_samples)

        # 5. Calibration: Expected Calibration Error (ECE) across 5 bins
        ece = GeneralizationMetrics._compute_ece(y_t, y_p, n_bins=5)

        # 6. Operational Risk Utility Metrics
        low_mask = y_p < low_risk_threshold
        low_count = int(np.sum(low_mask))
        low_busts = int(np.sum((y_t == 1) & low_mask))
        false_reassurance_rate = float(low_busts / low_count) if low_count > 0 else 0.0

        med_mask = (y_p >= low_risk_threshold) & (y_p <= high_risk_threshold)
        med_count = int(np.sum(med_mask))
        med_busts = int(np.sum((y_t == 1) & med_mask))
        med_bust_rate = float(med_busts / med_count) if med_count > 0 else 0.0

        high_mask = y_p > high_risk_threshold
        high_count = int(np.sum(high_mask))
        high_busts = int(np.sum((y_t == 1) & high_mask))
        high_risk_precision = float(high_busts / high_count) if high_count > 0 else 0.0
        high_risk_recall = float(high_busts / n_pos) if n_pos > 0 else 0.0

        uncertain_mask = (y_p >= 0.40) & (y_p <= 0.60)
        uncertain_fraction = float(np.mean(uncertain_mask))

        # 7. Run-Level Diagnostics (if run_ids provided)
        run_diagnostics = {}
        forecast_run_count = n_samples
        if run_ids is not None:
            r_ids = np.asarray(run_ids, dtype=str)
            unique_runs = np.unique(r_ids)
            forecast_run_count = len(unique_runs)

            # Aggregate by run: did run have >= 1 bust, and did run have >= 1 high risk alert
            df_runs = pd.DataFrame({"run_id": r_ids, "y_true": y_t, "y_prob": y_p, "y_high": high_mask.astype(int)})
            grouped = df_runs.groupby("run_id").agg({"y_true": "max", "y_high": "max", "y_prob": "mean"})

            run_total = len(grouped)
            run_busting = int((grouped["y_true"] == 1).sum())
            run_alerted = int((grouped["y_high"] == 1).sum())
            run_tp = int(((grouped["y_true"] == 1) & (grouped["y_high"] == 1)).sum())

            run_diagnostics = {
                "forecast_run_count": run_total,
                "busting_runs_count": run_busting,
                "alerted_runs_count": run_alerted,
                "run_level_bust_rate": round(float(run_busting / run_total), 4) if run_total > 0 else 0.0,
                "run_level_high_risk_precision": round(float(run_tp / run_alerted), 4) if run_alerted > 0 else 0.0,
                "records_per_run_avg": round(float(n_samples / max(run_total, 1)), 2),
            }

        # 8. Horizon-Stratified Breakdown (if lead_hours provided)
        horizon_breakdown = {}
        if lead_hours is not None:
            leads = np.asarray(lead_hours, dtype=int)
            buckets = [
                ("short_00_24h", (leads >= 0) & (leads <= 24)),
                ("medium_25_48h", (leads >= 25) & (leads <= 48)),
                ("extended_49_72h", (leads >= 49) & (leads <= 72)),
            ]
            for b_name, mask in buckets:
                sub_count = int(np.sum(mask))
                if sub_count > 0:
                    sub_yt = y_t[mask]
                    sub_yp = y_p[mask]
                    sub_pos = int(np.sum(sub_yt == 1))
                    horizon_breakdown[b_name] = {
                        "sample_count": sub_count,
                        "positive_count": sub_pos,
                        "base_bust_rate": round(float(sub_pos / sub_count), 4),
                        "brier_score": round(float(np.mean((sub_yt - sub_yp) ** 2)), 4),
                        "ece": round(GeneralizationMetrics._compute_ece(sub_yt, sub_yp, n_bins=5), 4),
                    }

        result: Dict[str, Any] = {
            "sample_count": n_samples,
            "forecast_run_count": forecast_run_count,
            "positive_count": n_pos,
            "negative_count": n_neg,
            "base_bust_rate": round(base_rate, 4),
            "threshold": round(float(threshold), 3),
            "classification": {
                "roc_auc": round(roc_auc, 4) if isinstance(roc_auc, float) else roc_auc,
                "pr_auc": round(pr_auc, 4) if isinstance(pr_auc, float) else pr_auc,
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1_score": round(f1, 4),
                "accuracy": round(acc, 4),
                "confusion_matrix": {
                    "tp": tp,
                    "fp": fp,
                    "tn": tn,
                    "fn": fn,
                },
            },
            "probabilistic": {
                "brier_score": round(brier, 4),
                "expected_calibration_error": round(ece, 4),
            },
            "forecast_risk_utility": {
                "false_reassurance_rate": round(false_reassurance_rate, 4),
                "low_risk_samples": low_count,
                "medium_risk_samples": med_count,
                "medium_risk_bust_rate": round(med_bust_rate, 4),
                "high_risk_samples": high_count,
                "high_risk_precision": round(high_risk_precision, 4),
                "high_risk_recall": round(high_risk_recall, 4),
                "uncertain_region_fraction": round(uncertain_fraction, 4),
            },
        }

        if run_diagnostics:
            result["run_diagnostics"] = run_diagnostics
        if horizon_breakdown:
            result["horizon_breakdown"] = horizon_breakdown

        return result

    @staticmethod
    def _compute_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 5) -> float:
        """Compute Expected Calibration Error (ECE)."""
        bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
        ece = 0.0
        n = len(y_true)

        if n == 0:
            return 0.0

        for i in range(n_bins):
            b_low = bin_edges[i]
            b_high = bin_edges[i + 1]
            if i == n_bins - 1:
                mask = (y_prob >= b_low) & (y_prob <= b_high)
            else:
                mask = (y_prob >= b_low) & (y_prob < b_high)

            bin_count = np.sum(mask)
            if bin_count > 0:
                acc_bin = np.mean(y_true[mask])
                conf_bin = np.mean(y_prob[mask])
                ece += (bin_count / n) * abs(acc_bin - conf_bin)

        return float(ece)
