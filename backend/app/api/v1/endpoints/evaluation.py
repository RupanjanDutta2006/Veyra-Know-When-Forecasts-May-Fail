"""Model Evaluation API endpoint for Veyra Phase 2 Day 12."""
from typing import Optional
from fastapi import APIRouter, Depends, Query

from backend.app.schemas.evaluation import ModelEvaluationResponse
from backend.app.services.evaluation_service import (
    EvaluationIntegrationService,
)

router = APIRouter()

# Default service instance
_default_evaluation_service = EvaluationIntegrationService()


def get_evaluation_service() -> EvaluationIntegrationService:
    """Dependency provider for EvaluationIntegrationService."""
    return _default_evaluation_service


@router.get(
    "/model/evaluation",
    response_model=ModelEvaluationResponse,
    summary="Get Model Evaluation Metrics",
    description=(
        "Returns validated historical evaluation metrics, test partition performance, "
        "dataset split metadata, and calibration status for the active or requested model."
    ),
)
async def get_model_evaluation(
    model_name: Optional[str] = Query(
        default=None,
        description="Optional model identifier to query specific model evaluation (e.g. 'builder2_gbm', 'baseline_logistic'). Defaults to active model.",
    ),
    service: EvaluationIntegrationService = Depends(get_evaluation_service),
) -> ModelEvaluationResponse:
    """Retrieve structured model evaluation and verification metrics."""
    return service.get_evaluation(model_name=model_name)
