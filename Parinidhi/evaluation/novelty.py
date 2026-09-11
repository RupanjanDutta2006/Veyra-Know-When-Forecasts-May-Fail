"""
Feature-Space Novelty and Out-Of-Distribution (OOD) Detection Module.

Fits strictly on training/reference issue-time features to determine if a new
forecast situations is operating outside familiar meteorological conditions.

Scientific Safeguards:
- Fits strictly on issue-time features X_train.
- Explicitly rejects fitting on verification/target columns.
- Robust to zero-variance features, singular matrices, and missing values.
- Zero future observation or test-set leakage.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from features.contract import UNAVAILABLE_UNTIL_VERIFICATION, validate_feature_contract


class FeatureNoveltyDetector:
    """
    Leakage-safe out-of-distribution (OOD) and feature-space novelty detector.
    Computes robust standardized manifold distances and reference quantile states.
    """

    def __init__(self, regularization_eps: float = 1e-4):
        self.regularization_eps = regularization_eps
        self.feature_names_: List[str] = []
        self.medians_: np.ndarray = np.array([])
        self.iqrs_: np.ndarray = np.array([])
        self.means_: np.ndarray = np.array([])
        self.stds_: np.ndarray = np.array([])

        # Reference distribution thresholds learned strictly on training data
        self.threshold_p75_: float = 1.0
        self.threshold_p90_: float = 1.5
        self.threshold_p99_: float = 2.5
        self.training_sample_count_: int = 0
        self.is_fitted_: bool = False

    def fit(self, X: Union[pd.DataFrame, np.ndarray], feature_names: Optional[List[str]] = None) -> "FeatureNoveltyDetector":
        """
        Fit baseline distribution moments and quantile thresholds strictly on training features.
        """
        if isinstance(X, pd.DataFrame):
            cols = list(X.columns)
            violations = validate_feature_contract(cols)
            if violations:
                raise ValueError(f"Cannot fit novelty detector on forbidden verification columns: {violations}")
            self.feature_names_ = cols
            arr = X.values.astype(float).copy()
        else:
            arr = np.asarray(X, dtype=float).copy()
            self.feature_names_ = feature_names or [f"feature_{i}" for i in range(arr.shape[1])]

        n_samples, n_features = arr.shape
        if n_samples == 0:
            raise ValueError("Cannot fit FeatureNoveltyDetector on empty dataset.")

        self.medians_ = np.zeros(n_features, dtype=float)
        self.iqrs_ = np.zeros(n_features, dtype=float)
        self.means_ = np.zeros(n_features, dtype=float)
        self.stds_ = np.zeros(n_features, dtype=float)

        for j in range(n_features):
            col_vals = arr[:, j]
            valid_vals = col_vals[~np.isnan(col_vals)]
            if len(valid_vals) > 0:
                self.medians_[j] = float(np.median(valid_vals))
                q75 = float(np.percentile(valid_vals, 75))
                q25 = float(np.percentile(valid_vals, 25))
                iqr = max(q75 - q25, self.regularization_eps)
                self.iqrs_[j] = iqr
                self.means_[j] = float(np.mean(valid_vals))
                std = float(np.std(valid_vals))
                self.stds_[j] = max(std, self.regularization_eps)
            else:
                self.medians_[j] = 0.0
                self.iqrs_[j] = 1.0
                self.means_[j] = 0.0
                self.stds_[j] = 1.0

        # Compute novelty scores on the training set to derive reference percentiles
        train_scores = self._compute_raw_scores(arr)
        self.threshold_p75_ = float(np.percentile(train_scores, 75))
        self.threshold_p90_ = float(np.percentile(train_scores, 90))
        self.threshold_p99_ = float(np.percentile(train_scores, 99))
        self.training_sample_count_ = n_samples
        self.is_fitted_ = True
        return self

    def _compute_raw_scores(self, arr: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """Compute normalized robust distance from median center."""
        arr_np = np.asarray(arr, dtype=float)
        n_samples, n_features = arr_np.shape
        # Impute NaNs with medians for distance calculation
        imputed = arr_np.copy()
        for j in range(n_features):
            nan_mask = np.isnan(imputed[:, j])
            imputed[nan_mask, j] = self.medians_[j]

        # Normalized robust Euclidean z-distance: sqrt(mean( ((x - med) / iqr)^2 ))
        diff = (imputed - self.medians_) / self.iqrs_
        sq_dist = np.mean(diff ** 2, axis=1)
        return np.sqrt(sq_dist)

    def score(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Compute continuous novelty score for input samples.
        Scores close to 1.0 are typical; scores > 2.0 indicate elevated novelty.
        """
        if not self.is_fitted_:
            raise RuntimeError("FeatureNoveltyDetector must be fitted before calling score().")
        if isinstance(X, pd.DataFrame):
            arr = X[self.feature_names_].values.astype(float) if self.feature_names_ else X.values.astype(float)
        else:
            arr = np.asarray(X, dtype=float)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        return self._compute_raw_scores(arr)

    def evaluate_sample(self, x: Union[pd.Series, pd.DataFrame, np.ndarray, Dict[str, float]]) -> Dict[str, Any]:
        """
        Evaluate a single forecast feature vector and produce structured novelty diagnostics.
        """
        if not self.is_fitted_:
            raise RuntimeError("FeatureNoveltyDetector must be fitted before evaluate_sample().")

        if isinstance(x, dict):
            arr = np.array([[x.get(f, np.nan) for f in self.feature_names_]], dtype=float)
        elif isinstance(x, pd.Series):
            arr = np.array([[x.get(f, np.nan) for f in self.feature_names_]], dtype=float)
        elif isinstance(x, pd.DataFrame):
            arr = x[self.feature_names_].values.astype(float)
        else:
            arr = np.asarray(x, dtype=float)
            if arr.ndim == 1:
                arr = arr.reshape(1, -1)

        raw_score = float(self._compute_raw_scores(arr)[0])

        if raw_score <= self.threshold_p75_:
            novelty_state = "NORMAL"
        elif raw_score <= self.threshold_p90_:
            novelty_state = "ELEVATED"
        elif raw_score <= self.threshold_p99_:
            novelty_state = "HIGH"
        else:
            novelty_state = "EXTREME"

        # Identify specific outlier features (|z| > 2.5)
        imputed_x = arr[0].copy()
        for j in range(len(imputed_x)):
            if np.isnan(imputed_x[j]):
                imputed_x[j] = self.medians_[j]

        z_scores = np.abs((imputed_x - self.medians_) / self.iqrs_)
        outliers = []
        for j, z in enumerate(z_scores):
            if z >= 2.5 and j < len(self.feature_names_):
                feat = self.feature_names_[j]
                outliers.append({
                    "feature": feat,
                    "value": float(arr[0, j]) if not np.isnan(arr[0, j]) else None,
                    "median": float(self.medians_[j]),
                    "robust_z_score": round(float(z), 2),
                })

        # Sort outliers by highest z-score
        outliers.sort(key=lambda o: o["robust_z_score"], reverse=True)

        return {
            "novelty_score": round(raw_score, 4),
            "novelty_state": novelty_state,
            "thresholds": {
                "p75": round(self.threshold_p75_, 4),
                "p90": round(self.threshold_p90_, 4),
                "p99": round(self.threshold_p99_, 4),
            },
            "outlier_features_count": len(outliers),
            "top_outlier_features": outliers[:5],
            "reference_training_samples": self.training_sample_count_,
        }
