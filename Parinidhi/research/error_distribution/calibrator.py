"""
Veyra Research — Track 1: Lead-Conditioned Probability Calibrator
Calibrates raw probability outputs P(|e| >= tau) per forecast lead using Isotonic Regression or Platt Scaling.
"""
from __future__ import annotations
from typing import Dict, Any, Optional
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression


class LeadConditionedCalibrator:
    """
    Fits and applies probability calibration independently per forecast lead time
    (+24h, +48h, ..., +240h). Supports Isotonic Regression (non-parametric) and
    Platt Scaling (parametric logistic calibration).
    """

    def __init__(self, method: str = "isotonic"):
        if method not in ["isotonic", "platt"]:
            raise ValueError(f"Method must be 'isotonic' or 'platt', got {method}")
        self.method = method
        self.calibrators: Dict[int, Any] = {}

    def fit(self, lead_hours: int, raw_probs: np.ndarray, true_labels: np.ndarray):
        """
        Fits calibration curve for a specific lead time using validation set outputs.
        """
        valid_mask = (~np.isnan(raw_probs)) & (~np.isnan(true_labels))
        p = raw_probs[valid_mask]
        y = true_labels[valid_mask]

        if len(p) < 10 or len(np.unique(y)) < 2:
            self.calibrators[lead_hours] = None
            return

        if self.method == "isotonic":
            cal = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            cal.fit(p, y)
            self.calibrators[lead_hours] = cal
        else:
            cal = LogisticRegression(C=1.0, solver="lbfgs")
            cal.fit(p.reshape(-1, 1), y)
            self.calibrators[lead_hours] = cal

    def predict_proba(self, lead_hours: int, raw_probs: np.ndarray) -> np.ndarray:
        """
        Applies fitted calibration for the given lead time.
        """
        cal = self.calibrators.get(lead_hours)
        if cal is None:
            # Identity fallback with clipping
            return np.clip(raw_probs, 0.0, 1.0)

        is_scalar = np.isscalar(raw_probs)
        p_arr = np.atleast_1d(np.asarray(raw_probs, dtype=np.float64))
        nan_mask = np.isnan(p_arr)
        out = np.full_like(p_arr, np.nan)

        valid_p = p_arr[~nan_mask]
        if len(valid_p) > 0:
            if self.method == "isotonic":
                calibrated = cal.predict(valid_p)
            else:
                calibrated = cal.predict_proba(valid_p.reshape(-1, 1))[:, 1]
            out[~nan_mask] = np.clip(calibrated, 0.0, 1.0)

        return float(out[0]) if is_scalar else out
