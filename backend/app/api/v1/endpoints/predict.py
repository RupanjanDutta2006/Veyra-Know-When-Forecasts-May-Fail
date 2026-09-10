"""Forecast bust prediction endpoint with centralized model integration layer."""
import os
from typing import Optional
from fastapi import APIRouter, Depends

from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.builder2.feature_adapter import Builder2FeatureAdapter
from backend.app.builder2.v3_feature_adapter import Builder2V3FeatureAdapter
from backend.app.core.config import settings
from backend.app.safety.abstention import SafetyEvaluator
from backend.app.schemas.prediction import PredictionRequest, PredictionResponse
from backend.app.services.explainability_service import ExplainabilityIntegrationService
from backend.app.services.feature_service import LiveFeatureService
from backend.app.services.model_integration_service import ModelIntegrationService
from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService

router = APIRouter()


def create_forecast_bust_agent(
    builder2_model_dir: Optional[str] = None,
    model_integration_service: Optional[ModelIntegrationService] = None,
    explainability_service: Optional[ExplainabilityIntegrationService] = None,
    active_model_key: Optional[str] = None,
) -> ForecastBustAgent:
    """Factory creating ForecastBustAgent with active services based on configuration.

    Integrates Day 11 ModelIntegrationService, Day 13 ExplainabilityIntegrationService,
    and Day 21 Authoritative V3 Model & Feature Adapters.
    """
    if model_integration_service:
        model_svc = model_integration_service
    else:
        active_key = active_model_key or os.getenv("BUILDER2_ACTIVE_MODEL", "builder2_v3")
        model_svc = ModelIntegrationService(
            builder2_model_dir=builder2_model_dir,
            active_model_key=active_key,
        )

    expl_svc = explainability_service or ExplainabilityIntegrationService()

    # Match feature service to active model architecture
    active_info = model_svc.get_active_model_info()
    if active_info.model_name == "builder2_v3":
        feature_svc = Builder2V3FeatureAdapter()
    elif active_info.model_name == "builder2_gbm":
        feature_svc = Builder2FeatureAdapter()
    else:
        feature_svc = LiveFeatureService()

    return ForecastBustAgent(
        weather_service=OpenMeteoGEFSWeatherService(),
        feature_service=feature_svc,
        model_service=model_svc,
        safety_evaluator=SafetyEvaluator(),
        explainability_service=expl_svc,
    )


# Default live production agent using authoritative V3
_default_agent = create_forecast_bust_agent(active_model_key="builder2_v3")


def get_forecast_bust_agent() -> ForecastBustAgent:
    """Dependency provider for ForecastBustAgent."""
    if os.getenv("BUILDER2_ACTIVE_MODEL"):
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
