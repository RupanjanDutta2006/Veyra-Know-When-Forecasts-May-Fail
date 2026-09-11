"""Baseline Machine Learning Classifier for Forecast Bust Probability Estimation."""
import logging
from typing import Optional
import numpy as np
from sklearn.linear_model import LogisticRegression

logger = logging.getLogger(__name__)


class LogisticRegressionBustModel:
    """Interpretable, class-balanced Logistic Regression classifier for bust probability estimation."""

    def __init__(
        self,
        c_regularization: float = 1.0,
        class_weight: str = "balanced",
        random_state: int = 42,
        max_iter: int = 1000,
    ):
        self.c_regularization = c_regularization
        self.class_weight = class_weight
        self.random_state = random_state
        self.max_iter = max_iter
        self.model: Optional[LogisticRegression] = None
        self.is_trained: bool = False
        self.classes_: np.ndarray = np.array([0, 1])

    def train(self, X_train: np.ndarray, y_train: np.ndarray) -> "LogisticRegressionBustModel":
        """Train the logistic regression classifier on training feature matrix and binary labels."""
        if len(X_train) == 0 or len(y_train) == 0:
            raise ValueError("Cannot train model on empty dataset")

        unique_classes = np.unique(y_train)
        if len(unique_classes) < 2:
            logger.warning("Training split contains only one class (%s). Using single-class fallback.", unique_classes)
            # Create a fitted dummy representation for single-class edge case in tiny test fixtures
            self.model = LogisticRegression(
                C=self.c_regularization,
                class_weight=None,
                random_state=self.random_state,
                max_iter=self.max_iter,
            )
            # Add a single synthetic pseudo-sample with negligible weight if strictly needed or fit intercept
            # Better: Fit model on data if 2 classes, else flag single class
            X_dummy = np.vstack([X_train, X_train[0:1]])
            y_dummy = np.append(y_train, 1 - y_train[0])
            sample_weight = np.append(np.ones(len(y_train)), 1e-6)
            self.model.fit(X_dummy, y_dummy, sample_weight=sample_weight)
        else:
            self.model = LogisticRegression(
                C=self.c_regularization,
                class_weight=self.class_weight,
                random_state=self.random_state,
                max_iter=self.max_iter,
            )
            self.model.fit(X_train, y_train)

        self.is_trained = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Output estimated bust probability P(bust) for each sample in X.

        Returns a 1D numpy array of probabilities strictly in [0.0, 1.0].
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model must be trained before calling predict_proba")

        if len(X) == 0:
            return np.array([], dtype=np.float64)

        # Scikit-learn predict_proba returns [P(class=0), P(class=1)]
        proba_matrix = self.model.predict_proba(X)
        if proba_matrix.shape[1] >= 2:
            return proba_matrix[:, 1].astype(np.float64)
        return proba_matrix[:, 0].astype(np.float64)

    def predict(self, X: np.ndarray, decision_threshold: float = 0.5) -> np.ndarray:
        """Output binary bust prediction (0 or 1) based on decision threshold."""
        probabilities = self.predict_proba(X)
        return (probabilities >= decision_threshold).astype(np.int64)

    def get_coefficients(self, feature_names: list[str]) -> dict[str, float]:
        """Return model feature weights / coefficients."""
        if not self.is_trained or self.model is None:
            return {}
        coefs = self.model.coef_[0]
        return {name: round(float(coefs[i]), 4) for i, name in enumerate(feature_names) if i < len(coefs)}
