"""Unit and Integration Tests for Day 32 Scientific Certification Gate (C1).

Covers:
- Exact 25-station frozen benchmark certification scope.
- Rejection of operational/extended non-benchmark stations (Dispur, Gangtok, Patna, Shillong, Varanasi, Vijayawada).
- Inclusion of authentic frozen benchmark stations (Leh, Kolkata, Delhi, etc.).
- Lead-horizon boundaries (<= 240h).
- Variable boundaries (temperature_2m, wind_speed_10m, surface_pressure).
- Cryptographic artifact integrity enforcement (Model SHA, Calibrator SHA).
- HTTP API contract enforcement for evaluate and policy endpoints.
"""
import pytest
from fastapi.testclient import TestClient

from backend.app.core.certification_policy import (
    CERTIFICATION_POLICY_VERSION,
    CERTIFIED_BENCHMARK_STATIONS,
    CERTIFIED_VARIABLES,
    EXPECTED_CALIBRATOR_SHA256,
    EXPECTED_MODEL_SHA256,
    MAX_CERTIFIED_LEAD_HOURS,
    evaluate_scientific_certification,
)
from backend.app.main import app
from backend.app.schemas.certification import (
    CertificationReasonCode,
    CertificationStatus,
)

client = TestClient(app)

# Authoritative frozen 25 benchmark stations from canonical benchmark dataset
EXPECTED_FROZEN_25_STATIONS = {
    "ahmedabad",
    "bengaluru",
    "bhopal",
    "bhubaneswar",
    "chandigarh",
    "chennai",
    "dehradun",
    "delhi",
    "goa",
    "guwahati",
    "hyderabad",
    "jaipur",
    "kochi",
    "kolkata",
    "leh",
    "lucknow",
    "mumbai",
    "nagpur",
    "pune",
    "raipur",
    "ranchi",
    "shimla",
    "srinagar",
    "thiruvananthapuram",
    "visakhapatnam",
}

# 6 operational/extended stations previously incorrectly certified
REMOVED_EXTRA_STATIONS = [
    "Dispur",
    "Gangtok",
    "Patna",
    "Shillong",
    "Varanasi",
    "Vijayawada",
]


def test_station_count_exactly_25():
    """Requirement A: Certification policy exposes exactly 25 benchmark stations."""
    assert len(CERTIFIED_BENCHMARK_STATIONS) == 25


def test_station_set_matches_frozen_benchmark():
    """Requirement B: The expected frozen 25 set exactly equals the policy set."""
    policy_station_set = {s.lower() for s in CERTIFIED_BENCHMARK_STATIONS}
    assert policy_station_set == EXPECTED_FROZEN_25_STATIONS


def test_leh_restored_to_certified_scope():
    """Requirement C: Leh + temperature_2m + 24h returns CERTIFIED / CERTIFIED_FROZEN_BENCHMARK_SCOPE."""
    res = evaluate_scientific_certification(
        location="Leh",
        variable="temperature_2m",
        lead_hours=24,
    )
    assert res.status == CertificationStatus.CERTIFIED
    assert res.is_certified is True
    assert res.reason_code == CertificationReasonCode.CERTIFIED_FROZEN_BENCHMARK_SCOPE
    assert res.evaluated_location == "Leh"


@pytest.mark.parametrize("station", REMOVED_EXTRA_STATIONS)
def test_removed_extra_stations_return_outside_certified_scope(station: str):
    """Requirement D: Non-benchmark operational stations return OUTSIDE_CERTIFIED_SCOPE / UNCERTIFIED_LOCATION."""
    res = evaluate_scientific_certification(
        location=station,
        variable="temperature_2m",
        lead_hours=24,
    )
    assert res.status == CertificationStatus.OUTSIDE_CERTIFIED_SCOPE
    assert res.is_certified is False
    assert res.reason_code == CertificationReasonCode.UNCERTIFIED_LOCATION
    assert station in res.reason_detail


def test_kolkata_certified_scope():
    """Requirement E: Kolkata + temperature_2m + 24h remains CERTIFIED / CERTIFIED_FROZEN_BENCHMARK_SCOPE."""
    res = evaluate_scientific_certification(
        location="Kolkata",
        variable="temperature_2m",
        lead_hours=24,
    )
    assert res.status == CertificationStatus.CERTIFIED
    assert res.is_certified is True
    assert res.reason_code == CertificationReasonCode.CERTIFIED_FROZEN_BENCHMARK_SCOPE
    assert res.evaluated_location == "Kolkata"
    assert res.evaluated_variable == "temperature_2m"
    assert res.evaluated_lead_hours == 24
    assert res.policy_version == CERTIFICATION_POLICY_VERSION


def test_kolkata_extended_lead_horizon():
    """Requirement F: Kolkata + temperature_2m + 264h remains OUTSIDE_CERTIFIED_SCOPE / UNCERTIFIED_LEAD_HORIZON."""
    res = evaluate_scientific_certification(
        location="Kolkata",
        variable="temperature_2m",
        lead_hours=264,
    )
    assert res.status == CertificationStatus.OUTSIDE_CERTIFIED_SCOPE
    assert res.is_certified is False
    assert res.reason_code == CertificationReasonCode.UNCERTIFIED_LEAD_HORIZON
    assert "264" in res.reason_detail


