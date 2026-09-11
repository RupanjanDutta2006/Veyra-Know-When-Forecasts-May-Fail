"""
Extended Issue-Time-Safe Feature Pipeline with Full Revision & Acceleration Dynamics.

Extracts both the canonical 26-feature baseline and experimental instability & revision
dynamics features across multi-cycle (00Z, 06Z, 12Z, 18Z) and multi-location forecast datasets.

Scientific Leakage & Integrity Invariants:
1. Revisions compare forecasts for the IDENTICAL valid_time across different issue times (T - offset).
2. Never subtract adjacent lead times within the same cycle run.
3. If any required prior cycle is missing, revision/acceleration strictly evaluates to NaN (never 0.0).
4. No future issue cycles (relative to current issue_time T) or verification truth data are accessed.
"""

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from builder2.feature_pipeline import (
    FEATURE_COLUMN_NAMES,
    METADATA_COLUMNS,
    IssueTimeSafeFeaturePipeline,
)

# Experimental instability feature columns (kept strictly isolated from canonical 26 features)
EXPERIMENTAL_INSTABILITY_FEATURE_NAMES = [
    # 1. Extended Revisions (12h) and Revision Magnitudes
    "forecast_delta_12h",
    "forecast_revision_mag_6h",
    "forecast_revision_mag_12h",
    "forecast_revision_mag_24h",
    "spread_delta_12h",
    # 2. Second-Order Revision & Spread Accelerations
    "revision_accel_6h",
    "revision_accel_12h",
    "spread_accel_6h",
]

ALL_DAY7_FEATURE_NAMES = FEATURE_COLUMN_NAMES + EXPERIMENTAL_INSTABILITY_FEATURE_NAMES


