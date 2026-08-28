"""Comprehensive automated unit and integration tests for Multi-Location Platform Support (Day 10).

Verifies multi-location contracts, batch validation, failure isolation, deduplication,
deterministic ordering, historical collection integration, QC isolation, Builder 2 bridges,
and FastAPI batch endpoints without requiring active internet access.
"""
import copy
import json
import os
import tempfile
from typing import Any
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.historical import (
    CanonicalHistoricalRecord,
    HistoricalCollectionResult,
    HistoricalDataRequest,
)
from backend.app.schemas.multi_location import (
    MAX_MULTI_LOCATION_BATCH_SIZE,
    MultiLocationHistoricalRequest,
    MultiLocationHistoricalResult,
    MultiLocationPredictionRequest,
    MultiLocationPredictionResult,
)
from backend.app.schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
    ReasonCode,
    RiskLevel,
    TrustState,
)
from backend.app.services.historical_service import HistoricalDataService
from backend.app.services.location_service import DynamicLocationService
from backend.app.services.multi_location_service import MultiLocationService


@pytest.fixture
def mock_openmeteo_historical_payload() -> dict[str, Any]:
    """Provide realistic deterministic historical archive payload for 2 hours x 2 variables."""
    return {
        "latitude": 22.57,
        "longitude": 88.36,
        "hourly": {
            "time": ["2026-08-01T00:00", "2026-08-01T01:00"],
            "temperature_2m": [28.5, 29.0],
            "surface_pressure": [1005.2, 1005.0],
            "wind_speed_10m": [3.5, 4.0],
            "relative_humidity_2m": [80.0, 78.0],
            "precipitation": [0.0, 0.5],
        },
    }


