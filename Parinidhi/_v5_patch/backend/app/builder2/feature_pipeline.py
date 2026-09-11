"""
Issue-Time-Safe Feature Pipeline.

Generates tabular features for Medium-Range Weather Forecast Bust Risk Estimation.

Scientific Constraints & Leakage Safeguards:
- All features must be computable strictly at forecast issue_time.
- Features are derived exclusively from the forecast trajectory, ensemble distribution statistics,
  physical gradients, inter-cycle forecast revisions, and issue-time calendar/astronomical timestamps.
- Ground truth / ERA5 observations / future verification errors are strictly forbidden as features.
- Inter-cycle revisions (6h, 24h) compare predictions for the SAME valid_time across preceding cycles.
  If the prior cycle does not exist, NaN is strictly preserved (never imputed with 0).
"""

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


# Explicit canonical feature list for model training and inference
FEATURE_COLUMN_NAMES = [
    # 1. Ensemble Dispersion & Spread Features
    "ensemble_std",
    "ensemble_range",
    "ensemble_iqr",
    "ensemble_skew_proxy",
    "ensemble_cv",
    "ensemble_spread_to_iqr_ratio",
    "member_count",
    "has_full_ensemble",
    # 2. Forecast Values & Inter-Cycle Revisions
    "forecast_value",
    "ensemble_mean",
    "ensemble_spread_delta_6h",
    "ensemble_spread_delta_24h",
    "forecast_delta_6h",
    "forecast_delta_24h",
    # 3. Horizon & Temporal/Cyclical Features
    "lead_hours",
    "lead_days",
    "valid_hour",
    "valid_month",
    "valid_dayofweek",
    "sin_hour",
    "cos_hour",
    "sin_month",
    "cos_month",
    "is_weekend",
    # 4. Spatial Coordinates
    "latitude",
    "longitude",
]

METADATA_COLUMNS = [
    "location",
    "variable",
    "issue_time",
    "valid_time",
    "lead_hours",
]