class InstabilityFeaturePipeline:
    """
    Extracts canonical 26 features + Day 7 experimental revision dynamics & accelerations.
    """

    def __init__(self, eps: float = 1e-6):
        self.eps = eps
        self.canonical_pipeline = IssueTimeSafeFeaturePipeline(eps=eps)

    def extract_features(
        self,
        df_forecast: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Extract canonical features, experimental features, and metadata.

        Args:
            df_forecast: Standardized forecast DataFrame.

        Returns:
            Tuple of (canonical_X_df, experimental_X_df, metadata_df).
            - canonical_X_df contains exactly the 26 canonical features for prototype-gbm-v1 compatibility.
            - experimental_X_df contains Day 7 experimental instability and acceleration features.
            - metadata_df contains alignment identifiers.
        """
        if df_forecast.empty:
            raise ValueError("Input DataFrame is empty.")

        df = df_forecast.copy()

        # 1. Base canonical feature extraction (handles 6h and 24h canonical deltas)
        canonical_X, metadata = self.canonical_pipeline.extract_features(df)

        # 2. Compute extended multi-cycle revisions & accelerations
        # Ensure datetime types
        df["valid_time"] = pd.to_datetime(df["valid_time"], utc=True)
        df["issue_time"] = pd.to_datetime(df["issue_time"], utc=True)
        if "value" in df.columns and "forecast_value" not in df.columns:
            df["forecast_value"] = df["value"]
        if "forecast_value" not in df.columns:
            df["forecast_value"] = df["value"] if "value" in df.columns else np.nan
        if "ensemble_std" not in df.columns:
            df["ensemble_std"] = np.nan

        # Build clean lookup table for previous cycle states
        lookup_cols = ["location", "variable", "valid_time", "issue_time", "forecast_value", "ensemble_std"]
        lookup_cols = [c for c in lookup_cols if c in df.columns]
        lookup = df[lookup_cols].drop_duplicates().copy()

        # Lookup: T - 6h
        df["_prior_issue_6h"] = df["issue_time"] - pd.Timedelta(hours=6)
        m6 = pd.merge(
            df,
            lookup.rename(columns={
                "forecast_value": "fc_prev_6h",
                "ensemble_std": "std_prev_6h",
                "issue_time": "issue_prev_6h",
            }),
            left_on=["location", "variable", "valid_time", "_prior_issue_6h"],
            right_on=["location", "variable", "valid_time", "issue_prev_6h"],
            how="left",
        )

        # Lookup: T - 12h
        df["_prior_issue_12h"] = df["issue_time"] - pd.Timedelta(hours=12)
        m12 = pd.merge(
            df,
            lookup.rename(columns={
                "forecast_value": "fc_prev_12h",
                "ensemble_std": "std_prev_12h",
                "issue_time": "issue_prev_12h",
            }),
            left_on=["location", "variable", "valid_time", "_prior_issue_12h"],
            right_on=["location", "variable", "valid_time", "issue_prev_12h"],
            how="left",
        )

        # Lookup: T - 24h
        df["_prior_issue_24h"] = df["issue_time"] - pd.Timedelta(hours=24)
        m24 = pd.merge(
            df,
            lookup.rename(columns={
                "forecast_value": "fc_prev_24h",
                "ensemble_std": "std_prev_24h",
                "issue_time": "issue_prev_24h",
            }),
            left_on=["location", "variable", "valid_time", "_prior_issue_24h"],
            right_on=["location", "variable", "valid_time", "issue_prev_24h"],
            how="left",
        )

        # ---------------------------------------------------------
        # Compute Experimental Revisions
        # ---------------------------------------------------------
        # 12h signed revision: X(T, V) - X(T-12h, V)
        forecast_delta_12h = m12["forecast_value"] - m12["fc_prev_12h"]

        # 12h spread delta: std(T, V) - std(T-12h, V)
        spread_delta_12h = m12["ensemble_std"] - m12["std_prev_12h"]

        # Revision magnitudes (absolute revisions)
        forecast_revision_mag_6h = canonical_X["forecast_delta_6h"].abs()
        forecast_revision_mag_12h = forecast_delta_12h.abs()
        forecast_revision_mag_24h = canonical_X["forecast_delta_24h"].abs()

        # ---------------------------------------------------------
        # Compute Second-Order Revision & Spread Accelerations
        # ---------------------------------------------------------
        # 6h revision acceleration:
        # delta_1 = X(T, V) - X(T-6h, V)
        # delta_2 = X(T-6h, V) - X(T-12h, V)
        # accel_6h = (delta_1 - delta_2) / 6 = (X(T, V) - 2*X(T-6h, V) + X(T-12h, V)) / 6
        fc_curr = df["forecast_value"]
        fc_6 = m6["fc_prev_6h"]
        fc_12 = m12["fc_prev_12h"]
        fc_24 = m24["fc_prev_24h"]

        revision_accel_6h = (fc_curr - 2.0 * fc_6 + fc_12) / 6.0

        # 12h revision acceleration: (X(T, V) - 2*X(T-12h, V) + X(T-24h, V)) / 12
        revision_accel_12h = (fc_curr - 2.0 * fc_12 + fc_24) / 12.0

        # 6h spread acceleration: (std(T, V) - 2*std(T-6h, V) + std(T-12h, V)) / 6
        std_curr = df["ensemble_std"]
        std_6 = m6["std_prev_6h"]
        std_12 = m12["std_prev_12h"]
        spread_accel_6h = (std_curr - 2.0 * std_6 + std_12) / 6.0

        # Build experimental DataFrame
        experimental_X = pd.DataFrame(
            {
                "forecast_delta_12h": forecast_delta_12h,
                "forecast_revision_mag_6h": forecast_revision_mag_6h,
                "forecast_revision_mag_12h": forecast_revision_mag_12h,
                "forecast_revision_mag_24h": forecast_revision_mag_24h,
                "spread_delta_12h": spread_delta_12h,
                "revision_accel_6h": revision_accel_6h,
                "revision_accel_12h": revision_accel_12h,
                "spread_accel_6h": spread_accel_6h,
            },
            index=df.index,
        )

        # Replace any inf/-inf with nan
        experimental_X = experimental_X.replace([np.inf, -np.inf], np.nan)

        return canonical_X, experimental_X, metadata
