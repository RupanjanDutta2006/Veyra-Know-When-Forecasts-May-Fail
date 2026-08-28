"""Day 8 Dynamic Location Resolution Automated Tests.

Verifies:
- Case 1-5: Dynamic resolution of benchmark and global cities (Kolkata, London, Paris, Tokyo, New Delhi, Siliguri, etc.)
- Case 6-7: Direct coordinate validation and normalization (-90 <= lat <= 90, -180 <= lon <= 180)
- Case 8: Safe abstention on unresolvable / fictional locations (Atlantis, InvalidCityXYZ123)
- Case 9: Coordinate boundary enforcement (out-of-bounds rejection: 999, 999)
- Case 10: Empty / whitespace location handling
- Case 11: Simulated geocoding API failure and network error resilience
- Case 12: End-to-end API prediction regression and backward compatibility
"""
from typing import Any, Dict
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.location import ResolvedLocation
from backend.app.schemas.prediction import ReasonCode, TrustState
from backend.app.services.location_service import (
    DynamicLocationService,
    KNOWN_BENCHMARK_LOCATIONS,
)
from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_geocoding_service() -> DynamicLocationService:
    """Fixture providing DynamicLocationService with a mock HTTP client for deterministic unit testing."""
    def mock_http(url: str) -> Dict[str, Any]:
        if "Paris" in url or "paris" in url:
            return {
                "results": [
                    {
                        "id": 2988507,
                        "name": "Paris",
                        "latitude": 48.85341,
                        "longitude": 2.3488,
                        "country": "France",
                        "admin1": "Ile-de-France",
                        "timezone": "Europe/Paris",
                    }
                ]
            }
        if "Siliguri" in url or "siliguri" in url:
            return {
                "results": [
                    {
                        "id": 1256525,
                        "name": "Siliguri",
                        "latitude": 26.71004,
                        "longitude": 88.42851,
                        "country": "India",
                        "admin1": "West Bengal",
                        "timezone": "Asia/Kolkata",
                    }
                ]
            }
        if "OutBoundsCity" in url:
            return {
                "results": [
                    {
                        "id": 99999,
                        "name": "OutBoundsCity",
                        "latitude": 95.0,
                        "longitude": 200.0,
                        "country": "Nowhere",
                    }
                ]
            }
        return {"generationtime_ms": 0.1}

    return DynamicLocationService(http_client=mock_http, enable_cache=True)


# =========================================================================
# UNIT TESTS: DynamicLocationService
# =========================================================================

def test_dynamic_city_resolution_benchmark_cities(mock_geocoding_service: DynamicLocationService):
    """Case 1, 2, 4, 5: Verify pre-seeded benchmark cities resolve with high accuracy."""
    for city_name in ["Kolkata", "London", "Tokyo", "New Delhi", "Mumbai", "Berlin"]:
        resolved = mock_geocoding_service.resolve(city_name)
        assert resolved is not None
        assert isinstance(resolved, ResolvedLocation)
        assert resolved.name.lower() == city_name.lower()
        assert -90.0 <= resolved.latitude <= 90.0
        assert -180.0 <= resolved.longitude <= 180.0
        assert resolved.source in ("registry", "dynamic_geocoding", "cache")


def test_dynamic_city_resolution_unregistered_city(mock_geocoding_service: DynamicLocationService):
    """Case 3: Verify dynamic place-name resolution via mock geocoder for new cities."""
    resolved_paris = mock_geocoding_service.resolve("Paris")
    assert resolved_paris is not None
    assert resolved_paris.name == "Paris"
    assert pytest.approx(resolved_paris.latitude, 0.01) == 48.85
    assert pytest.approx(resolved_paris.longitude, 0.01) == 2.35
    assert resolved_paris.country == "France"

    resolved_siliguri = mock_geocoding_service.resolve("Siliguri")
    assert resolved_siliguri is not None
    assert resolved_siliguri.name == "Siliguri"
    assert pytest.approx(resolved_siliguri.latitude, 0.01) == 26.71
    assert pytest.approx(resolved_siliguri.longitude, 0.01) == 88.43
    assert resolved_siliguri.state_region == "West Bengal"


def test_direct_coordinate_parsing_valid(mock_geocoding_service: DynamicLocationService):
    """Case 6, 7: Verify direct coordinate inputs parse and validate directly."""
    # Case 6: Kolkata coordinates
    res1 = mock_geocoding_service.resolve("22.5726, 88.3639")
    assert res1 is not None
    assert res1.latitude == 22.5726
    assert res1.longitude == 88.3639
    assert res1.source == "direct_coordinates"

    # Case 7: Western Europe / Paris coordinates
    res2 = mock_geocoding_service.resolve("48.8566, 2.3522")
    assert res2 is not None
    assert res2.latitude == 48.8566
    assert res2.longitude == 2.3522
    assert res2.source == "direct_coordinates"

    # Coordinate with extra whitespace
    res3 = mock_geocoding_service.resolve("  35.6762 ,  139.6503  ")
    assert res3 is not None
    assert res3.latitude == 35.6762
    assert res3.longitude == 139.6503


def test_coordinate_boundary_rejection(mock_geocoding_service: DynamicLocationService):
    """Case 9: Verify out-of-bounds coordinates are strictly rejected."""
    # Latitude > 90
    assert mock_geocoding_service.resolve("999.0, 999.0") is None
    assert mock_geocoding_service.resolve("91.0, 0.0") is None
    assert mock_geocoding_service.resolve("-91.0, 0.0") is None

    # Longitude > 180
    assert mock_geocoding_service.resolve("0.0, 181.0") is None
    assert mock_geocoding_service.resolve("0.0, -181.0") is None

    # Non-numeric garbage with commas
    assert mock_geocoding_service.resolve("abc, def") is None


