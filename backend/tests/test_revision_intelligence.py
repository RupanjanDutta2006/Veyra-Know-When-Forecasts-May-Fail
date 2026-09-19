"""Focused scientific tests for Day 30 revision intelligence."""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.location import ResolvedLocation
from backend.app.schemas.prediction import (
    CalibrationStatus,
    PredictionResponse,
    ReasonCode,
    RiskLevel,
    TrustState,
)
from backend.app.schemas.revision import ForecastRevisionRequest, RevisionDirection, RevisionStatus
from backend.app.services.revision_service import (
    REVISION_HISTORY_UNAVAILABLE,
    RevisionService,
    calculate_ensemble_revision,
    calculate_trajectory_diagnostics,
    get_revision_service,
)


class FixedLocationService:
    def resolve(self, query: str):
        if query.strip().lower() == "atlantis":
            return None
        return ResolvedLocation(
            original_input=query,
            name=query.strip(),
            latitude=22.5726,
            longitude=88.3639,
            country="India",
            source="registry",
        )


@pytest.fixture
def mock_agent():
    agent = MagicMock()

    def analyze(request):
        return PredictionResponse(
            location=request.location or "Kolkata",
            variable=request.variable,
            issue_time=request.issue_time,
            valid_time=request.valid_time,
            lead_hours=24,
            lead_days=1.0,
            bust_probability=0.25,
            risk_level=RiskLevel.MEDIUM,
            trust_state=TrustState.HIGH_CONFIDENCE,
            calibration_status=CalibrationStatus.CALIBRATED.value,
            model_version="veyra-v3-benchmark-lightgbm",
            data_version="gefs-openmeteo-v1.0",
            abstain=False,
            reason_codes=[ReasonCode.SUCCESS],
            request_id="req_day30_mock",
        )

    agent.analyze.side_effect = analyze
    return agent


@pytest.fixture
def service(mock_agent):
    return RevisionService(location_service=FixedLocationService(), agent=mock_agent)


@pytest.fixture
def client(service):
    app.dependency_overrides[get_revision_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_revision_service, None)


def valid_payload(**overrides):
    payload = {
        "location": "Kolkata",
        "variable": "temperature_2m",
        "lead_hours": 24,
    }
    payload.update(overrides)
    return payload


def test_revision_endpoint_registered(client):
    response = client.post("/v1/revision/trajectory", json=valid_payload())
    assert response.status_code == 200
    assert response.json()["request_id"].startswith("rev_")


def test_production_contract_reports_insufficient_history(client):
    data = client.post("/v1/revision/trajectory", json=valid_payload()).json()
    assert data["status"] == RevisionStatus.INSUFFICIENT_HISTORY.value
    assert REVISION_HISTORY_UNAVAILABLE in data["reason_codes"]
    assert data["history_is_durable"] is False
    assert data["history_source"] is None


def test_insufficient_history_preserves_all_revision_nulls(client):
    data = client.post("/v1/revision/trajectory", json=valid_payload()).json()
    assert data["current_issue_time"] is None
    assert data["previous_issue_time"] is None
    assert data["current_value"] is None
    assert data["previous_value"] is None
    assert data["revision_delta"] is None
    assert data["trajectory"] is None
    assert data["ensemble_revision"] is None
    assert data["trajectory_points"] == []


def test_repeated_caller_timestamps_cannot_manufacture_history(client):
    first = client.post(
        "/v1/revision/trajectory",
        json=valid_payload(
            issue_time="2026-09-19T00:00:00Z",
            valid_time="2026-09-20T12:00:00Z",
        ),
    ).json()
    second = client.post(
        "/v1/revision/trajectory",
        json=valid_payload(
            issue_time="2026-09-19T06:00:00Z",
            valid_time="2026-09-20T12:00:00Z",
        ),
    ).json()
    for result in (first, second):
        assert result["status"] == RevisionStatus.INSUFFICIENT_HISTORY.value
        assert result["previous_issue_time"] is None
        assert result["trajectory"] is None
        assert result["revision_delta"] is None


@pytest.mark.parametrize(
    "field,value",
    [("issue_time", "not-a-time"), ("valid_time", "tomorrow-ish")],
)
def test_invalid_timestamps_are_rejected(client, field, value):
    payload = valid_payload(
        issue_time="2026-09-19T00:00:00Z",
        valid_time="2026-09-20T00:00:00Z",
    )
    payload[field] = value
    assert client.post("/v1/revision/trajectory", json=payload).status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        valid_payload(issue_time="2026-09-19T00:00:00Z"),
        valid_payload(valid_time="2026-09-20T00:00:00Z"),
    ],
)
def test_partial_timestamp_pair_is_rejected(client, payload):
    assert client.post("/v1/revision/trajectory", json=payload).status_code == 422


def test_non_positive_temporal_target_is_rejected(client):
    response = client.post(
        "/v1/revision/trajectory",
        json=valid_payload(
            issue_time="2026-09-20T00:00:00Z",
            valid_time="2026-09-19T00:00:00Z",
        ),
    )
    assert response.status_code == 422


def test_non_hour_temporal_target_is_rejected(client):
    response = client.post(
        "/v1/revision/trajectory",
        json=valid_payload(
            issue_time="2026-09-19T00:00:00Z",
            valid_time="2026-09-20T00:30:00Z",
        ),
    )
    assert response.status_code == 422


def test_explicit_temporal_target_cannot_exceed_horizon(client):
    response = client.post(
        "/v1/revision/trajectory",
        json=valid_payload(
            issue_time="2026-09-01T00:00:00Z",
            valid_time="2026-09-18T00:00:00Z",
        ),
    )
    assert response.status_code == 422


