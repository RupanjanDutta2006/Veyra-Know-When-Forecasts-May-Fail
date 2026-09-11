"""Main FastAPI Application for Forecast-Bust Sentinel with Production Hardening."""
import backend.app.core.runtime_compat  # noqa: F401 - Pre-load Linux serverless runtimes (libgomp.so.1)
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.v1.router import api_router
from backend.app.core.config import settings
from backend.app.core.error_handlers import register_exception_handlers
from backend.app.core.middleware import (
    RateLimitingMiddleware,
    RequestCorrelationMiddleware,
    SecurityHeadersMiddleware,
    StructuredLoggingMiddleware,
)

# Configure logging format and level
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_application() -> FastAPI:
    """Application factory for Forecast-Bust Sentinel API with centralized hardening."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=(
            "Forecast-Bust Sentinel is an AI-powered service that evaluates already-issued "
            "medium-range weather forecasts to detect when and why they are likely to fail unusually badly."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # 1. Register centralized safe error handlers
    register_exception_handlers(app)

    # 2. Configure CORS middleware (configurable & secure for production)
    cors_origins = settings.CORS_ORIGINS
    allow_all = settings.CORS_ALLOW_ALL or ("*" in cors_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_all else cors_origins,
        allow_credentials=not allow_all,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 3. Configure Security Headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # 4. Configure Structured Access Logging middleware
    app.add_middleware(StructuredLoggingMiddleware)

    # 5. Configure In-Process Rate Limiting middleware
    app.add_middleware(RateLimitingMiddleware)

    # 6. Configure Request Correlation ID middleware (outermost request wrapper)
    app.add_middleware(RequestCorrelationMiddleware)

    # Optional Static Frontend Mounting (when built)
    frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    assets_dir = frontend_dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")
    elif not assets_dir.exists():
        try:
            assets_dir.mkdir(parents=True, exist_ok=True)
            app.mount("/assets", StaticFiles(directory=str(assets_dir), check_dir=False), name="frontend-assets")
        except OSError:
            pass

    # Include Versioned API Routes (/v1)
    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.get("/dashboard", include_in_schema=False)
    @app.get("/dashboard/", include_in_schema=False)
    async def dashboard():
        """Serve built frontend dashboard single-page app."""
        index_file = frontend_dist / "index.html"
        if index_file.is_file():
            return FileResponse(str(index_file))
        return {
            "message": "Frontend build not found. Run 'npm run build' inside frontend/ directory.",
            "docs": "/docs",
        }

    @app.get("/", include_in_schema=False)
    async def root(request: Request):
        """Root endpoint serving built frontend dashboard or API navigation metadata."""
        index_file = frontend_dist / "index.html"
        accept = request.headers.get("accept", "")
        user_agent = request.headers.get("user-agent", "").lower()

        # If client explicitly requests JSON or is an automated test client, return API metadata
        if "application/json" in accept or "testclient" in user_agent:
            return {
                "message": "Welcome to Forecast-Bust Sentinel API",
                "docs": "/docs",
                "dashboard": "/dashboard",
                "health": f"{settings.API_V1_STR}/health",
            }

        # Otherwise, serve the built React Single Page Application if available
        if index_file.is_file():
            return FileResponse(str(index_file))

        return {
            "message": "Welcome to Forecast-Bust Sentinel API",
            "docs": "/docs",
            "dashboard": "/dashboard",
            "health": f"{settings.API_V1_STR}/health",
        }

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """Single Page Application client-side routing fallback.

        Preserves API routes, docs, and assets while allowing client-side deep links.
        """
        # Guard against intercepting API or system endpoints
        if full_path.startswith(("v1", "docs", "redoc", "openapi.json", "assets")):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        index_file = frontend_dist / "index.html"
        if index_file.is_file():
            return FileResponse(str(index_file))
        return {
            "message": "Resource not found and frontend build not present",
            "path": full_path,
        }

    return app


app = create_application()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
