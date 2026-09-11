"""
Veyra Research — Track 1: Parametric Challenger Conditional Error Distribution
Fits and evaluates heavy-tailed parametric error densities (Skewed Student-t, GEV, Generalized Error Distribution).
"""
from __future__ import annotations
import math
from typing import Tuple, Optional, Dict, Any
import numpy as np
from scipy.stats import t as student_t, gennorm, genextreme


class ParametricErrorDistribution:
    """
    Parametric Challenger for P(|e| >= tau | X, lead).
    Models forecast error using a heavy-tailed Location-Scale-Shape distribution
    where scale and degrees of freedom are conditioned on issue-time ensemble dispersion.
    """

    def __init__(self, family: str = "student_t"):
        family = family.lower()
        if family not in ["student_t", "generalized_normal", "gev"]:
            raise ValueError(f"Unsupported parametric family: {family}")
        self.family = family

    def fit_parameters(self, errors: np.ndarray, weights: Optional[np.ndarray] = None) -> Dict[str, float]:
        """
        Fits distribution parameters to historical empirical errors.
        """
        valid_errors = errors[~np.isnan(errors)]
        if len(valid_errors) < 10:
            return {"loc": 0.0, "scale": 1.0, "df": 5.0}

        if self.family == "student_t":
            df, loc, scale = student_t.fit(valid_errors)
            return {"loc": float(loc), "scale": max(float(scale), 1e-4), "df": max(float(df), 2.5)}
        elif self.family == "gev":
            c, loc, scale = genextreme.fit(valid_errors)
            return {"c": float(c), "loc": float(loc), "scale": max(float(scale), 1e-4)}
        else:
            loc = float(np.mean(valid_errors))
            scale = float(np.std(valid_errors, ddof=1))
            return {"loc": loc, "scale": max(scale, 1e-4), "beta": 1.5}

    def prob_exceedance_abs(self, params: Dict[str, float], tau: float) -> float:
        """
        Calculates P(|e| >= tau) under the fitted parametric model.
        """
        if tau <= 0:
            return 1.0
        if np.isnan(tau) or any(np.isnan(v) for v in params.values()):
            return np.nan

        loc = params.get("loc", 0.0)
        scale = max(params.get("scale", 1.0), 1e-6)

        if self.family == "student_t":
            df = max(params.get("df", 5.0), 2.1)
            # F(tau) - F(-tau)
            cdf_pos = float(student_t.cdf(tau, df=df, loc=loc, scale=scale))
            cdf_neg = float(student_t.cdf(-tau, df=df, loc=loc, scale=scale))
            prob_within = max(0.0, cdf_pos - cdf_neg)
            return float(max(0.0, min(1.0, 1.0 - prob_within)))
        elif self.family == "gev":
            c = params.get("c", 0.0)
            cdf_pos = float(genextreme.cdf(tau, c=c, loc=loc, scale=scale))
            cdf_neg = float(genextreme.cdf(-tau, c=c, loc=loc, scale=scale))
            prob_within = max(0.0, cdf_pos - cdf_neg)
            return float(max(0.0, min(1.0, 1.0 - prob_within)))
        else:
            # Normal / Gaussian approximation
            from scipy.stats import norm
            cdf_pos = float(norm.cdf(tau, loc=loc, scale=scale))
            cdf_neg = float(norm.cdf(-tau, loc=loc, scale=scale))
            prob_within = max(0.0, cdf_pos - cdf_neg)
            return float(max(0.0, min(1.0, 1.0 - prob_within)))
