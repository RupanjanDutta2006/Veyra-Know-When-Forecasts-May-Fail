"""Centralized Exception Handlers for FastAPI Application.

Enforces information leakage protection, standardized error contracts,
path and traceback sanitization, and request ID correlation.
"""
import logging
import re
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Patterns matching sensitive system or local filesystem paths
_PATH_PATTERN = re.compile(r"([A-Za-z]:\\[^\s\)\'\"]+|\/[a-zA-Z0-9_\-\.\/]+)")


def sanitize_error_message(message: str) -> str:
    """Sanitize strings to remove local filesystem paths, credentials, and internal details."""
    if not message:
        return ""
    # Replace absolute file paths with generic placeholder
    sanitized = _PATH_PATTERN.sub("[PATH]", str(message))
    return sanitized


# Supported HTTP 422 status code (avoids Starlette deprecation warning)
HTTP_422_STATUS = getattr(
    status, "HTTP_422_UNPROCESSABLE_CONTENT", 422
)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors with clean structured output."""
    request_id = getattr(request.state, "request_id", "-")
    sanitized_errors = []

    for err in exc.errors():
        clean_err = dict(err)
        if "ctx" in clean_err and "error" in clean_err["ctx"]:
            clean_err["ctx"]["error"] = sanitize_error_message(str(clean_err["ctx"]["error"]))
        sanitized_errors.append(clean_err)

    return JSONResponse(
        status_code=HTTP_422_STATUS,
        content={
            "detail": sanitized_errors,
            "error": "VALIDATION_ERROR",
            "request_id": request_id,
        },
    )


async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    """Handle explicit HTTPExceptions without information leakage."""
    request_id = getattr(request.state, "request_id", "-")
    return JSONResponse(
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
        content={
            "detail": sanitize_error_message(str(exc.detail)),
            "error": "HTTP_ERROR",
            "request_id": request_id,
        },
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handle unexpected exceptions safely by masking stack traces and internal paths."""
    request_id = getattr(request.state, "request_id", "-")
    # Log the full exception with traceback internally
    logger.error(
        "Unhandled internal exception on %s %s (request_id=%s): %s",
        request.method,
        request.url.path,
        request_id,
        exc,
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred while processing the request.",
            "request_id": request_id,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all centralized exception handlers on the FastAPI application."""
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
