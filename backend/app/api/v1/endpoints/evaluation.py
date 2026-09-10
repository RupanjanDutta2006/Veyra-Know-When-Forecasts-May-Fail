"""Model Evaluation API endpoints for Veyra (Legacy Prototype & V3 Frozen Championship)."""
from typing import Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.schemas.evaluation import (
    ModelEvaluationResponse,
    V3ModelEvaluationResponse,
)
from backend.app.services.evaluation_service import (
    EvaluationIntegrationService,
    SUPPORTED_BASELINE_MODEL_ALIASES,
    SUPPORTED_V3_MODEL_ALIASES,
)

router = APIRouter()

_default_evaluation_service = EvaluationIntegrationService()


def get_evaluation_service() -> EvaluationIntegrationService:
    """Dependency provider for EvaluationIntegrationService."""
    return _default_evaluation_service


KNOWN_LEGACY_ALIASES = {"legacy", "prototype", "prototype-gbm-v1", "day4", "day4_prototype", "builder2_gbm"}


@router.get(
    "/model/evaluation",
    response_model=Union[V3ModelEvaluationResponse, ModelEvaluationResponse],
    summary="Get Model Evaluation & Performance Metrics (Default: Legacy Prototype)",
    description=(
        "Returns model performance, calibration curve data, and evaluation metrics. "
        "IMPORTANT: By default, returns the LEGACY PROTOTYPE EVALUATION ('prototype-gbm-v1') "
        "for backward compatibility. Query ?model=v3 for FROZEN V3 CHAMPIONSHIP EVALUATION "
        "or ?model=legacy for legacy prototype."
    ),
)
async def get_model_evaluation(
    model: Optional[str] = Query(
        default=None,
        description="Optional model identifier ('v3', 'legacy'). Defaults to legacy prototype.",
    ),
    model_name: Optional[str] = Query(
        default=None,
        description="Alias parameter for model selection.",
    ),
    service: EvaluationIntegrationService = Depends(get_evaluation_service),
) -> Union[V3ModelEvaluationResponse, ModelEvaluationResponse]:
    """Retrieve structured model evaluation and verification metrics."""
    target_model = model or model_name
    return service.get_evaluation(model_name=target_model)


@router.get(
    "/model/evaluation/v3",
    response_model=V3ModelEvaluationResponse,
    summary="Get V3 Frozen Championship Evaluation",
    description="Dedicated authoritative endpoint returning certified V3 frozen championship evaluation metrics.",
)
async def get_v3_model_evaluation(
    service: EvaluationIntegrationService = Depends(get_evaluation_service),
) -> V3ModelEvaluationResponse:
    """Retrieve authoritative V3 frozen championship evaluation metrics."""
    return service.get_v3_evaluation()
