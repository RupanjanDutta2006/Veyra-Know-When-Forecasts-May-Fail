"""Forecast bust prediction endpoint with centralized model integration layer."""
import os
from typing import Optional
from fastapi import APIRouter, Depends

from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.builder2.feature_adapter import Builder2FeatureAdapter
from backend.app.core.config import settings
from backend.app.safety.abstention import SafetyEvaluator
from backend.app.schemas.prediction import PredictionRequest, PredictionResponse
from backend.app.services.feature_service import LiveFeatureService
from backend.app.services.model_integration_service import ModelIntegrationService
from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService

router = APIRouter()


def create_forecast_bust_agent(
    builder2_model_dir: Optional[str] = None,
    model_integration_service: Optional[ModelIntegrationService] = None,
) -> ForecastBustAgent:
    """Factory creating ForecastBustAgent with active services based on configuration.

    Integrates Day 11 ModelIntegrationService as the single authoritative model gateway.
    """
    model_dir = builder2_model_dir or settings.BUILDER2_MODEL_DIR or os.getenv("BUILDER2_MODEL_DIR")
    model_svc = model_integration_service or ModelIntegrationService(builder2_model_dir=model_dir)

    # Match feature service to active model architecture
    if model_svc.get_active_model_info().model_name == "builder2_gbm":
        feature_svc = Builder2FeatureAdapter()
    else:
        feature_svc = LiveFeatureService()

    return ForecastBustAgent(
        weather_service=OpenMeteoGEFSWeatherService(),
        feature_service=feature_svc,
        model_service=model_svc,
        safety_evaluator=SafetyEvaluator(),
    )


# Default live production agent
_default_agent = create_forecast_bust_agent()


def get_forecast_bust_agent() -> ForecastBustAgent:
    """Dependency provider for ForecastBustAgent."""
    if settings.BUILDER2_MODEL_DIR or os.getenv("BUILDER2_MODEL_DIR"):
        return create_forecast_bust_agent()
    return _default_agent


@router.post(
    "/predict",
    response_model=PredictionResponse,
    summary="Predict Forecast Bust Risk",
    description=(
        "Evaluates the probability and risk of an issued weather forecast failing unusually badly "
        "using real-time GEFS weather ingestion, canonical feature engineering, and the centralized Model Integration Layer."
    ),
)
async def predict_forecast_bust(
    request: PredictionRequest,
    agent: ForecastBustAgent = Depends(get_forecast_bust_agent),
) -> PredictionResponse:
    """Evaluate forecast bust probability."""
    return agent.analyze(request)
