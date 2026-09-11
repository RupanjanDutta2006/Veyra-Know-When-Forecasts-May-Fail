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
    """Factory creating ForecastBustAgent backed exclusively by Authoritative V2 ForecastIntelligenceService."""
    return ForecastBustAgent(
        weather_service=OpenMeteoGEFSWeatherService(),
        feature_service=Builder2FeatureAdapter(),
        model_service=Builder2ModelAdapter(),
        safety_evaluator=SafetyEvaluator(),
    )


# Default live production agent backed by V2 Champion
_default_agent = create_forecast_bust_agent()


def get_forecast_bust_agent() -> ForecastBustAgent:
    """Dependency provider for ForecastBustAgent."""
    return create_forecast_bust_agent()


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
