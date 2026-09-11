"""ForecastBustAgent Orchestration Layer.

Orchestrates the sequential pipeline:
Request -> Weather Data -> Feature Pipeline -> ML Model -> Safety/Abstention -> Response

Designed with strict Dependency Injection and Fail-Safe Short-Circuiting.
"""
import logging
from typing import Optional
from backend.app.safety.abstention import SafetyAssessment, SafetyEvaluator
from backend.app.schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
    ReasonCode,
)
from backend.app.services.base import (
    BaseFeatureService,
    BaseModelService,
    BaseSafetyService,
    BaseWeatherService,
    FeatureResult,
    ModelResult,
    WeatherResult,
)
from backend.app.services.feature_service import UnavailableFeatureService
from backend.app.services.model_service import UnavailableModelService
from backend.app.services.weather_service import UnavailableWeatherService

logger = logging.getLogger(__name__)


class ForecastBustAgent:
    """Orchestration agent coordinating modular services to evaluate forecast bust risk.

    Acts strictly as an orchestrator — delegates weather ingestion, feature extraction,
    model inference, and safety evaluation to independent injected services.
    """

    def __init__(
        self,
        weather_service: Optional[BaseWeatherService] = None,
        feature_service: Optional[BaseFeatureService] = None,
        model_service: Optional[BaseModelService] = None,
        safety_service: Optional[BaseSafetyService] = None,
        safety_evaluator: Optional[SafetyEvaluator] = None,
    ):
        self.weather_service = weather_service or UnavailableWeatherService()
        self.feature_service = feature_service or UnavailableFeatureService()
        self.model_service = model_service or UnavailableModelService()
        self.safety_service = safety_service or safety_evaluator or SafetyEvaluator()

    def resolve_request(self, request: PredictionRequest) -> tuple[str, Optional[str]]:
        """Validate and resolve location and target date parameters."""
        return request.location.strip(), request.target_date

    def get_weather_data(
        self, location: str, target_date: Optional[str]
    ) -> WeatherResult:
        """Fetch weather and atmospheric forecast data from injected weather service."""
        try:
            return self.weather_service.get_forecast(location, target_date)
        except Exception as exc:
            logger.error("WeatherService raised an unexpected error: %s", exc)
            return WeatherResult(
                location=location,
                target_date=target_date,
                is_available=False,
                error=f"WeatherService error: {exc}",
            )

    def get_features(self, weather_result: WeatherResult) -> FeatureResult:
        """Extract engineered features from weather data via injected feature service."""
        try:
            return self.feature_service.build_features(weather_result)
        except Exception as exc:
            logger.error("FeatureService raised an unexpected error: %s", exc)
            return FeatureResult(
                location=weather_result.location,
                is_ready=False,
                error=f"FeatureService error: {exc}",
            )

    def run_model(self, feature_result: FeatureResult) -> ModelResult:
        """Execute ML model inference via injected model service."""
        try:
            return self.model_service.predict(feature_result)
        except Exception as exc:
            logger.error("ModelService raised an unexpected error: %s", exc)
            return ModelResult(
                is_ready=False,
                probability=None,
                error=f"ModelService error: {exc}",
            )

    def apply_safety(
        self,
        weather_result: Optional[WeatherResult] = None,
        feature_result: Optional[FeatureResult] = None,
        model_result: Optional[ModelResult] = None,
    ) -> SafetyAssessment:
        """Evaluate safety, OOD, and abstention criteria via injected safety service."""
        try:
            return self.safety_service.evaluate(
                weather_result=weather_result,
                feature_result=feature_result,
                model_result=model_result,
            )
        except Exception as exc:
            logger.error("SafetyService raised an unexpected error: %s", exc)
            return SafetyEvaluator.create_error_assessment(
                reason_code=ReasonCode.INTERNAL_ERROR,
                error_message="Safety evaluation encountered an internal error",
            )

    def build_response(
        self,
        location: str,
        safety_assessment: SafetyAssessment,
        model_result: Optional[ModelResult] = None,
        weather_result: Optional[WeatherResult] = None,
    ) -> PredictionResponse:
        """Construct the standardized API response payload preserving authoritative V2 fields."""
        m_meta = model_result.metadata if (model_result and model_result.metadata) else {}

        if safety_assessment.abstain or model_result is None or not model_result.is_ready:
            confidence_index = None
            uncertainty_pct = None
            ood_distance = None
            revision = None
            stability = None
            structural_overconfidence = None
            failure_fingerprint = None
            dominant_risk_drivers = None
            decision_mode = None
            within_trust_horizon = None
            operational_trust_horizon_hours = None
        else:
            confidence_index = m_meta.get("confidence_index")
            uncertainty_pct = m_meta.get("uncertainty_pct")
            ood_distance = m_meta.get("ood_score") if m_meta.get("ood_score") is not None else m_meta.get("ood_distance")
            revision = m_meta.get("revision")
            stability = m_meta.get("stability_index") if m_meta.get("stability_index") is not None else m_meta.get("stability")
            structural_overconfidence = m_meta.get("structural_overconfidence")
            failure_fingerprint = m_meta.get("failure_fingerprint")
            dominant_risk_drivers = m_meta.get("dominant_risk_drivers")
            decision_mode = m_meta.get("decision_mode")
            within_trust_horizon = m_meta.get("within_trust_horizon")
            operational_trust_horizon_hours = m_meta.get("operational_trust_horizon_hours")

        return PredictionResponse(
            location=location,
            bust_probability=safety_assessment.bust_probability,
            risk_level=safety_assessment.risk_level,
            trust_state=safety_assessment.trust_state,
            confidence_index=confidence_index,
            uncertainty_pct=uncertainty_pct,
            ood_distance=ood_distance,
            revision=revision,
            stability=stability,
            structural_overconfidence=structural_overconfidence,
            failure_fingerprint=failure_fingerprint,
            dominant_risk_drivers=dominant_risk_drivers,
            decision_mode=decision_mode,
            within_trust_horizon=within_trust_horizon,
            operational_trust_horizon_hours=operational_trust_horizon_hours,
            model_version=model_result.model_version if model_result else None,
            data_version=weather_result.data_version if weather_result else None,
            abstain=safety_assessment.abstain,
            reason_codes=safety_assessment.reason_codes,
        )

    def analyze(self, request: PredictionRequest) -> PredictionResponse:
        """Main entry point orchestrating the end-to-end evaluation pipeline.

        Short-circuits safely whenever a dependency is unavailable:
        - Weather unavailable -> abstains without calling Feature or Model service.
        - Features unavailable -> abstains without calling Model service.
        - Model unavailable -> abstains without fabricating fake probabilities.
        """
        try:
            # 1. Resolve request
            location, target_date = self.resolve_request(request)

            # 2. Weather Data Collection Stage
            weather_result = self.get_weather_data(location, target_date)
            if not weather_result.is_available or weather_result.error:
                safety_assessment = self.apply_safety(weather_result=weather_result)
                return self.build_response(
                    location=location,
                    safety_assessment=safety_assessment,
                    weather_result=weather_result,
                )

            # 3. Feature Engineering Stage
            feature_result = self.get_features(weather_result)
            if not feature_result.is_ready or feature_result.error:
                safety_assessment = self.apply_safety(
                    weather_result=weather_result,
                    feature_result=feature_result,
                )
                return self.build_response(
                    location=location,
                    safety_assessment=safety_assessment,
                    weather_result=weather_result,
                )

            # 4. ML Model Prediction Stage
            model_result = self.run_model(feature_result)
            if not model_result.is_ready or model_result.probability is None or model_result.error:
                safety_assessment = self.apply_safety(
                    weather_result=weather_result,
                    feature_result=feature_result,
                    model_result=model_result,
                )
                return self.build_response(
                    location=location,
                    safety_assessment=safety_assessment,
                    model_result=model_result,
                    weather_result=weather_result,
                )

            # 5. Safety & Abstention Evaluation on Model Prediction
            safety_assessment = self.apply_safety(
                weather_result=weather_result,
                feature_result=feature_result,
                model_result=model_result,
            )

            # 6. Response Construction
            return self.build_response(
                location=location,
                safety_assessment=safety_assessment,
                model_result=model_result,
                weather_result=weather_result,
            )

        except Exception as exc:
            logger.error("Unhandled error during ForecastBustAgent.analyze: %s", exc)
            fallback_assessment = SafetyEvaluator.create_error_assessment(
                reason_code=ReasonCode.INTERNAL_ERROR,
                error_message="Sentinel service encountered an unexpected error",
            )
            return self.build_response(
                location=request.location if request else "UNKNOWN",
                safety_assessment=fallback_assessment,
            )
