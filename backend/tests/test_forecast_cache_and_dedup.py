"""Day 17: Forecast Caching, In-Flight Deduplication & Upstream Efficiency Tests.

Deterministic test suite covering:
- TEST A: Single request causes 1 upstream fetch on cache miss.
- TEST B: Sequential reuse within TTL uses cache (upstream call count remains 1).
- TEST C: Concurrent deduplication (7 simultaneous identical requests -> 1 upstream fetch).
- TEST D: Full timeline concurrency (16 simultaneous identical requests -> 1 upstream fetch).
- TEST E: Coordinate isolation (Kolkata vs London do not share entries).
- TEST F: Cache expiration (new upstream fetch allowed after TTL expiry).
- TEST G: Upstream failure does not permanently poison cache.
- TEST H: HTTP 429 rate limit exhausted maps safely to DATA_UNAVAILABLE.
- TEST I: Wind units contract (wind_speed_10m remains m/s).
- TEST J: Genuine QC failure maps to QC_FAILED.
- TEST K: Invalid location maps to INVALID_LOCATION.
- Additional SingleFlight unit tests and Retry-After header extraction tests.
"""
import copy
import threading
import time
import urllib.error
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.core.cache import BoundedTTLCache, SingleFlight
from backend.app.core.http_retry import _extract_retry_after_seconds, execute_with_retry
from backend.app.main import app
from backend.app.safety.abstention import SafetyEvaluator
from backend.app.schemas.prediction import PredictionRequest, ReasonCode
from backend.app.services.explainability_service import ExplainabilityIntegrationService
from backend.app.services.feature_service import LiveFeatureService
from backend.app.services.model_service import LiveLogisticModelService
from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService


def _generate_synthetic_gefs_payload(
    base_temp: float = 25.0,
    base_wind: float = 4.5,
    num_hours: int = 384,
) -> Dict[str, Any]:
    """Generate a realistic 384-hour Open-Meteo GEFS ensemble payload with valid dates."""
    times = []
    temps = []
    pressures = []
    winds = []
    humidities = []
    precips = []
    base_dt = datetime(2026, 8, 30, 0, 0)

    for h in range(num_hours):
        dt = base_dt + timedelta(hours=h)
        times.append(dt.strftime("%Y-%m-%dT%H:%M"))
        temps.append(round(base_temp + (h % 24) * 0.2, 1))
        pressures.append(1012.5)
        winds.append(round(base_wind + (h % 12) * 0.1, 1))
        humidities.append(65.0)
        precips.append(0.0)

    return {
        "latitude": 22.57,
        "longitude": 88.36,
        "generationtime_ms": 1.5,
        "timezone": "UTC",
        "hourly": {
            "time": times,
            "temperature_2m": temps,
            "surface_pressure": pressures,
            "wind_speed_10m": winds,
            "relative_humidity_2m": humidities,
            "precipitation": precips,
        },
        "hourly_units": {
            "time": "iso8601",
            "temperature_2m": "°C",
            "surface_pressure": "hPa",
            "wind_speed_10m": "m/s",
            "relative_humidity_2m": "%",
            "precipitation": "mm",
        },
    }


# =========================================================================
# TEST A: Single Request -> 1 Upstream Fetch on Cache Miss
# =========================================================================
def test_a_single_request_triggers_single_upstream_fetch():
    """TEST A: One forecast acquisition causes one upstream fetch on cache miss."""
    call_counter = {"count": 0}

    def counting_http_client(url: str) -> dict:
        call_counter["count"] += 1
        return _generate_synthetic_gefs_payload()

    cache = BoundedTTLCache(maxsize=10, default_ttl=60)
    dedup = SingleFlight()
    service = OpenMeteoGEFSWeatherService(
        http_client=counting_http_client,
        cache=cache,
        deduplicator=dedup,
    )

    result = service.get_forecast("Kolkata")

    assert result.is_available is True
    assert call_counter["count"] == 1
    assert result.metadata["status"] == ReasonCode.SUCCESS.value


