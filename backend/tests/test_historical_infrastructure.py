"""Phase 2 / Builder 1 / Day 9 — Historical Data Infrastructure Test Suite.

Validates historical data collection, Day 8 location integration, canonical normalization,
quality control, deterministic deduplication, provider failure isolation, anti-leakage guards,
and Builder 2 dataset interfaces.
"""
import math
import os
import tempfile
import pytest
from pydantic import ValidationError

from backend.app.data.historical_qc import (
    HistoricalDeduplicator,
    HistoricalQualityControl,
)
from backend.app.schemas.historical import (
    CanonicalHistoricalRecord,
    HistoricalCollectionResult,
    HistoricalDataRequest,
)
from backend.app.schemas.reference import ReferenceWeatherRecord
from backend.app.services.historical_service import HistoricalDataService
from backend.app.services.location_service import DynamicLocationService


# Mock deterministic provider payload
SAMPLE_PROVIDER_PAYLOAD = {
    "latitude": 22.5726,
    "longitude": 88.3639,
    "timezone": "UTC",
    "hourly": {
        "time": [
            "2026-08-01T00:00",
            "2026-08-01T01:00",
            "2026-08-01T02:00",
        ],
        "temperature_2m": [28.5, 28.1, 27.8],
        "surface_pressure": [1005.2, 1005.4, 1005.8],
        "wind_speed_10m": [3.4, 3.2, 2.9],
        "relative_humidity_2m": [82.0, 84.5, 87.0],
        "precipitation": [0.0, 0.2, 0.0],
    },
}


def mock_http_client_success(url: str) -> dict:
    """Deterministic mock client returning valid meteorological data."""
    return SAMPLE_PROVIDER_PAYLOAD


def mock_http_client_timeout(url: str) -> dict:
    """Mock client simulating provider timeout."""
    raise TimeoutError("Connection to archive provider timed out after 15s")


def mock_http_client_malformed(url: str) -> list:
    """Mock client returning non-dict payload."""
    return ["malformed", "list", "instead", "of", "dict"]


# =============================================================================
# TEST 1: Valid Historical Collection Request
# =============================================================================
def test_valid_historical_collection_request():
    """Test 1: Valid historical collection request returns structured canonical records."""
    svc = HistoricalDataService(http_client=mock_http_client_success)
    req = HistoricalDataRequest(
        location="Kolkata",
        start_date="2026-08-01",
        end_date="2026-08-01",
        variables=["temperature_2m", "surface_pressure"],
    )
    result = svc.collect(req)

    assert isinstance(result, HistoricalCollectionResult)
    assert result.is_success is True
    assert result.location == "Kolkata"
    assert result.latitude == pytest.approx(22.5726, abs=1e-4)
    assert result.longitude == pytest.approx(88.3639, abs=1e-4)
    assert result.total_records == 6  # 3 time steps * 2 variables
    assert result.qc_passed is True
    assert len(result.qc_violations) == 0
    assert result.error_message is None

    # Check record structure
    first_rec = result.records[0]
    assert isinstance(first_rec, CanonicalHistoricalRecord)
    assert first_rec.location == "Kolkata"
    assert first_rec.variable in ("temperature_2m", "surface_pressure")
    assert first_rec.is_ground_truth_label is True
    assert first_rec.record_id is not None and len(first_rec.record_id) > 0


# =============================================================================
# TEST 2: Dynamic City Input through Day 8 Location Resolution
# =============================================================================
def test_dynamic_city_input_through_day8_location_service():
    """Test 2: Dynamic city resolution feeds resolved coordinates to historical collection."""
    svc = HistoricalDataService(http_client=mock_http_client_success)
    req = HistoricalDataRequest(
        location="London",
        start_date="2026-08-01",
        end_date="2026-08-01",
        variables=["temperature_2m"],
    )
    result = svc.collect(req)

    assert result.is_success is True
    assert result.location == "London"
    assert result.latitude == pytest.approx(51.5074, abs=1e-4)
    assert result.longitude == pytest.approx(-0.1278, abs=1e-4)
    assert result.total_records == 3


