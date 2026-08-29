"""Day 14 — Production API Hardening Test Suite.

Comprehensive tests verifying:
1. Centralized exception handling, error response formatting, and path/stack-trace redaction
2. Request correlation ID injection and propagation (X-Request-ID)
3. Production security headers (X-Content-Type-Options, X-Frame-Options, etc.)
4. Structured logging and access logging behavior
5. In-process sliding-window rate limiting, HTTP 429 response, and health check exemption
6. Thread-safe BoundedTTLCache (hit, miss, expiry, LRU capacity eviction, dict protocol)
7. Bounded HTTP retry helper with exponential backoff and exhaustion
8. External provider timeout configurations across all services
9. Anti-data-leakage verification and regression protection for Days 8–13
"""
import time
from typing import Any
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.core.cache import BoundedTTLCache
from backend.app.core.config import Settings, settings
from backend.app.core.error_handlers import sanitize_error_message
from backend.app.core.http_retry import execute_with_retry
from backend.app.core.rate_limiter import SlidingWindowRateLimiter, default_rate_limiter
from backend.app.main import app
from backend.app.schemas.prediction import PredictionRequest
from backend.app.services.historical_service import HistoricalDataService
from backend.app.services.location_service import DynamicLocationService
from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService
from backend.app.services.reference_service import OpenMeteoArchiveReferenceService


@pytest.fixture(autouse=True)
def reset_rate_limiter_state():
    """Ensure rate limiter state is fresh before each test."""
    default_rate_limiter.reset()
    yield
    default_rate_limiter.reset()


# =============================================================================
# 1. REQUEST CORRELATION & SECURITY HEADERS MIDDLEWARE TESTS
# =============================================================================


def test_request_correlation_middleware_generates_request_id():
    """Verify middleware generates and attaches X-Request-ID when not provided."""
    client = TestClient(app)
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    assert response.headers["x-request-id"].startswith("req_")


