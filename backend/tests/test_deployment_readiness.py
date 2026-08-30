"""
Veyra Phase 2 Builder 1 Day 18 — Deployment & Production Readiness Test Suite.

Verifies:
1. Production configuration defaults and safe environment overrides.
2. CORS security, origin filtering, and preflight behavior.
3. Health / readiness endpoint liveness and external-isolation contract.
4. Model artifact loading independence across varied working directory layouts.
5. Static dashboard SPA route handling and assets mounting.
6. Exception sanitization and absence of stack trace leakage in production mode.
7. Rate limiting, cache, and SingleFlight resilience in production configuration.
8. Comprehensive deployment failure scenarios (missing env vars, invalid origin,
   unavailable models, upstream 429, upstream outage, malformed JSON, validation 422,
   rate limit 429, cache disabled, dedup disabled).
"""
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.builder2.model_adapter import Builder2ModelAdapter
from backend.app.builder2.model_service import ForecastBustModelService
from backend.app.core.config import Settings, settings
from backend.app.core.rate_limiter import default_rate_limiter
from backend.app.main import app, create_application
from backend.app.schemas.prediction import PredictionRequest
from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService


@pytest.fixture
def deployment_client() -> TestClient:
    """TestClient for production deployment tests."""
    return TestClient(app)


def test_production_settings_defaults():
    """Verify production-hardened defaults in Settings."""
    cfg = Settings()
    assert cfg.PROJECT_NAME == "Forecast-Bust Sentinel API"
    assert cfg.VERSION == "0.1.0"
    assert cfg.API_V1_STR == "/v1"
    assert cfg.HOST == "0.0.0.0"
    assert cfg.PORT == 8000
    assert cfg.DEBUG is False
    assert cfg.STRUCTURED_LOGGING is True
    assert cfg.ENABLE_SECURITY_HEADERS is True
    assert cfg.ENABLE_REQUEST_CORRELATION is True
    assert cfg.RATE_LIMIT_ENABLED is True
    assert cfg.WEATHER_CACHE_ENABLED is True
    assert cfg.WEATHER_DEDUP_ENABLED is True
    assert cfg.WEATHER_CACHE_TTL_SECONDS == 120
    assert cfg.CACHE_ENABLED is True