# =============================================================================
# TEST 3: Direct Coordinates Support
# =============================================================================
def test_direct_coordinates_historical_collection():
    """Test 3: Direct coordinates work without requiring place-name geocoding."""
    svc = HistoricalDataService(http_client=mock_http_client_success)
    req = HistoricalDataRequest(
        location="22.5726, 88.3639",
        start_date="2026-08-01",
        end_date="2026-08-01",
        variables=["temperature_2m"],
    )
    result = svc.collect(req)

    assert result.is_success is True
    assert result.latitude == pytest.approx(22.5726, abs=1e-4)
    assert result.longitude == pytest.approx(88.3639, abs=1e-4)
    assert result.total_records == 3


# =============================================================================
# TEST 4: Invalid Location Safety
# =============================================================================
def test_invalid_location_safety():
    """Test 4: Unresolvable location safely fails without generating fake records."""
    svc = HistoricalDataService(http_client=mock_http_client_success)
    req = HistoricalDataRequest(
        location="Atlantis",
        start_date="2026-08-01",
        end_date="2026-08-01",
    )
    result = svc.collect(req)

    assert result.is_success is False
    assert result.error_message == "INVALID_LOCATION"
    assert len(result.records) == 0
    assert result.total_records == 0
    assert result.qc_passed is False


# =============================================================================
# TEST 5: Invalid Coordinates Safety
# =============================================================================
def test_invalid_coordinates_safety():
    """Test 5: Out-of-bounds coordinates are rejected safely."""
    svc = HistoricalDataService(http_client=mock_http_client_success)
    req = HistoricalDataRequest(
        location="999.0, 999.0",
        start_date="2026-08-01",
        end_date="2026-08-01",
    )
    result = svc.collect(req)

    assert result.is_success is False
    assert result.error_message in ("INVALID_LOCATION", "INVALID_COORDINATES")
    assert len(result.records) == 0


# =============================================================================
# TEST 6: Invalid Date/Time Ordering
# =============================================================================
def test_invalid_date_ordering_validation_error():
    """Test 6: start_date > end_date raises Pydantic validation error."""
    with pytest.raises(ValidationError) as excinfo:
        HistoricalDataRequest(
            location="Kolkata",
            start_date="2026-08-10",
            end_date="2026-08-01",  # Before start_date
        )
    assert "start_date" in str(excinfo.value) and "must be before or equal to end_date" in str(excinfo.value)


# =============================================================================
# TEST 7: Unsupported Variable Rejection
# =============================================================================
def test_unsupported_variable_validation_error():
    """Test 7: Unsupported variable name is rejected by schema validator."""
    with pytest.raises(ValidationError) as excinfo:
        HistoricalDataRequest(
            location="Kolkata",
            start_date="2026-08-01",
            end_date="2026-08-01",
            variables=["unsupported_stock_price"],
        )
    assert "Unsupported variable" in str(excinfo.value)


# =============================================================================
# TEST 8: Provider Timeout / Failure Handling
# =============================================================================
def test_provider_timeout_handled_gracefully():
    """Test 8: Provider timeout returns structured controlled error without crashing."""
    svc = HistoricalDataService(http_client=mock_http_client_timeout)
    req = HistoricalDataRequest(
        location="Kolkata",
        start_date="2026-08-01",
        end_date="2026-08-01",
    )
    result = svc.collect(req)

    assert result.is_success is False
    assert result.error_message == "PROVIDER_ERROR"
    assert len(result.records) == 0
    assert result.qc_passed is False
    assert any("timed out" in v for v in result.qc_violations)


# =============================================================================
# TEST 9: Malformed Provider Response
# =============================================================================
def test_malformed_provider_response_handled_gracefully():
    """Test 9: Malformed non-dictionary provider payload triggers controlled failure."""
    svc = HistoricalDataService(http_client=mock_http_client_malformed)
    req = HistoricalDataRequest(
        location="Kolkata",
        start_date="2026-08-01",
        end_date="2026-08-01",
    )
    result = svc.collect(req)

    assert result.is_success is False
    assert result.error_message == "MALFORMED_PROVIDER_RESPONSE"
    assert len(result.records) == 0


