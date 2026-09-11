"""
Model Evaluation and Diagnostic Analysis Framework.

Computes PR-AUC, Brier Score, ROC-AUC, confusion matrix, threshold curves,
stratified lead-time bins, and per-variable breakdowns in pure NumPy.
"""

from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


class ModelEvaluator:
    """Comprehensive evaluation suite for forecast bust risk estimation."""

    @staticmethod
    def compute_metrics(
        y_true: Union[pd.Series, np.ndarray],
        y_prob: Union[pd.Series, np.ndarray],
        threshold: float = 0.5,
    ) -> Dict[str, Union[float, int, dict]]:
        """Compute standard validation and test classification metrics."""
        y_t = np.asarray(y_true).astype(int)
        y_p = np.asarray(y_prob).astype(float)
        if y_p.ndim == 2:
            y_p = y_p[:, 1]

        y_p = np.clip(y_p, 0.0, 1.0)
        y_pred = (y_p >= threshold).astype(int)

        n_pos = int(y_t.sum())
        n_neg = int(len(y_t) - n_pos)

        # 1. Brier Score
        brier = float(np.mean((y_t - y_p) ** 2)) if len(y_t) > 0 else 0.0

        # 2. PR-AUC (Average Precision)
        if n_pos == 0:
            pr_auc = 0.0
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
            roc_auc = float("nan")
        else:
            ranks = pd.Series(y_p).rank(method="average").values
            rank_sum_pos = np.sum(ranks[y_t == 1])
            u = rank_sum_pos - (n_pos * (n_pos + 1)) / 2.0
            roc_auc = float(u / (n_pos * n_neg))

        # 4. Confusion matrix counts
        tp = int(np.sum((y_t == 1) & (y_pred == 1)))
        fp = int(np.sum((y_t == 0) & (y_pred == 1)))
        tn = int(np.sum((y_t == 0) & (y_pred == 0)))
        fn = int(np.sum((y_t == 1) & (y_pred == 0)))

        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

        # 5. Expected Calibration Error (ECE) with 5 bins
        ece = ModelEvaluator._compute_ece(y_t, y_p, n_bins=5)

        return {
            "total_samples": len(y_t),
            "positive_busts": n_pos,
            "negative_non_busts": n_neg,
            "base_bust_rate": round(float(n_pos / len(y_t)) if len(y_t) > 0 else 0.0, 4),
            "threshold": round(float(threshold), 3),
            "pr_auc": round(pr_auc, 4),
            "brier_score": round(brier, 4),
            "roc_auc": round(roc_auc, 4) if not np.isnan(roc_auc) else None,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "expected_calibration_error": round(ece, 4),
            "confusion_matrix": {
                "tp": int(tp),
                "fp": int(fp),
                "tn": int(tn),
                "fn": int(fn),
            },
        }

    @staticmethod
    def _compute_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 5) -> float:
        """Compute Expected Calibration Error across probability bins."""
        bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
        ece = 0.0
        n = len(y_true)
        if n == 0:
            return 0.0

        for i in range(n_bins):
            bin_mask = (y_prob >= bin_edges[i]) & (y_prob < bin_edges[i + 1]) if i < n_bins - 1 else (y_prob >= bin_edges[i]) & (y_prob <= bin_edges[i + 1])
            bin_size = int(bin_mask.sum())
            if bin_size > 0:
                bin_acc = float(y_true[bin_mask].mean())
                bin_conf = float(y_prob[bin_mask].mean())
                ece += (bin_size / n) * abs(bin_acc - bin_conf)

        return float(ece)

    @staticmethod
    def find_optimal_thresholds(
        y_true: Union[pd.Series, np.ndarray],
        y_prob: Union[pd.Series, np.ndarray],
    ) -> Dict[str, dict]:
        """Analyze Precision-Recall curve to identify operational operating points."""
        y_t = np.asarray(y_true).astype(int)
        y_p = np.asarray(y_prob).astype(float)
        if y_p.ndim == 2:
            y_p = y_p[:, 1]

        n_pos = int(y_t.sum())
        if n_pos == 0:
            return {
                "optimal_f1": {"threshold": 0.5, "f1": 0.0, "precision": 0.0, "recall": 0.0},
                "high_precision": {"threshold": 0.5, "precision": 0.0, "recall": 0.0},
                "high_recall": {"threshold": 0.5, "precision": 0.0, "recall": 0.0},
                "default_0_5": {"threshold": 0.5, "precision": 0.0, "recall": 0.0, "f1": 0.0},
            }

        # Evaluate across fine grid of thresholds
        threshold_candidates = np.linspace(0.05, 0.95, 91)
        records = []

        for th in threshold_candidates:
            y_pred = (y_p >= th).astype(int)
            tp = np.sum((y_t == 1) & (y_pred == 1))
            fp = np.sum((y_t == 0) & (y_pred == 1))
            fn = np.sum((y_t == 1) & (y_pred == 0))

            p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
            records.append((th, p, r, f1))

        df_thresh = pd.DataFrame(records, columns=["th", "prec", "rec", "f1"])

        # Best F1
        best_f1_row = df_thresh.loc[df_thresh["f1"].idxmax()]

        # High Precision (precision >= 0.5 with maximum recall, or highest precision)
        high_prec_candidates = df_thresh[df_thresh["prec"] >= 0.5]
        if len(high_prec_candidates) > 0:
            high_prec_row = high_prec_candidates.loc[high_prec_candidates["rec"].idxmax()]
        else:
            high_prec_row = best_f1_row

        # High Recall (recall >= 0.75 with highest precision)
        high_rec_candidates = df_thresh[df_thresh["rec"] >= 0.75]
        if len(high_rec_candidates) > 0:
            high_rec_row = high_rec_candidates.loc[high_rec_candidates["prec"].idxmax()]
        else:
            high_rec_row = best_f1_row

        # Default 0.5
        row_05 = df_thresh.iloc[(df_thresh["th"] - 0.5).abs().argmin()]

        return {
            "optimal_f1": {
                "threshold": round(float(best_f1_row["th"]), 3),
                "f1": round(float(best_f1_row["f1"]), 4),
                "precision": round(float(best_f1_row["prec"]), 4),
                "recall": round(float(best_f1_row["rec"]), 4),
            },
            "high_precision": {
                "threshold": round(float(high_prec_row["th"]), 3),
                "precision": round(float(high_prec_row["prec"]), 4),
                "recall": round(float(high_prec_row["rec"]), 4),
            },
            "high_recall": {
                "threshold": round(float(high_rec_row["th"]), 3),
                "precision": round(float(high_rec_row["prec"]), 4),
                "recall": round(float(high_rec_row["rec"]), 4),
            },
            "default_0_5": {
                "threshold": 0.5,
                "precision": round(float(row_05["prec"]), 4),
                "recall": round(float(row_05["rec"]), 4),
                "f1": round(float(row_05["f1"]), 4),
            },
        }

    @staticmethod
    def evaluate_by_lead_time_bins(
        df: pd.DataFrame,
        y_true: Union[pd.Series, np.ndarray],
        y_prob: Union[pd.Series, np.ndarray],
        threshold: float = 0.5,
    ) -> Dict[str, dict]:
        """Stratify performance across canonical medium-range lead time groups."""
        y_t = np.asarray(y_true).astype(int)
        y_p = np.asarray(y_prob).astype(float)
        if y_p.ndim == 2:
            y_p = y_p[:, 1]

        lead_hours = df["lead_hours"].astype(int).values

        bins = [
            ("0-24h", 0, 24),
            ("24-48h", 25, 48),
            ("48-72h", 49, 72),
            ("72-120h", 73, 120),
            ("120-168h", 121, 168),
            ("168-240h", 169, 240),
        ]

        results = {}
        for bin_name, min_h, max_h in bins:
            mask = (lead_hours >= min_h) & (lead_hours <= max_h)
            sub_count = int(mask.sum())

            if sub_count == 0:
                results[bin_name] = {
                    "sample_count": 0,
                    "status": "NO_DATA",
                }
                continue

            sub_yt = y_t[mask]
            sub_yp = y_p[mask]
            metrics = ModelEvaluator.compute_metrics(sub_yt, sub_yp, threshold=threshold)

            metrics["sample_count"] = sub_count
            metrics["reliable_sample_size"] = bool(sub_count >= 10 and sub_yt.sum() > 0)
            results[bin_name] = metrics

        return results

    @staticmethod
    def evaluate_by_variable(
        df: pd.DataFrame,
        y_true: Union[pd.Series, np.ndarray],
        y_prob: Union[pd.Series, np.ndarray],
        threshold: float = 0.5,
    ) -> Dict[str, dict]:
        """Stratify diagnostic performance across physical weather variables."""
        y_t = np.asarray(y_true).astype(int)
        y_p = np.asarray(y_prob).astype(float)
        if y_p.ndim == 2:
            y_p = y_p[:, 1]

        variables = sorted(df["variable"].unique())
        results = {}

        for var in variables:
            mask = (df["variable"] == var).values
            sub_yt = y_t[mask]
            sub_yp = y_p[mask]
            sub_count = int(mask.sum())

            metrics = ModelEvaluator.compute_metrics(sub_yt, sub_yp, threshold=threshold)
            metrics["sample_count"] = sub_count
            metrics["reliable_sample_size"] = bool(sub_count >= 10 and sub_yt.sum() > 0)
            results[var] = metrics

        return results
