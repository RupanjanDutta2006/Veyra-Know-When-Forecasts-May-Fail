"""Core configuration, caching, middleware, and resilience package."""
from backend.app.core.cache import (
    BoundedTTLCache,
    SingleFlight,
    forecast_cache,
    forecast_deduplicator,
    location_cache,
)
from backend.app.core.config import Settings, settings
from backend.app.core.error_handlers import register_exception_handlers
from backend.app.core.http_retry import execute_with_retry
from backend.app.core.middleware import (
    RateLimitingMiddleware,
    RequestCorrelationMiddleware,
    SecurityHeadersMiddleware,
    StructuredLoggingMiddleware,
)
from backend.app.core.rate_limiter import SlidingWindowRateLimiter, default_rate_limiter

__all__ = [
    "BoundedTTLCache",
    "RateLimitingMiddleware",
    "RequestCorrelationMiddleware",
    "SecurityHeadersMiddleware",
    "Settings",
    "SingleFlight",
    "SlidingWindowRateLimiter",
    "StructuredLoggingMiddleware",
    "default_rate_limiter",
    "execute_with_retry",
    "forecast_cache",
    "forecast_deduplicator",
    "location_cache",
    "register_exception_handlers",
    "settings",
]