# =============================================================================
# TEST 10: Missing Values / Non-Finite QC Detection
# =============================================================================
def test_qc_detects_non_finite_and_out_of_bounds_values():
    """Test 10: QC engine detects non-finite and physically impossible values."""
    qc = HistoricalQualityControl()
    bad_records = [
        CanonicalHistoricalRecord.create(
            location="Kolkata",
            latitude=22.5726,
            longitude=88.3639,
            valid_time="2026-08-01T00:00:00Z",
            variable="temperature_2m",
            unit="celsius",
            value=float("nan"),  # Non-finite
        ),
        CanonicalHistoricalRecord.create(
            location="Kolkata",
            latitude=22.5726,
            longitude=88.3639,
            valid_time="2026-08-01T01:00:00Z",
            variable="temperature_2m",
            unit="celsius",
            value=120.0,  # Physically impossible > 60°C
        ),
    ]
    qc_res = qc.validate_records(bad_records)

    assert qc_res.passed is False
    assert qc_res.flags["has_non_finite_values"] is True
    assert qc_res.flags["has_out_of_bounds"] is True
    assert len(qc_res.violations) >= 2


# =============================================================================
# TEST 11: Duplicate Records Removed Deterministically
# =============================================================================
def test_duplicate_records_removed_deterministically():
    """Test 11: Identical duplicate records are filtered out while preserving one."""
    deduplicator = HistoricalDeduplicator()
    rec1 = CanonicalHistoricalRecord.create(
        location="Kolkata",
        latitude=22.5726,
        longitude=88.3639,
        valid_time="2026-08-01T00:00:00Z",
        variable="temperature_2m",
        unit="celsius",
        value=28.5,
    )
    rec2 = CanonicalHistoricalRecord.create(
        location="Kolkata",
        latitude=22.5726,
        longitude=88.3639,
        valid_time="2026-08-01T00:00:00Z",
        variable="temperature_2m",
        unit="celsius",
        value=28.5,
    )
    rec3 = CanonicalHistoricalRecord.create(
        location="Kolkata",
        latitude=22.5726,
        longitude=88.3639,
        valid_time="2026-08-01T00:00:00Z",
        variable="temperature_2m",
        unit="celsius",
        value=28.5,
    )

    deduped, removed_count = deduplicator.deduplicate([rec1, rec2, rec3])
    assert len(deduped) == 1
    assert removed_count == 2
    assert deduped[0].value == 28.5


# =============================================================================
# TEST 12: Distinct Legitimate Records Preserved
# =============================================================================
def test_distinct_legitimate_records_preserved():
    """Test 12: Distinct timestamps and variables are strictly preserved."""
    deduplicator = HistoricalDeduplicator()
    rec_time1 = CanonicalHistoricalRecord.create(
        location="Kolkata",
        latitude=22.5726,
        longitude=88.3639,
        valid_time="2026-08-01T00:00:00Z",
        variable="temperature_2m",
        unit="celsius",
        value=28.5,
    )
    rec_time2 = CanonicalHistoricalRecord.create(
        location="Kolkata",
        latitude=22.5726,
        longitude=88.3639,
        valid_time="2026-08-01T01:00:00Z",  # Different timestamp
        variable="temperature_2m",
        unit="celsius",
        value=28.1,
    )
    rec_var2 = CanonicalHistoricalRecord.create(
        location="Kolkata",
        latitude=22.5726,
        longitude=88.3639,
        valid_time="2026-08-01T00:00:00Z",
        variable="surface_pressure",  # Different variable
        unit="hPa",
        value=1005.2,
    )

    deduped, removed_count = deduplicator.deduplicate([rec_time1, rec_time2, rec_var2])
    assert len(deduped) == 3
    assert removed_count == 0


