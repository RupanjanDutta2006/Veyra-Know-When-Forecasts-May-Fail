"""Forecast Revision and Trajectory Intelligence API Endpoints for Veyra Phase 3 Day 30."""
from fastapi import APIRouter, Depends

from backend.app.schemas.revision import (
    ForecastRevisionRequest,
    ForecastRevisionResponse,
)
from backend.app.services.revision_service import (
    RevisionService,
    get_revision_service,
)

router = APIRouter()


@router.post(
    "/trajectory",
    response_model=ForecastRevisionResponse,
    summary="Evaluate Forecast Revision & Issue-Cycle Trajectory",
    description=(
        "Evaluates calibrated current V3 P(BUST) and exposes revision diagnostics only when "
        "durable, provider-verified issue-cycle history exists for the exact same target. "
        "Otherwise revision fields remain null with an explicit insufficient-history status."
    ),
)
async def evaluate_forecast_revision(
    request: ForecastRevisionRequest,
    service: RevisionService = Depends(get_revision_service),
) -> ForecastRevisionResponse:
    """Evaluate forecast revision across issue cycles for the requested target."""
    return service.evaluate_revision(request)
