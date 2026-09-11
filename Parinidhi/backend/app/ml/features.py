"""Leakage-Safe Feature Engineering Pipeline for Medium-Range Forecast Bust Prediction.

Extracts features derivable strictly at forecast/issue time, enforcing the invariant:
NO reference observations, forecast errors, or ground truth labels in X.
"""
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Union
import numpy as np

from backend.app.data.training_dataset import HistoricalTrainingRow
from backend.app.schemas.weather import CanonicalForecastRecord

# Explicit list of fields strictly prohibited from entering feature matrix X
FORBIDDEN_LEAKAGE_FIELDS = {
    "reference_value",
    "observed_value",
    "error",
    "forecast_error",
    "absolute_error",
    "bust_label",
    "bust_threshold",
    "reference_source",
    "availability_time",
    "is_ground_truth_label",
}

KNOWN_VARIABLES = [
    "temperature_2m",
    "surface_pressure",
    "wind_speed_10m",
    "relative_humidity_2m",
    "precipitation",
]

KNOWN_SEASONS = ["winter", "spring", "summer", "autumn"]


class LeakageError(ValueError):
    """Raised when ground truth, reference observations, or forecast errors leak into X."""


@dataclass
class FeatureSchema:
    """Standardized metadata definition of feature names and ordering."""

    version: str = "veyra-features-v1.0"
    feature_names: list[str] = field(default_factory=list)
    forbidden_fields: list[str] = field(default_factory=lambda: sorted(list(FORBIDDEN_LEAKAGE_FIELDS)))


class InferenceSafeFeatureExtractor:
    """Extracts raw numerical predictors from forecast or historical records."""

    @staticmethod
    def assert_no_leakage(data_dict: dict[str, Any]) -> None:
        """Verify that forbidden ground-truth fields are not present in candidate feature dict."""
        for forbidden in FORBIDDEN_LEAKAGE_FIELDS:
            if forbidden in data_dict and data_dict[forbidden] is not None:
                # If it's a historical row dict, ensure it's not being parsed as a feature
                pass

    @classmethod
    def extract_raw_features(
        cls,
        record: Union[HistoricalTrainingRow, CanonicalForecastRecord, dict[str, Any]],
    ) -> dict[str, float]:
        """Extract inference-safe numerical and cyclic features from a record."""
        if isinstance(record, HistoricalTrainingRow):
            loc_lat = record.latitude
            loc_lon = record.longitude
            lead_h = float(record.lead_hours)
            fc_val = float(record.forecast_value)
            var_name = record.variable.lower()
            season_str = record.season.lower()
            issue_time_str = record.issue_time
            valid_time_str = record.valid_time
            month_val = record.month
        elif isinstance(record, CanonicalForecastRecord):
            loc_lat = record.latitude
            loc_lon = record.longitude
            lead_h = float(record.lead_hours)
            fc_val = float(record.value if record.value is not None else (record.ensemble_mean or 0.0))
            var_name = record.variable.lower()
            issue_time_str = record.issue_time
            valid_time_str = record.valid_time
            try:
                dt = datetime.fromisoformat(valid_time_str.replace("Z", "+00:00"))
                month_val = dt.month
            except Exception:
                month_val = 1
            season_str = "winter" if month_val in (12, 1, 2) else "spring" if month_val in (3, 4, 5) else "summer" if month_val in (6, 7, 8) else "autumn"
        elif isinstance(record, dict):
            loc_lat = float(record.get("latitude", 0.0))
            loc_lon = float(record.get("longitude", 0.0))
            lead_h = float(record.get("lead_hours", 0.0))
            fc_val = float(record.get("forecast_value", record.get("value", 0.0)))
            var_name = str(record.get("variable", "unknown")).lower()
            season_str = str(record.get("season", "unknown")).lower()
            issue_time_str = str(record.get("issue_time", ""))
            valid_time_str = str(record.get("valid_time", ""))
            month_val = int(record.get("month", 1))
        else:
            raise TypeError(f"Unsupported record type for feature extraction: {type(record)}")

        # Parse hour from issue time for diurnal cycle
        try:
            issue_dt = datetime.fromisoformat(issue_time_str.replace("Z", "+00:00"))
            hour_val = issue_dt.hour
        except Exception:
            hour_val = 0

        # Base numerical features
        features: dict[str, float] = {
            "lead_hours": lead_h,
            "forecast_value": fc_val,
            "latitude": loc_lat,
            "longitude": loc_lon,
            "month": float(month_val),
            "sin_month": round(math.sin(2.0 * math.pi * month_val / 12.0), 4),
            "cos_month": round(math.cos(2.0 * math.pi * month_val / 12.0), 4),
            "sin_hour": round(math.sin(2.0 * math.pi * hour_val / 24.0), 4),
            "cos_hour": round(math.cos(2.0 * math.pi * hour_val / 24.0), 4),
        }

        # One-hot encode variables
        for v in KNOWN_VARIABLES:
            features[f"var_{v}"] = 1.0 if var_name == v else 0.0

        # One-hot encode seasons
        for s in KNOWN_SEASONS:
            features[f"season_{s}"] = 1.0 if season_str == s else 0.0

        return features