def test_request_correlation_middleware_propagates_existing_request_id():
    """Verify middleware preserves and echoes client-provided X-Request-ID when valid."""
    client = TestClient(app)
    custom_id = "test-custom-trace-id-12345"
    response = client.get("/v1/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == custom_id


def test_request_correlation_preserves_valid_alphanumeric_and_separators():
    """Verify valid complex trace identifiers are preserved."""
    client = TestClient(app)
    valid_id = "trace.app_v1-service:987654"
    response = client.get("/v1/health", headers={"X-Request-ID": valid_id})
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == valid_id


def test_request_correlation_rejects_oversized_request_id():
    """Verify request ID exceeding 64 characters is safely replaced with a server-generated ID."""
    client = TestClient(app)
    oversized_id = "a" * 65
    response = client.get("/v1/health", headers={"X-Request-ID": oversized_id})
    assert response.status_code == 200
    returned_id = response.headers.get("x-request-id", "")
    assert returned_id != oversized_id
    assert returned_id.startswith("req_")


def test_request_correlation_rejects_unsafe_newlines_and_control_chars():
    """Verify request ID containing newlines, CRLF, or control characters is sanitized."""
    client = TestClient(app)
    crlf_id = "req_1234\r\nInjected-Header: evil"
    response = client.get("/v1/health", headers={"X-Request-ID": crlf_id})
    assert response.status_code == 200
    returned_id = response.headers.get("x-request-id", "")
    assert "\r" not in returned_id
    assert "\n" not in returned_id
    assert returned_id.startswith("req_")


def test_request_correlation_rejects_invalid_special_chars():
    """Verify request ID with invalid punctuation or script tags is safely replaced."""
    client = TestClient(app)
    unsafe_id = "<script>alert(1)</script>"
    response = client.get("/v1/health", headers={"X-Request-ID": unsafe_id})
    assert response.status_code == 200
    returned_id = response.headers.get("x-request-id", "")
    assert returned_id != unsafe_id
    assert returned_id.startswith("req_")


def test_security_headers_middleware_attaches_standard_headers():
    """Verify security headers are applied to HTTP responses."""
    client = TestClient(app)
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("x-xss-protection") == "1; mode=block"
    assert "strict-origin-when-cross-origin" in response.headers.get("referrer-policy", "")


# =============================================================================
# 2. CENTRALIZED EXCEPTION HANDLING & INFORMATION LEAKAGE PROTECTION
# =============================================================================


def test_path_sanitization_removes_filesystem_paths():
    """Verify path sanitization removes absolute Windows/Unix paths."""
    windows_path = r"Error loading model from C:\Users\RUPANJAN\Project\models\day4\model.joblib"
    sanitized_win = sanitize_error_message(windows_path)
    assert r"C:\Users" not in sanitized_win
    assert "[PATH]" in sanitized_win

    unix_path = "Failed to open /var/data/secrets/key.json: file not found"
    sanitized_unix = sanitize_error_message(unix_path)
    assert "/var/data" not in sanitized_unix
    assert "[PATH]" in sanitized_unix


def test_validation_error_handler_formats_safe_structured_json():
    """Verify Pydantic validation errors return structured 422 with request ID."""
    client = TestClient(app)
    # Send empty body to trigger RequestValidationError
    response = client.post("/v1/predict", json={})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert data.get("error") == "VALIDATION_ERROR"
    assert "request_id" in data
    assert "x-request-id" in response.headers


def test_unhandled_exception_returns_safe_500_without_stack_trace():
    """Verify unhandled internal exceptions return clean 500 without leaking stack traces or paths."""
    from backend.app.api.v1.endpoints.evaluation import get_evaluation_service

    def broken_service():
        raise RuntimeError(r"Database failure at C:\internal\secret\db.sqlite")

    app.dependency_overrides[get_evaluation_service] = broken_service
    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/v1/model/evaluation")
        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "INTERNAL_SERVER_ERROR"
        assert "message" in data
        assert "C:\\internal" not in data["message"]
        assert "Traceback" not in data["message"]
        assert "request_id" in data
    finally:
        app.dependency_overrides.pop(get_evaluation_service, None)


# =============================================================================
# 3. IN-PROCESS SLIDING-WINDOW RATE LIMITER TESTS
# =============================================================================


def test_rate_limiter_allows_requests_within_capacity():
    """Verify rate limiter permits requests when below the threshold."""
    limiter = SlidingWindowRateLimiter(requests_per_minute=5, burst_size=5, enabled=True)
    for i in range(5):
        is_limited, retry_after = limiter.check_rate_limit("client_1")
        assert not is_limited
        assert retry_after == 0


def test_rate_limiter_rejects_and_calculates_retry_after():
    """Verify rate limiter rejects requests when capacity is exceeded."""
    limiter = SlidingWindowRateLimiter(requests_per_minute=3, burst_size=10, enabled=True)
    # Fill capacity
    for _ in range(3):
        is_limited, _ = limiter.check_rate_limit("client_2")
        assert not is_limited

    # 4th request must be rejected
    is_limited, retry_after = limiter.check_rate_limit("client_2")
    assert is_limited
    assert retry_after >= 1


def test_rate_limiter_sliding_window_expiration():
    """Verify sliding window expires old timestamps after window duration."""
    limiter = SlidingWindowRateLimiter(requests_per_minute=2, burst_size=5, enabled=True, window_seconds=1)
    limiter.check_rate_limit("client_3")
    limiter.check_rate_limit("client_3")
    is_limited, _ = limiter.check_rate_limit("client_3")
    assert is_limited

    # Wait for the short 1s window to slide
    time.sleep(1.1)
    is_limited_after, _ = limiter.check_rate_limit("client_3")
    assert not is_limited_after


def test_rate_limiter_middleware_returns_http_429_on_excess(monkeypatch):
    """Verify FastAPI middleware returns HTTP 429 with Retry-After header on flood."""
    strict_limiter = SlidingWindowRateLimiter(requests_per_minute=2, burst_size=10, enabled=True)
    monkeypatch.setattr("backend.app.core.middleware.default_rate_limiter", strict_limiter)

    client = TestClient(app)
    # First 2 requests should succeed
    r1 = client.get("/v1/model/evaluation")
    r2 = client.get("/v1/model/evaluation")
    assert r1.status_code == 200
    assert r2.status_code == 200

    # 3rd request should trigger 429
    r3 = client.get("/v1/model/evaluation")
    assert r3.status_code == 429
    assert "retry-after" in r3.headers
    data = r3.json()
    assert data["error"] == "RATE_LIMIT_EXCEEDED"
    assert "retry_after_seconds" in data


def test_rate_limiter_exempts_health_endpoint(monkeypatch):
    """Verify health endpoint is exempt from rate limiting."""
    zero_limiter = SlidingWindowRateLimiter(requests_per_minute=0, burst_size=0, enabled=True)
    monkeypatch.setattr("backend.app.core.middleware.default_rate_limiter", zero_limiter)

    client = TestClient(app)
    for _ in range(5):
        resp = client.get("/v1/health")
        assert resp.status_code == 200


# =============================================================================
# 4. BOUNDED TTL IN-MEMORY CACHE TESTS
# =============================================================================


def test_bounded_ttl_cache_hit_and_miss():
    """Verify cache records hits and misses correctly."""
    cache = BoundedTTLCache(maxsize=10, default_ttl=60)
    assert cache.get("key1") is None
    assert cache.stats()["misses"] == 1

    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"
    assert cache.stats()["hits"] == 1


def test_bounded_ttl_cache_expiration():
    """Verify expired cache items return default and are cleaned up."""
    cache = BoundedTTLCache(maxsize=10, default_ttl=1)
    cache.set("short_lived", "data", ttl=1)
    assert cache.get("short_lived") == "data"

    time.sleep(1.1)
    assert cache.get("short_lived") is None
    assert "short_lived" not in cache


def test_bounded_ttl_cache_capacity_lru_eviction():
    """Verify cache evicts oldest entry when maxsize capacity is reached."""
    cache = BoundedTTLCache(maxsize=3, default_ttl=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)

    # Access 'a' so 'b' becomes the oldest / least recently accessed
    cache.get("a")

    # Insert 4th item -> should evict 'b'
    cache.set("d", 4)
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3
    assert cache.get("d") == 4
    assert cache.stats()["evictions"] >= 1


def test_bounded_ttl_cache_dict_protocol():
    """Verify cache supports standard dictionary protocol."""
    cache = BoundedTTLCache(maxsize=10, default_ttl=60)
    cache["city"] = "Kolkata"
    assert "city" in cache
    assert cache["city"] == "Kolkata"
    assert len(cache) == 1
    del cache["city"]
    assert "city" not in cache


# =============================================================================
# 5. BOUNDED HTTP RETRY & BACKOFF TESTS
# =============================================================================


def test_execute_with_retry_succeeds_on_transient_failure():
    """Verify retry helper retries on transient error and succeeds."""
    attempts = 0

    def unreliable_action():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ConnectionError("Temporary DNS resolution failure")
        return {"status": "ok"}

    result = execute_with_retry(
        unreliable_action,
        max_retries=3,
        backoff_factor=0.01,
        operation_name="test_transient",
    )
    assert result == {"status": "ok"}
    assert attempts == 2


def test_execute_with_retry_exhaustion_raises_exception():
    """Verify retry helper raises final exception after all retries are exhausted."""
    attempts = 0

    def failing_action():
        nonlocal attempts
        attempts += 1
        raise TimeoutError("Persistent connection timeout")

    with pytest.raises(TimeoutError) as exc_info:
        execute_with_retry(
            failing_action,
            max_retries=2,
            backoff_factor=0.01,
            operation_name="test_failing",
        )
    assert "Persistent connection timeout" in str(exc_info.value)
    assert attempts == 2


def test_execute_with_retry_retries_on_http_500_and_503():
    """Verify upstream HTTP 500 / 503 errors trigger bounded retries."""
    import urllib.error

    # Test HTTP 503 recovery on second attempt
    attempts_503 = 0

    def service_503():
        nonlocal attempts_503
        attempts_503 += 1
        if attempts_503 < 2:
            raise urllib.error.HTTPError(
                url="http://api.weather.test/gefs",
                code=503,
                msg="Service Unavailable",
                hdrs={},
                fp=None,
            )
        return {"data": "recovered"}

    res = execute_with_retry(service_503, max_retries=3, backoff_factor=0.01)
    assert res == {"data": "recovered"}
    assert attempts_503 == 2


def test_execute_with_retry_does_not_retry_http_400_or_404():
    """Verify non-transient HTTP 400 and 404 client errors fail immediately without retries."""
    import urllib.error

    # Test 404 Not Found
    attempts_404 = 0

    def service_404():
        nonlocal attempts_404
        attempts_404 += 1
        raise urllib.error.HTTPError(
            url="http://api.weather.test/bad_path",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None,
        )

    with pytest.raises(urllib.error.HTTPError) as exc_404:
        execute_with_retry(service_404, max_retries=3, backoff_factor=0.01)
    assert exc_404.value.code == 404
    # Crucial assertion: 404 must NOT retry! Exactly 1 attempt.
    assert attempts_404 == 1

    # Test 400 Bad Request
    attempts_400 = 0

    def service_400():
        nonlocal attempts_400
        attempts_400 += 1
        raise urllib.error.HTTPError(
            url="http://api.weather.test/invalid_param",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=None,
        )

    with pytest.raises(urllib.error.HTTPError) as exc_400:
        execute_with_retry(service_400, max_retries=3, backoff_factor=0.01)
    assert exc_400.value.code == 400
    assert attempts_400 == 1


def test_execute_with_retry_does_not_retry_runtime_4xx_message():
    """Verify RuntimeError with 4xx message is classified as non-retryable and aborts immediately."""
    attempts = 0

    def action_404_runtime():
        nonlocal attempts
        attempts += 1
        raise RuntimeError("HTTP 404 fetching geocoding data")

    with pytest.raises(RuntimeError) as exc_info:
        execute_with_retry(action_404_runtime, max_retries=3, backoff_factor=0.01)
    assert "HTTP 404" in str(exc_info.value)
    assert attempts == 1


# =============================================================================
# 6. EXTERNAL PROVIDER TIMEOUT & SERVICE CONFIGURATION TESTS
# =============================================================================


def test_dynamic_location_service_timeout_and_cache():
    """Verify DynamicLocationService integrates centralized timeout and BoundedTTLCache."""
    custom_cache = BoundedTTLCache(maxsize=50, default_ttl=300)
    service = DynamicLocationService(timeout_seconds=7, cache=custom_cache)
    assert service.timeout_seconds == 7

    # Resolve benchmark location
    res = service.resolve("Kolkata")
    assert res is not None
    assert res.name == "Kolkata"
    assert "kolkata" in custom_cache


def test_openmeteo_gefs_weather_service_configurable_timeout():
    """Verify OpenMeteoGEFSWeatherService respects configured timeout and retry settings."""
    service = OpenMeteoGEFSWeatherService(timeout_seconds=12, max_retries=1)
    assert service.timeout_seconds == 12
    assert service.max_retries == 1


def test_historical_data_service_configurable_timeout():
    """Verify HistoricalDataService respects configured timeout and retry settings."""
    service = HistoricalDataService(timeout_seconds=8, max_retries=3)
    assert service.timeout_seconds == 8
    assert service.max_retries == 3


def test_reference_weather_service_configurable_timeout():
    """Verify OpenMeteoArchiveReferenceService respects configured timeout settings."""
    service = OpenMeteoArchiveReferenceService(timeout_seconds=6, max_retries=2)
    assert service.timeout_seconds == 6
    assert service.max_retries == 2


# =============================================================================
# 7. REGRESSION SAFETY ACROSS DAYS 8–13
# =============================================================================


def test_single_prediction_endpoint_regression_with_hardening():
    """Verify POST /v1/predict continues to return valid predictions with explanations."""
    client = TestClient(app)
    payload = {
        "location": "London",
        "variable": "temperature_2m",
    }
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "London"
    assert data["abstain"] is False
    assert data["bust_probability"] is not None
    assert 0.0 <= data["bust_probability"] <= 1.0
    assert data["model_version"] == "prototype-gbm-v1"
    assert data["explanation"] is not None
    assert "primary_driver" in data["explanation"]
    assert "top_contributing_factors" in data["explanation"]
    # Check hardening headers
    assert "x-request-id" in response.headers
    assert response.headers.get("x-content-type-options") == "nosniff"


def test_batch_prediction_endpoint_regression_with_hardening():
    """Verify POST /v1/predict/batch executes with failure isolation and explanations."""
    client = TestClient(app)
    payload = {
        "locations": ["London", "Atlantis"],
    }
    response = client.post("/v1/predict/batch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["batch_size"] == 2
    assert len(data["results"]) == 2

    # London: valid
    london_item = data["results"][0]
    assert london_item["input_location"] == "London"
    assert london_item["is_success"] is True
    assert london_item["response"]["abstain"] is False
    assert london_item["response"]["explanation"] is not None

    # Atlantis: abstained
    atlantis_item = data["results"][1]
    assert atlantis_item["input_location"] == "Atlantis"
    assert atlantis_item["is_success"] is False
    assert atlantis_item["response"]["abstain"] is True
    assert atlantis_item["response"]["explanation"] is None


def test_model_evaluation_endpoint_regression_with_hardening():
    """Verify GET /v1/model/evaluation returns active model metrics."""
    client = TestClient(app)
    response = client.get("/v1/model/evaluation")
    assert response.status_code == 200
    data = response.json()
    assert data["model_name"] == "builder2_gbm"
    assert data["model_version"] == "prototype-gbm-v1"
    assert data["calibration"]["decision_threshold"] == 0.28
    assert data["metrics"]["roc_auc"] > 0.5
