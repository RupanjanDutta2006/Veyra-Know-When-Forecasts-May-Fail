"""Unit tests for Leakage-Safe Feature Engineering Pipeline."""
import pytest
from backend.app.data.training_dataset import HistoricalTrainingRow
from backend.app.ml.features import (
    FORBIDDEN_LEAKAGE_FIELDS,
    FeaturePipeline,
    InferenceSafeFeatureExtractor,
)
from backend.app.schemas.weather import CanonicalForecastRecord


def _sample_training_row(
    issue_time: str = "2026-08-20T00:00:00Z",
    valid_time: str = "2026-08-23T12:00:00Z",
    lead_hours: int = 84,
    forecast_val: float = 24.5,
    reference_val: float = 20.0,
    bust_label: int = 1,
    variable: str = "temperature_2m",
    season: str = "summer",
) -> HistoricalTrainingRow:
    fc_err = round(forecast_val - reference_val, 4)
    return HistoricalTrainingRow(
        location="London",
        latitude=51.5074,
        longitude=-0.1278,
        region="western_europe",
        variable=variable,
        issue_time=issue_time,
        valid_time=valid_time,
        lead_hours=lead_hours,
        forecast_value=forecast_val,
        reference_value=reference_val,
        unit="celsius",
        error=fc_err,
        absolute_error=abs(fc_err),
        season=season,
        month=8,
        bust_label=bust_label,
        bust_threshold=3.0,
        forecast_source="NOAA_GEFS_OPENMETEO",
        reference_source="ERA5_REANALYSIS",
    )


def test_feature_extractor_excludes_leakage_fields():
    """Verify that forbidden ground truth and error fields NEVER enter extracted features."""
    row = _sample_training_row()
    extractor = InferenceSafeFeatureExtractor()
    features = extractor.extract_raw_features(row)

    for forbidden in FORBIDDEN_LEAKAGE_FIELDS:
        assert forbidden not in features, f"Forbidden leakage field '{forbidden}' found in extracted features!"


def test_feature_extractor_cyclic_and_onehot_encodings():
    """Test cyclic trigonometric encodings and one-hot encoding of variable and season."""
    row = _sample_training_row(variable="temperature_2m", season="summer")
    extractor = InferenceSafeFeatureExtractor()
    features = extractor.extract_raw_features(row)

    assert "sin_month" in features
    assert "cos_month" in features
    assert "sin_hour" in features
    assert "cos_hour" in features
    assert features["var_temperature_2m"] == 1.0
    assert features["var_wind_speed_10m"] == 0.0
    assert features["season_summer"] == 1.0
    assert features["season_winter"] == 0.0


def test_feature_pipeline_fit_and_transform():
    """Test standard feature normalization and deterministic ordering."""
    train_rows = [
        _sample_training_row(forecast_val=15.0, bust_label=0),
        _sample_training_row(forecast_val=22.0, bust_label=0),
        _sample_training_row(forecast_val=28.0, bust_label=1),
    ]

    pipeline = FeaturePipeline()
    pipeline.fit(train_rows)

    assert pipeline.is_fitted is True
    feature_names = pipeline.get_feature_names()
    assert len(feature_names) > 10
    assert feature_names == sorted(feature_names)

    X, y = pipeline.transform(train_rows)
    assert X.shape == (3, len(feature_names))
    assert y.shape == (3,)
    assert list(y) == [0, 0, 1]


def test_feature_pipeline_transform_inference_compatibility():
    """Test that live CanonicalForecastRecords can be transformed seamlessly for inference."""
    train_rows = [
        _sample_training_row(forecast_val=18.0, bust_label=0),
        _sample_training_row(forecast_val=25.0, bust_label=1),
    ]
    pipeline = FeaturePipeline().fit(train_rows)

    live_record = CanonicalForecastRecord(
        location="London",
        latitude=51.5074,
        longitude=-0.1278,
        issue_time="2026-08-25T00:00:00Z",
        valid_time="2026-08-28T12:00:00Z",
        lead_hours=84,
        variable="temperature_2m",
        unit="celsius",
        value=23.4,
    )

    X_live = pipeline.transform_inference([live_record])
    assert X_live.shape == (1, len(pipeline.get_feature_names()))
