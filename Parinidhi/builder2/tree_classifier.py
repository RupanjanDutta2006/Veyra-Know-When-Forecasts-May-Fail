"""
Conservative Gradient-Boosted Tree Classifier for Bust Prediction.

Uses LightGBM native C-engine (lightgbm.train) with native NaN handling, constrained tree depth,
and scale_pos_weight specifically configured to prevent overfitting on small sample sizes.
"""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd
import lightgbm as lgb


class LightGBMBustClassifier:
    """Conservative LightGBM model for medium-range forecast bust risk estimation."""

    def __init__(
        self,
        n_estimators: int = 50,
        max_depth: int = 3,
        num_leaves: int = 7,
        learning_rate: float = 0.05,
        min_child_samples: int = 15,
        scale_pos_weight: Optional[float] = None,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        random_state: int = 42,
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.num_leaves = num_leaves
        self.learning_rate = learning_rate
        self.min_child_samples = min_child_samples
        self.scale_pos_weight = scale_pos_weight
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.random_state = random_state
        self.booster_: Optional[lgb.Booster] = None
        self.feature_names_: List[str] = []

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        eval_set: Optional[List[tuple]] = None,
    ) -> "LightGBMBustClassifier":
        self.feature_names_ = list(X.columns)

        # Compute empirical scale_pos_weight if not explicitly provided
        pos_weight = self.scale_pos_weight
        if pos_weight is None:
            n_pos = int(y.sum())
            n_neg = len(y) - n_pos
            pos_weight = float(n_neg / n_pos) if n_pos > 0 else 1.0

        train_data = lgb.Dataset(X, label=y.values, feature_name=self.feature_names_, free_raw_data=False)

        params = {
            "objective": "binary",
            "metric": "binary_logloss",
            "boosting_type": "gbdt",
            "learning_rate": self.learning_rate,
            "num_leaves": self.num_leaves,
            "max_depth": self.max_depth,
            "min_child_samples": self.min_child_samples,
            "scale_pos_weight": pos_weight,
            "subsample": self.subsample,
            "subsample_freq": 1,
            "colsample_bytree": self.colsample_bytree,
            "seed": self.random_state,
            "feature_fraction_seed": self.random_state,
            "bagging_seed": self.random_state,
            "verbose": -1,
        }

        self.booster_ = lgb.train(
            params,
            train_data,
            num_boost_round=self.n_estimators,
        )
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if self.booster_ is None:
            raise ValueError("Model must be fitted before calling predict_proba.")
        p1 = self.booster_.predict(X)
        p1 = np.clip(p1, 0.0, 1.0)
        p0 = 1.0 - p1
        return np.column_stack([p0, p1])

    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        probs = self.predict_proba(X)[:, 1]
        return (probs >= threshold).astype(int)

    def get_feature_importances(self) -> Dict[str, Dict[str, float]]:
        """Return native split and gain feature importances."""
        if self.booster_ is None:
            raise ValueError("Model must be fitted first.")

        split_imp = self.booster_.feature_importance(importance_type="split")
        gain_imp = self.booster_.feature_importance(importance_type="gain")

        importances = {}
        for i, name in enumerate(self.feature_names_):
            importances[name] = {
                "split": float(split_imp[i]),
                "gain": float(gain_imp[i]),
            }
        return importances