@pytest.fixture
def mock_multi_service(mock_openmeteo_historical_payload: dict[str, Any]) -> MultiLocationService:
    """Provide a MultiLocationService instance backed by deterministic mock HTTP client."""
    def mock_http(url: str) -> dict[str, Any]:
        if "fail_provider" in url:
            raise RuntimeError("Simulated upstream provider outage (HTTP 502)")
        if "timeout_provider" in url:
            raise TimeoutError("Simulated network timeout (15s exceeded)")
        return copy.deepcopy(mock_openmeteo_historical_payload)

    hist_service = HistoricalDataService(
        http_client=mock_http,
        location_service=DynamicLocationService(),
    )
    return MultiLocationService(
        historical_service=hist_service,
        location_service=DynamicLocationService(),
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# =====================================================================
# 1. BATCH VALIDATION & REQUEST CONTRACT TESTS
# =====================================================================

def test_single_location_in_multi_location_request():
    """Verify that a single location works seamlessly via multi-location contract."""
    req = MultiLocationHistoricalRequest(
        locations=["Kolkata"],
        start_date="2026-08-01",
        end_date="2026-08-01",
    )
    assert len(req.locations) == 1
    assert req.locations[0] == "Kolkata"


def test_multiple_valid_cities_request():
    """Verify multi-city batch creation and validation."""
    cities = ["Kolkata", "London", "Tokyo", "Paris"]
    req = MultiLocationHistoricalRequest(
        locations=cities,
        start_date="2026-08-01",
        end_date="2026-08-02",
    )
    assert len(req.locations) == 4
    assert req.locations == cities


def test_mixed_city_and_direct_coordinates():
    """Verify mixed city names and direct coordinate strings in a single batch."""
    mixed = ["Kolkata", "51.5074, -0.1278", "Tokyo", "48.8566, 2.3522"]
    req = MultiLocationHistoricalRequest(
        locations=mixed,
        start_date="2026-08-01",
        end_date="2026-08-01",
    )
    assert len(req.locations) == 4


def test_empty_location_list_validation_error():
    """Verify validation error when locations list is empty."""
    with pytest.raises(ValueError, match="locations"):
        MultiLocationHistoricalRequest(
            locations=[],
            start_date="2026-08-01",
            end_date="2026-08-01",
        )


def test_whitespace_location_entry_validation_error():
    """Verify validation error when an individual location entry is pure whitespace."""
    with pytest.raises(ValueError, match="whitespace"):
        MultiLocationHistoricalRequest(
            locations=["Kolkata", "   ", "London"],
            start_date="2026-08-01",
            end_date="2026-08-01",
        )


def test_batch_above_maximum_limit_error():
    """Verify validation error when batch size exceeds MAX_MULTI_LOCATION_BATCH_SIZE (50)."""
    oversize = [f"City_{i}" for i in range(MAX_MULTI_LOCATION_BATCH_SIZE + 5)]
    with pytest.raises(Exception, match="(at most 50|exceeds maximum)"):
        MultiLocationHistoricalRequest(
            locations=oversize,
            start_date="2026-08-01",
            end_date="2026-08-01",
        )


def test_invalid_date_order_in_multi_location_request():
    """Verify validation error when start_date > end_date in multi-location request."""
    with pytest.raises(ValueError, match="start_date"):
        MultiLocationHistoricalRequest(
            locations=["Kolkata"],
            start_date="2026-08-10",
            end_date="2026-08-01",
        )


# =====================================================================
# 2. FAILURE ISOLATION & MIXED BATCH TESTS
# =====================================================================

def test_valid_plus_invalid_location_failure_isolation(mock_multi_service: MultiLocationService):
    """CRITICAL TEST: One bad location ('Atlantis') must NOT fail valid locations."""
    req = MultiLocationHistoricalRequest(
        locations=["Kolkata", "Atlantis", "London"],
        start_date="2026-08-01",
        end_date="2026-08-01",
        variables=["temperature_2m"],
    )
    result = mock_multi_service.collect_historical(req)

    assert result.batch_size == 3
    assert result.successful_locations == 2
    assert result.failed_locations == 1
    assert len(result.results) == 3

    # Index 0: Kolkata -> SUCCESS
    assert result.results[0].input_location == "Kolkata"
    assert result.results[0].is_success is True
    assert result.results[0].status == "SUCCESS"
    assert len(result.results[0].records) > 0

    # Index 1: Atlantis -> INVALID_LOCATION
    assert result.results[1].input_location == "Atlantis"
    assert result.results[1].is_success is False
    assert result.results[1].status == "INVALID_LOCATION"
    assert len(result.results[1].records) == 0

    # Index 2: London -> SUCCESS
    assert result.results[2].input_location == "London"
    assert result.results[2].is_success is True
    assert result.results[2].status == "SUCCESS"
    assert len(result.results[2].records) > 0


def test_all_invalid_batch_handling(mock_multi_service: MultiLocationService):
    """Verify that an all-invalid batch produces structured failure without crashing."""
    req = MultiLocationHistoricalRequest(
        locations=["Atlantis", "999.0, 999.0", "InvalidCityXYZ123"],
        start_date="2026-08-01",
        end_date="2026-08-01",
    )
    result = mock_multi_service.collect_historical(req)

    assert result.batch_size == 3
    assert result.successful_locations == 0
    assert result.failed_locations == 3
    assert result.total_records == 0
    assert len(result.all_records) == 0
    for item in result.results:
        assert item.is_success is False
        assert len(item.records) == 0


def test_provider_failure_isolation(mock_openmeteo_historical_payload: dict[str, Any]):
    """Verify that provider HTTP failure on one location does not fail other locations."""
    def selective_mock_http(url: str) -> dict[str, Any]:
        # Fail when querying Tokyo coordinates (35.6762)
        if "35.6762" in url:
            raise RuntimeError("HTTP 500 Provider Down for Tokyo")
        return copy.deepcopy(mock_openmeteo_historical_payload)

    hist_svc = HistoricalDataService(
        http_client=selective_mock_http,
        location_service=DynamicLocationService(),
    )
    multi_svc = MultiLocationService(historical_service=hist_svc)

    req = MultiLocationHistoricalRequest(
        locations=["Kolkata", "Tokyo", "London"],
        start_date="2026-08-01",
        end_date="2026-08-01",
    )
    result = multi_svc.collect_historical(req)

    assert result.batch_size == 3
    assert result.results[0].status == "SUCCESS"
    assert result.results[1].status == "PROVIDER_ERROR"
    assert result.results[1].is_success is False
    assert result.results[2].status == "SUCCESS"
    assert result.successful_locations == 2
    assert result.failed_locations == 1


def test_provider_timeout_isolation(mock_openmeteo_historical_payload: dict[str, Any]):
    """Verify that provider timeout on one location does not fail other locations."""
    def timeout_mock_http(url: str) -> dict[str, Any]:
        if "51.5074" in url:  # London
            raise TimeoutError("15s timeout reached")
        return copy.deepcopy(mock_openmeteo_historical_payload)

    hist_svc = HistoricalDataService(
        http_client=timeout_mock_http,
        location_service=DynamicLocationService(),
    )
    multi_svc = MultiLocationService(historical_service=hist_svc)

    req = MultiLocationHistoricalRequest(
        locations=["Kolkata", "London"],
        start_date="2026-08-01",
        end_date="2026-08-01",
    )
    result = multi_svc.collect_historical(req)

    assert result.results[0].status == "SUCCESS"
    assert result.results[1].status == "PROVIDER_ERROR"
    assert "timeout" in result.results[1].error_message.lower()


# =====================================================================
# 3. DETERMINISTIC ORDERING & DEDUPLICATION TESTS
# =====================================================================

def test_deterministic_result_mapping_order(mock_multi_service: MultiLocationService):
    """Verify that output results strictly match input list order."""
    inputs = ["Tokyo", "Kolkata", "London", "Paris", "Siliguri"]
    req = MultiLocationHistoricalRequest(
        locations=inputs,
        start_date="2026-08-01",
        end_date="2026-08-01",
    )
    result = mock_multi_service.collect_historical(req)

    assert len(result.results) == len(inputs)
    for i, orig_loc in enumerate(inputs):
        assert result.results[i].input_location == orig_loc


def test_duplicate_locations_deduplication_and_mapping(mock_multi_service: MultiLocationService):
    """Verify duplicate queries in batch are deduplicated during fetch while mapped to all output positions."""
    inputs = ["Kolkata", "London", "Kolkata", "London", "Kolkata"]
    req = MultiLocationHistoricalRequest(
        locations=inputs,
        start_date="2026-08-01",
        end_date="2026-08-01",
    )
    result = mock_multi_service.collect_historical(req)

    assert result.batch_size == 5
    assert result.successful_locations == 5
    assert len(result.results) == 5
    assert result.metadata["unique_locations_processed"] == 2

    # Check each position retains correct input_location and identical records
    for i, expected_loc in enumerate(inputs):
        assert result.results[i].input_location == expected_loc
        assert result.results[i].is_success is True


# =====================================================================
# 4. QC ISOLATION & DATA LEAKAGE SAFETY
# =====================================================================

def test_qc_isolation_across_locations(mock_openmeteo_historical_payload: dict[str, Any]):
    """Verify that QC failure on one location does not mark the entire batch as failed."""
    def qc_fail_mock_http(url: str) -> dict[str, Any]:
        payload = copy.deepcopy(mock_openmeteo_historical_payload)
        if "51.5074" in url:  # Corrupt London temperature to 999.0 °C
            payload["hourly"]["temperature_2m"] = [999.0, 999.0]
        return payload

    hist_svc = HistoricalDataService(
        http_client=qc_fail_mock_http,
        location_service=DynamicLocationService(),
    )
    multi_svc = MultiLocationService(historical_service=hist_svc)

    req = MultiLocationHistoricalRequest(
        locations=["Kolkata", "London", "Tokyo"],
        start_date="2026-08-01",
        end_date="2026-08-01",
    )
    result = multi_svc.collect_historical(req)

    assert result.results[0].status == "SUCCESS"
    assert result.results[0].qc_passed is True

    # London failed QC
    assert result.results[1].status == "QC_FAILED"
    assert result.results[1].qc_passed is False
    assert result.results[1].is_success is False

    assert result.results[2].status == "SUCCESS"
    assert result.results[2].qc_passed is True


def test_reference_prediction_data_isolation(mock_multi_service: MultiLocationService):
    """Verify strict anti-data-leakage markers on all aggregated canonical records."""
    req = MultiLocationHistoricalRequest(
        locations=["Kolkata", "London"],
        start_date="2026-08-01",
        end_date="2026-08-01",
    )
    result = mock_multi_service.collect_historical(req)

    assert len(result.all_records) > 0
    for rec in result.all_records:
        assert rec.is_ground_truth_label is True
        assert rec.record_type == "OBSERVATION"
        assert rec.issue_time is None
        assert rec.lead_hours is None


# =====================================================================
# 5. BUILDER 2 INTERFACE & SERIALIZATION TESTS
# =====================================================================

def test_builder2_jsonl_export_and_load(mock_multi_service: MultiLocationService):
    """Verify JSONL export and round-trip loading for multi-location historical records."""
    req = MultiLocationHistoricalRequest(
        locations=["Kolkata", "London"],
        start_date="2026-08-01",
        end_date="2026-08-01",
    )
    result = mock_multi_service.collect_historical(req)

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = os.path.join(tmpdir, "multi_loc_test.jsonl")
        exported_count = MultiLocationService.export_to_jsonl(result, jsonl_path)
        assert exported_count == len(result.all_records)
        assert os.path.exists(jsonl_path)

        loaded_records = MultiLocationService.load_from_jsonl(jsonl_path)
        assert len(loaded_records) == exported_count
        assert loaded_records[0].record_id == result.all_records[0].record_id


def test_builder2_to_reference_records_bridge(mock_multi_service: MultiLocationService):
    """Verify conversion of multi-location historical result to ReferenceWeatherRecord list."""
    req = MultiLocationHistoricalRequest(
        locations=["Kolkata", "London"],
        start_date="2026-08-01",
        end_date="2026-08-01",
    )
    result = mock_multi_service.collect_historical(req)
    ref_records = MultiLocationService.to_reference_records(result)

    assert len(ref_records) == len(result.all_records)
    for ref_rec in ref_records:
        assert ref_rec.is_ground_truth_label is True
        assert ref_rec.location in ["Kolkata", "London"]


# =====================================================================
# 6. BATCH PREDICTION TESTS
# =====================================================================

def test_batch_prediction_execution(mock_multi_service: MultiLocationService):
    """Verify batch prediction across valid and invalid locations."""
    pred_req = MultiLocationPredictionRequest(
        locations=["London", "Kolkata", "Atlantis"],
        variable="temperature_2m",
    )
    pred_result = mock_multi_service.predict_batch(pred_req)

    assert pred_result.batch_size == 3
    assert len(pred_result.results) == 3

    # London: valid location -> prediction returned
    assert pred_result.results[0].input_location == "London"
    assert pred_result.results[0].response.location == "London"
    assert pred_result.results[0].response.risk_level in [
        RiskLevel.LOW,
        RiskLevel.MEDIUM,
        RiskLevel.HIGH,
        RiskLevel.CRITICAL,
    ]

    # Kolkata: valid location -> prediction returned
    assert pred_result.results[1].input_location == "Kolkata"
    assert pred_result.results[1].response.location == "Kolkata"

    # Atlantis: invalid location -> safe abstention
    assert pred_result.results[2].input_location == "Atlantis"
    assert pred_result.results[2].response.abstain is True
    assert pred_result.results[2].response.trust_state == TrustState.UNAVAILABLE
    assert ReasonCode.INVALID_LOCATION in pred_result.results[2].response.reason_codes


# =====================================================================
# 7. FASTAPI HTTP BATCH ENDPOINT TESTS
# =====================================================================

def test_http_batch_historical_endpoint(client: TestClient):
    """Test POST /v1/historical/batch via FastAPI TestClient."""
    payload = {
        "locations": ["Kolkata", "Atlantis"],
        "start_date": "2026-08-01",
        "end_date": "2026-08-01",
        "variables": ["temperature_2m"],
    }
    response = client.post("/v1/historical/batch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["batch_size"] == 2
    assert len(data["results"]) == 2
    assert data["results"][0]["input_location"] == "Kolkata"
    assert data["results"][1]["input_location"] == "Atlantis"
    assert data["results"][1]["is_success"] is False


def test_http_batch_prediction_endpoint(client: TestClient):
    """Test POST /v1/predict/batch via FastAPI TestClient."""
    payload = {
        "locations": ["London", "Atlantis"],
        "variable": "temperature_2m",
    }
    response = client.post("/v1/predict/batch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["batch_size"] == 2
    assert len(data["results"]) == 2
    assert data["results"][0]["input_location"] == "London"
    assert data["results"][1]["input_location"] == "Atlantis"
    assert data["results"][1]["response"]["abstain"] is True


def test_http_batch_empty_locations_rejected(client: TestClient):
    """Test that POST /v1/historical/batch rejects empty locations with HTTP 422."""
    payload = {
        "locations": [],
        "start_date": "2026-08-01",
        "end_date": "2026-08-01",
    }
    response = client.post("/v1/historical/batch", json=payload)
    assert response.status_code == 422


def test_http_single_location_prediction_unaffected(client: TestClient):
    """Verify backward compatibility: POST /v1/predict remains 100% operational."""
    payload = {"location": "London"}
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "London"
    assert "bust_probability" in data
