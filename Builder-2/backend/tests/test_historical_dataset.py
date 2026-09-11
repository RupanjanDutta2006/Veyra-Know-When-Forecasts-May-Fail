"""Unit tests for Historical Training Dataset construction and Reference Service."""
import os
import tempfile
from unittest.mock import MagicMock
from backend.app.data.alignment import AlignedVerificationRecord
from backend.app.data.training_dataset import (
    HistoricalDatasetBuilder,
    HistoricalTrainingRow,
    derive_season,
)
from backend.app.schemas.reference import ReferenceWeatherRecord
from backend.app.services.reference_service import OpenMeteoArchiveReferenceService


def _sample_aligned_record(
    valid_time: str = "2026-08-23T12:00:00Z",
    lead_hours: int = 84,
    forecast_val: float = 26.0,
    reference_val: float = 22.0,
) -> AlignedVerificationRecord:
    fc_err = round(forecast_val - reference_val, 4)
    return AlignedVerificationRecord(
        location="London",
        latitude=51.5074,
        longitude=-0.1278,
        variable="temperature_2m",
        unit="celsius",
        issue_time="2026-08-20T00:00:00Z",
        valid_time=valid_time,
        lead_hours=lead_hours,
        forecast_value=forecast_val,
        reference_value=reference_val,
        original_reference_value=reference_val,
        original_reference_unit="celsius",
        forecast_error=fc_err,
        absolute_error=abs(fc_err),
    )


def test_derive_season():
    """Test seasonal partitioning across calendar months."""
    assert derive_season(1) == "winter"
    assert derive_season(12) == "winter"
    assert derive_season(4) == "spring"
    assert derive_season(7) == "summer"
    assert derive_season(10) == "autumn"


def test_historical_dataset_builder_row():
    """Test converting aligned record to a complete HistoricalTrainingRow."""
    builder = HistoricalDatasetBuilder(region="europe")
    aligned = _sample_aligned_record(valid_time="2026-08-23T12:00:00Z", forecast_val=26.0, reference_val=22.0)
    row = builder.build_row(aligned)

    assert isinstance(row, HistoricalTrainingRow)
    assert row.location == "London"
    assert row.variable == "temperature_2m"
    assert row.season == "summer"
    assert row.month == 8
    assert row.error == 4.0
    assert row.absolute_error == 4.0
    assert row.bust_label == 1  # 4.0 >= 3.0 threshold
    assert row.bust_threshold == 3.0
    assert row.is_ground_truth_label is True


def test_historical_dataset_jsonl_serialization():
    """Test serialization and round-trip deserialization of training rows to JSON Lines."""
    builder = HistoricalDatasetBuilder()
    rows = [
        builder.build_row(_sample_aligned_record(forecast_val=22.0, reference_val=21.0)),
        builder.build_row(_sample_aligned_record(forecast_val=28.0, reference_val=22.0)),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = os.path.join(tmpdir, "test_dataset.jsonl")
        HistoricalDatasetBuilder.save_to_jsonl(rows, jsonl_path)

        assert os.path.exists(jsonl_path)
        loaded = HistoricalDatasetBuilder.load_from_jsonl(jsonl_path)
        assert len(loaded) == 2
        assert loaded[0]["location"] == "London"
        assert loaded[0]["bust_label"] == 0
        assert loaded[1]["bust_label"] == 1


def test_reference_weather_service_offline():
    """Test OpenMeteoArchiveReferenceService using mock HTTP transport."""
    mock_payload = {
        "latitude": 51.5,
        "longitude": -0.12,
        "hourly": {
            "time": ["2026-08-20T00:00", "2026-08-20T06:00"],
            "temperature_2m": [14.2, 17.5],
            "surface_pressure": [1015.0, 1014.2],
            "wind_speed_10m": [3.1, 4.0],
            "relative_humidity_2m": [80.0, 70.0],
            "precipitation": [0.0, 0.0],
        },
    }
    mock_http = MagicMock(return_value=mock_payload)
    service = OpenMeteoArchiveReferenceService(http_client=mock_http)
    records = service.get_reference_data("London", "2026-08-20", "2026-08-20")

    assert len(records) == 10  # 2 timestamps * 5 variables
    first = records[0]
    assert isinstance(first, ReferenceWeatherRecord)
    assert first.location == "London"
    assert first.variable == "temperature_2m"
    assert first.observed_value == 14.2
    assert first.source == "ERA5_REANALYSIS"
    assert first.is_ground_truth_label is True
