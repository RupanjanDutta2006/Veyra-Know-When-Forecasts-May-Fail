"""Unit tests for Quality Control (QC) validation engine."""
from backend.app.data.qc import ForecastQualityControl, QualityControlResult
from backend.app.schemas.prediction import ReasonCode
from backend.app.schemas.weather import CanonicalForecastRecord


def _create_sample_record(
    location: str = "London",
    issue_time: str = "2026-08-25T00:00:00Z",
    valid_time: str = "2026-08-25T06:00:00Z",
    lead_hours: int = 6,
    variable: str = "temperature_2m",
    unit: str = "celsius",
    value: float = 18.5,
    member_count: int = 31,
    ensemble_min: float = 15.0,
    ensemble_max: float = 22.0,
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
        member_count=member_count,
        ensemble_mean=value,
        ensemble_min=ensemble_min,
        ensemble_max=ensemble_max,
    )


def test_qc_clean_records_pass():
    """Test that valid physical records pass all QC checks."""
    records = [
        _create_sample_record(valid_time="2026-08-25T06:00:00Z", lead_hours=6, value=18.5),
        _create_sample_record(valid_time="2026-08-25T12:00:00Z", lead_hours=12, value=21.0),
    ]
    qc = ForecastQualityControl()
    result = qc.validate_records(records)

    assert isinstance(result, QualityControlResult)
    assert result.passed is True
    assert result.flags["qc_passed"] is True
    assert len(result.violations) == 0
    assert result.reason_code == ReasonCode.SUCCESS


def test_qc_detects_empty_records():
    """Test that an empty record set fails QC with DATA_UNAVAILABLE."""
    qc = ForecastQualityControl()
    result = qc.validate_records([])

    assert result.passed is False
    assert result.flags["empty_dataset"] is True
    assert result.reason_code == ReasonCode.DATA_UNAVAILABLE


def test_qc_detects_duplicate_timestamps():
    """Test that duplicate variable records on the same valid timestamp trigger QC failure."""
    records = [
        _create_sample_record(valid_time="2026-08-25T06:00:00Z", lead_hours=6),
        _create_sample_record(valid_time="2026-08-25T06:00:00Z", lead_hours=6),
    ]
    qc = ForecastQualityControl()
    result = qc.validate_records(records)

    assert result.passed is False
    assert result.flags["has_duplicates"] is True
    assert result.reason_code == ReasonCode.QC_FAILED


def test_qc_detects_invalid_lead_hours():
    """Test that negative or mismatched lead times trigger QC failure."""
    rec = _create_sample_record(
        issue_time="2026-08-25T00:00:00Z",
        valid_time="2026-08-25T06:00:00Z",
        lead_hours=18,  # Mismatched (actual difference is 6)
    )
    qc = ForecastQualityControl()
    result = qc.validate_records([rec])

    assert result.passed is False
    assert result.flags["has_invalid_lead_times"] is True


def test_qc_detects_inconsistent_units():
    """Test that wrong unit strings (e.g., kelvin instead of celsius) trigger QC failure."""
    rec = _create_sample_record(variable="temperature_2m", unit="kelvin", value=293.15)
    qc = ForecastQualityControl()
    result = qc.validate_records([rec])

    assert result.passed is False
    assert result.flags["has_inconsistent_units"] is True


def test_qc_detects_out_of_bounds_temperature():
    """Test that physically impossible temperature values trigger QC failure."""
    rec = _create_sample_record(variable="temperature_2m", value=95.0)  # Impossible 95°C
    qc = ForecastQualityControl()
    result = qc.validate_records([rec])

    assert result.passed is False
    assert result.flags["has_out_of_bounds"] is True


def test_qc_detects_ensemble_min_greater_than_max():
    """Test that ensemble min > max triggers QC failure."""
    rec = _create_sample_record(ensemble_min=25.0, ensemble_max=15.0)
    qc = ForecastQualityControl()
    result = qc.validate_records([rec])

    assert result.passed is False
    assert result.flags["has_out_of_bounds"] is True
