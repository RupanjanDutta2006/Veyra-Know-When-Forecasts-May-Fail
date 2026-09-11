"""Chronological Time-Aware Data Splitter for Leakage-Safe Model Training."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from backend.app.data.training_dataset import HistoricalTrainingRow


class TemporalLeakageError(ValueError):
    """Raised when temporal train/validation/test partitions overlap or violate causality."""


@dataclass
class DatasetSplits:
    """Container holding chronological data partitions."""

    train_rows: list[HistoricalTrainingRow]
    val_rows: list[HistoricalTrainingRow]
    test_rows: list[HistoricalTrainingRow]
    train_time_range: tuple[str, str]
    val_time_range: tuple[str, str]
    test_time_range: tuple[str, str]


class TemporalDataSplitter:
    """Partitions historical verification records strictly by chronological issue timestamp."""

    def __init__(
        self,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
    ):
        if not abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-5:
            raise ValueError(f"Ratios must sum to 1.0, got {train_ratio + val_ratio + test_ratio}")
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio

    @staticmethod
    def _parse_iso(iso_str: str) -> datetime:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))

    def split(self, rows: list[HistoricalTrainingRow]) -> DatasetSplits:
        """Split rows chronologically into Train, Validation, and Test partitions.

        Strict Scientific Rule:
        max(train.issue_time) <= min(val.issue_time) <= max(val.issue_time) <= min(test.issue_time)
        """
        if len(rows) < 3:
            raise ValueError(f"Need at least 3 rows for temporal train/val/test split, got {len(rows)}")

        # Sort chronologically by issue_time first, then valid_time
        sorted_rows = sorted(
            rows,
            key=lambda r: (self._parse_iso(r.issue_time), self._parse_iso(r.valid_time)),
        )

        n = len(sorted_rows)
        n_train = max(1, int(n * self.train_ratio))
        n_val = max(1, int(n * self.val_ratio))

        # Adjust for boundary allocations
        if n_train + n_val >= n:
            n_train = max(1, n - 2)
            n_val = 1

        train = sorted_rows[:n_train]
        val = sorted_rows[n_train : n_train + n_val]
        test = sorted_rows[n_train + n_val :]

        if not test:
            test = [val.pop()] if len(val) > 1 else [train.pop()]

        # Verify temporal boundaries
        train_max = self._parse_iso(train[-1].issue_time)
        val_min = self._parse_iso(val[0].issue_time)
        val_max = self._parse_iso(val[-1].issue_time)
        test_min = self._parse_iso(test[0].issue_time)

        if train_max > val_min:
            raise TemporalLeakageError(
                f"Temporal leakage detected: max(train.issue_time) ({train_max}) > min(val.issue_time) ({val_min})"
            )
        if val_max > test_min:
            raise TemporalLeakageError(
                f"Temporal leakage detected: max(val.issue_time) ({val_max}) > min(test.issue_time) ({test_min})"
            )

        return DatasetSplits(
            train_rows=train,
            val_rows=val,
            test_rows=test,
            train_time_range=(train[0].issue_time, train[-1].issue_time),
            val_time_range=(val[0].issue_time, val[-1].issue_time),
            test_time_range=(test[0].issue_time, test[-1].issue_time),
        )