class IssueTimeSafeFeaturePipeline:
    """Extracts issue-time safe features from standardized forecast datasets."""

    def __init__(self, eps: float = 1e-6):
        self.eps = eps

    def extract_features(
        self,
        df_forecast: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Transform standardized forecast records into a clean feature matrix X and metadata DataFrame.

        Args:
            df_forecast: Standardized forecast DataFrame (from GEFSStandardizer or Historical paired set).

        Returns:
            Tuple of (features_df, metadata_df).
        """
        if df_forecast.empty:
            raise ValueError("Input DataFrame is empty.")

        df = df_forecast.copy()

        # Normalize column names if needed
        if "value" in df.columns and "forecast_value" not in df.columns:
            df["forecast_value"] = df["value"]
        if "ensemble_std" not in df.columns:
            df["ensemble_std"] = np.nan

        # Ensure datetime types
        df["valid_time"] = pd.to_datetime(df["valid_time"], utc=True)
        df["issue_time"] = pd.to_datetime(df["issue_time"], utc=True)

        # Sort chronologically by location, variable, issue_time, valid_time
        sort_keys = ["location", "variable", "issue_time", "valid_time"]
        avail_sort = [k for k in sort_keys if k in df.columns]
        df = df.sort_values(by=avail_sort).reset_index(drop=True)

        # ---------------------------------------------------------
        # 1. Ensemble Dispersion & Spread Features
        # ---------------------------------------------------------
        ens_std = df["ensemble_std"].fillna(0.0).astype(float) if "ensemble_std" in df.columns else pd.Series(0.0, index=df.index)
        ens_mean = df["ensemble_mean"].fillna(df["forecast_value"]).astype(float) if "ensemble_mean" in df.columns else df["forecast_value"].astype(float)
        ens_min = df["ensemble_min"].fillna(ens_mean).astype(float) if "ensemble_min" in df.columns else ens_mean
        ens_max = df["ensemble_max"].fillna(ens_mean).astype(float) if "ensemble_max" in df.columns else ens_mean
        q10 = df["q10"].fillna(ens_min).astype(float) if "q10" in df.columns else ens_min
        q90 = df["q90"].fillna(ens_max).astype(float) if "q90" in df.columns else ens_max

        df["ensemble_range"] = (ens_max - ens_min).clip(lower=0.0)
        df["ensemble_iqr"] = (q90 - q10).clip(lower=0.0)
        
        # Ensemble skewness proxy: (mean - midpoint) / (std + eps)
        midpoint = 0.5 * (ens_max + ens_min)
        df["ensemble_skew_proxy"] = (ens_mean - midpoint) / (ens_std + self.eps)

        # Coefficient of variation: std / (|mean| + eps)
        df["ensemble_cv"] = ens_std / (ens_mean.abs() + self.eps)

        # Ratio of spread to IQR
        df["ensemble_spread_to_iqr_ratio"] = ens_std / (df["ensemble_iqr"] + self.eps)

        # Member-count provenance: never invent 31 when the source did not provide it.
        # Historical GEFSv12 reforecast has 5 members normally / 11 on weekly extended runs;
        # operational providers may expose a provider-specific subset.
        if "member_count" not in df.columns:
            df["member_count"] = 0
        df["member_count"] = pd.to_numeric(df["member_count"], errors="coerce").fillna(0).astype(int)
        if "has_full_ensemble" not in df.columns:
            source_text = df.get("forecast_source", pd.Series("", index=df.index)).astype(str).str.lower()
            expected = np.where(source_text.str.contains("reforecast"), 5, 30)
            df["has_full_ensemble"] = (df["member_count"] >= expected).astype(int)

        # ---------------------------------------------------------
        # 2. Inter-Cycle Forecast & Spread Revisions (for identical valid_time)
        # ---------------------------------------------------------
        # Compare prediction for the SAME valid_time against the preceding cycle (~6h or ~24h earlier).
        # For each current row (issue_time=T), find the forecast from the cycle issued at T-6h or T-24h
        # that predicted the same valid_time. If no such prior cycle exists, NaN is preserved.
        lookup_cols = ["location", "variable", "valid_time", "issue_time", "forecast_value", "ensemble_std"]
        lookup_cols = [c for c in lookup_cols if c in df.columns]
        lookup = df[lookup_cols].drop_duplicates().copy()

        # 6-hour prior cycle lookup: find forecast from cycle issued 6h before current
        df["_prior_issue_6h"] = df["issue_time"] - pd.Timedelta(hours=6)
        m6 = pd.merge(
            df,
            lookup.rename(columns={"forecast_value": "forecast_value_prev_6h",
                                   "ensemble_std": "ensemble_std_prev_6h",
                                   "issue_time": "issue_time_prev"}),
            left_on=["location", "variable", "valid_time", "_prior_issue_6h"],
            right_on=["location", "variable", "valid_time", "issue_time_prev"],
            how="left",
        )

        # 24-hour prior cycle lookup: find forecast from cycle issued 24h before current
        df["_prior_issue_24h"] = df["issue_time"] - pd.Timedelta(hours=24)
        m24 = pd.merge(
            df,
            lookup.rename(columns={"forecast_value": "forecast_value_prev_24h",
                                   "ensemble_std": "ensemble_std_prev_24h",
                                   "issue_time": "issue_time_prev"}),
            left_on=["location", "variable", "valid_time", "_prior_issue_24h"],
            right_on=["location", "variable", "valid_time", "issue_time_prev"],
            how="left",
        )

        # Revisions: current forecast minus prior cycle forecast for the SAME valid_time
        # If previous cycle does not exist, leaves NaN (never fills with 0)
        df["forecast_delta_6h"] = m6["forecast_value"] - m6["forecast_value_prev_6h"]
        df["ensemble_spread_delta_6h"] = m6["ensemble_std"] - m6["ensemble_std_prev_6h"]

        df["forecast_delta_24h"] = m24["forecast_value"] - m24["forecast_value_prev_24h"]
        df["ensemble_spread_delta_24h"] = m24["ensemble_std"] - m24["ensemble_std_prev_24h"]

        # Clean up temporary columns
        df.drop(columns=["_prior_issue_6h", "_prior_issue_24h"], inplace=True)

        # ---------------------------------------------------------
        # 3. Horizon & Temporal/Cyclical Features
        # ---------------------------------------------------------
        df["lead_hours"] = df["lead_hours"].astype(int)
        df["lead_days"] = (df["lead_hours"] / 24.0).round(3)

        valid_hour = df["valid_time"].dt.hour
        valid_month = df["valid_time"].dt.month
        valid_dow = df["valid_time"].dt.dayofweek

        df["valid_hour"] = valid_hour
        df["valid_month"] = valid_month
        df["valid_dayofweek"] = valid_dow
        df["is_weekend"] = valid_dow.isin([5, 6]).astype(int)

        # Cyclical trigonometry transformations
        df["sin_hour"] = np.sin(2 * np.pi * valid_hour / 24.0).round(5)
        df["cos_hour"] = np.cos(2 * np.pi * valid_hour / 24.0).round(5)
        df["sin_month"] = np.sin(2 * np.pi * valid_month / 12.0).round(5)
        df["cos_month"] = np.cos(2 * np.pi * valid_month / 12.0).round(5)

        # ---------------------------------------------------------
        # 4. Spatial Coordinates
        # ---------------------------------------------------------
        df["latitude"] = df["latitude"].astype(float)
        df["longitude"] = df["longitude"].astype(float)

        # Build feature DataFrame and metadata DataFrame
        X = df[FEATURE_COLUMN_NAMES].copy()
        
        # Replace any inf / -inf with nan
        X = X.replace([np.inf, -np.inf], np.nan)

        meta_cols_present = [c for c in METADATA_COLUMNS if c in df.columns]
        metadata = df[meta_cols_present].copy()

        return X, metadata