def test_explicit_valid_target_derives_exact_lead(client):
    data = client.post(
        "/v1/revision/trajectory",
        json=valid_payload(
            issue_time="2026-09-19T06:00:00Z",
            valid_time="2026-09-20T12:00:00Z",
        ),
    ).json()
    assert data["lead_hours"] == 30
    assert data["valid_time"] == "2026-09-20T12:00:00Z"


def test_removed_target_date_is_rejected(client):
    response = client.post(
        "/v1/revision/trajectory",
        json=valid_payload(target_date="2026-09-20"),
    )
    assert response.status_code == 422


def test_current_prediction_uses_one_coherent_agent_call(service, mock_agent):
    response = service.evaluate_revision(ForecastRevisionRequest(**valid_payload()))
    assert response.status == RevisionStatus.INSUFFICIENT_HISTORY
    assert mock_agent.analyze.call_count == 1
    mock_agent.get_weather_data.assert_not_called()


def test_current_p_bust_preserved_previous_p_bust_unavailable(client):
    data = client.post("/v1/revision/trajectory", json=valid_payload()).json()
    assert data["bust_probability"] == 0.25
    assert data["previous_bust_probability"] is None
    assert data["bust_probability_delta"] is None


def test_missing_current_forecast_abstains_without_fake_values(mock_agent):
    mock_agent.analyze.return_value = PredictionResponse(
        location="Kolkata",
        bust_probability=None,
        risk_level=None,
        trust_state=TrustState.UNAVAILABLE,
        calibration_status=CalibrationStatus.UNAVAILABLE.value,
        abstain=True,
        reason_codes=[ReasonCode.DATA_UNAVAILABLE],
        request_id="req_unavailable",
    )
    mock_agent.analyze.side_effect = None
    service = RevisionService(location_service=FixedLocationService(), agent=mock_agent)
    response = service.evaluate_revision(ForecastRevisionRequest(**valid_payload()))
    assert response.status == RevisionStatus.ABSTAINED
    assert response.bust_probability is None
    assert response.current_value is None
    assert response.trajectory is None


def test_unresolved_location_abstains_before_inference(mock_agent):
    service = RevisionService(location_service=FixedLocationService(), agent=mock_agent)
    response = service.evaluate_revision(
        ForecastRevisionRequest(location="Atlantis", variable="temperature_2m", lead_hours=24)
    )
    assert response.status == RevisionStatus.ABSTAINED
    assert response.latitude is None
    assert response.longitude is None
    assert response.bust_probability is None
    assert response.trajectory is None
    mock_agent.analyze.assert_not_called()


@pytest.mark.parametrize("lead", [24, 240])
def test_benchmark_scope_metadata(client, lead):
    data = client.post(
        "/v1/revision/trajectory", json=valid_payload(lead_hours=lead)
    ).json()
    assert data["scientific_scope"] == "WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE"
    assert data["is_certified_horizon"] is True


@pytest.mark.parametrize("lead", [264, 384])
def test_extended_scope_metadata(client, lead):
    data = client.post(
        "/v1/revision/trajectory", json=valid_payload(lead_hours=lead)
    ).json()
    assert data["scientific_scope"] == "EXTENDED_OPERATIONAL_HORIZON"
    assert data["is_certified_horizon"] is False


@pytest.mark.parametrize("variable,unit", [
    ("temperature_2m", "°C"),
    ("wind_speed_10m", "m/s"),
    ("surface_pressure", "hPa"),
])
def test_units_remain_variable_aware(client, variable, unit):
    data = client.post(
        "/v1/revision/trajectory", json=valid_payload(variable=variable)
    ).json()
    assert data["units"]["value"] == unit


def test_unsupported_variable_rejected(client):
    response = client.post(
        "/v1/revision/trajectory", json=valid_payload(variable="rain_probability")
    )
    assert response.status_code == 422


@pytest.mark.parametrize("lead", [0, 385])
def test_lead_bounds_rejected(client, lead):
    assert client.post(
        "/v1/revision/trajectory", json=valid_payload(lead_hours=lead)
    ).status_code == 422


def test_delta_helpers_use_current_minus_previous():
    increased = calculate_trajectory_diagnostics(31.5, 30.0)
    decreased = calculate_trajectory_diagnostics(28.0, 30.0)
    unchanged = calculate_trajectory_diagnostics(30.0, 30.0)
    assert increased.revision_delta == 1.5
    assert increased.direction == RevisionDirection.INCREASED
    assert decreased.revision_delta == -2.0
    assert decreased.direction == RevisionDirection.DECREASED
    assert unchanged.revision_delta == 0.0
    assert unchanged.direction == RevisionDirection.UNCHANGED


def test_ensemble_delta_helpers_preserve_nulls_and_signs():
    diagnostics = calculate_ensemble_revision(8.0, 7.5, 1.1, 1.4)
    assert diagnostics.mean_delta == 0.5
    assert diagnostics.spread_delta == -0.3
    missing = calculate_ensemble_revision(None, 7.5, 1.1, None)
    assert missing.mean_delta is None
    assert missing.spread_delta is None


def test_calibration_failure_never_fabricates_probability(mock_agent):
    mock_agent.analyze.return_value = PredictionResponse(
        location="Kolkata",
        bust_probability=None,
        risk_level=None,
        trust_state=TrustState.ABSTAINED,
        calibration_status=CalibrationStatus.FAILED.value,
        abstain=True,
        reason_codes=[ReasonCode.CALIBRATION_FAILURE],
        request_id="req_calibration_failure",
    )
    mock_agent.analyze.side_effect = None
    service = RevisionService(location_service=FixedLocationService(), agent=mock_agent)
    response = service.evaluate_revision(ForecastRevisionRequest(**valid_payload()))
    assert response.bust_probability is None
    assert response.previous_bust_probability is None
    assert response.bust_probability_delta is None
