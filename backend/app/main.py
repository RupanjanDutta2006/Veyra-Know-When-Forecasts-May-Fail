"""Main FastAPI Application for Forecast-Bust Sentinel with Production Hardening."""
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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

    # 2. Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
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
    if (frontend_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="frontend-assets")

    # Include Versioned API Routes (/v1)
    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.get("/dashboard", include_in_schema=False)
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
    async def root():
        """Root endpoint returning service identity."""
        return {
            "message": "Welcome to Forecast-Bust Sentinel API",
            "docs": "/docs",
            "dashboard": "/dashboard",
            "health": f"{settings.API_V1_STR}/health",
        }

    return app


app = create_application()
