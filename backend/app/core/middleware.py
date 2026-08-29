"""Production FastAPI Middleware for Security, Correlation, Logging, and Rate Limiting."""
import logging
import time
import uuid
from typing import Callable
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.core.config import settings
from backend.app.core.rate_limiter import default_rate_limiter

import re

logger = logging.getLogger("veyra.access")

# Allowed characters for client-supplied request IDs: alphanumeric, hyphen, underscore, dot, colon (max 64 chars)
_REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.:]{1,64}$")


def sanitize_or_generate_request_id(client_request_id: str | None) -> str:
    """Validate and sanitize client-supplied request ID, or generate a fresh server ID.

    Prevents newline injection, control characters, overly long strings,
    and log-poisoning payloads from propagating into logs or response headers.
    """
    if client_request_id and isinstance(client_request_id, str):
        trimmed = client_request_id.strip()
        if _REQUEST_ID_REGEX.fullmatch(trimmed):
            return trimmed
    return f"req_{uuid.uuid4().hex[:12]}"


# Exempt paths that should never be rate limited or blocked
RATE_LIMIT_EXEMPT_PATHS = {
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    f"{settings.API_V1_STR}/health",
    "/health",
}


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware attaching and propagating a validated X-Request-ID across the request lifecycle."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.ENABLE_REQUEST_CORRELATION:
            return await call_next(request)

        # Extract and sanitize incoming request ID or generate a new one
        raw_request_id = request.headers.get("X-Request-ID")
        request_id = sanitize_or_generate_request_id(raw_request_id)

        # Store in request state for access in logs and handlers
        request.state.request_id = request_id

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware attaching standard production security and privacy headers."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response: Response = await call_next(request)

        if settings.ENABLE_SECURITY_HEADERS:
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware recording structured request latency, completion, and diagnostic metrics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        request_id = getattr(request.state, "request_id", "-")

        try:
            response: Response = await call_next(request)
            duration_ms = round((time.time() - start_time) * 1000, 2)

            if settings.STRUCTURED_LOGGING:
                logger.info(
                    "request_complete method=%s path=%s status=%d duration_ms=%.2f client_ip=%s request_id=%s",
                    request.method,
                    request.url.path,
                    response.status_code,
                    duration_ms,
                    client_ip,
                    request_id,
                )

            return response
        except Exception as exc:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(
                "request_failed method=%s path=%s error=%s duration_ms=%.2f client_ip=%s request_id=%s",
                request.method,
                request.url.path,
                exc,
                duration_ms,
                client_ip,
                request_id,
            )
            raise exc


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Middleware enforcing sliding-window rate limits to prevent endpoint abuse."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Bypass rate limiting for exempt system endpoints
        if path in RATE_LIMIT_EXEMPT_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "127.0.0.1"
        is_limited, retry_after = default_rate_limiter.check_rate_limit(client_ip)

        if is_limited:
            request_id = getattr(request.state, "request_id", "-")
            response = JSONResponse(
                status_code=429,
                content={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Please retry after the specified backoff period.",
                    "retry_after_seconds": retry_after,
                    "request_id": request_id,
                },
            )
            response.headers["Retry-After"] = str(retry_after)
            return response

        return await call_next(request)
