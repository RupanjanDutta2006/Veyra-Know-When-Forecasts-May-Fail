"""Health check response schema."""
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check endpoint response schema."""

    status: str = Field(default="ok", description="Service health status indicator")
    service: str = Field(
        default="forecast-bust-sentinel",
        description="Name of the service",
    )
    version: str = Field(default="0.1.0", description="API version")
