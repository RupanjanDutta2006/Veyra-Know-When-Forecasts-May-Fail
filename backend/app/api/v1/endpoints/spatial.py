"""Spatial Forecast Reliability API Endpoint for Veyra Phase 3 Day 27.

Provides dedicated multi-location spatial reliability intelligence at POST /v1/spatial/reliability.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Request

from backend.app.schemas.spatial import (
    SpatialReliabilityRequest,
    SpatialReliabilityResponse,
)
from backend.app.services.spatial_service import SpatialReliabilityService

router = APIRouter()

# Default singleton service
_default_spatial_service = SpatialReliabilityService()


def get_spatial_service() -> SpatialReliabilityService:
    """Dependency provider for SpatialReliabilityService."""
    return _default_spatial_service


@router.post(
    "/reliability",
    response_model=SpatialReliabilityResponse,
    summary="Evaluate Spatial Forecast Reliability",
    description=(
        "Evaluates discrete spatial forecast reliability intelligence across multiple locations "
        "using authoritative V3 calibrated inference. Preserves exact 1:1 input ordering, deduplicates "
        "redundant remote queries, provides per-location failure isolation, and separates frozen benchmark "
        "lead scope (<=240h) from extended operational horizons (264h-384h). Does NOT interpolate or "
        "fabricate continuous surfaces."
    ),
    response_description="Discrete spatial forecast reliability evaluation with summary metrics",
)
async def evaluate_spatial_reliability(
    request: SpatialReliabilityRequest,
    http_request: Request,
    service: SpatialReliabilityService = Depends(get_spatial_service),
) -> SpatialReliabilityResponse:
    """Evaluate and return spatial forecast reliability across discrete locations."""
    request_id = getattr(http_request.state, "request_id", None)
    if not request_id:
        request_id = (
            http_request.headers.get("x-request-id")
            or http_request.headers.get("X-Request-ID")
        )

    return service.evaluate_spatial(request, request_id=request_id)
