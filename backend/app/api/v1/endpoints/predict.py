"""Forecast bust prediction endpoint with live model serving."""
import os
from typing import Optional
from fastapi import APIRouter, Depends
from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.builder2.feature_adapter import Builder2FeatureAdapter
from backend.app.builder2.model_adapter import Builder2ModelAdapter
from backend.app.core.config import settings
from backend.app.safety.abstention import SafetyEvaluator
from backend.app.schemas.prediction import PredictionRequest, PredictionResponse
from backend.app.services.feature_service import LiveFeatureService
from backend.app.services.model_service import LiveLogisticModelService
from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService

router = APIRouter()


def create_forecast_bust_agent(
    builder2_model_dir: Optional[str] = None,
) -> ForecastBustAgent:
    """Factory creating ForecastBustAgent with active services based on configuration.

    When BUILDER2_MODEL_DIR is configured, Builder 2 feature and model adapters
    are activated as the primary scientific bust risk pipeline.
    When BUILDER2_MODEL_DIR is unconfigured or unavailable, falls back to the
    standard baseline service or safe abstention.
    """
    model_dir = builder2_model_dir or settings.BUILDER2_MODEL_DIR or os.getenv("BUILDER2_MODEL_DIR")
    if model_dir:
        return ForecastBustAgent(
            weather_service=OpenMeteoGEFSWeatherService(),
            feature_service=Builder2FeatureAdapter(),
            model_service=Builder2ModelAdapter(model_dir=model_dir),
            safety_evaluator=SafetyEvaluator(),
        )
    return ForecastBustAgent(
        weather_service=OpenMeteoGEFSWeatherService(),
        feature_service=LiveFeatureService(),
        model_service=LiveLogisticModelService(),
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
        "using real-time GEFS weather ingestion, leakage-safe feature engineering, and the trained baseline ML model."
    ),
)
async def predict_forecast_bust(
    request: PredictionRequest,
    agent: ForecastBustAgent = Depends(get_forecast_bust_agent),
) -> PredictionResponse:
    """Evaluate forecast bust probability."""
    return agent.analyze(request)
