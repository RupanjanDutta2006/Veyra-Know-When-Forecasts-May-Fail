"""Unit and Integration Tests for Day 32 Scientific Certification Gate (C1)."""
import pytest
from fastapi.testclient import TestClient

from backend.app.core.certification_policy import (
    CERTIFICATION_POLICY_VERSION,
    CERTIFIED_BENCHMARK_STATIONS,
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


def test_case_1_certified_frozen_benchmark_scope():
    """Case 1: Certified benchmark station, variable, and lead <= 240h -> CERTIFIED."""
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


def test_case_2_uncertified_location():
    """Case 2: Valid location outside the 25 benchmark stations -> OUTSIDE_CERTIFIED_SCOPE."""
    res = evaluate_scientific_certification(
        location="London",
        variable="temperature_2m",
        lead_hours=24,
    )
    assert res.status == CertificationStatus.OUTSIDE_CERTIFIED_SCOPE
    assert res.is_certified is False
    assert res.reason_code == CertificationReasonCode.UNCERTIFIED_LOCATION
    assert "London" in res.reason_detail


def test_case_3_uncertified_lead_horizon():
    """Case 3: Lead horizon > 240h (e.g. 264h) -> OUTSIDE_CERTIFIED_SCOPE."""
    res = evaluate_scientific_certification(
        location="Kolkata",
        variable="temperature_2m",
        lead_hours=264,
    )
    assert res.status == CertificationStatus.OUTSIDE_CERTIFIED_SCOPE
    assert res.is_certified is False
    assert res.reason_code == CertificationReasonCode.UNCERTIFIED_LEAD_HORIZON
    assert "264" in res.reason_detail


def test_case_4_uncertified_variable():
    """Case 4: Unsupported/uncertified variable -> OUTSIDE_CERTIFIED_SCOPE."""
    res = evaluate_scientific_certification(
        location="Kolkata",
        variable="precipitation",
        lead_hours=24,
    )
    assert res.status == CertificationStatus.OUTSIDE_CERTIFIED_SCOPE
    assert res.is_certified is False
    assert res.reason_code == CertificationReasonCode.UNCERTIFIED_VARIABLE


def test_case_5_model_sha_mismatch():
    """Case 5: Serving model artifact mismatch -> CERTIFICATION_UNKNOWN."""
    res = evaluate_scientific_certification(
        location="Kolkata",
        variable="temperature_2m",
        lead_hours=24,
        model_sha256="0000000000000000000000000000000000000000000000000000000000000000",
    )
    assert res.status == CertificationStatus.CERTIFICATION_UNKNOWN
    assert res.is_certified is False
    assert res.reason_code == CertificationReasonCode.MODEL_ARTIFACT_MISMATCH


def test_case_6_calibrator_sha_mismatch():
    """Case 5b: Serving calibrator artifact mismatch -> CERTIFICATION_UNKNOWN."""
    res = evaluate_scientific_certification(
        location="Kolkata",
        variable="temperature_2m",
        lead_hours=24,
        calibrator_sha256="0000000000000000000000000000000000000000000000000000000000000000",
    )
    assert res.status == CertificationStatus.CERTIFICATION_UNKNOWN
    assert res.is_certified is False
    assert res.reason_code == CertificationReasonCode.CALIBRATOR_ARTIFACT_MISMATCH


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


def test_http_certification_policy_endpoint():
    """HTTP GET /v1/certification/policy returns authoritative metadata."""
    resp = client.get("/v1/certification/policy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["policy_version"] == CERTIFICATION_POLICY_VERSION
    assert data["model_sha256"] == EXPECTED_MODEL_SHA256
    assert data["calibrator_sha256"] == EXPECTED_CALIBRATOR_SHA256
    assert data["max_certified_lead_hours"] == MAX_CERTIFIED_LEAD_HOURS
    assert len(data["certified_benchmark_stations"]) == len(CERTIFIED_BENCHMARK_STATIONS)


def test_predict_endpoint_contains_certification_metadata():
    """POST /v1/predict response includes certification gate result object."""
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
