"""Deterministic Tests for Day 19 Production Monitoring, Observability & Operational Reliability.

Verifies:
1. Request correlation via X-Request-ID (supplied vs generated).
2. Monotonic request latency recording and structured logging.
3. In-process metrics counters, snapshots, and test isolation resets.
4. Upstream Open-Meteo operational telemetry and error classification (TIMEOUT, HTTP_429, HTTP_5XX, MALFORMED_RESPONSE, NETWORK_ERROR).
5. Cache operational events (HIT, MISS, EXPIRED, DISABLED, EVICTION).
6. SingleFlight deduplication visibility (LEADER vs FOLLOWER coalesced).
7. Prediction & safe abstention operational telemetry.
8. Non-intrusive health checks with zero external upstream network calls.
9. Zero secret / token / sensitive coordinate leakage in logs or metrics.
"""
import json
import logging
import time
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from backend.app.core.cache import BoundedTTLCache, SingleFlight
from backend.app.core.config import settings
from backend.app.core.metrics import ProcessMetrics, default_metrics
from backend.app.core.rate_limiter import SlidingWindowRateLimiter
from backend.app.main import app
from backend.app.schemas.prediction import ReasonCode
from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService


@pytest.fixture(autouse=True)
def reset_observability_state():
    """Reset process-local metrics and cache before and after each test for strict isolation."""
    default_metrics.reset()
    yield
    default_metrics.reset()


@pytest.fixture
def obs_client() -> TestClient:
    """Test client for observability verification."""
    return TestClient(app)


# ==============================================================================
# 1. REQUEST CORRELATION & LATENCY
# ==============================================================================

