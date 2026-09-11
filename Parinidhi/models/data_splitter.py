"""
Chronological and Group-Preserving Data Splitter.

Ensures strict temporal ordering with zero issue_time group leakage across
train, validation, and test splits.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np


@dataclass
class SplitData:
    """Container for split dataframes and metadata."""
    X_train: pd.DataFrame
    y_train: pd.Series
    df_train: pd.DataFrame
    X_val: pd.DataFrame
    y_val: pd.Series
    df_val: pd.DataFrame
    X_test: pd.DataFrame
    y_test: pd.Series
    df_test: pd.DataFrame
    train_cycles: List[str]
    val_cycles: List[str]
    test_cycles: List[str]


class ChronologicalDataSplitter:
    """Splits dataset chronologically by issue_time cycles to prevent temporal leakage."""

    def __init__(
        self,
        feature_columns: List[str],
        target_column: str = "bust_label",
        group_column: str = "issue_time",
    ):
        self.feature_columns = feature_columns
        self.target_column = target_column
        self.group_column = group_column

    def split_by_dates(
        self,
        df: pd.DataFrame,
        train_end_date: str = "2026-08-19",
        val_date: str = "2026-08-20",
        test_date: str = "2026-08-21",
    ) -> SplitData:
        """
        Split dataset into train, validation, and test by explicit issue_time cycle dates.
        
        Args:
            df: Full training dataset DataFrame.
            train_end_date: Last date for training (inclusive).
            val_date: Date for validation cycle.
            test_date: Date for test cycle.
            
        Returns:
            SplitData container.
        """
        df_work = df.copy()
        df_work["_issue_ts"] = pd.to_datetime(df_work[self.group_column], utc=True)

        t_train_end = pd.Timestamp(f"{train_end_date} 23:59:59", tz="UTC")
        t_val_start = pd.Timestamp(f"{val_date} 00:00:00", tz="UTC")
        t_val_end = pd.Timestamp(f"{val_date} 23:59:59", tz="UTC")
        t_test_start = pd.Timestamp(f"{test_date} 00:00:00", tz="UTC")
        t_test_end = pd.Timestamp(f"{test_date} 23:59:59", tz="UTC")

        mask_train = df_work["_issue_ts"] <= t_train_end
        mask_val = (df_work["_issue_ts"] >= t_val_start) & (df_work["_issue_ts"] <= t_val_end)
        mask_test = (df_work["_issue_ts"] >= t_test_start) & (df_work["_issue_ts"] <= t_test_end)

        df_train = df_work[mask_train].drop(columns=["_issue_ts"]).reset_index(drop=True)
        df_val = df_work[mask_val].drop(columns=["_issue_ts"]).reset_index(drop=True)
        df_test = df_work[mask_test].drop(columns=["_issue_ts"]).reset_index(drop=True)

        if len(df_train) == 0:
            raise ValueError(f"Train split is empty for train_end_date <= {train_end_date}")
        if len(df_val) == 0:
            raise ValueError(f"Validation split is empty for val_date = {val_date}")
        if len(df_test) == 0:
            raise ValueError(f"Test split is empty for test_date = {test_date}")

        # Invariant check: zero group overlap
        train_groups = set(df_train[self.group_column].astype(str).unique())
        val_groups = set(df_val[self.group_column].astype(str).unique())
        test_groups = set(df_test[self.group_column].astype(str).unique())

        if train_groups.intersection(val_groups):
            raise ValueError("Group overlap detected between Train and Validation sets!")
        if train_groups.intersection(test_groups):
            raise ValueError("Group overlap detected between Train and Test sets!")
        if val_groups.intersection(test_groups):
            raise ValueError("Group overlap detected between Validation and Test sets!")

        # Extract features and targets
        X_train = df_train[self.feature_columns].copy()
        y_train = df_train[self.target_column].astype(int)

        X_val = df_val[self.feature_columns].copy()
        y_val = df_val[self.target_column].astype(int)

        X_test = df_test[self.feature_columns].copy()
        y_test = df_test[self.target_column].astype(int)

        return SplitData(
            X_train=X_train,
            y_train=y_train,
            df_train=df_train,
            X_val=X_val,
            y_val=y_val,
            df_val=df_val,
            X_test=X_test,
            y_test=y_test,
            df_test=df_test,
            train_cycles=sorted(list(train_groups)),
            val_cycles=sorted(list(val_groups)),
            test_cycles=sorted(list(test_groups)),
        )

    def get_summary(self, split_data: SplitData) -> Dict[str, dict]:
        """Return structured summary of split statistics."""
        def _split_stats(df_split: pd.DataFrame, y_split: pd.Series, cycles: List[str]) -> dict:
            pos = int(y_split.sum())
            total = len(y_split)
            neg = total - pos
            rate = float(pos / total) if total > 0 else 0.0
            return {
                "total_rows": total,
                "cycles_count": len(cycles),
                "cycles": cycles,
                "positive_busts": pos,
                "negative_non_busts": neg,
                "positive_rate_pct": round(rate * 100.0, 2),
            }

        return {
            "train": _split_stats(split_data.df_train, split_data.y_train, split_data.train_cycles),
            "validation": _split_stats(split_data.df_val, split_data.y_val, split_data.val_cycles),
            "test": _split_stats(split_data.df_test, split_data.y_test, split_data.test_cycles),
        }
