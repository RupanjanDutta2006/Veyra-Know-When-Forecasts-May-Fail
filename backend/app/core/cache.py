"""Thread-safe Bounded In-Memory LRU Cache with Time-To-Live (TTL) expiration."""
from collections import OrderedDict
import logging
import threading
import time
from typing import Any, Callable, Dict, Iterator, Optional, Tuple

from backend.app.core.config import settings
from backend.app.core.metrics import default_metrics

logger = logging.getLogger(__name__)


class BoundedTTLCache:
    """Thread-safe, in-memory LRU cache with per-item TTL expiration and eviction controls."""

    def __init__(
        self,
        maxsize: int = 1024,
        default_ttl: int = 3600,
        enabled: bool = True,
    ):
        self.maxsize = maxsize
        self.default_ttl = default_ttl
        self.enabled = enabled
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self._lock = threading.RLock()
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0

    def _is_expired(self, expiry_time: float) -> bool:
        """Check if expiration timestamp has passed."""
        return time.time() > expiry_time

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve an item from cache if present and not expired."""
        if not self.enabled:
            return default

        with self._lock:
            if key not in self._cache:
                self._misses += 1
                default_metrics.record_cache_miss()
                return default

            value, expiry_time = self._cache[key]
            if self._is_expired(expiry_time):
                # Remove expired entry
                del self._cache[key]
                self._misses += 1
                default_metrics.record_cache_miss()
                return default

            # Move to end to signify recent access (LRU)
            self._cache.move_to_end(key)
            self._hits += 1
            default_metrics.record_cache_hit()
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Insert or update an item in cache with TTL."""
        if not self.enabled:
            return

        effective_ttl = ttl if ttl is not None else self.default_ttl
        expiry_time = time.time() + max(0, effective_ttl)

        with self._lock:
            # Clean up expired items if reaching capacity
            if len(self._cache) >= self.maxsize and key not in self._cache:
                self._evict_expired_or_oldest()

            if key in self._cache:
                self._cache.move_to_end(key)

            self._cache[key] = (value, expiry_time)

    def _evict_expired_or_oldest(self) -> None:
        """Evict first found expired item, or oldest entry if none expired."""
        now = time.time()
        expired_keys = [k for k, (_, exp) in self._cache.items() if now > exp]
        if expired_keys:
            for k in expired_keys[:5]:
                if k in self._cache:
                    del self._cache[k]
                    self._evictions += 1
                    default_metrics.record_cache_eviction()
            return

        # Evict oldest (least recently used)
        if self._cache:
            self._cache.popitem(last=False)
            self._evictions += 1
            default_metrics.record_cache_eviction()

    def delete(self, key: str) -> bool:
        """Remove a key from the cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all cached entries and reset metrics."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def size(self) -> int:
        """Return current count of non-expired cached entries."""
        with self._lock:
            now = time.time()
            return sum(1 for _, exp in self._cache.values() if exp > now)

    def stats(self) -> Dict[str, Any]:
        """Return cache operational metrics."""
        with self._lock:
            return {
                "size": len(self._cache),
                "maxsize": self.maxsize,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "enabled": self.enabled,
            }

    # Dict-like protocol support for seamless interoperability
    def __contains__(self, key: str) -> bool:
        if not self.enabled:
            return False
        with self._lock:
            if key not in self._cache:
                return False
            _, expiry_time = self._cache[key]
            if self._is_expired(expiry_time):
                del self._cache[key]
                return False
            return True

    def __getitem__(self, key: str) -> Any:
        with self._lock:
            if key not in self._cache:
                raise KeyError(key)
            val, expiry_time = self._cache[key]
            if self._is_expired(expiry_time):
                del self._cache[key]
                raise KeyError(key)
            self._cache.move_to_end(key)
            self._hits += 1
            return val

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __delitem__(self, key: str) -> None:
        with self._lock:
            if not self.delete(key):
                raise KeyError(key)

    def __len__(self) -> int:
        return self.size()


# Default global location resolution cache
location_cache = BoundedTTLCache(
    maxsize=settings.CACHE_MAX_SIZE,
    default_ttl=settings.CACHE_TTL_SECONDS,
    enabled=settings.CACHE_ENABLED,
)

# Default global short-lived weather forecast response cache (Day 17)
forecast_cache = BoundedTTLCache(
    maxsize=settings.WEATHER_CACHE_MAX_SIZE,
    default_ttl=settings.WEATHER_CACHE_TTL_SECONDS,
    enabled=settings.WEATHER_CACHE_ENABLED,
)


class SingleFlight:
    """Thread-safe in-flight request deduplication (Flight Coalescing).

    Ensures that for any given key, only one execution of a slow/network operation
    is in progress at any time. Concurrent callers for the same key await the active
    flight and share the identical result (or exception) without duplicate upstream calls.
    """

    class _Flight:
        def __init__(self):
            self.event = threading.Event()
            self.result: Any = None
            self.exception: Optional[BaseException] = None
            self.waiters: int = 1

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._lock = threading.Lock()
        self._flights: Dict[str, SingleFlight._Flight] = {}
        self._total_calls: int = 0
        self._coalesced_calls: int = 0

    def do(self, key: str, action: Callable[[], Any]) -> Any:
        """Execute action or await active flight for key."""
        if not self.enabled:
            return action()

        with self._lock:
            self._total_calls += 1
            if key in self._flights:
                flight = self._flights[key]
                flight.waiters += 1
                self._coalesced_calls += 1
                is_leader = False
            else:
                flight = self._Flight()
                self._flights[key] = flight
                is_leader = True

        default_metrics.record_singleflight(is_leader)

        if not is_leader:
            flight.event.wait()
            if flight.exception is not None:
                raise flight.exception
            return flight.result

        try:
            result = action()
            flight.result = result
            return result
        except BaseException as exc:
            flight.exception = exc
            raise exc
        finally:
            with self._lock:
                self._flights.pop(key, None)
            flight.event.set()

    def stats(self) -> Dict[str, Any]:
        """Return operational metrics."""
        with self._lock:
            return {
                "active_flights": len(self._flights),
                "total_calls": self._total_calls,
                "coalesced_calls": self._coalesced_calls,
                "enabled": self.enabled,
            }

    def reset(self) -> None:
        """Reset internal metrics and flights."""
        with self._lock:
            self._flights.clear()
            self._total_calls = 0
            self._coalesced_calls = 0


# Default global in-flight request deduplicator (Day 17)
forecast_deduplicator = SingleFlight(
    enabled=settings.WEATHER_DEDUP_ENABLED,
)
