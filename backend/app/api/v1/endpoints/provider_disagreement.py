"""Cross-Provider Disagreement Intelligence API Endpoints for Veyra Phase 3 Day 38 (Gate C8)."""

from fastapi import APIRouter, Depends

from backend.app.schemas.provider_disagreement import (
    CrossProviderDisagreementRequest,
    CrossProviderDisagreementResponse,
)
from backend.app.services.provider_disagreement_service import (
    CrossProviderDisagreementService,
    get_cross_provider_disagreement_service,
)

router = APIRouter()


@router.post(
    "/diagnostics",
    response_model=CrossProviderDisagreementResponse,
    summary="Evaluate Cross-Provider Forecast Divergence Diagnostics",
    description=(
        "Evaluates forecast divergence between normalized multi-provider forecast outputs "
        "for the same location, variable, and time horizon. Kept strictly distinct from "
        "GEFS ensemble member dispersion and calibrated P(BUST) risk estimation."
    ),
)
async def evaluate_cross_provider_disagreement(
    request: CrossProviderDisagreementRequest,
    service: CrossProviderDisagreementService = Depends(get_cross_provider_disagreement_service),
) -> CrossProviderDisagreementResponse:
    """Evaluate cross-provider forecast divergence diagnostics."""
    return service.evaluate_disagreement(request)
