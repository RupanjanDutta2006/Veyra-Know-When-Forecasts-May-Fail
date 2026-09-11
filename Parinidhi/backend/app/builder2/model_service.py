"""
Production Inference Service for Forecast-Bust Sentinel.

Provides a stable, versioned, and leakage-safe prediction service
wrapping the trained LightGBM model and Platt Sigmoid calibrator.
"""

import json
import logging
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import joblib
import numpy as np
import pandas as pd

from backend.app.builder2.feature_pipeline import FEATURE_COLUMN_NAMES
import backend.app.builder2.tree_classifier as _tree_classifier
import backend.app.builder2.calibrator as _calibrator

# Compatibility alias for unpickling artifacts saved under 'models.*' module namespace
sys.modules.setdefault("models.tree_classifier", _tree_classifier)
sys.modules.setdefault("models.calibrator", _calibrator)

logger = logging.getLogger(__name__)

# Allowed NaN features in the current 00Z single-cycle dataset
REVISION_FEATURES = {
    "ensemble_spread_delta_6h",
    "ensemble_spread_delta_24h",
    "forecast_delta_6h",
    "forecast_delta_24h",
}


class ForecastBustModelService:
    """Stable public inference service for forecast bust risk estimation."""

    DEFAULT_MODEL_VERSION = "prototype-gbm-v1"
    DEFAULT_THRESHOLD = 0.280

    def __init__(self, model_dir: Union[str, Path] = "models/day4"):
        """
        Initialize and load model artifacts from disk.

        Args:
            model_dir: Directory containing serialized model artifacts and metadata.
        """
        self.model_dir = Path(model_dir)

        # File paths
        self.model_path = self.model_dir / "lightgbm_bust_model.joblib"
        self.calibrator_path = self.model_dir / "probability_calibrator.joblib"
        self.metadata_path = self.model_dir / "model_metadata.json"

        # Verify existence
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model artifact not found at {self.model_path}")
        if not self.calibrator_path.exists():
            raise FileNotFoundError(f"Calibrator artifact not found at {self.calibrator_path}")
        if not self.metadata_path.exists():
            raise FileNotFoundError(f"Model metadata not found at {self.metadata_path}")

        # Load artifacts
        try:
            self.model = joblib.load(self.model_path)
            self.calibrator = joblib.load(self.calibrator_path)
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load model artifacts from {self.model_dir}: {e}") from e

        # Extract metadata configuration
        self.model_version = self.metadata.get("model_version", self.DEFAULT_MODEL_VERSION)
        self.threshold = float(self.metadata.get("decision_threshold", self.DEFAULT_THRESHOLD))
        self.feature_names = self.metadata.get("features", FEATURE_COLUMN_NAMES)

        # Validate feature list matches canonical contract
        if self.feature_names != FEATURE_COLUMN_NAMES:
            warnings.warn(
                f"Model metadata features differ from canonical FEATURE_COLUMN_NAMES.",
                UserWarning,
                stacklevel=2,
            )

    def validate_and_prepare_features(self, features: pd.DataFrame) -> pd.DataFrame:
        """
        Validate input schema, check types, handle extra/missing columns, and order features.

        Args:
            features: Input DataFrame with forecast and ensemble features.

        Returns:
            Validated DataFrame with exact 26 canonical features in canonical order.
        """
        if not isinstance(features, pd.DataFrame):
            raise TypeError(f"Expected pandas DataFrame, got {type(features).__name__}")

        if features.empty:
            raise ValueError("Input DataFrame is empty. At least one row is required.")

        # 1. Check for missing required features
        missing = [col for col in self.feature_names if col not in features.columns]
        if missing:
            raise ValueError(f"Missing required feature columns: {missing}")

        # 2. Check for extra columns (log/record and ignore)
        extra = [col for col in features.columns if col not in self.feature_names]
        if extra:
            logger.debug("Ignoring extra input columns: %s", extra)

        # 3. Select canonical features in exact canonical order
        df_ordered = features[self.feature_names].copy()

        # 4. Validate numeric types and attempt safe numeric coercion
        for col in self.feature_names:
            series = df_ordered[col]
            if not pd.api.types.is_numeric_dtype(series):
                # Try safe coercion
                try:
                    converted = pd.to_numeric(series, errors="raise")
                    df_ordered[col] = converted
                except (ValueError, TypeError) as e:
                    raise TypeError(
                        f"Column '{col}' contains non-numeric values that cannot be safely converted: {e}"
                    ) from e

        # 5. Check for unexpected NaNs in non-revision columns
        non_revision_cols = [c for c in self.feature_names if c not in REVISION_FEATURES]
        unexpected_nans = [c for c in non_revision_cols if df_ordered[c].isna().any()]
        if unexpected_nans:
            warnings.warn(
                f"Unexpected NaN values detected in non-revision features: {unexpected_nans}. "
                f"LightGBM will use native missing splits.",
                UserWarning,
                stacklevel=3,
            )

        return df_ordered

    def predict(self, features: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Compute calibrated forecast-bust probabilities for input features.

        Args:
            features: DataFrame containing at least the 26 canonical model features.

        Returns:
            List of dictionaries with keys:
                - probability (float): Calibrated bust probability in [0, 1]
                - bust_alert (bool): True if probability >= decision_threshold (0.280)
                - model_version (str): Version string of the model
        """
        X = self.validate_and_prepare_features(features)

        # 1. Raw LightGBM prediction (handles NaNs natively)
        raw_probs = self.model.predict_proba(X)

        # 2. Platt Sigmoid calibration
        calibrated_probs_2d = self.calibrator.predict_proba(raw_probs)
        p_calibrated = calibrated_probs_2d[:, 1]

        # 3. Enforce strict probability bounds
        p_calibrated = np.clip(p_calibrated, 0.0, 1.0)

        # 4. Construct response
        results = []
        for p in p_calibrated:
            prob_float = float(p)
            results.append({
                "probability": prob_float,
                "bust_alert": bool(prob_float >= self.threshold),
                "model_version": self.model_version,
            })

        return results

    def predict_single(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convenience method for single-row prediction from a dictionary.

        Args:
            features: Dictionary containing feature key-value pairs.

        Returns:
            Dictionary with probability, bust_alert, and model_version.
        """
        if not isinstance(features, dict):
            raise TypeError(f"Expected dict, got {type(features).__name__}")

        df = pd.DataFrame([features])
        results = self.predict(df)
        return results[0]

    def get_metadata(self) -> Dict[str, Any]:
        """Return model metadata dictionary for provenance and auditability."""
        return dict(self.metadata)