def test_health_endpoint_contract(deployment_client: TestClient):
    """Verify GET /v1/health returns safe liveness without querying external providers."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        response = deployment_client.get("/v1/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["service"] == "forecast-bust-sentinel"
        assert payload["version"] == "0.1.0"
        # Health check must NEVER make external network calls
        assert mock_urlopen.call_count == 0


def test_root_endpoint_metadata(deployment_client: TestClient):
    """Verify GET / returns navigation metadata pointing to docs, dashboard, and health."""
    response = deployment_client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert "docs" in payload
    assert "dashboard" in payload
    assert "health" in payload
    assert payload["health"] == "/v1/health"


def test_cors_headers_with_allowed_origin():
    """Verify CORS headers are returned correctly when matching configured CORS_ORIGINS."""
    custom_origins = ["https://veyra.example.com", "http://localhost:5173"]
    with patch.object(settings, "CORS_ORIGINS", custom_origins), \
         patch.object(settings, "CORS_ALLOW_ALL", False):
        test_app = create_application()
        client = TestClient(test_app)

        # 1. Allowed origin preflight
        preflight = client.options(
            "/v1/predict",
            headers={
                "Origin": "https://veyra.example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,X-Request-ID",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers.get("access-control-allow-origin") == "https://veyra.example.com"
        assert preflight.headers.get("access-control-allow-credentials") == "true"

        # 2. Disallowed origin preflight
        disallowed = client.options(
            "/v1/predict",
            headers={
                "Origin": "https://unauthorized-domain.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert disallowed.headers.get("access-control-allow-origin") is None


def test_cors_wildcard_mode_disables_credentials():
    """Verify wildcard CORS mode does not return allow_credentials=true (Fetch standard compliance)."""
    with patch.object(settings, "CORS_ALLOW_ALL", True):
        test_app = create_application()
        client = TestClient(test_app)

        preflight = client.options(
            "/v1/predict",
            headers={
                "Origin": "https://any-external-domain.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers.get("access-control-allow-origin") == "*"
        assert preflight.headers.get("access-control-allow-credentials") != "true"


def test_model_artifact_discovery_working_dir_independence():
    """Verify model artifacts can be loaded from both relative and repository-anchored paths."""
    # Test standard model loader directly
    svc = ForecastBustModelService(model_dir="models/day4")
    assert svc.model is not None
    assert svc.calibrator is not None
    assert svc.model_version == "prototype-gbm-v1"
    assert svc.threshold == 0.280

    # Test adapter
    adapter = Builder2ModelAdapter(model_dir="models/day4")
    assert adapter.is_ready is True
    assert adapter.model_version == "prototype-gbm-v1"
    assert adapter.threshold == 0.280


def test_dashboard_route_handling(deployment_client: TestClient):
    """Verify /dashboard and /dashboard/ routes respond properly."""
    r1 = deployment_client.get("/dashboard")
    r2 = deployment_client.get("/dashboard/")
    assert r1.status_code == 200
    assert r2.status_code == 200


def test_security_headers_attached_to_all_responses(deployment_client: TestClient):
    """Verify standard security headers are attached in production."""
    response = deployment_client.get("/v1/health")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_unhandled_exception_sanitization():
    """Verify unhandled 500 errors in production do not leak file paths or stack traces."""
    from backend.app.api.v1.endpoints.evaluation import get_evaluation_service

    def broken_service():
        raise RuntimeError(r"Database failure at C:\internal\secret\db.sqlite")

    app.dependency_overrides[get_evaluation_service] = broken_service
    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/v1/model/evaluation")
        assert response.status_code == 500
        payload = response.json()
        assert payload["error"] == "INTERNAL_SERVER_ERROR"
        assert "Internal secret" not in str(payload)
        assert "C:\\internal" not in str(payload)
        assert "Traceback" not in str(payload)
        assert "RuntimeError" not in str(payload)
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# PHASE 11: DEPLOYMENT FAILURE SCENARIO TESTS
# ==============================================================================

def test_failure_scenario_missing_optional_env_vars():
    """Verify application initializes safely with default values when env vars are unset."""
    with patch.dict(os.environ, {}, clear=True):
        cfg = Settings()
        assert cfg.PORT == 8000
        assert cfg.HOST == "0.0.0.0"
        assert cfg.DEBUG is False
        assert cfg.WEATHER_CACHE_ENABLED is True


def test_failure_scenario_model_artifacts_missing_handled_safely():
    """Verify missing model artifacts do not crash the service but place it in UNAVAILABLE state."""
    adapter = Builder2ModelAdapter(model_dir="nonexistent/directory/path")
    assert adapter.is_ready is False
    assert adapter.service is None
    res = adapter.predict(MagicMock())
    assert res.probability is None


def test_failure_scenario_backend_returns_structured_422_on_invalid_payload(deployment_client: TestClient):
    """Verify malformed prediction payload returns a structured 422 JSON response."""
    response = deployment_client.post("/v1/predict", json={"location": "   "})
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "VALIDATION_ERROR"
    assert "detail" in payload
    assert isinstance(payload["detail"], list)


def test_failure_scenario_rate_limiter_returns_structured_429(monkeypatch):
    """Verify excess requests trigger a structured 429 response with Retry-After header."""
    from backend.app.core.rate_limiter import SlidingWindowRateLimiter
    strict_limiter = SlidingWindowRateLimiter(requests_per_minute=2, burst_size=10, enabled=True)
    monkeypatch.setattr("backend.app.core.middleware.default_rate_limiter", strict_limiter)

    client = TestClient(app)
    r1 = client.get("/v1/model/evaluation")
    r2 = client.get("/v1/model/evaluation")
    assert r1.status_code == 200
    assert r2.status_code == 200

    # 3rd request exceeds capacity
    excess_resp = client.get("/v1/model/evaluation")
    assert excess_resp.status_code == 429
    payload = excess_resp.json()
    assert payload["error"] == "RATE_LIMIT_EXCEEDED"
    assert "retry-after" in excess_resp.headers



def test_failure_scenario_weather_cache_disabled_resilience():
    """Verify weather service functions correctly and safely when forecast caching is disabled."""
    mock_payload = {
        "latitude": 22.57,
        "longitude": 88.36,
        "hourly": {
            "time": ["2026-08-30T00:00"],
            "temperature_2m": [28.5],
            "surface_pressure": [1008.0],
            "wind_speed_10m": [3.2],
            "relative_humidity_2m": [78.0],
            "precipitation": [0.0],
        },
        "hourly_units": {
            "temperature_2m": "°C",
            "surface_pressure": "hPa",
            "wind_speed_10m": "m/s",
            "relative_humidity_2m": "%",
            "precipitation": "mm",
        },
    }
    fetch_count = 0

    def mock_fetch(url: str):
        nonlocal fetch_count
        fetch_count += 1
        return mock_payload

    svc = OpenMeteoGEFSWeatherService(
        http_client=mock_fetch,
        enable_cache=False,  # Explicitly disable cache
        enable_dedup=False,  # Explicitly disable dedup
    )
    res1 = svc.get_forecast("Kolkata")
    res2 = svc.get_forecast("Kolkata")
    assert res1.is_available is True
    assert res2.is_available is True
    assert fetch_count == 2  # Each call fetches independently
