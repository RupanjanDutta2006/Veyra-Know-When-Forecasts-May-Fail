"""In-process Sliding-Window Rate Limiter for Abuse Protection."""
import logging
import threading
import time
from typing import Dict, List, Optional, Tuple

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding window rate limiter per client IP / key.

    Suitable for single-instance deployments and prototype testing.
    For multi-instance distributed production, a shared cache (e.g. Redis)
    can be plugged behind the same interface.
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        enabled: bool = True,
        window_seconds: int = 60,
    ):
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.enabled = enabled
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = {}
        self._lock = threading.RLock()
        self._last_cleanup = time.time()

    def _cleanup_stale_records(self, now: float) -> None:
        """Periodically prune inactive client records to avoid memory growth."""
        if now - self._last_cleanup < 60:
            return

        self._last_cleanup = now
        cutoff = now - self.window_seconds
        stale_keys = [k for k, timestamps in self._history.items() if not timestamps or timestamps[-1] < cutoff]
        for k in stale_keys:
            del self._history[k]

    def check_rate_limit(
        self,
        client_key: str,
        limit: Optional[int] = None,
        burst: Optional[int] = None,
    ) -> Tuple[bool, int]:
        """Evaluate if the client request exceeds rate limits.

        Returns:
            (is_limited, retry_after_seconds)
            If allowed: (False, 0)
            If rate-limited: (True, retry_after_seconds)
        """
        if not self.enabled:
            return False, 0

        now = time.time()
        effective_limit = limit if limit is not None else self.requests_per_minute
        effective_burst = burst if burst is not None else self.burst_size
        cutoff = now - self.window_seconds

        with self._lock:
            self._cleanup_stale_records(now)

            # Get timestamps for this client within the active sliding window
            timestamps = self._history.setdefault(client_key, [])
            valid_timestamps = [t for t in timestamps if t > cutoff]
            self._history[client_key] = valid_timestamps

            # Check capacity
            # In a 1-second burst window:
            one_sec_cutoff = now - 1.0
            recent_burst_count = sum(1 for t in valid_timestamps if t > one_sec_cutoff)

            if len(valid_timestamps) >= effective_limit:
                oldest_in_window = valid_timestamps[0]
                retry_after = max(1, int(oldest_in_window + self.window_seconds - now) + 1)
                logger.warning(
                    "Rate limit exceeded for client '%s': %d/%d req/min (Retry-After: %ds)",
                    client_key,
                    len(valid_timestamps),
                    effective_limit,
                    retry_after,
                )
                return True, retry_after

            if recent_burst_count >= effective_burst:
                logger.warning(
                    "Burst rate limit exceeded for client '%s': %d req/sec (burst cap: %d)",
                    client_key,
                    recent_burst_count,
                    effective_burst,
                )
                return True, 1

            # Request is allowed -> record timestamp
            valid_timestamps.append(now)
            return False, 0

    def reset(self) -> None:
        """Reset rate limiter state (useful for test isolation)."""
        with self._lock:
            self._history.clear()
            self._last_cleanup = time.time()


# Global rate limiter instance configured from settings
default_rate_limiter = SlidingWindowRateLimiter(
    requests_per_minute=settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
    burst_size=settings.RATE_LIMIT_BURST_SIZE,
    enabled=settings.RATE_LIMIT_ENABLED,
)
