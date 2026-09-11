"""
Generalization Data Splitters for Location and Climate Held-Out Protocols.

Provides group-aware, leakage-safe dataset partitioners:
- HeldOutSplit: Structured container for disjoint evaluation partitions.
- LocationHeldOutSplitter: Holds out one or more geographic locations entirely from training.
- ClimateHeldOutSplitter: Holds out entire Köppen climate zones or physical meteorological regimes.

Note on Chronological Splitting:
For single-station or in-domain temporal splits without geographic holdout,
refer to models.data_splitter.ChronologicalDataSplitter.

Scientific Leakage Safeguards:
- Train and test partitions are guaranteed strictly disjoint across grouping dimensions.
- Two-sided temporal guarantees when temporal_train_cutoff is supplied (train <= cutoff, test > cutoff).
- Forecast identity collision checking on (location_id, variable, issue_time_utc, valid_time_utc).
- No future observation or label threshold leakage between partitions.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple, Union
import numpy as np
import pandas as pd

from api.location_service import LocationRegistry


@dataclass
class HeldOutSplit:
    """Container for held-out evaluation dataset partitions and split metadata."""
    df_train: pd.DataFrame
    df_test: pd.DataFrame
    train_locations: List[str]
    held_out_locations: List[str]
    train_climates: List[str]
    held_out_climates: List[str]
    split_type: str  # 'location_held_out' | 'climate_held_out' | 'meteorological_regime_held_out'
    split_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def train_size(self) -> int:
        return len(self.df_train)

    @property
    def test_size(self) -> int:
        return len(self.df_test)

    def validate_invariants(self) -> None:
        """
        Verify fundamental scientific invariants on the split:
        1. Non-empty partitions.
        2. Disjoint location or climate sets.
        3. Zero forecast identity overlap.
        4. Two-sided temporal separation if cutoff was specified.
        """
        if self.train_size == 0:
            raise ValueError(f"Training split is empty for {self.split_type}.")
        if self.test_size == 0:
            raise ValueError(f"Held-out test split is empty for {self.split_type}.")

        # Invariant 1: Disjoint locations in location-held-out mode
        if self.split_type == "location_held_out":
            overlap_locs = set(self.train_locations).intersection(set(self.held_out_locations))
            if overlap_locs:
                raise ValueError(f"Spatial leakage detected! Locations present in both train and test: {overlap_locs}")

        # Invariant 2: Disjoint climates in climate-held-out mode
        if self.split_type in ("climate_held_out", "meteorological_regime_held_out"):
            overlap_clim = set(self.train_climates).intersection(set(self.held_out_climates))
            if overlap_clim:
                raise ValueError(f"Climatic leakage detected! Climates present in both train and test: {overlap_clim}")

        # Invariant 3: Zero forecast identity collision
        id_cols = [c for c in ["location_id", "variable", "issue_time_utc", "valid_time_utc"] if c in self.df_train.columns and c in self.df_test.columns]
        if len(id_cols) >= 2:
            train_keys = set(self.df_train[id_cols].astype(str).agg("_".join, axis=1))
            test_keys = set(self.df_test[id_cols].astype(str).agg("_".join, axis=1))
            overlap_keys = train_keys.intersection(test_keys)
            if overlap_keys:
                raise ValueError(f"Forecast identity collision detected! {len(overlap_keys)} records overlap across split boundary.")

        # Invariant 4: Two-sided temporal precedence check
        cutoff_val = self.split_metadata.get("temporal_train_cutoff")
        if cutoff_val is not None and "issue_time_utc" in self.df_train.columns and "issue_time_utc" in self.df_test.columns:
            cutoff_ts = pd.to_datetime(cutoff_val, utc=True)
            max_train_t = pd.to_datetime(self.df_train["issue_time_utc"], utc=True).max()
            min_test_t = pd.to_datetime(self.df_test["issue_time_utc"], utc=True).min()
            if max_train_t > cutoff_ts:
                raise ValueError(f"Temporal violation: train issue time {max_train_t} exceeds cutoff {cutoff_ts}.")
            if min_test_t <= cutoff_ts:
                raise ValueError(f"Temporal violation: test issue time {min_test_t} is on or before cutoff {cutoff_ts}.")


class LocationHeldOutSplitter:
    """
    Splits canonical datasets by holding out specific locations entirely from training.
    Evaluates out-of-domain geographic generalization.
    """

    def __init__(self, location_registry: Optional[LocationRegistry] = None):
        self.location_registry = location_registry or LocationRegistry()

    def split(
        self,
        df: pd.DataFrame,
        held_out_locations: Union[str, List[str]],
        temporal_train_cutoff: Optional[Union[str, pd.Timestamp]] = None,
    ) -> HeldOutSplit:
        """
        Split dataset holding out specified locations for testing.
        Guarantees two-sided temporal separation if temporal_train_cutoff is provided:
            max(train issue_time) <= cutoff AND min(test issue_time) > cutoff.

        Args:
            df: Canonical historical DataFrame containing 'location_id'.
            held_out_locations: Single location_id or list of location_ids to hold out.
            temporal_train_cutoff: Optional UTC timestamp cutoff for training data.

        Returns:
            HeldOutSplit containing disjoint train and test DataFrames.
        """
        if df.empty:
            raise ValueError("Input DataFrame is empty.")
        if "location_id" not in df.columns:
            raise ValueError("DataFrame must contain 'location_id' column.")

        if isinstance(held_out_locations, str):
            held_out_list = [held_out_locations.strip().lower()]
        else:
            held_out_list = [str(loc).strip().lower() for loc in held_out_locations]

        all_locations = sorted(list(df["location_id"].str.lower().unique()))
        held_out_set = set(held_out_list)

        # Check if held-out locations exist in dataset
        missing_in_data = held_out_set - set(all_locations)
        if len(missing_in_data) == len(held_out_set):
            raise ValueError(f"None of the requested held-out locations {held_out_list} exist in dataset (available: {all_locations}).")

        train_locations = [loc for loc in all_locations if loc not in held_out_set]
        if not train_locations:
            raise ValueError(f"Holding out {held_out_list} leaves no locations for training.")

        mask_held_out = df["location_id"].str.lower().isin(held_out_set)
        df_train = df[~mask_held_out].copy()
        df_test = df[mask_held_out].copy()

        # Two-sided temporal filter: Train <= cutoff AND Test > cutoff
        if temporal_train_cutoff is not None:
            cutoff_ts = pd.to_datetime(temporal_train_cutoff, utc=True)
            if "issue_time_utc" in df_train.columns:
                df_train = df_train[pd.to_datetime(df_train["issue_time_utc"], utc=True) <= cutoff_ts].copy()
            if "issue_time_utc" in df_test.columns:
                df_test = df_test[pd.to_datetime(df_test["issue_time_utc"], utc=True) > cutoff_ts].copy()

            if df_train.empty:
                raise ValueError(f"Temporal cutoff {temporal_train_cutoff} leaves no records in training split.")
            if df_test.empty:
                raise ValueError(f"Temporal cutoff {temporal_train_cutoff} leaves no records in test split (> cutoff).")

        train_climates = sorted(list(df_train["climate_zone"].dropna().unique())) if "climate_zone" in df_train.columns else []
        held_out_climates = sorted(list(df_test["climate_zone"].dropna().unique())) if "climate_zone" in df_test.columns else []

        split = HeldOutSplit(
            df_train=df_train.reset_index(drop=True),
            df_test=df_test.reset_index(drop=True),
            train_locations=train_locations,
            held_out_locations=sorted(list(held_out_set.intersection(set(all_locations)))),
            train_climates=train_climates,
            held_out_climates=held_out_climates,
            split_type="location_held_out",
            split_metadata={
                "temporal_train_cutoff": str(temporal_train_cutoff) if temporal_train_cutoff else None,
                "total_records": len(df),
                "train_records": len(df_train),
                "test_records": len(df_test),
            },
        )
        split.validate_invariants()
        return split

    def generate_leave_one_location_out(self, df: pd.DataFrame) -> Iterator[HeldOutSplit]:
        """Generate Leave-One-Location-Out (LOLO) cross-validation splits for all locations in df."""
        if "location_id" not in df.columns:
            raise ValueError("DataFrame must contain 'location_id' column.")
        locations = sorted(list(df["location_id"].str.lower().unique()))
        if len(locations) < 2:
            raise ValueError(f"Need at least 2 distinct locations for Leave-One-Location-Out, found {len(locations)}.")

        for loc in locations:
            yield self.split(df, held_out_locations=[loc])


class ClimateHeldOutSplitter:
    """
    Splits canonical datasets by holding out entire Köppen climate zones or physical meteorological regimes.
    Supports two distinct scientific evaluation protocols:
        1. Köppen-class holdout (climate_column='climate_zone')
        2. Meteorological-regime holdout (climate_column='meteorological_regime')
    """

    def __init__(self, location_registry: Optional[LocationRegistry] = None):
        self.location_registry = location_registry or LocationRegistry()

    def split(
        self,
        df: pd.DataFrame,
        held_out_climates: Union[str, List[str]],
        climate_column: str = "climate_zone",
        match_mode: str = "exact",  # 'exact' | 'contains'
    ) -> HeldOutSplit:
        """
        Split dataset holding out specified climate zones or meteorological regimes.

        Args:
            df: Canonical historical DataFrame.
            held_out_climates: Single climate zone / regime string or list of strings.
            climate_column: Column defining climate grouping ('climate_zone' or 'meteorological_regime').
            match_mode: 'exact' string match or 'contains' substring matching for broad regime families.

        Returns:
            HeldOutSplit containing disjoint train and test DataFrames.
        """
        if df.empty:
            raise ValueError("Input DataFrame is empty.")
        if climate_column not in df.columns:
            raise ValueError(f"Column '{climate_column}' not found in DataFrame.")

        if isinstance(held_out_climates, str):
            held_out_list = [held_out_climates.strip()]
        else:
            held_out_list = [str(c).strip() for c in held_out_climates]

        all_climates = sorted(list(df[climate_column].dropna().unique()))

        if match_mode == "contains":
            # Match any regime string containing the search keyword
            held_out_set = {
                c for c in all_climates
                if any(k.lower() in c.lower() for k in held_out_list)
            }
        else:
            held_out_set = set(held_out_list)

        missing_in_data = held_out_set - set(all_climates)
        if len(missing_in_data) == len(held_out_set) or not held_out_set:
            raise ValueError(f"None of the requested held-out climates {held_out_list} exist in dataset (available: {all_climates}).")

        train_climates = [c for c in all_climates if c not in held_out_set]
        if not train_climates:
            raise ValueError(f"Holding out {held_out_list} leaves no climate regimes for training.")

        mask_held_out = df[climate_column].isin(held_out_set)
        df_train = df[~mask_held_out].copy()
        df_test = df[mask_held_out].copy()

        train_locs = sorted(list(df_train["location_id"].str.lower().unique())) if "location_id" in df_train.columns else []
        held_out_locs = sorted(list(df_test["location_id"].str.lower().unique())) if "location_id" in df_test.columns else []

        split_type = "meteorological_regime_held_out" if climate_column == "meteorological_regime" else "climate_held_out"

        split = HeldOutSplit(
            df_train=df_train.reset_index(drop=True),
            df_test=df_test.reset_index(drop=True),
            train_locations=train_locs,
            held_out_locations=held_out_locs,
            train_climates=train_climates,
            held_out_climates=sorted(list(held_out_set.intersection(set(all_climates)))),
            split_type=split_type,
            split_metadata={
                "climate_column": climate_column,
                "match_mode": match_mode,
                "total_records": len(df),
                "train_records": len(df_train),
                "test_records": len(df_test),
            },
        )
        split.validate_invariants()
        return split

    def generate_leave_one_climate_out(
        self,
        df: pd.DataFrame,
        climate_column: str = "climate_zone",
    ) -> Iterator[HeldOutSplit]:
        """Generate Leave-One-Climate-Out (LOCO) cross-validation splits for all climate zones in df."""
        if climate_column not in df.columns:
            raise ValueError(f"Column '{climate_column}' not found in DataFrame.")
        climates = sorted(list(df[climate_column].dropna().unique()))
        if len(climates) < 2:
            raise ValueError(f"Need at least 2 distinct climate regimes for Leave-One-Climate-Out, found {len(climates)}.")

        for c in climates:
            yield self.split(df, held_out_climates=[c], climate_column=climate_column)
