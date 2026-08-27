"""
Probability Calibration for Forecast-Bust Sentinel.

Provides Platt Scaling (Sigmoid) and Isotonic Regression calibrators,
fit strictly on out-of-fold validation probabilities in pure NumPy.
"""

from typing import Literal, Optional, Union
import numpy as np


class ProbabilityCalibrator:
    """Post-hoc probability calibration for raw model probabilities."""

    def __init__(self, method: Literal["sigmoid", "isotonic"] = "sigmoid"):
        self.method = method
        self.w_: float = 1.0
        self.b_: float = 0.0
        self.iso_x_: np.ndarray = np.array([])
        self.iso_y_: np.ndarray = np.array([])

    def fit(self, raw_probs: np.ndarray, y_true: np.ndarray) -> "ProbabilityCalibrator":
        """
        Fit calibrator on validation probabilities and validation ground-truth binary targets.
        """
        # Ensure 1D array of positive class probabilities
        if raw_probs.ndim == 2:
            p = raw_probs[:, 1]
        else:
            p = raw_probs

        p_clipped = np.clip(p, 1e-6, 1.0 - 1e-6)
        y = np.asarray(y_true, dtype=float)
        n = len(y)

        if self.method == "sigmoid":
            # Platt scaling: univariate logistic on logit / log-odds
            logit = np.log(p_clipped / (1.0 - p_clipped))
            w = 1.0
            b = 0.0

            for _ in range(50):
                z = np.clip(w * logit + b, -30.0, 30.0)
                p_cal = 1.0 / (1.0 + np.exp(-z))
                err = p_cal - y

                grad_w = np.sum(err * logit) / n + 0.01 * w
                grad_b = np.sum(err) / n

                w_w = np.sum(p_cal * (1.0 - p_cal) * (logit ** 2)) / n + 0.01
                w_b = np.sum(p_cal * (1.0 - p_cal)) / n + 1e-4

                w -= grad_w / w_w
                b -= grad_b / w_b

            self.w_ = float(w)
            self.b_ = float(b)

        elif self.method == "isotonic":
            # Pool Adjacent Violators Algorithm (PAVA)
            order = np.argsort(p_clipped)
            x_sorted = p_clipped[order]
            y_sorted = y[order]

            # PAVA implementation
            y_iso = y_sorted.copy()
            w_iso = np.ones(n)

            i = 0
            while i < n - 1:
                if y_iso[i] > y_iso[i + 1]:
                    # Pool
                    j = i
                    while j >= 0 and y_iso[j] > y_iso[j + 1]:
                        pooled_y = (w_iso[j] * y_iso[j] + w_iso[j + 1] * y_iso[j + 1]) / (w_iso[j] + w_iso[j + 1])
                        pooled_w = w_iso[j] + w_iso[j + 1]
                        y_iso[j:j + 2] = pooled_y
                        w_iso[j:j + 2] = pooled_w
                        j -= 1
                    i = max(0, j)
                else:
                    i += 1

            self.iso_x_ = x_sorted
            self.iso_y_ = y_iso
        else:
            raise ValueError(f"Unknown calibration method: {self.method}")

        return self

    def predict_proba(self, raw_probs: np.ndarray) -> np.ndarray:
        """Transform raw probabilities into calibrated probabilities."""
        if raw_probs.ndim == 2:
            p = raw_probs[:, 1]
        else:
            p = raw_probs

        p_clipped = np.clip(p, 1e-6, 1.0 - 1e-6)

        if self.method == "sigmoid":
            logit = np.log(p_clipped / (1.0 - p_clipped))
            z = self.w_ * logit + self.b_
            cal_p = 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0)))
        elif self.method == "isotonic":
            cal_p = np.interp(p_clipped, self.iso_x_, self.iso_y_)
        else:
            cal_p = p

        cal_p = np.clip(cal_p, 0.0, 1.0)
        return np.column_stack([1.0 - cal_p, cal_p])

    def evaluate_calibration_impact(
        self,
        raw_probs: np.ndarray,
        y_true: np.ndarray,
    ) -> dict:
        """Compare Brier score before and after calibration."""
        if raw_probs.ndim == 2:
            p_raw = raw_probs[:, 1]
        else:
            p_raw = raw_probs

        p_cal = self.predict_proba(p_raw)[:, 1]

        brier_before = float(np.mean((y_true - p_raw) ** 2))
        brier_after = float(np.mean((y_true - p_cal) ** 2))

        return {
            "method": self.method,
            "brier_score_uncalibrated": round(brier_before, 4),
            "brier_score_calibrated": round(brier_after, 4),
            "brier_improvement_pct": round((brier_before - brier_after) / (brier_before + 1e-9) * 100.0, 2),
        }
