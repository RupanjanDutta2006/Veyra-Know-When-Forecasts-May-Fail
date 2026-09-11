"""
Veyra Scientific Verification Engine.

Provides continuous, probabilistic, ensemble, and classification verification metrics
for forecast failure and bust analysis.

Mathematical Definitions & Metrics:
1. Continuous:
   - Bias = (1/N) * sum(forecast - reference)
   - MAE  = (1/N) * sum(|forecast - reference|)
   - RMSE = sqrt((1/N) * sum((forecast - reference)^2))
   - Quantile Errors = P10, P50 (median), P90, P99 of absolute error

2. Probabilistic & Calibration:
   - Brier Score = (1/N) * sum((p_i - y_i)^2)
   - ECE (Expected Calibration Error) = sum_b (|B_b| / N) * |acc(B_b) - conf(B_b)|
   - Reliability Curve = 10 uniform probability bins with mean predicted vs mean observed
   - Calibration Slope / Intercept = logistic regression of y_i onto logit(p_i)

3. Ensemble Verification:
   - Spread-Skill Ratio = mean(ensemble_std) / RMSE(ensemble_mean)
     * SSR ~ 1.0 indicates statistically calibrated ensemble dispersion
     * SSR < 1.0 indicates under-dispersion / overconfidence
     * SSR > 1.0 indicates over-dispersion
   - Spread-Error Correlation = Pearson correlation between ensemble_std and absolute_error

4. Classifier Verification:
   - ROC-AUC (Wilcoxon-Mann-Whitney rank statistic)
   - PR-AUC (trapezoidal integration over sorted precision-recall curve)
   - FAR (False Alarm Rate) = FP / (FP + TN)
   - Recall = TP / (TP + FN), Precision = TP / (TP + FP), F1
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


class ScientificVerificationEngine:
    """
    Comprehensive verification framework for deterministic, probabilistic, ensemble,
    and classification weather forecast evaluations.
    """

    @staticmethod
    def verify_continuous(
        forecast_values: Union[pd.Series, np.ndarray],
        reference_values: Union[pd.Series, np.ndarray],
    ) -> Dict[str, float]:
        """Compute continuous deterministic verification metrics."""
        fc = np.asarray(forecast_values, dtype=float)
        ref = np.asarray(reference_values, dtype=float)

        if len(fc) == 0 or len(ref) == 0:
            return {"sample_count": 0, "mae": 0.0, "rmse": 0.0, "bias": 0.0}

        err = fc - ref
        abs_err = np.abs(err)

        return {
            "sample_count": int(len(fc)),
            "bias": round(float(np.mean(err)), 4),
            "mae": round(float(np.mean(abs_err)), 4),
            "rmse": round(float(np.sqrt(np.mean(err ** 2))), 4),
            "error_p10": round(float(np.percentile(abs_err, 10)), 4),
            "error_p50_median": round(float(np.percentile(abs_err, 50)), 4),
            "error_p90": round(float(np.percentile(abs_err, 90)), 4),
            "error_p99": round(float(np.percentile(abs_err, 99)), 4),
        }

    @staticmethod
    def verify_probabilistic(
        y_true: Union[pd.Series, np.ndarray],
        y_prob: Union[pd.Series, np.ndarray],
        n_bins: int = 5,
    ) -> Dict[str, Any]:
        """
        Compute probabilistic calibration and reliability metrics with both uniform and adaptive quantile bins.
        """
        y_t = np.asarray(y_true, dtype=int)
        y_p = np.asarray(y_prob, dtype=float)
        if y_p.ndim == 2:
            y_p = y_p[:, 1]
        y_p = np.clip(y_p, 1e-6, 1.0 - 1e-6)

        n = len(y_t)
        if n == 0:
            return {"brier_score": 0.0, "ece": 0.0, "reliability_curve": [], "adaptive_bins": []}

        # 1. Brier Score
        brier = float(np.mean((y_t - y_p) ** 2))

        # 2. Uniform Probability Bins & ECE
        bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
        reliability_bins = []
        ece = 0.0
        non_empty_bins_count = 0

        for b in range(n_bins):
            low, high = bin_edges[b], bin_edges[b + 1]
            mask = (y_p >= low) & (y_p <= high) if b == n_bins - 1 else (y_p >= low) & (y_p < high)
            bin_size = int(np.sum(mask))

            if bin_size > 0:
                non_empty_bins_count += 1
                mean_conf = float(np.mean(y_p[mask]))
                obs_freq = float(np.mean(y_t[mask]))
                ece += (bin_size / n) * abs(obs_freq - mean_conf)
                reliability_bins.append({
                    "bin_index": b + 1,
                    "bin_range": f"{low:.2f}-{high:.2f}",
                    "count": bin_size,
                    "mean_predicted_prob": round(mean_conf, 4),
                    "observed_bust_frequency": round(obs_freq, 4),
                    "calibration_gap": round(obs_freq - mean_conf, 4),
                    "is_empty": False,
                })
            else:
                reliability_bins.append({
                    "bin_index": b + 1,
                    "bin_range": f"{low:.2f}-{high:.2f}",
                    "count": 0,
                    "mean_predicted_prob": round((low + high) / 2.0, 4),
                    "observed_bust_frequency": None,
                    "calibration_gap": None,
                    "is_empty": True,
                })

        # 3. Adaptive Quantile Bins (Equal Sample Counts)
        adaptive_bins = []
        try:
            q_edges = np.quantile(y_p, np.linspace(0.0, 1.0, n_bins + 1))
            q_edges = np.unique(q_edges)
            if len(q_edges) > 1:
                for qb in range(len(q_edges) - 1):
                    q_low, q_high = q_edges[qb], q_edges[qb + 1]
                    q_mask = (y_p >= q_low) & (y_p <= q_high) if qb == len(q_edges) - 2 else (y_p >= q_low) & (y_p < q_high)
                    q_size = int(np.sum(q_mask))
                    if q_size > 0:
                        adaptive_bins.append({
                            "bin_index": qb + 1,
                            "range": f"{q_low:.3f}-{q_high:.3f}",
                            "count": q_size,
                            "mean_predicted_prob": round(float(np.mean(y_p[q_mask])), 4),
                            "observed_bust_frequency": round(float(np.mean(y_t[q_mask])), 4),
                            "gap": round(float(np.mean(y_t[q_mask]) - np.mean(y_p[q_mask])), 4),
                        })
        except Exception:
            adaptive_bins = []

        # 4. Calibration Slope and Intercept via Linear Fit on Logit(p)
        logit_p = np.log(y_p / (1.0 - y_p))
        if y_t.sum() > 0 and (n - y_t.sum()) > 0:
            x_mean = float(np.mean(logit_p))
            y_mean = float(np.mean(y_t))
            num = float(np.sum((logit_p - x_mean) * (y_t - y_mean)))
            den = float(np.sum((logit_p - x_mean) ** 2)) + 1e-9
            slope = float(num / den)
            intercept = float(y_mean - slope * x_mean)
        else:
            slope = 1.0
            intercept = 0.0

        return {
            "sample_count": n,
            "brier_score": round(brier, 4),
            "expected_calibration_error": round(ece, 4),
            "non_empty_uniform_bins_count": non_empty_bins_count,
            "total_uniform_bins": n_bins,
            "calibration_slope": round(slope, 3),
            "calibration_intercept": round(intercept, 3),
            "reliability_curve": reliability_bins,
            "adaptive_quantile_bins": adaptive_bins,
        }

    @staticmethod
    def verify_ensemble(
        ensemble_stds: Union[pd.Series, np.ndarray],
        errors: Union[pd.Series, np.ndarray],
    ) -> Dict[str, float]:
        """Compute ensemble spread-skill relationship and dispersion ratio."""
        stds = np.asarray(ensemble_stds, dtype=float)
        abs_errs = np.abs(np.asarray(errors, dtype=float))

        if len(stds) == 0 or len(abs_errs) == 0:
            return {"spread_skill_ratio": 1.0, "mean_spread": 0.0, "rmse": 0.0}

        mean_spread = float(np.mean(stds))
        rmse = float(np.sqrt(np.mean(abs_errs ** 2)))
        ssr = float(mean_spread / (rmse + 1e-9))

        # Correlation between spread and realized error
        if len(stds) > 1 and float(np.std(stds)) > 1e-6 and float(np.std(abs_errs)) > 1e-6:
            s_m = float(np.mean(stds))
            e_m = float(np.mean(abs_errs))
            num = float(np.sum((stds - s_m) * (abs_errs - e_m)))
            den = float(np.sqrt(np.sum((stds - s_m) ** 2) * np.sum((abs_errs - e_m) ** 2))) + 1e-9
            corr = float(num / den)
        else:
            corr = 0.0

        # Dispersion classification
        if ssr < 0.80:
            disp_regime = "UNDER_DISPERSED"
        elif ssr > 1.20:
            disp_regime = "OVER_DISPERSED"
        else:
            disp_regime = "CALIBRATED_DISPERSION"

        return {
            "mean_ensemble_spread": round(mean_spread, 4),
            "rmse": round(rmse, 4),
            "spread_skill_ratio": round(ssr, 4),
            "spread_error_correlation": round(corr, 4),
            "dispersion_regime": disp_regime,
        }

    @staticmethod
    def verify_classifier(
        y_true: Union[pd.Series, np.ndarray],
        y_prob: Union[pd.Series, np.ndarray],
        threshold: float = 0.5,
    ) -> Dict[str, Any]:
        """Compute classification performance metrics."""
        y_t = np.asarray(y_true, dtype=int)
        y_p = np.asarray(y_prob, dtype=float)
        if y_p.ndim == 2:
            y_p = y_p[:, 1]
        y_p = np.clip(y_p, 0.0, 1.0)
        y_pred = (y_p >= threshold).astype(int)

        n_pos = int(y_t.sum())
        n_neg = int(len(y_t) - n_pos)

        # 1. Brier Score
        brier = float(np.mean((y_t - y_p) ** 2)) if len(y_t) > 0 else 0.0

        # 2. PR-AUC
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

        # 3. ROC-AUC
        if n_pos == 0 or n_neg == 0:
            roc_auc = float("nan")
        else:
            ranks = pd.Series(y_p).rank(method="average").values
            rank_sum_pos = np.sum(ranks[y_t == 1])
            u = rank_sum_pos - (n_pos * (n_pos + 1)) / 2.0
            roc_auc = float(u / (n_pos * n_neg))

        # 4. Confusion Matrix Counts
        tp = int(np.sum((y_t == 1) & (y_pred == 1)))
        fp = int(np.sum((y_t == 0) & (y_pred == 1)))
        tn = int(np.sum((y_t == 0) & (y_pred == 0)))
        fn = int(np.sum((y_t == 1) & (y_pred == 0)))

        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        far = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
        f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

        return {
            "sample_count": len(y_t),
            "positive_bust_count": n_pos,
            "negative_count": n_neg,
            "bust_rate": round(float(n_pos / len(y_t)) if len(y_t) > 0 else 0.0, 4),
            "threshold": round(float(threshold), 3),
            "roc_auc": round(roc_auc, 4) if not np.isnan(roc_auc) else None,
            "pr_auc": round(pr_auc, 4),
            "brier_score": round(brier, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "false_alarm_rate": round(far, 4),
            "f1_score": round(f1, 4),
            "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        }