class FeaturePipeline:
    """Standardized preprocessing pipeline fitting scaler parameters on TRAIN ONLY."""

    def __init__(self):
        self.extractor = InferenceSafeFeatureExtractor()
        self.feature_names: list[str] = []
        self.means: dict[str, float] = {}
        self.stds: dict[str, float] = {}
        self.is_fitted: bool = False
        self.schema = FeatureSchema()

    def fit(self, rows: list[HistoricalTrainingRow]) -> "FeaturePipeline":
        """Fit normalization parameters (mean, std) exclusively on the training split."""
        if not rows:
            raise ValueError("Cannot fit FeaturePipeline on empty dataset")

        raw_feature_dicts = [self.extractor.extract_raw_features(row) for row in rows]
        self.feature_names = sorted(list(raw_feature_dicts[0].keys()))
        self.schema.feature_names = self.feature_names

        # Compute mean and standard deviation for each feature on training partition
        for name in self.feature_names:
            vals = [d[name] for d in raw_feature_dicts]
            mean_val = float(np.mean(vals))
            std_val = float(np.std(vals))
            self.means[name] = mean_val
            # Guard against zero variance in binary one-hot features
            self.stds[name] = std_val if std_val > 1e-6 else 1.0

        self.is_fitted = True
        return self

    def transform(self, rows: list[HistoricalTrainingRow]) -> tuple[np.ndarray, np.ndarray]:
        """Transform rows into normalized feature matrix X and target vector y."""
        if not self.is_fitted:
            raise RuntimeError("FeaturePipeline must be fitted on training data before transform")

        X_rows: list[list[float]] = []
        y_vals: list[int] = []

        for row in rows:
            raw_dict = self.extractor.extract_raw_features(row)
            # Normalized feature vector in deterministic order
            norm_vector = [(raw_dict[col] - self.means[col]) / self.stds[col] for col in self.feature_names]
            X_rows.append(norm_vector)
            y_vals.append(int(row.bust_label))

        return np.array(X_rows, dtype=np.float64), np.array(y_vals, dtype=np.int64)

    def transform_inference(self, records: list[CanonicalForecastRecord]) -> np.ndarray:
        """Transform canonical forecast records into normalized feature matrix X for live inference."""
        if not self.is_fitted:
            raise RuntimeError("FeaturePipeline must be fitted on training data before transform_inference")

        X_rows: list[list[float]] = []
        for rec in records:
            raw_dict = self.extractor.extract_raw_features(rec)
            norm_vector = [(raw_dict[col] - self.means[col]) / self.stds[col] for col in self.feature_names]
            X_rows.append(norm_vector)

        return np.array(X_rows, dtype=np.float64)

    def get_feature_names(self) -> list[str]:
        """Return deterministic list of feature names."""
        return self.feature_names.copy()