# =========================================================================
# TEST B: Sequential Reuse -> Uses Cache within TTL
# =========================================================================
def test_b_sequential_reuse_within_ttl_uses_cache():
    """TEST B: Second identical request within TTL uses cache (call count remains 1)."""
    call_counter = {"count": 0}

    def counting_http_client(url: str) -> dict:
        call_counter["count"] += 1
        return _generate_synthetic_gefs_payload()

    cache = BoundedTTLCache(maxsize=10, default_ttl=60)
    dedup = SingleFlight()
    service = OpenMeteoGEFSWeatherService(
        http_client=counting_http_client,
        cache=cache,
        deduplicator=dedup,
    )

    # First fetch: cache miss
    res1 = service.get_forecast("Kolkata")
    assert res1.is_available is True
    assert call_counter["count"] == 1

    # Second fetch: cache hit
    res2 = service.get_forecast("Kolkata")
    assert res2.is_available is True
    assert call_counter["count"] == 1  # Still 1!

    # Third fetch with case variance: still cache hit (same coordinates)
    res3 = service.get_forecast("kolkata")
    assert res3.is_available is True
    assert call_counter["count"] == 1  # Still 1!


# =========================================================================
# TEST C: Concurrent Deduplication (7 simultaneous requests -> 1 upstream fetch)
# =========================================================================
def test_c_concurrent_deduplication_standard_timeline():
    """TEST C: 7 simultaneous identical forecast acquisitions cause ONE upstream fetch."""
    call_counter = {"count": 0}
    lock = threading.Lock()

    def slow_counting_http_client(url: str) -> dict:
        with lock:
            call_counter["count"] += 1
        # Add slight delay to ensure followers arrive during active flight
        time.sleep(0.05)
        return _generate_synthetic_gefs_payload()

    cache = BoundedTTLCache(maxsize=10, default_ttl=60)
    dedup = SingleFlight()
    service = OpenMeteoGEFSWeatherService(
        http_client=slow_counting_http_client,
        cache=cache,
        deduplicator=dedup,
    )

    results = [None] * 7

    def worker(idx: int):
        results[idx] = service.get_forecast("Kolkata")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(7)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All 7 must succeed and receive complete records
    for i, res in enumerate(results):
        assert res is not None, f"Thread {i} returned None"
        assert res.is_available is True
        assert len(res.raw_data["records"]) == 384 * 5  # 5 variables per timestep

    # Crucial assertion: Upstream HTTP client was called exactly ONCE!
    assert call_counter["count"] == 1


# =========================================================================
# TEST D: Full Timeline Concurrency (16 simultaneous requests -> 1 upstream fetch)
# =========================================================================
def test_d_concurrent_deduplication_full_timeline():
    """TEST D: 16 simultaneous requests (Full Timeline 384h) cause ONE upstream fetch."""
    call_counter = {"count": 0}
    lock = threading.Lock()

    def slow_counting_http_client(url: str) -> dict:
        with lock:
            call_counter["count"] += 1
        time.sleep(0.05)
        return _generate_synthetic_gefs_payload()

    cache = BoundedTTLCache(maxsize=10, default_ttl=60)
    dedup = SingleFlight()
    service = OpenMeteoGEFSWeatherService(
        http_client=slow_counting_http_client,
        cache=cache,
        deduplicator=dedup,
    )

    num_threads = 16
    results = [None] * num_threads

    def worker(idx: int):
        results[idx] = service.get_forecast("Kolkata")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for i, res in enumerate(results):
        assert res is not None
        assert res.is_available is True

    # Upstream HTTP fetch count remains strictly 1
    assert call_counter["count"] == 1


# =========================================================================
# TEST E: Coordinate Isolation (Kolkata vs London do not share entries)
# =========================================================================
def test_e_coordinate_isolation_different_locations():
    """TEST E: Kolkata and London must not incorrectly share cache entries."""
    call_counter = {"Kolkata": 0, "London": 0}

    def multi_location_http_client(url: str) -> dict:
        if "latitude=22.5726" in url:
            call_counter["Kolkata"] += 1
            return _generate_synthetic_gefs_payload(base_temp=30.0)
        elif "latitude=51.5074" in url:
            call_counter["London"] += 1
            return _generate_synthetic_gefs_payload(base_temp=15.0)
        else:
            raise ValueError(f"Unexpected URL: {url}")

    cache = BoundedTTLCache(maxsize=10, default_ttl=60)
    dedup = SingleFlight()
    service = OpenMeteoGEFSWeatherService(
        http_client=multi_location_http_client,
        cache=cache,
        deduplicator=dedup,
    )

    res_kolkata = service.get_forecast("Kolkata")
    res_london = service.get_forecast("London")

    assert res_kolkata.is_available is True
    assert res_london.is_available is True

    # Each distinct location triggered its own independent upstream fetch
    assert call_counter["Kolkata"] == 1
    assert call_counter["London"] == 1

    # Verify distinct temperature data
    temp_kolkata = res_kolkata.raw_data["records"][0]["value"]
    temp_london = res_london.raw_data["records"][0]["value"]
    assert temp_kolkata == 30.0
    assert temp_london == 15.0


