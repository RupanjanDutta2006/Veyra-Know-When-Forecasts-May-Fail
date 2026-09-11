"""Unit tests for Chronological Time-Aware Data Splitter."""
import pytest
from backend.app.data.training_dataset import HistoricalTrainingRow
from backend.app.ml.splitting import TemporalDataSplitter, TemporalLeakageError


def _create_row_at_time(issue_time: str, valid_time: str) -> HistoricalTrainingRow:
    return HistoricalTrainingRow(
        location="London",
        latitude=51.5074,
        longitude=-0.1278,
        region="western_europe",
        variable="temperature_2m",
        issue_time=issue_time,
        valid_time=valid_time,
        lead_hours=24,
        forecast_value=20.0,
        reference_value=19.0,
        unit="celsius",
        error=1.0,
        absolute_error=1.0,
        season="summer",
        month=8,
        bust_label=0,
        bust_threshold=3.0,
    )


def test_temporal_splitter_chronological_order():
    """Test that records are partitioned strictly into past (train), intermediate (val), and future (test)."""
    rows = [
        _create_row_at_time("2026-08-01T00:00:00Z", "2026-08-02T00:00:00Z"),
        _create_row_at_time("2026-08-05T00:00:00Z", "2026-08-06T00:00:00Z"),
        _create_row_at_time("2026-08-10T00:00:00Z", "2026-08-11T00:00:00Z"),
        _create_row_at_time("2026-08-15T00:00:00Z", "2026-08-16T00:00:00Z"),
        _create_row_at_time("2026-08-20T00:00:00Z", "2026-08-21T00:00:00Z"),
    ]

    splitter = TemporalDataSplitter(train_ratio=0.60, val_ratio=0.20, test_ratio=0.20)
    splits = splitter.split(rows)

    assert len(splits.train_rows) >= 1
    assert len(splits.val_rows) >= 1
    assert len(splits.test_rows) >= 1

    # Check temporal invariant: train <= val <= test
    assert splits.train_rows[-1].issue_time <= splits.val_rows[0].issue_time
    assert splits.val_rows[-1].issue_time <= splits.test_rows[0].issue_time


def test_temporal_splitter_ratio_validation():
    """Test that invalid split ratios summing != 1.0 raise ValueError."""
    with pytest.raises(ValueError):
        TemporalDataSplitter(train_ratio=0.5, val_ratio=0.2, test_ratio=0.1)


def test_temporal_splitter_min_rows_validation():
    """Test that fewer than 3 rows raises ValueError."""
    with pytest.raises(ValueError):
        TemporalDataSplitter().split([_create_row_at_time("2026-08-01T00:00:00Z", "2026-08-02T00:00:00Z")])
