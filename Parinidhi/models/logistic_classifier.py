"""
Regularized Logistic Regression Classifier with Explicit Imputation.

Preprocesses numeric features with median imputation + missingness indicators,
followed by standard scaling and regularized L2 logistic regression with balanced class weights.
Implemented in pure NumPy for deterministic numerical stability and zero external C-extension dependencies.
"""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd


class RegularizedLogisticClassifier:
    """Logistic regression classifier with strict leakage-free preprocessing pipeline."""

    def __init__(
        self,
        C: float = 1.0,
        class_weight: Optional[str] = "balanced",
        random_state: int = 42,
        max_iter: int = 200,
        tol: float = 1e-6,
    ):
        self.C = C
        self.class_weight = class_weight
        self.random_state = random_state
        self.max_iter = max_iter
        self.tol = tol

        # Preprocessing parameters learned strictly on training data
        self.feature_names_: List[str] = []
        self.medians_: np.ndarray = np.array([])
        self.means_: np.ndarray = np.array([])
        self.stds_: np.ndarray = np.array([])
        self.missing_indicator_cols_: List[int] = []
        self.transformed_names_: List[str] = []

        # Model weights
        self.intercept_: float = 0.0
        self.coef_: np.ndarray = np.array([])

    def _preprocess(self, X: pd.DataFrame, fit: bool = False) -> np.ndarray:
        arr = X.values.astype(float).copy()
        n_samples, n_features = arr.shape

        if fit:
            self.medians_ = np.zeros(n_features)
            for j in range(n_features):
                valid_vals = arr[~np.isnan(arr[:, j]), j]
                self.medians_[j] = float(np.median(valid_vals)) if len(valid_vals) > 0 else 0.0
            # Find which columns contain missing values
            self.missing_indicator_cols_ = [i for i in range(n_features) if np.isnan(arr[:, i]).any()]

        # 1. Add missing indicators
        indicators = []
        for col_idx in self.missing_indicator_cols_:
            indicators.append(np.isnan(arr[:, col_idx]).astype(float))

        # 2. Impute NaNs with training medians
        for i in range(n_features):
            mask = np.isnan(arr[:, i])
            arr[mask, i] = self.medians_[i] if not np.isnan(self.medians_[i]) else 0.0

        if indicators:
            arr_expanded = np.column_stack([arr] + indicators)
        else:
            arr_expanded = arr

        # 3. Standard scaling
        if fit:
            self.means_ = np.mean(arr_expanded, axis=0)
            self.stds_ = np.std(arr_expanded, axis=0)
            self.stds_[self.stds_ == 0.0] = 1.0 # prevent divide by zero
            
            # Store transformed feature names
            self.transformed_names_ = list(self.feature_names_)
            for col_idx in self.missing_indicator_cols_:
                self.transformed_names_.append(f"{self.feature_names_[col_idx]}_is_missing")

        arr_scaled = (arr_expanded - self.means_) / self.stds_
        return arr_scaled

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "RegularizedLogisticClassifier":
        self.feature_names_ = list(X.columns)
        X_scaled = self._preprocess(X, fit=True)
        y_arr = y.values.astype(float)
        n_samples, n_features = X_scaled.shape

        X_ext = np.column_stack([np.ones(n_samples), X_scaled])

        # Class weights
        if self.class_weight == "balanced":
            n_pos = np.sum(y_arr == 1)
            n_neg = np.sum(y_arr == 0)
            w_pos = n_samples / (2.0 * n_pos) if n_pos > 0 else 1.0
            w_neg = n_samples / (2.0 * n_neg) if n_neg > 0 else 1.0
            sample_weights = np.where(y_arr == 1, w_pos, w_neg)
        else:
            sample_weights = np.ones(n_samples)

        # Initialize weights with small random seed
        rng = np.random.RandomState(self.random_state)
        w = rng.randn(n_features + 1) * 0.01

        l2_reg = 1.0 / self.C
        reg_matrix = np.eye(n_features + 1) * l2_reg
        reg_matrix[0, 0] = 0.0 # Do not regularize intercept

        # Newton-Raphson / IRLS with damping
        for _ in range(self.max_iter):
            z = np.clip(X_ext @ w, -30.0, 30.0)
            p = 1.0 / (1.0 + np.exp(-z))

            grad = X_ext.T @ (sample_weights * (p - y_arr)) + reg_matrix @ w

            W = sample_weights * p * (1.0 - p)
            W = np.clip(W, 1e-5, None)
            Hess = (X_ext.T * W) @ X_ext + reg_matrix + np.eye(n_features + 1) * 1e-4

            try:
                delta = np.linalg.solve(Hess, grad)
            except np.linalg.LinAlgError:
                delta = np.linalg.lstsq(Hess, grad, rcond=None)[0]

            w -= 0.8 * delta # Damped step for stability
            if np.max(np.abs(delta)) < self.tol:
                break

        self.intercept_ = float(w[0])
        self.coef_ = w[1:]
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        X_scaled = self._preprocess(X, fit=False)
        z = np.clip(X_scaled @ self.coef_ + self.intercept_, -30.0, 30.0)
        p1 = 1.0 / (1.0 + np.exp(-z))
        p0 = 1.0 - p1
        return np.column_stack([p0, p1])

    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        probs = self.predict_proba(X)[:, 1]
        return (probs >= threshold).astype(int)

    def get_feature_coefficients(self) -> Dict[str, float]:
        """Extract learned coefficients for interpretable feature importance."""
        return {name: float(self.coef_[i]) for i, name in enumerate(self.transformed_names_[:len(self.coef_)])}