# =========================================================================
# TEST F: Cache Expiration (New fetch allowed after TTL)
# =========================================================================
def test_f_cache_expiration_triggers_new_fetch():
    """TEST F: After TTL expiry, a new upstream fetch is performed."""
    call_counter = {"count": 0}

    def counting_http_client(url: str) -> dict:
        call_counter["count"] += 1
        return _generate_synthetic_gefs_payload(base_temp=20.0 + call_counter["count"])

    # 1 second TTL
    cache = BoundedTTLCache(maxsize=10, default_ttl=1)
    dedup = SingleFlight()
    service = OpenMeteoGEFSWeatherService(
        http_client=counting_http_client,
        cache=cache,
        cache_ttl=1,
        deduplicator=dedup,
    )

    res1 = service.get_forecast("Kolkata")
    assert call_counter["count"] == 1
    assert res1.raw_data["records"][0]["value"] == 21.0

    # Wait for TTL to expire
    time.sleep(1.1)

    res2 = service.get_forecast("Kolkata")
    assert call_counter["count"] == 2
    assert res2.raw_data["records"][0]["value"] == 22.0


# =========================================================================
# TEST G: Upstream Failure Does Not Poison Cache
# =========================================================================
def test_g_upstream_failure_does_not_poison_cache():
    """TEST G: Failure must not poison the cache permanently."""
    attempt_counter = {"count": 0}

    def flaky_http_client(url: str) -> dict:
        attempt_counter["count"] += 1
        if attempt_counter["count"] == 1:
            raise RuntimeError("Temporary network outage 503")
        return _generate_synthetic_gefs_payload(base_temp=28.0)

    cache = BoundedTTLCache(maxsize=10, default_ttl=60)
    dedup = SingleFlight()
    service = OpenMeteoGEFSWeatherService(
        http_client=flaky_http_client,
        cache=cache,
        deduplicator=dedup,
        max_retries=1,
    )

    # First attempt fails
    res1 = service.get_forecast("Kolkata")
    assert res1.is_available is False
    assert res1.quality_flags.get("network_error") is True
    assert res1.metadata.get("status") == ReasonCode.DATA_UNAVAILABLE.value

    # Second attempt must NOT return a cached failure; it attempts a fresh fetch
    res2 = service.get_forecast("Kolkata")
    assert res2.is_available is True
    assert res2.metadata.get("status") == ReasonCode.SUCCESS.value
    assert attempt_counter["count"] == 2


# =========================================================================
# TEST H: HTTP 429 Rate Limit Exhaustion Maps to DATA_UNAVAILABLE
# =========================================================================
def test_h_http_429_exhaustion_maps_to_data_unavailable():
    """TEST H: After bounded retries on 429, result remains DATA_UNAVAILABLE."""
    def rate_limited_http(url: str) -> dict:
        raise urllib.error.HTTPError(
            url=url,
            code=429,
            msg="Too Many Requests",
            hdrs={"Retry-After": "1"},
            fp=None,
        )

    cache = BoundedTTLCache(maxsize=10, default_ttl=60)
    dedup = SingleFlight()
    service = OpenMeteoGEFSWeatherService(
        http_client=rate_limited_http,
        cache=cache,
        deduplicator=dedup,
        max_retries=2,
    )

    result = service.get_forecast("Kolkata")

    assert result.is_available is False
    assert result.quality_flags.get("network_error") is True
    assert result.metadata.get("status") == ReasonCode.DATA_UNAVAILABLE.value