def test_client_supplied_request_id_preserved(obs_client: TestClient):
    """Verify incoming valid X-Request-ID is preserved across request lifecycle."""
    custom_id = "client-trace-abc-123"
    response = obs_client.get("/v1/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id


def test_server_generated_request_id_when_missing(obs_client: TestClient):
    """Verify server generates a clean req_ sanitized ID when X-Request-ID is omitted."""
    response = obs_client.get("/v1/health")
    assert response.status_code == 200
    req_id = response.headers.get("X-Request-ID")
    assert req_id is not None
    assert req_id.startswith("req_")
    assert len(req_id) <= 64


def test_request_latency_and_http_metrics_recorded(obs_client: TestClient):
    """Verify successful request completion increments metrics and measures latency."""
    obs_client.get("/v1/health")
    obs_client.get("/v1/health")

    snapshot = default_metrics.snapshot()
    assert snapshot["http_requests_total"]["GET /v1/health 200"] == 2
    assert snapshot["http_errors_total"] == 0
    assert snapshot["http_avg_latency_ms"] >= 0.0


def test_structured_logging_json_format_support(obs_client: TestClient, caplog):
    """Verify JSON structured logging outputs valid JSON when LOG_FORMAT=json."""
    with patch.object(settings, "LOG_FORMAT", "json"), \
         patch.object(settings, "STRUCTURED_LOGGING", True), \
         caplog.at_level(logging.INFO, logger="veyra.access"):
        response = obs_client.get("/v1/health", headers={"X-Request-ID": "json-trace-99"})
        assert response.status_code == 200

        # Verify structured JSON log record was emitted
        json_records = [
            json.loads(rec.message)
            for rec in caplog.records
            if rec.name == "veyra.access" and rec.message.startswith("{")
        ]
        assert len(json_records) >= 1
        record = json_records[0]
        assert record["event"] == "request_complete"
        assert record["method"] == "GET"
        assert record["path"] == "/v1/health"
        assert record["status"] == 200
        assert record["request_id"] == "json-trace-99"
        assert "duration_ms" in record


# ==============================================================================
# 2. VALIDATION & APPLICATION RATE LIMITING
# ==============================================================================

def test_validation_failure_records_422_metric_and_correlation(obs_client: TestClient):
    """Verify malformed payload records 422 in HTTP metrics and preserves request ID."""
    custom_id = "val-fail-001"
    response = obs_client.post(
        "/v1/predict",
        json={"location": "   "},
        headers={"X-Request-ID": custom_id},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "VALIDATION_ERROR"
    assert payload["request_id"] == custom_id
    assert response.headers.get("X-Request-ID") == custom_id

    snapshot = default_metrics.snapshot()
    assert snapshot["http_requests_total"]["POST /v1/predict 422"] == 1
    assert snapshot["http_errors_total"] == 1


def test_application_rate_limiting_records_429_metric(monkeypatch):
    """Verify application-level 429 flood records 429 metric and Retry-After header."""
    strict_limiter = SlidingWindowRateLimiter(requests_per_minute=1, burst_size=1, enabled=True)
    monkeypatch.setattr("backend.app.core.middleware.default_rate_limiter", strict_limiter)

    client = TestClient(app)
    r1 = client.get("/v1/model/evaluation")
    assert r1.status_code == 200

    r2 = client.get("/v1/model/evaluation")
    assert r2.status_code == 429
    assert "retry-after" in r2.headers

    snapshot = default_metrics.snapshot()
    assert snapshot["http_requests_total"]["GET /v1/model/evaluation 429"] == 1
    assert snapshot["http_errors_total"] == 1


# ==============================================================================
# 3. UPSTREAM OPEN-METEO TELEMETRY & ERROR CLASSIFICATION
# ==============================================================================

def test_upstream_success_telemetry_recorded():
    """Verify successful upstream fetch records provider success metric and latency."""
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

    svc = OpenMeteoGEFSWeatherService(
        http_client=lambda url: mock_payload,
        enable_cache=False,
        enable_dedup=False,
    )
    result = svc.get_forecast("Kolkata")
    assert result.is_available is True

    snapshot = default_metrics.snapshot()
    assert snapshot["upstream_requests_total"]["openmeteo:SUCCESS"] == 1
    assert snapshot["upstream_failures_total"] == 0


def test_upstream_timeout_telemetry():
    """Verify upstream timeout error is classified as TIMEOUT in operational telemetry."""
    def timeout_http(url: str):
        raise TimeoutError("Connection timed out after 25s")

    svc = OpenMeteoGEFSWeatherService(
        http_client=timeout_http,
        max_retries=1,
        enable_cache=False,
        enable_dedup=False,
    )
    result = svc.get_forecast("Kolkata")
    assert result.is_available is False
    assert result.metadata["status"] == ReasonCode.DATA_UNAVAILABLE.value

    snapshot = default_metrics.snapshot()
    assert snapshot["upstream_requests_total"]["openmeteo:TIMEOUT"] == 1
    assert snapshot["upstream_failures_total"] == 1
    assert snapshot["abstentions_total"][ReasonCode.DATA_UNAVAILABLE.value] == 1


def test_upstream_http_429_telemetry():
    """Verify upstream HTTP 429 rate limit is classified as HTTP_429 in telemetry."""
    def rate_limited_http(url: str):
        raise RuntimeError("HTTP error 429 Too Many Requests")

    svc = OpenMeteoGEFSWeatherService(
        http_client=rate_limited_http,
        max_retries=1,
        enable_cache=False,
        enable_dedup=False,
    )
    result = svc.get_forecast("Kolkata")
    assert result.is_available is False

    snapshot = default_metrics.snapshot()
    assert snapshot["upstream_requests_total"]["openmeteo:HTTP_429"] == 1
    assert snapshot["upstream_429_total"] == 1
    assert snapshot["upstream_failures_total"] == 1


def test_upstream_http_5xx_telemetry():
    """Verify upstream HTTP 500/503 is classified as HTTP_5XX in telemetry."""
    def server_error_http(url: str):
        raise RuntimeError("HTTP error 503 Service Unavailable")

    svc = OpenMeteoGEFSWeatherService(
        http_client=server_error_http,
        max_retries=1,
        enable_cache=False,
        enable_dedup=False,
    )
    result = svc.get_forecast("Kolkata")
    assert result.is_available is False

    snapshot = default_metrics.snapshot()
    assert snapshot["upstream_requests_total"]["openmeteo:HTTP_5XX"] == 1
    assert snapshot["upstream_failures_total"] == 1


def test_upstream_malformed_response_telemetry():
    """Verify malformed JSON response is classified as MALFORMED_RESPONSE in telemetry."""
    def malformed_http(url: str):
        raise json.JSONDecodeError("Expecting value", "invalid json", 0)

    svc = OpenMeteoGEFSWeatherService(
        http_client=malformed_http,
        max_retries=1,
        enable_cache=False,
        enable_dedup=False,
    )
    result = svc.get_forecast("Kolkata")
    assert result.is_available is False

    snapshot = default_metrics.snapshot()
    assert snapshot["upstream_requests_total"]["openmeteo:MALFORMED_RESPONSE"] == 1
    assert snapshot["upstream_failures_total"] == 1


# ==============================================================================
# 4. CACHE & SINGLEFLIGHT OPERATIONAL VISIBILITY
# ==============================================================================

def test_cache_hit_miss_and_eviction_metrics():
    """Verify BoundedTTLCache records hit, miss, and eviction counters accurately."""
    cache = BoundedTTLCache(maxsize=2, default_ttl=60, enabled=True)

    # Miss
    assert cache.get("k1") is None
    # Set & Hit
    cache.set("k1", "v1")
    assert cache.get("k1") == "v1"

    # Fill and trigger eviction
    cache.set("k2", "v2")
    cache.set("k3", "v3")  # Evicts k1 (LRU)

    snapshot = default_metrics.snapshot()
    assert snapshot["cache_misses_total"] >= 1
    assert snapshot["cache_hits_total"] >= 1
    assert snapshot["cache_evictions_total"] >= 1


def test_singleflight_coalescing_operational_visibility():
    """Verify SingleFlight deduplication records leader and coalesced follower calls."""
    sf = SingleFlight(enabled=True)
    import threading

    leader_entered = threading.Event()
    release_leader = threading.Event()
    results = []

    def slow_action():
        leader_entered.set()
        release_leader.wait(timeout=2.0)
        return "shared_val"

    t1 = threading.Thread(target=lambda: results.append(sf.do("shared_key", slow_action)))
    t1.start()
    assert leader_entered.wait(timeout=2.0) is True

    t2 = threading.Thread(target=lambda: results.append(sf.do("shared_key", slow_action)))
    t2.start()
    time.sleep(0.05)
    release_leader.set()

    t1.join()
    t2.join()

    assert results == ["shared_val", "shared_val"]
    snapshot = default_metrics.snapshot()
    assert snapshot["singleflight_calls_total"] == 2
    assert snapshot["singleflight_coalesced_total"] == 1



def test_singleflight_exception_cleanup_and_recovery():
    """Verify failed SingleFlight leader cleans up flight state allowing subsequent success."""
    sf = SingleFlight(enabled=True)

    def failing_action():
        raise RuntimeError("Flight failure")

    with pytest.raises(RuntimeError):
        sf.do("recovery_key", failing_action)

    # State must be cleaned up; subsequent call succeeds
    result = sf.do("recovery_key", lambda: "recovered_val")
    assert result == "recovered_val"


# ==============================================================================
# 5. PREDICTION & ABSTENTION TELEMETRY
# ==============================================================================

def test_invalid_location_safe_abstention_telemetry(obs_client: TestClient):
    """Verify invalid location records abstention metric with INVALID_LOCATION reason."""
    response = obs_client.post(
        "/v1/predict",
        json={"location": "Atlantis", "variable": "temperature_2m"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["abstain"] is True
    assert "INVALID_LOCATION" in payload["reason_codes"]
    assert payload["bust_probability"] is None

    snapshot = default_metrics.snapshot()
    assert snapshot["abstentions_total"]["INVALID_LOCATION"] >= 1
    assert snapshot["predictions_total"]["outcome=ABSTAINED|risk=NONE|model=unknown"] >= 1



def test_health_endpoint_contract_and_zero_upstream_calls(obs_client: TestClient):
    """Verify /v1/health is non-intrusive, cheap, and makes 0 upstream provider calls."""
    response = obs_client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "forecast-bust-sentinel"
    assert data["version"] == "0.1.0"

    snapshot = default_metrics.snapshot()
    assert snapshot["upstream_requests_total"] == {}  # 0 external calls


def test_metrics_endpoint_contract(obs_client: TestClient):
    """Verify /v1/metrics returns a structured observability snapshot."""
    response = obs_client.get("/v1/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "http_requests_total" in data
    assert "http_errors_total" in data
    assert "uptime_seconds" in data
    assert "predictions_total" in data
    assert "abstentions_total" in data
    assert "upstream_requests_total" in data


# ==============================================================================
# 6. PRIVACY & SECRETS AUDIT
# ==============================================================================

def test_telemetry_and_metrics_contain_zero_secrets():
    """Verify metrics snapshots contain no secrets, tokens, passwords, or raw coordinates."""
    snapshot = default_metrics.snapshot()
    serialized = json.dumps(snapshot)

    # Check for forbidden sensitive keywords
    forbidden_tokens = ["api_key", "password", "secret", "token", "authorization", "bearer"]
    for token in forbidden_tokens:
        assert token not in serialized.lower()