def test_uncertified_variable():
    """Requirement G: Unsupported variable behavior remains unchanged."""
    res = evaluate_scientific_certification(
        location="Kolkata",
        variable="precipitation",
        lead_hours=24,
    )
    assert res.status == CertificationStatus.OUTSIDE_CERTIFIED_SCOPE
    assert res.is_certified is False
    assert res.reason_code == CertificationReasonCode.UNCERTIFIED_VARIABLE


def test_model_sha_mismatch():
    """Requirement H1: Model artifact mismatch returns CERTIFICATION_UNKNOWN."""
    res = evaluate_scientific_certification(
        location="Kolkata",
        variable="temperature_2m",
        lead_hours=24,
        model_sha256="0000000000000000000000000000000000000000000000000000000000000000",
    )
    assert res.status == CertificationStatus.CERTIFICATION_UNKNOWN
    assert res.is_certified is False
    assert res.reason_code == CertificationReasonCode.MODEL_ARTIFACT_MISMATCH


def test_calibrator_sha_mismatch():
    """Requirement H2: Calibrator artifact mismatch returns CERTIFICATION_UNKNOWN."""
    res = evaluate_scientific_certification(
        location="Kolkata",
        variable="temperature_2m",
        lead_hours=24,
        calibrator_sha256="0000000000000000000000000000000000000000000000000000000000000000",
    )
    assert res.status == CertificationStatus.CERTIFICATION_UNKNOWN
    assert res.is_certified is False
    assert res.reason_code == CertificationReasonCode.CALIBRATOR_ARTIFACT_MISMATCH


def test_invalid_empty_location():
    """Requirement I: Invalid/empty request parameters remain distinguishable."""
    res = evaluate_scientific_certification(
        location="",
        variable="temperature_2m",
        lead_hours=24,
    )
    assert res.status == CertificationStatus.OUTSIDE_CERTIFIED_SCOPE
    assert res.is_certified is False
    assert res.reason_code == CertificationReasonCode.UNCERTIFIED_LOCATION


def test_http_certification_evaluate_endpoint():
    """HTTP POST /v1/certification/evaluate returns structured certification result."""
    payload = {
        "location": "Delhi",
        "variable": "surface_pressure",
        "lead_hours": 48,
    }
    resp = client.post("/v1/certification/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "CERTIFIED"
    assert data["is_certified"] is True
    assert data["reason_code"] == "CERTIFIED_FROZEN_BENCHMARK_SCOPE"
    assert data["evaluated_location"] == "Delhi"
    assert len(data["certified_benchmark_stations"]) == 25


def test_http_certification_policy_endpoint():
    """HTTP GET /v1/certification/policy returns authoritative metadata with exactly 25 stations."""
    resp = client.get("/v1/certification/policy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["policy_version"] == CERTIFICATION_POLICY_VERSION
    assert data["model_sha256"] == EXPECTED_MODEL_SHA256
    assert data["calibrator_sha256"] == EXPECTED_CALIBRATOR_SHA256
    assert data["max_certified_lead_hours"] == MAX_CERTIFIED_LEAD_HOURS
    assert len(data["certified_benchmark_stations"]) == 25
    assert data["certified_station_count"] == 25
    assert "Leh" in data["certified_benchmark_stations"]
    assert "Dispur" not in data["certified_benchmark_stations"]
    assert "Vijayawada" not in data["certified_benchmark_stations"]


def test_predict_endpoint_contains_certification_metadata():
    """POST /v1/predict response includes certification gate result object."""
    from unittest.mock import patch
    from backend.app.schemas.weather import CanonicalForecastDataset, CanonicalForecastRecord
    from backend.app.services.base import WeatherResult

    mock_rec = CanonicalForecastRecord(
        location="Kolkata",
        latitude=22.5726,
        longitude=88.3639,
        issue_time="2026-09-20T00:00:00Z",
        valid_time="2026-09-21T00:00:00Z",
        lead_hours=24,
        variable="temperature_2m",
        forecast_value=300.15,
        unit="K",
        ensemble_mean=300.10,
        ensemble_std=1.2,
        member_values=[300.0 + (i * 0.1 - 1.5) for i in range(31)],
    )
    mock_res = WeatherResult(
        location="Kolkata",
        target_date="2026-09-21",
        raw_data={"dataset": CanonicalForecastDataset(
            location="Kolkata",
            latitude=22.5726,
            longitude=88.3639,
            issue_time="2026-09-20T00:00:00Z",
            records=[mock_rec],
        ).model_dump()},
        data_version="gefs-openmeteo-v1.0",
        is_available=True,
    )
    mock_res.record = mock_rec  # type: ignore

    with patch("backend.app.services.openmeteo_service.OpenMeteoGEFSWeatherService.get_forecast", return_value=mock_res):
        payload = {
            "location": "Kolkata",
            "variable": "temperature_2m",
        }
        resp = client.post("/v1/predict", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "certification" in data
        assert data["certification"]["status"] == "CERTIFIED"
        assert data["certification"]["is_certified"] is True