def test_unresolvable_and_fictional_locations(mock_geocoding_service: DynamicLocationService):
    """Case 8: Verify fictional and unresolvable locations return None safely."""
    assert mock_geocoding_service.resolve("Atlantis") is None
    assert mock_geocoding_service.resolve("atlantis_unknown_city") is None
    assert mock_geocoding_service.resolve("InvalidCityXYZ123") is None
    assert mock_geocoding_service.resolve("NonexistentCityXYZ") is None


def test_empty_and_whitespace_location(mock_geocoding_service: DynamicLocationService):
    """Case 10: Verify empty and whitespace strings return None."""
    assert mock_geocoding_service.resolve("") is None
    assert mock_geocoding_service.resolve("   ") is None


def test_simulated_provider_failure_isolation():
    """Case 11: Verify network timeout and provider 500 error are safely isolated."""
    def failing_http(url: str) -> Dict[str, Any]:
        raise RuntimeError("Simulated connection timeout (504 Gateway Timeout)")

    failing_service = DynamicLocationService(http_client=failing_http, enable_cache=False)
    # Query an unseeded city that must query the failing provider
    result = failing_service.resolve("UnseededUnknownPlace")
    assert result is None, "Provider failure must return None without raising exception"


def test_geocoder_out_of_bounds_response_filtered(mock_geocoding_service: DynamicLocationService):
    """Verify that if geocoder returns corrupt out-of-bounds coordinates, it is rejected."""
    assert mock_geocoding_service.resolve("OutBoundsCity") is None


# =========================================================================
# INTEGRATION TESTS: Weather Service with Dynamic Location
# =========================================================================

def test_openmeteo_service_with_dynamic_locations(mock_geocoding_service: DynamicLocationService):
    """Verify OpenMeteoGEFSWeatherService uses dynamic location resolution."""
    weather_svc = OpenMeteoGEFSWeatherService(location_service=mock_geocoding_service)

    # Resolved via dynamic geocoding
    coords_siliguri = weather_svc.resolve_coordinates("Siliguri")
    assert coords_siliguri is not None
    assert pytest.approx(coords_siliguri[0], 0.01) == 26.71
    assert pytest.approx(coords_siliguri[1], 0.01) == 88.43

    # Resolved via direct coordinates
    coords_direct = weather_svc.resolve_coordinates("22.5726, 88.3639")
    assert coords_direct == (22.5726, 88.3639)

    # Out-of-bounds coordinates rejected
    assert weather_svc.resolve_coordinates("999.0, 999.0") is None

    # Unresolvable location rejected
    assert weather_svc.resolve_coordinates("Atlantis") is None


# =========================================================================
# END-TO-END API TESTS: /v1/predict with Dynamic Location Resolution
# =========================================================================

def test_api_predict_dynamic_city(client: TestClient):
    """Case 1: Test valid dynamic prediction for Kolkata."""
    response = client.post(
        "/v1/predict",
        json={
            "location": "Kolkata",
            "variable": "temperature_2m",
            "issue_time": "2026-08-27T00:00:00Z",
            "valid_time": "2026-08-28T00:00:00Z",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "Kolkata"
    assert data["abstain"] is False
    assert data["bust_probability"] is not None
    assert 0.0 <= data["bust_probability"] <= 1.0
    assert data["trust_state"] == TrustState.HIGH_CONFIDENCE.value
    assert ReasonCode.SUCCESS.value in data["reason_codes"]


def test_api_predict_direct_coordinates(client: TestClient):
    """Case 6: Test valid prediction using direct geographic coordinate string."""
    response = client.post(
        "/v1/predict",
        json={
            "location": "22.5726, 88.3639",
            "variable": "temperature_2m",
            "issue_time": "2026-08-27T00:00:00Z",
            "valid_time": "2026-08-28T00:00:00Z",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "22.5726, 88.3639"
    assert data["abstain"] is False
    assert data["bust_probability"] is not None
    assert 0.0 <= data["bust_probability"] <= 1.0


def test_api_predict_invalid_location_safe_abstention(client: TestClient):
    """Case 8: Test invalid location triggers safe abstention without 500 error."""
    response = client.post(
        "/v1/predict",
        json={"location": "Atlantis"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "Atlantis"
    assert data["abstain"] is True
    assert data["bust_probability"] is None
    assert data["trust_state"] == TrustState.UNAVAILABLE.value
    assert ReasonCode.INVALID_LOCATION.value in data["reason_codes"]


def test_api_predict_invalid_coordinates_safe_abstention(client: TestClient):
    """Case 9: Test out-of-bounds coordinates trigger safe abstention."""
    response = client.post(
        "/v1/predict",
        json={"location": "999.0, 999.0"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["abstain"] is True
    assert data["bust_probability"] is None
    assert data["trust_state"] == TrustState.UNAVAILABLE.value
    assert ReasonCode.INVALID_LOCATION.value in data["reason_codes"]


def test_api_predict_empty_location_rejection(client: TestClient):
    """Case 10: Test empty or whitespace location is rejected with HTTP 422."""
    response = client.post("/v1/predict", json={"location": "   "})
    assert response.status_code == 422


def test_phase1_backward_compatibility(client: TestClient):
    """Case 12: Verify full backward compatibility with Phase 1 requests."""
    # Health endpoint
    health_resp = client.get("/v1/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"

    # Standard London request
    london_resp = client.post("/v1/predict", json={"location": "London"})
    assert london_resp.status_code == 200
    data = london_resp.json()
    assert data["location"] == "London"
    assert data["abstain"] is False
    assert data["model_version"] == "prototype-gbm-v1"
