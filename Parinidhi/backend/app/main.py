"""Main FastAPI Application for Forecast-Bust Sentinel."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.v1.router import api_router
from backend.app.core.config import settings


def create_application() -> FastAPI:
    """Application factory for Forecast-Bust Sentinel API."""
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

    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include Versioned API Routes (/v1)
    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.get("/", include_in_schema=False)
    async def root():
        """Root endpoint returning service identity."""
        return {
            "message": "Welcome to Forecast-Bust Sentinel API",
            "docs": "/docs",
            "health": f"{settings.API_V1_STR}/health",
        }

    return app


app = create_application()
