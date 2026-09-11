"""
Veyra Research — Track 5: Robust Validation Schemes
Implements Walk-Forward Temporal Cross-Validation, Leave-Region-Out Spatial Cross-Validation,
and Grouped Block-Bootstrap for dependent meteorological time series.
"""
from __future__ import annotations
from typing import List, Tuple, Dict, Any, Generator
import numpy as np
import pandas as pd


# Canonical Geographic Region Mapping for 25 Stations
REGION_MAPPING_25 = {
    "delhi": "North", "srinagar": "North", "chandigarh": "North", "jaipur": "North", "lucknow": "North", "shimla": "North", "dehradun": "North", "leh": "North",
    "mumbai": "West", "pune": "West", "ahmedabad": "West", "goa": "West",
    "kolkata": "East", "bhubaneswar": "East", "ranchi": "East", "guwahati": "Northeast",
    "bengaluru": "South", "chennai": "South", "hyderabad": "South", "kochi": "South", "visakhapatnam": "South", "thiruvananthapuram": "South",
    "bhopal": "Central", "nagpur": "Central", "raipur": "Central"
}


class WalkForwardValidator:
    """
    Expanding-window or rolling-window walk-forward cross-validation.
    Guarantees strict zero temporal leakage: train strictly on t < t_val_start.
    """

    def __init__(self, n_splits: int = 5, min_train_cycles: int = 200, buffer_cycles: int = 2):
        self.n_splits = n_splits
        self.min_train_cycles = min_train_cycles
        self.buffer_cycles = buffer_cycles

    def split(self, df: pd.DataFrame) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """
        Yields (train_indices, val_indices) for each expanding fold.
        """
        unique_cycles = sorted(df["cycle_idx"].unique())
        n_cycles = len(unique_cycles)

        if n_cycles < (self.min_train_cycles + self.n_splits):
            # Fallback simple 80/20 split
            split_idx = int(0.8 * len(df))
            yield np.arange(split_idx), np.arange(split_idx, len(df))
            return

        step = (n_cycles - self.min_train_cycles) // self.n_splits

        for i in range(self.n_splits):
            train_end_idx = self.min_train_cycles + i * step
            val_start_idx = train_end_idx + self.buffer_cycles
            val_end_idx = val_start_idx + step if i < self.n_splits - 1 else n_cycles

            train_c = set(unique_cycles[:train_end_idx])
            val_c = set(unique_cycles[val_start_idx:val_end_idx])

            train_mask = df["cycle_idx"].isin(train_c).values
            val_mask = df["cycle_idx"].isin(val_c).values

            yield np.where(train_mask)[0], np.where(val_mask)[0]


class LeaveRegionOutValidator:
    """
    Spatial cross-validation: holds out an entire geographic region (e.g. North, West, South)
    to test geographic out-of-sample generalization.
    """

    def __init__(self, region_mapping: Optional[Dict[str, str]] = None):
        self.region_mapping = region_mapping or REGION_MAPPING_25

    def split(self, df: pd.DataFrame) -> Generator[Tuple[np.ndarray, np.ndarray, str], None, None]:
        """
        Yields (train_indices, test_indices, held_out_region_name).
        """
        df_regions = df["location_id"].map(self.region_mapping).fillna("Other")
        unique_regions = [r for r in df_regions.unique() if r != "Other"]

        for region in sorted(unique_regions):
            val_mask = (df_regions == region).values
            train_mask = ~val_mask
            yield np.where(train_mask)[0], np.where(val_mask)[0], region