# =========================================================================
# TEST I: Wind Units Contract Preservation (m/s)
# =========================================================================
def test_i_wind_speed_unit_preservation_and_query_contract():
    """TEST I: Query URL includes wind_speed_unit=ms and parsed records preserve m/s."""
    service = OpenMeteoGEFSWeatherService()
    url = service.build_query_url(22.5726, 88.3639)
    assert "wind_speed_unit=ms" in url

    payload = _generate_synthetic_gefs_payload(base_wind=6.2)
    records = service.parse_canonical_records(payload, "Kolkata", 22.5726, 88.3639)
    wind_records = [r for r in records if r.variable == "wind_speed_10m"]
    assert len(wind_records) > 0
    assert wind_records[0].unit == "m/s"
    assert wind_records[0].value == 6.2


# =========================================================================
# TEST J: Genuine Meteorological QC Failure Maps to QC_FAILED
# =========================================================================
def test_j_genuine_qc_failure_maps_to_qc_failed():
    """TEST J: Genuine physical out-of-bounds violations map to QC_FAILED."""
    # Temperature out of physical limits (80°C)
    payload = _generate_synthetic_gefs_payload(base_temp=80.0)

    cache = BoundedTTLCache(maxsize=10, default_ttl=60)
    service = OpenMeteoGEFSWeatherService(
        http_client=lambda url: payload,
        cache=cache,
    )
    result = service.get_forecast("Kolkata")

    assert result.is_available is False
    assert result.quality_flags.get("qc_passed") is False
    assert result.metadata.get("status") == ReasonCode.QC_FAILED.value
    assert "Quality control checks failed" in result.error


# =========================================================================
# TEST K: Unresolvable Location Maps to INVALID_LOCATION
# =========================================================================
def test_k_invalid_location_maps_to_invalid_location():
    """TEST K: Unresolvable or fictional location maps to INVALID_LOCATION."""
    service = OpenMeteoGEFSWeatherService()
    result = service.get_forecast("AtlantisFictionalCityXYZ")

    assert result.is_available is False
    assert result.quality_flags.get("invalid_location") is True
    assert result.metadata.get("status") == ReasonCode.INVALID_LOCATION.value


