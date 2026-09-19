"""Forecast Disagreement Intelligence API Endpoints for Veyra Phase 3 Day 29."""
from fastapi import APIRouter, Depends

from backend.app.schemas.disagreement import (
    ForecastDisagreementRequest,
    ForecastDisagreementResponse,
)
from backend.app.services.disagreement_service import (
    DisagreementService,
    get_disagreement_service,
)

router = APIRouter()


@router.post(
    "/diagnostics",
    response_model=ForecastDisagreementResponse,
    summary="Evaluate Forecast Disagreement & Ensemble Dispersion",
    description=(
        "Evaluates real ensemble dispersion metrics (spread, range, IQR, CV) derived from "
        "authoritative NOAA GEFS ensemble forecast members alongside calibrated V3 P(BUST) "
        "without conflating disagreement with failure risk."
    ),
)
async def evaluate_forecast_disagreement(
    request: ForecastDisagreementRequest,
    service: DisagreementService = Depends(get_disagreement_service),
) -> ForecastDisagreementResponse:
    """Evaluate ensemble disagreement diagnostics for the requested location and horizon."""
    return service.evaluate_disagreement(request)
