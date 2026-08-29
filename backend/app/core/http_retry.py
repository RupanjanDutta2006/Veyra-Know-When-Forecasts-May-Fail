"""Bounded HTTP execution with retry and exponential backoff."""
import logging
import re
import socket
import time
import urllib.error
from typing import Any, Callable, Optional, Sequence, Type

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# HTTP status codes that represent transient failures eligible for retry
RETRYABLE_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}

# HTTP status codes that represent non-transient client errors that should NOT be retried
NON_RETRYABLE_HTTP_STATUS_CODES = {400, 401, 403, 404, 405, 409, 410, 422}

# Regex to detect 4xx / 5xx status codes embedded in RuntimeError strings
_HTTP_ERROR_CODE_REGEX = re.compile(r"HTTP\s*(?:error\s*)?(\d{3})", re.IGNORECASE)


def is_retryable_exception(exc: Exception) -> bool:
    """Classify whether an exception represents a transient failure eligible for retry.

    Transient / Retryable:
    - urllib.error.HTTPError with 5xx status codes (500, 502, 503, 504) or 429
    - Transient network / connection errors: TimeoutError, ConnectionError, socket.timeout
    - urllib.error.URLError (non-HTTPError network/DNS connection failures)
    - Transient OS-level socket errors (OSError)

    Non-Retryable:
    - urllib.error.HTTPError with 4xx status codes (400, 401, 403, 404, 422, etc. except 429)
    - RuntimeError explicitly signaling a 4xx client response
    """
    # 1. urllib.error.HTTPError with HTTP status code
    if isinstance(exc, urllib.error.HTTPError):
        code = getattr(exc, "code", None)
        if code is not None:
            if code in RETRYABLE_HTTP_STATUS_CODES:
                return True
            if code in NON_RETRYABLE_HTTP_STATUS_CODES or (400 <= code < 500 and code != 429):
                return False

    # 2. Transient timeout and socket/connection errors
    if isinstance(exc, (TimeoutError, ConnectionError, socket.timeout)):
        return True

    # 3. Pure URLError (e.g. host unreachable, DNS lookup failed, connection refused)
    if isinstance(exc, urllib.error.URLError):
        return True

    # 4. Check explicit status_code / status attributes on custom error objects
    status_code = getattr(exc, "status_code", getattr(exc, "status", None))
    if isinstance(status_code, int):
        if status_code in RETRYABLE_HTTP_STATUS_CODES:
            return True
        if status_code in NON_RETRYABLE_HTTP_STATUS_CODES or (400 <= status_code < 500 and status_code != 429):
            return False

    # 5. RuntimeError parsing (e.g. "HTTP error 404 fetching ...")
    if isinstance(exc, RuntimeError):
        match = _HTTP_ERROR_CODE_REGEX.search(str(exc))
        if match:
            code = int(match.group(1))
            if code in RETRYABLE_HTTP_STATUS_CODES:
                return True
            if code in NON_RETRYABLE_HTTP_STATUS_CODES or (400 <= code < 500 and code != 429):
                return False
        return True

    # 6. General OSError (network-level I/O issues)
    if isinstance(exc, OSError):
        return True

    return False


def execute_with_retry(
    action: Callable[[], Any],
    max_retries: int = 2,
    backoff_factor: float = 0.3,
    retryable_classifier: Optional[Callable[[Exception], bool]] = None,
    retryable_exceptions: Optional[Sequence[Type[Exception]]] = None,
    operation_name: str = "HTTP request",
) -> Any:
    """Execute a callable with bounded retry and exponential backoff.

    Args:
        action: Zero-argument callable to execute.
        max_retries: Total number of attempts (minimum 1).
        backoff_factor: Multiplier for exponential sleep between attempts.
        retryable_classifier: Optional custom classification callable returning True if retryable.
        retryable_exceptions: Optional tuple of exception classes (for backward compatibility).
        operation_name: Human-readable description for structured logs.

    Returns:
        The result of the action callable.

    Raises:
        The caught exception immediately if non-retryable, or the final caught exception once retries are exhausted.
    """
    total_attempts = max(1, max_retries)

    for attempt in range(1, total_attempts + 1):
        try:
            return action()
        except Exception as exc:
            # Determine retry eligibility
            should_retry = False
            if retryable_exceptions is not None:
                should_retry = isinstance(exc, tuple(retryable_exceptions))
            elif retryable_classifier is not None:
                should_retry = retryable_classifier(exc)
            else:
                should_retry = is_retryable_exception(exc)

            if not should_retry:
                logger.info(
                    "%s encountered non-retryable error (%s). Aborting without retry.",
                    operation_name,
                    exc,
                )
                raise exc

            if attempt >= total_attempts:
                logger.warning(
                    "%s failed after %d attempt(s): %s",
                    operation_name,
                    attempt,
                    exc,
                )
                raise exc

            sleep_duration = backoff_factor * (2 ** (attempt - 1))
            logger.info(
                "%s failed attempt %d/%d (%s). Retrying in %.2fs...",
                operation_name,
                attempt,
                total_attempts,
                exc,
                sleep_duration,
            )
            if sleep_duration > 0:
                time.sleep(sleep_duration)
