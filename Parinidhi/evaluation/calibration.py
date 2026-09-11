"""
Probability Calibration Engine & Reliability Analysis for Forecast Bust Detection.

Provides:
- ProbabilityCalibrator: Fits Platt scaling (Sigmoid) or Isotonic regression strictly on training data.
- ReliabilityAnalyzer: Computes calibration curves, Expected Calibration Error (ECE),
  Maximum Calibration Error (MCE), Brier Score, and Brier Skill Score (BSS).

Scientific Invariants:
- Calibration parameters MUST be learned exclusively on training/calibration splits.
- Never calibrate using test observations.
- Handles edge cases: single-class data, zero-positive bins, extreme probabilities [0, 1].
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


class ProbabilityCalibrator:
    """
    Fits and applies probability calibration methods strictly on training data.
    Supported methods: 'platt' (logistic sigmoid), 'isotonic' (isotonic regression), 'none' (identity).
    """

    def __init__(self, method: str = "platt"):
        norm_method = method.strip().lower()
        if norm_method not in {"platt", "sigmoid", "isotonic", "none"}:
            raise ValueError(f"Unsupported calibration method '{method}'. Must be 'platt', 'isotonic', or 'none'.")
        self.method = "platt" if norm_method == "sigmoid" else norm_method
        self.a_: float = 1.0
        self.b_: float = 0.0
        self.isotonic_x_: Optional[np.ndarray] = None
        self.isotonic_y_: Optional[np.ndarray] = None
        self.is_fitted_: bool = False

    def fit(
        self,
        y_true: Union[pd.Series, np.ndarray, List[int]],
        y_prob: Union[pd.Series, np.ndarray, List[float]],
    ) -> "ProbabilityCalibrator":
        """
        Fit calibration parameters strictly on training predictions and labels.
        """
        yt = np.asarray(y_true, dtype=float)
        yp = np.asarray(y_prob, dtype=float)
        if yp.ndim == 2:
            yp = yp[:, 1]
        yp = np.clip(yp, 1e-6, 1.0 - 1e-6)

        n = len(yt)
        if n == 0:
            raise ValueError("Cannot fit calibrator on empty training data.")

        n_pos = np.sum(yt == 1.0)
        # If single-class training partition, fallback to identity
        if n_pos == 0 or n_pos == n or self.method == "none":
            self.a_ = 1.0
            self.b_ = 0.0
            self.is_fitted_ = True
            return self

        if self.method == "platt":
            # Platt Scaling via Newton-Raphson logistic regression on logit(yp)
            logits = np.log(yp / (1.0 - yp))
            logits = np.clip(logits, -20.0, 20.0)

            # Initialize: a=1.0, b=0.0
            a, b = 1.0, 0.0
            for _ in range(50):
                z = np.clip(a * logits + b, -30.0, 30.0)
                p = 1.0 / (1.0 + np.exp(-z))
                err = p - yt
                grad_a = np.mean(err * logits) + 0.01 * a
                grad_b = np.mean(err)

                w_a = np.mean(p * (1.0 - p) * (logits ** 2)) + 0.01
                w_b = np.mean(p * (1.0 - p)) + 1e-4

                delta_a = grad_a / w_a
                delta_b = grad_b / w_b

                a -= np.clip(delta_a, -2.0, 2.0)
                b -= np.clip(delta_b, -2.0, 2.0)

                if abs(delta_a) < 1e-5 and abs(delta_b) < 1e-5:
                    break

            self.a_ = float(a)
            self.b_ = float(b)

        elif self.method == "isotonic":
            # Non-parametric Isotonic Regression via Pair Adjacent Violators (PAV)
            order = np.argsort(yp)
            x_sorted = yp[order]
            y_sorted = yt[order]

            # Weighted PAV algorithm
            weights = np.ones(n, dtype=float)
            y_iso = y_sorted.copy()

            blocks = [[y_iso[i], weights[i], [i]] for i in range(n)]
            i = 0
            while i < len(blocks) - 1:
                if blocks[i][0] > blocks[i + 1][0]:
                    # Pool adjacent violators
                    w_total = blocks[i][1] + blocks[i + 1][1]
                    y_mean = (blocks[i][0] * blocks[i][1] + blocks[i + 1][0] * blocks[i + 1][1]) / w_total
                    indices = blocks[i][2] + blocks[i + 1][2]
                    blocks[i] = [y_mean, w_total, indices]
                    del blocks[i + 1]
                    if i > 0:
                        i -= 1
                else:
                    i += 1

            self.isotonic_x_ = x_sorted
            self.isotonic_y_ = np.zeros(n, dtype=float)
            for block in blocks:
                for idx in block[2]:
                    self.isotonic_y_[idx] = block[0]

        self.is_fitted_ = True
        return self

    def predict_proba(self, y_prob: Union[pd.Series, np.ndarray, List[float]]) -> np.ndarray:
        """
        Apply learned calibration transformation to input probabilities.
        """
        yp = np.asarray(y_prob, dtype=float)
        is_1d = (yp.ndim == 1)
        if yp.ndim == 2:
            yp = yp[:, 1]
        yp_clipped = np.clip(yp, 1e-6, 1.0 - 1e-6)

        if not self.is_fitted_ or self.method == "none":
            calibrated_p = np.clip(yp, 0.0, 1.0)
        elif self.method == "platt":
            logits = np.log(yp_clipped / (1.0 - yp_clipped))
            logits = np.clip(logits, -20.0, 20.0)
            z = np.clip(self.a_ * logits + self.b_, -30.0, 30.0)
            calibrated_p = 1.0 / (1.0 + np.exp(-z))
        elif self.method == "isotonic":
            if self.isotonic_x_ is None or self.isotonic_y_ is None or len(self.isotonic_x_) == 0:
                calibrated_p = np.clip(yp, 0.0, 1.0)
            else:
                calibrated_p = np.interp(yp, self.isotonic_x_, self.isotonic_y_, left=self.isotonic_y_[0], right=self.isotonic_y_[-1])

        calibrated_p = np.clip(calibrated_p, 0.0, 1.0)
        if is_1d:
            return calibrated_p
        else:
            probs = np.zeros((len(calibrated_p), 2), dtype=float)
            probs[:, 0] = 1.0 - calibrated_p
            probs[:, 1] = calibrated_p
            return probs


class ReliabilityAnalyzer:
    """Computes comprehensive probability calibration diagnostics, curves, and skill scores."""

    @staticmethod
    def compute_reliability_curve(
        y_true: Union[pd.Series, np.ndarray, List[int]],
        y_prob: Union[pd.Series, np.ndarray, List[float]],
        n_bins: int = 5,
    ) -> Dict[str, Any]:
        """
        Compute reliability table and calibration metrics.

        Args:
            y_true: Binary ground truth labels.
            y_prob: Predicted bust probabilities.
            n_bins: Number of probability bins (default 5).

        Returns:
            Dictionary containing bin details, ECE, MCE, Brier score, and BSS.
        """
        yt = np.asarray(y_true, dtype=int)
        yp = np.asarray(y_prob, dtype=float)
        if yp.ndim == 2:
            yp = yp[:, 1]
        yp = np.clip(yp, 0.0, 1.0)
        n = len(yt)

        if n == 0:
            return {
                "sample_count": 0,
                "status": "INSUFFICIENT_DATA",
                "ece": 0.0,
                "mce": 0.0,
                "brier_score": 0.0,
                "brier_skill_score": 0.0,
                "bins": [],
            }

        base_rate = float(np.mean(yt))
        brier = float(np.mean((yt - yp) ** 2))
        brier_climatology = float(base_rate * (1.0 - base_rate))
        brier_skill_score = float(1.0 - (brier / brier_climatology)) if brier_climatology > 1e-6 else 0.0

        bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
        bins_data: List[Dict[str, Any]] = []
        ece = 0.0
        mce = 0.0

        for i in range(n_bins):
            b_low = float(bin_edges[i])
            b_high = float(bin_edges[i + 1])
            if i == n_bins - 1:
                mask = (yp >= b_low) & (yp <= b_high)
            else:
                mask = (yp >= b_low) & (yp < b_high)

            count = int(np.sum(mask))
            if count > 0:
                obs_freq = float(np.mean(yt[mask]))
                mean_pred = float(np.mean(yp[mask]))
                calib_gap = abs(obs_freq - mean_pred)
                ece += (count / n) * calib_gap
                mce = max(mce, calib_gap)
            else:
                obs_freq = 0.0
                mean_pred = (b_low + b_high) / 2.0
                calib_gap = 0.0

            bins_data.append({
                "bin_index": i + 1,
                "bin_range": f"[{b_low:.2f}, {b_high:.2f}]",
                "sample_count": count,
                "sample_fraction": round(float(count / n), 4),
                "mean_predicted_probability": round(mean_pred, 4),
                "observed_bust_frequency": round(obs_freq, 4),
                "calibration_gap": round(calib_gap, 4),
            })

        return {
            "sample_count": n,
            "positive_count": int(np.sum(yt == 1)),
            "base_bust_rate": round(base_rate, 4),
            "expected_calibration_error": round(float(ece), 4),
            "maximum_calibration_error": round(float(mce), 4),
            "brier_score": round(brier, 4),
            "brier_skill_score": round(brier_skill_score, 4),
            "n_bins": n_bins,
            "bins": bins_data,
        }
