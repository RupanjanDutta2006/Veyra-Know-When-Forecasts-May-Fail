"""
Baseline Models for Forecast-Bust Sentinel.

Provides:
- MajorityClassBaseline (always predicts non-bust, P=0)
- ClimatologyBaseline (predicts training-set empirical bust rate)
- PersistenceBaseline (persists recent 24h forecast revision magnitude mapped to risk)
- SpreadHeuristicBaseline (logistic sigmoid fit on ensemble_std from training set)
"""

from typing import Optional, Union
import numpy as np
import pandas as pd


class MajorityClassBaseline:
    """Baseline: Majority-class predictor (always predicts non-bust, P=0.0)."""

    def __init__(self):
        self.majority_class_ = 0

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "MajorityClassBaseline":
        self.majority_class_ = int(y.mode().iloc[0]) if len(y) > 0 else 0
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        n = len(X)
        probs = np.zeros((n, 2), dtype=float)
        probs[:, 0] = 1.0
        probs[:, 1] = 0.0
        return probs

    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        return np.zeros(len(X), dtype=int)


class ClimatologyBaseline:
    """Baseline E0: Climatological probability baseline using training data only."""

    def __init__(self):
        self.prior_probability_: float = 0.0

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "ClimatologyBaseline":
        self.prior_probability_ = float(y.mean()) if len(y) > 0 else 0.0
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        n = len(X)
        p = self.prior_probability_
        probs = np.zeros((n, 2), dtype=float)
        probs[:, 0] = 1.0 - p
        probs[:, 1] = p
        return probs

    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        p = self.prior_probability_
        pred = 1 if p >= threshold else 0
        return np.full(len(X), pred, dtype=int)


class PersistenceBaseline:
    """
    Baseline E1: Issue-Time Revision Persistence Baseline.
    
    Persists the recent forecast volatility state into future bust probability:
    uses the absolute 24h inter-cycle forecast revision (|forecast_delta_24h|) available at issue_time,
    mapped via univariate logistic regression fit on training data.
    If 24h revision is missing (NaN on first cycle), falls back to training climatological prior.
    """

    def __init__(self, revision_column: str = "forecast_delta_24h"):
        self.revision_column = revision_column
        self.w_: float = 0.5
        self.b_: float = -1.5
        self.prior_: float = 0.1149

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "PersistenceBaseline":
        self.prior_ = float(y.mean()) if len(y) > 0 else 0.1149
        rev = X[self.revision_column].values.astype(float) if self.revision_column in X.columns else np.full(len(X), np.nan)
        target = y.values.astype(float)

        # Fit on non-NaN training revision samples
        valid_mask = ~np.isnan(rev)
        if np.sum(valid_mask) >= 10:
            v_rev = np.abs(rev[valid_mask])
            v_tgt = target[valid_mask]
            n = len(v_tgt)

            w = 0.5
            b = -1.5
            for _ in range(50):
                z = np.clip(w * v_rev + b, -30.0, 30.0)
                p = 1.0 / (1.0 + np.exp(-z))
                err = p - v_tgt
                grad_w = np.sum(err * v_rev) / n + 0.01 * w
                grad_b = np.sum(err) / n

                w_w = np.sum(p * (1.0 - p) * (v_rev ** 2)) / n + 0.01
                w_b = np.sum(p * (1.0 - p)) / n + 1e-4

                w -= grad_w / w_w
                b -= grad_b / w_b

            self.w_ = float(w)
            self.b_ = float(b)

        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        n = len(X)
        if self.revision_column in X.columns:
            rev = X[self.revision_column].values.astype(float)
        else:
            rev = np.full(n, np.nan)

        probs = np.full(n, self.prior_, dtype=float)
        valid_mask = ~np.isnan(rev)
        if np.any(valid_mask):
            abs_rev = np.abs(rev[valid_mask])
            z = self.w_ * abs_rev + self.b_
            p1 = 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0)))
            probs[valid_mask] = p1

        probs = np.clip(probs, 0.0, 1.0)
        return np.column_stack([1.0 - probs, probs])

    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        probs = self.predict_proba(X)[:, 1]
        return (probs >= threshold).astype(int)


class SpreadHeuristicBaseline:
    """
    Baseline E2: Ensemble spread heuristic.
    
    Fits a simple univariate logistic mapping on `ensemble_std` strictly from training data:
        P(bust | spread) = 1 / (1 + exp(-(w * spread + b)))
    where higher ensemble spread monotonically increases predicted bust probability.
    """

    def __init__(self, spread_column: str = "ensemble_std"):
        self.spread_column = spread_column
        self.w_: float = 1.0
        self.b_: float = 0.0

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "SpreadHeuristicBaseline":
        spread = X[self.spread_column].fillna(0.0).values.astype(float)
        target = y.values.astype(float)
        n = len(target)

        w = 0.5
        b = -1.0
        for _ in range(50):
            z = np.clip(w * spread + b, -30.0, 30.0)
            p = 1.0 / (1.0 + np.exp(-z))
            err = p - target
            grad_w = np.sum(err * spread) / n + 0.01 * w
            grad_b = np.sum(err) / n
            
            w_w = np.sum(p * (1.0 - p) * (spread ** 2)) / n + 0.01
            w_b = np.sum(p * (1.0 - p)) / n + 1e-4

            w -= grad_w / w_w
            b -= grad_b / w_b

        self.w_ = float(w)
        self.b_ = float(b)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        spread = X[self.spread_column].fillna(0.0).values.astype(float)
        z = self.w_ * spread + self.b_
        p1 = 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0)))
        p0 = 1.0 - p1
        return np.column_stack([p0, p1])

    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        probs = self.predict_proba(X)[:, 1]
        return (probs >= threshold).astype(int)
