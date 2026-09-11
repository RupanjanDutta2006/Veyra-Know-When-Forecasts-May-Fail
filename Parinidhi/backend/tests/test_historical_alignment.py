"""Unit tests for Historical Alignment Engine and Forecast Error Calculation."""
from backend.app.data.alignment import (
    AlignedVerificationRecord,
    HistoricalAlignmentEngine,
)
from backend.app.schemas.reference import ReferenceWeatherRecord
from backend.app.schemas.weather import CanonicalForecastRecord


def _sample_forecast_record(
    location: str = "London",
    variable: str = "temperature_2m",
    unit: str = "celsius",
    issue_time: str = "2026-08-20T00:00:00Z",
    valid_time: str = "2026-08-23T12:00:00Z",
    lead_hours: int = 84,
    value: float = 24.5,
) -> CanonicalForecastRecord:
    return CanonicalForecastRecord(
        location=location,
        latitude=51.5074,
        longitude=-0.1278,
        issue_time=issue_time,
        valid_time=valid_time,
        lead_hours=lead_hours,
        variable=variable,
        unit=unit,
        value=value,
        member_count=31,
        ensemble_mean=value,
    )


def _sample_reference_record(
    location: str = "London",
    variable: str = "temperature_2m",
    unit: str = "celsius",
    valid_time: str = "2026-08-23T12:00:00Z",
    observed_value: float = 21.0,
) -> ReferenceWeatherRecord:
    return ReferenceWeatherRecord(
        location=location,
        latitude=51.5074,
        longitude=-0.1278,
        variable=variable,
        unit=unit,
        valid_time=valid_time,
        observed_value=observed_value,
        source="ERA5_REANALYSIS",
    )


def test_align_single_exact_match():
    """Test exact spatial, temporal, and variable alignment."""
    fc = _sample_forecast_record(value=25.0)
    ref = _sample_reference_record(observed_value=21.5)

    engine = HistoricalAlignmentEngine()
    aligned = engine.align_single(fc, ref)

    assert isinstance(aligned, AlignedVerificationRecord)
    assert aligned.location == "London"
    assert aligned.variable == "temperature_2m"
    assert aligned.forecast_value == 25.0
    assert aligned.reference_value == 21.5
    assert aligned.forecast_error == 3.5  # 25.0 - 21.5
    assert aligned.absolute_error == 3.5
    assert aligned.issue_time == "2026-08-20T00:00:00Z"
    assert aligned.valid_time == "2026-08-23T12:00:00Z"
    assert aligned.lead_hours == 84
    assert aligned.alignment_status == "SUCCESS"


def test_align_single_unit_conversion():
    """Test alignment when reference observation uses a compatible but different unit (Kelvin -> Celsius)."""
    fc = _sample_forecast_record(unit="celsius", value=22.0)
    # 293.15 K == 20.0 °C
    ref = _sample_reference_record(unit="kelvin", observed_value=293.15)

    engine = HistoricalAlignmentEngine()
    aligned = engine.align_single(fc, ref)

    assert aligned is not None
    assert aligned.unit == "celsius"
    assert aligned.reference_value == 20.0
    assert aligned.forecast_error == 2.0  # 22.0 - 20.0
    assert aligned.absolute_error == 2.0
    assert aligned.alignment_status == "UNIT_CONVERTED"


def test_align_single_valid_time_mismatch_fails():
    """Test that mismatched valid times do not align."""
    fc = _sample_forecast_record(valid_time="2026-08-23T12:00:00Z")
    ref = _sample_reference_record(valid_time="2026-08-23T18:00:00Z")

    engine = HistoricalAlignmentEngine()
    aligned = engine.align_single(fc, ref)
    assert aligned is None


def test_align_single_variable_mismatch_fails():
    """Test that different meteorological variables do not align."""
    fc = _sample_forecast_record(variable="temperature_2m")
    ref = _sample_reference_record(variable="wind_speed_10m")

    engine = HistoricalAlignmentEngine()
    aligned = engine.align_single(fc, ref)
    assert aligned is None


def test_align_single_anti_leakage_guard():
    """Test that a reference observation timestamp before the forecast issue cycle is rejected."""
    fc = _sample_forecast_record(
        issue_time="2026-08-25T00:00:00Z",
        valid_time="2026-08-20T00:00:00Z",  # Valid time in the past relative to issue
    )
    ref = _sample_reference_record(valid_time="2026-08-20T00:00:00Z")

    engine = HistoricalAlignmentEngine()
    aligned = engine.align_single(fc, ref)
    assert aligned is None


def test_align_datasets_bulk():
    """Test bulk alignment of multiple forecast records against reference observation table."""
    fc_list = [
        _sample_forecast_record(valid_time="2026-08-23T06:00:00Z", value=18.0),
        _sample_forecast_record(valid_time="2026-08-23T12:00:00Z", value=24.0),
        _sample_forecast_record(valid_time="2026-08-23T18:00:00Z", value=20.0),
    ]
    ref_list = [
        _sample_reference_record(valid_time="2026-08-23T06:00:00Z", observed_value=16.0),
        _sample_reference_record(valid_time="2026-08-23T12:00:00Z", observed_value=21.0),
        # 18:00 observation is missing
    ]

    engine = HistoricalAlignmentEngine()
    aligned_list = engine.align_datasets(fc_list, ref_list)

    assert len(aligned_list) == 2
    assert aligned_list[0].valid_time == "2026-08-23T06:00:00Z"
    assert aligned_list[0].forecast_error == 2.0
    assert aligned_list[1].valid_time == "2026-08-23T12:00:00Z"
    assert aligned_list[1].forecast_error == 3.0
