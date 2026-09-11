"""Tests for GET /v1/health endpoint."""
from fastapi.testclient import TestClient


def test_health_endpoint_returns_200(client: TestClient):
    """Test that GET /v1/health returns HTTP status 200."""
    response = client.get("/v1/health")
    assert response.status_code == 200


def test_health_response_schema(client: TestClient):
    """Test that health response reports status=ok and service=forecast-bust-sentinel."""
    response = client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "forecast-bust-sentinel"
    assert "version" in data
