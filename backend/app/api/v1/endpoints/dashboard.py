"""Dashboard Intelligence API Endpoint for Veyra Phase 3 Day 25.

Provides unified, dashboard-ready intelligence orchestration at POST /v1/dashboard/intelligence.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Request

from backend.app.schemas.dashboard import (
    DashboardIntelligenceResponse,
    DashboardRequest,
)
from backend.app.services.dashboard_service import DashboardIntelligenceService

router = APIRouter()

# Default singleton service
_default_dashboard_service = DashboardIntelligenceService()


def get_dashboard_service() -> DashboardIntelligenceService:
    """Dependency provider for DashboardIntelligenceService."""
    return _default_dashboard_service


@router.post(
    "/intelligence",
    response_model=DashboardIntelligenceResponse,
    summary="Dashboard Intelligence Orchestration",
    description=(
        "Returns a unified, dashboard-ready intelligence payload containing resolved location context, "
        "canonical 24h prediction, multi-horizon risk timeline (single, standard 7-day, or full 16-day), "
        "deterministic summary metrics, peak risk indicators, and certified scientific provenance. "
        "Eliminates client-side timeline orchestration and repeated upstream requests."
    ),
    response_description="Unified dashboard intelligence response with timeline and summary",
)
async def get_dashboard_intelligence(
    request: DashboardRequest,
    http_request: Request,
    service: DashboardIntelligenceService = Depends(get_dashboard_service),
) -> DashboardIntelligenceResponse:
    """Orchestrate and return complete dashboard intelligence."""
    request_id = getattr(http_request.state, "request_id", None)
    if not request_id:
        request_id = http_request.headers.get("x-request-id") or http_request.headers.get("X-Request-ID")

    return service.orchestrate(request, request_id=request_id)