# =========================================================================
# SingleFlight Unit Tests
# =========================================================================
def test_single_flight_leader_follower_synchronization():
    """Verify SingleFlight coordinates leader and multiple followers cleanly."""
    sf = SingleFlight(enabled=True)
    execution_count = 0
    lock = threading.Lock()

    def slow_action():
        nonlocal execution_count
        with lock:
            execution_count += 1
        time.sleep(0.05)
        return "shared_value"

    threads_count = 10
    results = [None] * threads_count

    def worker(i: int):
        results[i] = sf.do("test_key", slow_action)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(threads_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert execution_count == 1
    for r in results:
        assert r == "shared_value"

    stats = sf.stats()
    assert stats["active_flights"] == 0
    assert stats["total_calls"] == threads_count
    assert stats["coalesced_calls"] == threads_count - 1


def test_single_flight_exception_propagation_to_all_waiters():
    """Verify that if leader raises an exception, all waiting callers receive it."""
    sf = SingleFlight(enabled=True)

    def failing_action():
        time.sleep(0.03)
        raise ValueError("Leader failed")

    threads_count = 5
    exceptions = [None] * threads_count

    def worker(i: int):
        try:
            sf.do("error_key", failing_action)
        except Exception as exc:
            exceptions[i] = exc

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(threads_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for e in exceptions:
        assert isinstance(e, ValueError)
        assert str(e) == "Leader failed"

    # In-flight entry must be cleaned up
    assert sf.stats()["active_flights"] == 0


def test_retry_after_header_extraction():
    """Verify bounded extraction of Retry-After header."""
    # Test valid small integer
    class MockHttpErrorWithHeader(Exception):
        headers = {"Retry-After": "1.5"}

    assert _extract_retry_after_seconds(MockHttpErrorWithHeader()) == 1.5

    # Test large integer is capped to 2.0s
    class MockHttpErrorLargeHeader(Exception):
        headers = {"Retry-After": "3600"}

    assert _extract_retry_after_seconds(MockHttpErrorLargeHeader()) == 2.0

    # Test non-numeric header
    class MockHttpErrorInvalidHeader(Exception):
        headers = {"Retry-After": "invalid"}

    assert _extract_retry_after_seconds(MockHttpErrorInvalidHeader()) is None

    # Test missing header
    class MockHttpErrorNoHeader(Exception):
        headers = {}

    assert _extract_retry_after_seconds(MockHttpErrorNoHeader()) is None


# =========================================================================
# End-to-End Multi-Horizon ForecastBustAgent Tests
# =========================================================================
def test_end_to_end_agent_multi_horizon_cache_reuse():
    """Verify that 7 multi-horizon prediction requests from ForecastBustAgent make exactly 1 upstream fetch."""
    call_counter = {"count": 0}

    def counting_http(url: str) -> dict:
        call_counter["count"] += 1
        return _generate_synthetic_gefs_payload()

    cache = BoundedTTLCache(maxsize=10, default_ttl=60)
    dedup = SingleFlight()
    weather_svc = OpenMeteoGEFSWeatherService(
        http_client=counting_http,
        cache=cache,
        deduplicator=dedup,
    )
    feature_svc = LiveFeatureService()
    model_svc = LiveLogisticModelService()
    safety_evaluator = SafetyEvaluator()
    expl_svc = ExplainabilityIntegrationService()

    agent = ForecastBustAgent(
        weather_service=weather_svc,
        feature_service=feature_svc,
        model_service=model_svc,
        safety_evaluator=safety_evaluator,
        explainability_service=expl_svc,
    )

    lead_hours_list = [24, 48, 72, 96, 120, 144, 168]
    issue_time = "2026-08-30T00:00:00Z"

    responses = []
    for lead in lead_hours_list:
        valid_time = (datetime(2026, 8, 30, 0, 0) + timedelta(hours=lead)).isoformat() + "Z"
        req = PredictionRequest(
            location="Kolkata",
            variable="temperature_2m",
            issue_time=issue_time,
            valid_time=valid_time,
        )
        resp = agent.analyze(req)
        responses.append(resp)

    # All 7 horizon evaluations succeeded
    for resp in responses:
        assert resp.abstain is False
        assert resp.bust_probability is not None
        assert 0.0 <= resp.bust_probability <= 1.0

    # Exactly 1 upstream fetch performed across all 7 horizons!
    assert call_counter["count"] == 1


def test_end_to_end_agent_concurrent_multi_horizon_dedup():
    """Verify that 16 concurrent multi-horizon requests (Full Timeline 384h) make exactly 1 upstream fetch."""
    call_counter = {"count": 0}
    lock = threading.Lock()

    def slow_counting_http(url: str) -> dict:
        with lock:
            call_counter["count"] += 1
        time.sleep(0.05)
        return _generate_synthetic_gefs_payload()

    cache = BoundedTTLCache(maxsize=10, default_ttl=60)
    dedup = SingleFlight()
    weather_svc = OpenMeteoGEFSWeatherService(
        http_client=slow_counting_http,
        cache=cache,
        deduplicator=dedup,
    )
    feature_svc = LiveFeatureService()
    model_svc = LiveLogisticModelService()
    safety_evaluator = SafetyEvaluator()
    expl_svc = ExplainabilityIntegrationService()

    agent = ForecastBustAgent(
        weather_service=weather_svc,
        feature_service=feature_svc,
        model_service=model_svc,
        safety_evaluator=safety_evaluator,
        explainability_service=expl_svc,
    )

    lead_hours_list = [24, 48, 72, 96, 120, 144, 168, 192, 216, 240, 264, 288, 312, 336, 360, 384]
    issue_time = "2026-08-30T00:00:00Z"
    responses = [None] * len(lead_hours_list)

    def worker(idx: int, lead: int):
        valid_time = (datetime(2026, 8, 30, 0, 0) + timedelta(hours=lead)).isoformat() + "Z"
        req = PredictionRequest(
            location="Kolkata",
            variable="temperature_2m",
            issue_time=issue_time,
            valid_time=valid_time,
        )
        responses[idx] = agent.analyze(req)

    threads = [
        threading.Thread(target=worker, args=(i, lead))
        for i, lead in enumerate(lead_hours_list)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for resp in responses:
        assert resp is not None
        assert resp.abstain is False
        assert resp.bust_probability is not None

    # Upstream HTTP fetch count remains strictly 1 for all 16 concurrent horizons!
    assert call_counter["count"] == 1

