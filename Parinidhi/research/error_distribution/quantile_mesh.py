"""
Veyra Research — Track 1: Conditional Error Distribution Engine
Quantile-mesh conditional distribution, monotonic rearrangement, piecewise-linear CDF, and tail handling.
"""
from __future__ import annotations
import math
from typing import List, Tuple, Dict, Any, Optional
import numpy as np


class QuantileMeshDistribution:
    """
    Estimates P(|e| >= tau | X, lead) via a monotonic quantile mesh.
    Computes quantile knots across probabilities alpha in [0.01 ... 0.99],
    enforces monotonicity via Chernozhukov sorting, and interpolates piecewise-linear CDFs
    with generalized Pareto/exponential tail extrapolation.
    """
    DEFAULT_QUANTILES = (0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 0.99)

    def __init__(self, quantiles: Optional[Tuple[float, ...]] = None):
        self.quantiles = np.array(sorted(quantiles if quantiles is not None else self.DEFAULT_QUANTILES), dtype=np.float64)
        if not np.all((self.quantiles > 0.0) & (self.quantiles < 1.0)):
            raise ValueError("Quantiles must be strictly between 0 and 1.")

    @staticmethod
    def enforce_monotonicity(predicted_quantiles: np.ndarray) -> np.ndarray:
        """
        Enforces quantile monotonicity (Chernozhukov et al. rearrangement)
        along the last axis. Handles 1D and 2D arrays.
        """
        if predicted_quantiles.ndim == 1:
            return np.sort(predicted_quantiles)
        return np.sort(predicted_quantiles, axis=-1)

    def cdf(self, knots: np.ndarray, x: float | np.ndarray) -> float | np.ndarray:
        """
        Evaluates the conditional cumulative distribution function F(x) = P(E <= x | X)
        given monotonically sorted quantile knots corresponding to self.quantiles.
        """
        knots = np.asarray(knots, dtype=np.float64)
        if np.any(np.isnan(knots)):
            return np.nan if np.isscalar(x) else np.full_like(x, np.nan, dtype=np.float64)

        # Enforce rearrangement
        sorted_knots = self.enforce_monotonicity(knots)
        alphas = self.quantiles

        is_scalar = np.isscalar(x)
        x_arr = np.atleast_1d(np.asarray(x, dtype=np.float64))
        results = np.zeros_like(x_arr, dtype=np.float64)

        for i, val in enumerate(x_arr):
            if np.isnan(val):
                results[i] = np.nan
                continue

            if val <= sorted_knots[0]:
                # Left tail extrapolation (exponential decay to 0)
                # P(E <= x) = alpha_0 * exp((x - q_0) / scale)
                scale = max(sorted_knots[1] - sorted_knots[0], 1e-6)
                decay = np.exp((val - sorted_knots[0]) / scale)
                results[i] = max(0.0, min(alphas[0], alphas[0] * decay))
            elif val >= sorted_knots[-1]:
                # Right tail extrapolation (exponential approach to 1)
                # 1 - P(E <= x) = (1 - alpha_N) * exp(-(x - q_N) / scale)
                scale = max(sorted_knots[-1] - sorted_knots[-2], 1e-6)
                decay = np.exp(-(val - sorted_knots[-1]) / scale)
                tail_prob = (1.0 - alphas[-1]) * decay
                results[i] = min(1.0, max(alphas[-1], 1.0 - tail_prob))
            else:
                # Piecewise-linear interpolation between knots
                idx = np.searchsorted(sorted_knots, val, side='right') - 1
                q_low, q_high = sorted_knots[idx], sorted_knots[idx + 1]
                a_low, a_high = alphas[idx], alphas[idx + 1]
                if q_high > q_low:
                    slope = (a_high - a_low) / (q_high - q_low)
                    results[i] = a_low + slope * (val - q_low)
                else:
                    results[i] = a_low

        return float(results[0]) if is_scalar else results

    def prob_exceedance_abs(self, error_knots: np.ndarray, tau: float) -> float:
        """
        Computes P(|error| >= tau) = 1 - P(-tau <= error <= tau)
                                  = 1 - [F(tau) - F(-tau)]
        """
        if tau <= 0:
            return 1.0
        if np.isnan(tau) or np.any(np.isnan(error_knots)):
            return np.nan

        f_pos = float(self.cdf(error_knots, tau))
        f_neg = float(self.cdf(error_knots, -tau))

        if np.isnan(f_pos) or np.isnan(f_neg):
            return np.nan

        prob_within = max(0.0, f_pos - f_neg)
        prob_exceed = max(0.0, min(1.0, 1.0 - prob_within))
        return prob_exceed


def build_synthetic_error_knots(mean_bias: float, spread: float, lead_hours: int,
                                quantiles: Optional[Tuple[float, ...]] = None) -> np.ndarray:
    """
    Utility to construct scientifically grounded synthetic error quantile knots
    scaled by ensemble spread and lead degradation for testing and fallback.
    """
    if np.isnan(mean_bias) or np.isnan(spread) or spread <= 0:
        return np.full(len(quantiles or QuantileMeshDistribution.DEFAULT_QUANTILES), np.nan)

    qs = quantiles or QuantileMeshDistribution.DEFAULT_QUANTILES
    # Heavier tails at longer leads (student-t approximation with df decaying from 10 to 4)
    df = max(3.5, 10.0 - (lead_hours / 240.0) * 6.0)
    scale = spread * math.sqrt((df - 2.0) / df) if df > 2 else spread

    from scipy.stats import t as student_t
    knots = np.array([student_t.ppf(q, df=df, loc=mean_bias, scale=scale) for q in qs], dtype=np.float64)
    return knots