# =============================================================================
# TEST 13: Canonical Schema Consistency
# =============================================================================
def test_canonical_schema_consistency():
    """Test 13: Provider data correctly mapped to canonical units and names."""
    svc = HistoricalDataService(http_client=mock_http_client_success)
    req = HistoricalDataRequest(
        location="Kolkata",
        start_date="2026-08-01",
        end_date="2026-08-01",
        variables=["temperature", "pressure", "wind_speed", "humidity", "precipitation"],
    )
    result = svc.collect(req)

    assert result.is_success is True
    variables = {r.variable for r in result.records}
    units = {r.variable: r.unit for r in result.records}

    assert "temperature_2m" in variables and units["temperature_2m"] == "celsius"
    assert "surface_pressure" in variables and units["surface_pressure"] == "hPa"
    assert "wind_speed_10m" in variables and units["wind_speed_10m"] == "m/s"
    assert "relative_humidity_2m" in variables and units["relative_humidity_2m"] == "%"
    assert "precipitation" in variables and units["precipitation"] == "mm"


# =============================================================================
# TEST 14: Anti-Data-Leakage Isolation
# =============================================================================
def test_reference_prediction_data_isolation():
    """Test 14: Historical ground truth records have is_ground_truth_label=True and are isolated."""
    svc = HistoricalDataService(http_client=mock_http_client_success)
    req = HistoricalDataRequest(
        location="Kolkata",
        start_date="2026-08-01",
        end_date="2026-08-01",
        variables=["temperature_2m"],
    )
    result = svc.collect(req)

    for rec in result.records:
        assert rec.is_ground_truth_label is True
        assert rec.record_type == "OBSERVATION"


# =============================================================================
# TEST 15: Day 8 Dynamic Location Compatibility
# =============================================================================
def test_day8_dynamic_location_compatibility():
    """Test 15: Day 8 DynamicLocationService resolves non-predefined cities correctly."""
    loc_svc = DynamicLocationService()
    resolved = loc_svc.resolve("Siliguri")
    assert resolved is not None
    assert resolved.name == "Siliguri"
    assert resolved.latitude > 0.0
    assert resolved.longitude > 0.0

    # Pass into HistoricalDataService
    hist_svc = HistoricalDataService(
        location_service=loc_svc,
        http_client=mock_http_client_success,
    )
    req = HistoricalDataRequest(
        location="Siliguri",
        start_date="2026-08-01",
        end_date="2026-08-01",
        variables=["temperature_2m"],
    )
    result = hist_svc.collect(req)
    assert result.is_success is True
    assert result.location == "Siliguri"


# =============================================================================
# TEST 16: Builder 2 Interface & JSONL Serialization
# =============================================================================
def test_builder2_jsonl_serialization_and_reference_conversion():
    """Test 16: Builder 2 JSONL export/load and conversion to ReferenceWeatherRecord."""
    svc = HistoricalDataService(http_client=mock_http_client_success)
    req = HistoricalDataRequest(
        location="Kolkata",
        start_date="2026-08-01",
        end_date="2026-08-01",
        variables=["temperature_2m"],
    )
    result = svc.collect(req)

    # Test export and load
    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = os.path.join(tmpdir, "historical_kolkata.jsonl")
        exported_count = HistoricalDataService.export_to_jsonl(result.records, jsonl_path)
        assert exported_count == len(result.records)

        loaded_records = HistoricalDataService.load_from_jsonl(jsonl_path)
        assert len(loaded_records) == len(result.records)
        assert loaded_records[0].record_id == result.records[0].record_id
        assert loaded_records[0].value == result.records[0].value

    # Test conversion to ReferenceWeatherRecord
    ref_records = HistoricalDataService.to_reference_records(result.records)
    assert len(ref_records) == len(result.records)
    assert isinstance(ref_records[0], ReferenceWeatherRecord)
    assert ref_records[0].location == "Kolkata"
    assert ref_records[0].observed_value == result.records[0].value
    assert ref_records[0].is_ground_truth_label is True
