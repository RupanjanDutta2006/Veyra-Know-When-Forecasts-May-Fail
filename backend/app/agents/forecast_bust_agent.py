"""ForecastBustAgent Orchestration Layer.

Orchestrates the sequential pipeline:
Request -> Weather Data -> Feature Pipeline -> ML Model -> Safety/Abstention -> Response

Designed with strict Dependency Injection and Fail-Safe Short-Circuiting.
"""
import logging
import time
from typing import Optional
from backend.app.core.metrics import default_metrics
from backend.app.safety.abstention import SafetyAssessment, SafetyEvaluator
from backend.app.schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
    ReasonCode,
    RiskLevel,
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
from backend.app.services.explainability_service import (
    BaseExplainabilityService,
    ExplainabilityIntegrationService,
)
from backend.app.services.feature_service import UnavailableFeatureService
from backend.app.services.model_service import UnavailableModelService
from backend.app.services.weather_service import UnavailableWeatherService

logger = logging.getLogger(__name__)


class ForecastBustAgent:
    """Orchestration agent coordinating modular services to evaluate forecast bust risk.

    Acts strictly as an orchestrator — delegates weather ingestion, feature extraction,
    model inference, explainability integration, and safety evaluation to independent injected services.
    """

    def __init__(
        self,
        weather_service: Optional[BaseWeatherService] = None,
        feature_service: Optional[BaseFeatureService] = None,
        model_service: Optional[BaseModelService] = None,
        safety_service: Optional[BaseSafetyService] = None,
        safety_evaluator: Optional[SafetyEvaluator] = None,
        explainability_service: Optional[BaseExplainabilityService] = None,
    ):
        self.weather_service = weather_service or UnavailableWeatherService()
        self.feature_service = feature_service or UnavailableFeatureService()
        self.model_service = model_service or UnavailableModelService()
        self.safety_service = safety_service or safety_evaluator or SafetyEvaluator()
        self.explainability_service = explainability_service or ExplainabilityIntegrationService()

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
        feature_result: Optional[FeatureResult] = None,
    ) -> PredictionResponse:
        """Construct the standardized API response payload."""
        explanation = None
        if not safety_assessment.abstain and model_result and model_result.is_ready and model_result.probability is not None:
            raw_expl = model_result.metadata.get("explanation") if model_result.metadata else None
            if raw_expl is not None:
                explanation = self.explainability_service.validate_explanation(raw_expl)
            elif feature_result and feature_result.features:
                explanation = self.explainability_service.explain(
                    feature_row=feature_result.features,
                    bust_probability=safety_assessment.bust_probability,
                    threshold=getattr(model_result, "threshold", 0.280),
                    is_abstained=safety_assessment.abstain,
                )

        # Extract Builder 2 advanced intelligence metadata
        model_meta = model_result.metadata if (model_result and model_result.metadata) else {}
        feat_meta = feature_result.metadata if (feature_result and feature_result.metadata) else {}

        # 1. Failure / Instability Fingerprint
        fingerprint = model_meta.get("instability_fingerprint") or feat_meta.get("instability_fingerprint")

        # 2. Dominant risk drivers from explanation
        dominant_drivers = None
        if explanation is not None:
            drivers: list[str] = []
            if getattr(explanation, "primary_driver", None):
                drivers.append(explanation.primary_driver)
            factors = getattr(explanation, "top_contributing_factors", [])
            for f in factors:
                factor_name = getattr(f, "factor", None) or (f.get("factor") if isinstance(f, dict) else None)
                if factor_name and factor_name not in drivers:
                    drivers.append(factor_name)
            if drivers:
                dominant_drivers = drivers

        # 3. Decision Mode and Guidance
        if safety_assessment.abstain:
            decision_mode = "ABSTAINED"
            decision_guidance = "Model safely abstained due to data/QC or OOD limits. Revert to raw NWP ensemble."
        elif safety_assessment.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
            decision_mode = "ACTIVE_ALERT"
            decision_guidance = "Elevated forecast failure risk detected. High probability of model divergence; prepare contingency plans."
        elif safety_assessment.risk_level == RiskLevel.MEDIUM:
            decision_mode = "ELEVATED_RISK"
            decision_guidance = "Moderate forecast failure risk. Monitor upcoming ensemble revision cycles."
        else:
            decision_mode = "STANDARD_MONITORING"
            decision_guidance = "Forecast within nominal stability bounds. Low bust probability; standard operations recommended."

        # 4. Operational Trust Horizon (120 hours default for medium-range GFS/GEFS)
        op_trust_horizon = 120
        within_trust_h = None
        if feature_result and feature_result.features:
            lead_h = feature_result.features.get("lead_hours")
            if lead_h is not None:
                within_trust_h = bool(lead_h <= op_trust_horizon)

        # 5. Uncertainty and Confidence Index
        conf_index = None
        uncert_pct = None
        if not safety_assessment.abstain and safety_assessment.bust_probability is not None:
            prob = safety_assessment.bust_probability
            uncert_pct = round(min(100.0, max(0.0, (1.0 - abs(prob - 0.5) * 2) * 100)), 1)
            conf_index = round(max(0.0, min(1.0, 1.0 - (uncert_pct / 100.0))), 3)

        # 6. Structural Overconfidence & Stability from fingerprint
        struct_overconf = None
        stab_index = None
        if fingerprint and isinstance(fingerprint, dict):
            struct_overconf = fingerprint.get("structural_overconfidence", False)
            traj_data = fingerprint.get("revision_instability", {})
            if isinstance(traj_data, dict):
                mag6 = traj_data.get("magnitude_6h")
                if mag6 is not None:
                    try:
                        stab_index = round(max(0.0, 1.0 / (1.0 + float(mag6))), 3)
                    except (ValueError, TypeError, ZeroDivisionError):
                        stab_index = None

        # 7. OOD Score
        ood_score = model_meta.get("ood_score") or feat_meta.get("ood_distance")

        return PredictionResponse(
            location=location,
            bust_probability=safety_assessment.bust_probability,
            risk_level=safety_assessment.risk_level,
            trust_state=safety_assessment.trust_state,
            abstain=safety_assessment.abstain,
            reason_codes=safety_assessment.reason_codes,
            model_version=model_result.model_version if model_result else None,
            data_version=weather_result.data_version if weather_result else None,
            explanation=explanation,
            confidence_index=conf_index,
            uncertainty_pct=uncert_pct,
            ood_score=ood_score,
            stability_index=stab_index,
            structural_overconfidence=struct_overconf,
            failure_fingerprint=fingerprint,
            dominant_risk_drivers=dominant_drivers,
            decision_mode=decision_mode,
            decision_guidance=decision_guidance,
            within_trust_horizon=within_trust_h,
            operational_trust_horizon_hours=op_trust_horizon,
        )

    def analyze(self, request: PredictionRequest) -> PredictionResponse:
        """Main entry point orchestrating the end-to-end evaluation pipeline with operational telemetry.

        Short-circuits safely whenever a dependency is unavailable:
        - Weather unavailable -> abstains without calling Feature or Model service.
        - Features unavailable -> abstains without calling Model service.
        - Model unavailable -> abstains without fabricating fake probabilities.
        """
        start_t = time.perf_counter()
        try:
            # 1. Resolve request
            location, target_date = self.resolve_request(request)

            # 2. Weather Data Collection Stage
            weather_result = self.get_weather_data(location, target_date)
            if not weather_result.is_available or weather_result.error:
                safety_assessment = self.apply_safety(weather_result=weather_result)
                resp = self.build_response(
                    location=location,
                    safety_assessment=safety_assessment,
                    weather_result=weather_result,
                )
                self._record_pipeline_telemetry(resp, request, start_t)
                return resp

            # Propagate target forecast parameters into metadata for downstream feature selection
            if request.valid_time:
                weather_result.metadata["valid_time"] = request.valid_time
            if request.issue_time:
                weather_result.metadata["issue_time"] = request.issue_time
            if request.variable:
                weather_result.metadata["variable"] = request.variable
            if request.target_date:
                weather_result.metadata["target_date"] = request.target_date

            # 3. Feature Engineering Stage
            feature_result = self.get_features(weather_result)
            if not feature_result.is_ready or feature_result.error:
                safety_assessment = self.apply_safety(
                    weather_result=weather_result,
                    feature_result=feature_result,
                )
                resp = self.build_response(
                    location=location,
                    safety_assessment=safety_assessment,
                    weather_result=weather_result,
                    feature_result=feature_result,
                )
                self._record_pipeline_telemetry(resp, request, start_t)
                return resp

            # 4. ML Model Prediction Stage
            model_result = self.run_model(feature_result)
            if not model_result.is_ready or model_result.probability is None or model_result.error:
                safety_assessment = self.apply_safety(
                    weather_result=weather_result,
                    feature_result=feature_result,
                    model_result=model_result,
                )
                resp = self.build_response(
                    location=location,
                    safety_assessment=safety_assessment,
                    model_result=model_result,
                    weather_result=weather_result,
                    feature_result=feature_result,
                )
                self._record_pipeline_telemetry(resp, request, start_t)
                return resp

            # 5. Safety & Abstention Evaluation on Model Prediction
            safety_assessment = self.apply_safety(
                weather_result=weather_result,
                feature_result=feature_result,
                model_result=model_result,
            )

            # 6. Response Construction
            resp = self.build_response(
                location=location,
                safety_assessment=safety_assessment,
                model_result=model_result,
                weather_result=weather_result,
                feature_result=feature_result,
            )
            self._record_pipeline_telemetry(resp, request, start_t)
            return resp

        except Exception as exc:
            logger.error("Unhandled error during ForecastBustAgent.analyze: %s", exc)
            fallback_assessment = SafetyEvaluator.create_error_assessment(
                reason_code=ReasonCode.INTERNAL_ERROR,
                error_message="Sentinel service encountered an unexpected error",
            )
            resp = self.build_response(
                location=request.location if request else "UNKNOWN",
                safety_assessment=fallback_assessment,
            )
            self._record_pipeline_telemetry(resp, request, start_t)
            return resp

    def _record_pipeline_telemetry(
        self,
        response: PredictionResponse,
        request: Optional[PredictionRequest],
        start_time_perf: float,
    ) -> None:
        """Record operational metrics and structured operational log for prediction event."""
        duration_ms = round((time.perf_counter() - start_time_perf) * 1000, 2)
        model_ver = response.model_version or "unknown"
        var_name = request.variable if request and request.variable else "temperature_2m"

        if response.abstain:
            reason_raw = response.reason_codes[0] if response.reason_codes else "UNKNOWN_ABSTENTION"
            reason = getattr(reason_raw, "value", str(reason_raw))
            default_metrics.record_prediction(outcome="ABSTAINED", risk_level="NONE", model_version=model_ver)
            default_metrics.record_abstention(reason_code=reason)
            logger.info(
                "event=prediction_abstained model=%s variable=%s reason=%s duration_ms=%.2f",
                model_ver,
                var_name,
                reason,
                duration_ms,
            )
        else:
            risk = getattr(response.risk_level, "value", str(response.risk_level)) if response.risk_level else "UNKNOWN"
            default_metrics.record_prediction(outcome="COMPLETED", risk_level=risk, model_version=model_ver)
            logger.info(
                "event=prediction_completed model=%s variable=%s risk=%s duration_ms=%.2f",
                model_ver,
                var_name,
                risk,
                duration_ms,
            )
