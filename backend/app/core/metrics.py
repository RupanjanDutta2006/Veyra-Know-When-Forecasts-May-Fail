"""Thread-safe Bounded In-Process Application Metrics for Operational Observability.

Provides process-local operational counters and latency statistics with zero external
telemetry SDK dependencies. Explicitly designed for lightweight runtime diagnostics,
resettable in unit tests, and safe against memory unbounded growth.
"""
from collections import defaultdict
import threading
import time
from typing import Any, Dict, Optional


class ProcessMetrics:
    """Thread-safe, bounded, low-overhead in-process metrics tracker."""

    def __init__(self, enabled: bool = True, max_keys: int = 1024):
        self.enabled = enabled
        self._max_keys = max_keys
        self._lock = threading.Lock()

        # HTTP Request Counters & Latency
        self._http_requests: Dict[str, int] = defaultdict(int)
        self._http_errors: int = 0
        self._http_latencies_ms: list[float] = []
        self._max_latencies_stored: int = 500

        # Prediction & Abstention Counters
        self._predictions: Dict[str, int] = defaultdict(int)
        self._abstentions: Dict[str, int] = defaultdict(int)

        # Upstream Provider Telemetry
        self._upstream_requests: Dict[str, int] = defaultdict(int)
        self._upstream_failures: int = 0
        self._upstream_429: int = 0

        # Cache & Deduplication
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        self._cache_evictions: int = 0
        self._singleflight_calls: int = 0
        self._singleflight_coalesced: int = 0

        # Retries
        self._retries_attempted: int = 0

        self._start_time: float = time.time()

    def record_http_request(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        """Record an incoming HTTP request completion."""
        if not self.enabled:
            return
        # Normalize path to prevent cardinality explosion (e.g. static assets)
        normalized_path = path if not path.startswith("/assets/") else "/assets/*"
        key = f"{method.upper()} {normalized_path} {status_code}"
        with self._lock:
            if len(self._http_requests) < self._max_keys or key in self._http_requests:
                self._http_requests[key] += 1
            if status_code >= 400:
                self._http_errors += 1
            if len(self._http_latencies_ms) < self._max_latencies_stored:
                self._http_latencies_ms.append(duration_ms)

    def record_prediction(self, outcome: str, risk_level: Optional[str] = None, model_version: Optional[str] = None) -> None:
        """Record a forecast bust prediction event."""
        if not self.enabled:
            return
        key = f"outcome={outcome}|risk={risk_level or 'NONE'}|model={model_version or 'unknown'}"
        with self._lock:
            if len(self._predictions) < self._max_keys or key in self._predictions:
                self._predictions[key] += 1

    def record_abstention(self, reason_code: str) -> None:
        """Record a safety abstention event."""
        if not self.enabled:
            return
        with self._lock:
            if len(self._abstentions) < self._max_keys or reason_code in self._abstentions:
                self._abstentions[reason_code] += 1

    def record_upstream_request(self, provider: str, outcome: str, duration_ms: Optional[float] = None) -> None:
        """Record an upstream weather/data provider call."""
        if not self.enabled:
            return
        key = f"{provider}:{outcome}"
        with self._lock:
            if len(self._upstream_requests) < self._max_keys or key in self._upstream_requests:
                self._upstream_requests[key] += 1
            if outcome in ("NETWORK_ERROR", "TIMEOUT", "HTTP_5XX", "MALFORMED_RESPONSE", "HTTP_429"):
                self._upstream_failures += 1
            if outcome == "HTTP_429":
                self._upstream_429 += 1

    def record_cache_hit(self) -> None:
        """Record an in-memory cache hit."""
        if not self.enabled:
            return
        with self._lock:
            self._cache_hits += 1

    def record_cache_miss(self) -> None:
        """Record an in-memory cache miss."""
        if not self.enabled:
            return
        with self._lock:
            self._cache_misses += 1

    def record_cache_eviction(self) -> None:
        """Record an in-memory cache eviction."""
        if not self.enabled:
            return
        with self._lock:
            self._cache_evictions += 1

    def record_singleflight(self, is_leader: bool) -> None:
        """Record a SingleFlight request deduplication event."""
        if not self.enabled:
            return
        with self._lock:
            self._singleflight_calls += 1
            if not is_leader:
                self._singleflight_coalesced += 1

    def record_retry(self) -> None:
        """Record an HTTP retry execution."""
        if not self.enabled:
            return
        with self._lock:
            self._retries_attempted += 1

    def snapshot(self) -> Dict[str, Any]:
        """Return a read-only snapshot of all process-local metrics."""
        with self._lock:
            avg_latency = (
                round(sum(self._http_latencies_ms) / len(self._http_latencies_ms), 2)
                if self._http_latencies_ms
                else 0.0
            )
            return {
                "uptime_seconds": round(time.time() - self._start_time, 2),
                "http_requests_total": dict(self._http_requests),
                "http_errors_total": self._http_errors,
                "http_avg_latency_ms": avg_latency,
                "predictions_total": dict(self._predictions),
                "abstentions_total": dict(self._abstentions),
                "upstream_requests_total": dict(self._upstream_requests),
                "upstream_failures_total": self._upstream_failures,
                "upstream_429_total": self._upstream_429,
                "cache_hits_total": self._cache_hits,
                "cache_misses_total": self._cache_misses,
                "cache_evictions_total": self._cache_evictions,
                "singleflight_calls_total": self._singleflight_calls,
                "singleflight_coalesced_total": self._singleflight_coalesced,
                "retries_attempted_total": self._retries_attempted,
            }

    def reset(self) -> None:
        """Reset all metrics to initial states (for test isolation)."""
        with self._lock:
            self._http_requests.clear()
            self._http_errors = 0
            self._http_latencies_ms.clear()
            self._predictions.clear()
            self._abstentions.clear()
            self._upstream_requests.clear()
            self._upstream_failures = 0
            self._upstream_429 = 0
            self._cache_hits = 0
            self._cache_misses = 0
            self._cache_evictions = 0
            self._singleflight_calls = 0
            self._singleflight_coalesced = 0
            self._retries_attempted = 0
            self._start_time = time.time()


# Global process metrics singleton instance
default_metrics = ProcessMetrics()
