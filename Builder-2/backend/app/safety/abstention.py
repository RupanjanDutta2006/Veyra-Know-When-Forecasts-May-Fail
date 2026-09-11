"""Safety, OOD Detection, and Abstention Layer."""
from dataclasses import dataclass, field
from typing import Any, Optional
from backend.app.schemas.prediction import ReasonCode, RiskLevel, TrustState
from backend.app.services.base import (
    BaseSafetyService,
    FeatureResult,
    ModelResult,
    WeatherResult,
)


@dataclass
class SafetyAssessment:
    """Standard safety evaluation output controlling final trust state and abstention."""

    bust_probability: Optional[float] = None
    risk_level: Optional[RiskLevel] = None
    trust_state: TrustState = TrustState.UNAVAILABLE
    abstain: bool = True
    reason_codes: list[str] = field(
        default_factory=lambda: [ReasonCode.MODEL_NOT_READY.value]
    )
    metadata: dict[str, Any] = field(default_factory=dict)


# Alias for consistency
SafetyResult = SafetyAssessment


class SafetyEvaluator(BaseSafetyService):
    """Evaluates data validity, ML model availability, and safety criteria to decide on abstention."""

    def evaluate(
        self,
        weather_result: Optional[WeatherResult] = None,
        feature_result: Optional[FeatureResult] = None,
        model_result: Optional[ModelResult] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> SafetyAssessment:
        """Perform safety evaluation across all pipeline stages.

        If any upstream dependency (weather data, features, or model) is unavailable or unready,
        safely ABSTAIN with trust_state=UNAVAILABLE, bust_probability=None, and appropriate reason codes.
        """
        # 1. Weather Data Stage Check
        if weather_result is not None:
            if not weather_result.is_available or weather_result.error:
                if weather_result.quality_flags and weather_result.quality_flags.get("invalid_location"):
                    reason = ReasonCode.INVALID_LOCATION.value
                elif weather_result.quality_flags and weather_result.quality_flags.get("qc_passed") is False:
                    reason = ReasonCode.QC_FAILED.value
                elif weather_result.metadata and "status" in weather_result.metadata:
                    reason = weather_result.metadata["status"]
                else:
                    reason = ReasonCode.DATA_NOT_READY.value

                return SafetyAssessment(
                    bust_probability=None,
                    risk_level=None,
                    trust_state=TrustState.UNAVAILABLE,
                    abstain=True,
                    reason_codes=[reason],
                    metadata={"error": weather_result.error} if weather_result.error else {},
                )


        # 2. Feature Pipeline Stage Check
        if feature_result is not None:
            if not feature_result.is_ready or feature_result.error:
                if feature_result.metadata and "status" in feature_result.metadata:
                    reason = feature_result.metadata["status"]
                else:
                    reason = ReasonCode.FEATURES_NOT_READY.value

                return SafetyAssessment(
                    bust_probability=None,
                    risk_level=None,
                    trust_state=TrustState.UNAVAILABLE,
                    abstain=True,
                    reason_codes=[reason],
                    metadata={"error": feature_result.error} if feature_result.error else {},
                )

        # 3. Model Inference Stage Check
        if model_result is None or not model_result.is_ready or model_result.probability is None:
            reason = (
                model_result.metadata.get("status", ReasonCode.MODEL_NOT_READY.value)
                if (model_result and model_result.metadata)
                else ReasonCode.MODEL_NOT_READY.value
            )
            return SafetyAssessment(
                bust_probability=None,
                risk_level=None,
                trust_state=TrustState.UNAVAILABLE,
                abstain=True,
                reason_codes=[reason],
                metadata={"error": model_result.error} if (model_result and model_result.error) else {},
            )

        # 4. Valid Model Result Evaluation
        probability = model_result.probability

        # Boundary check
        if not (0.0 <= probability <= 1.0):
            return SafetyAssessment(
                bust_probability=None,
                risk_level=None,
                trust_state=TrustState.ABSTAINED,
                abstain=True,
                reason_codes=[ReasonCode.QC_FAILED.value],
                metadata={"error": f"Invalid probability out of bounds: {probability}"},
            )

        # Map categorical risk level
        risk_level = self._map_risk_level(probability)

        # Default confident prediction (future OOD evaluation will plug in here)
        return SafetyAssessment(
            bust_probability=probability,
            risk_level=risk_level,
            trust_state=TrustState.HIGH_CONFIDENCE,
            abstain=False,
            reason_codes=[ReasonCode.SUCCESS.value],
            metadata=model_result.metadata,
        )

    @staticmethod
    def create_error_assessment(
        reason_code: ReasonCode = ReasonCode.INTERNAL_ERROR,
        error_message: Optional[str] = None,
    ) -> SafetyAssessment:
        """Construct a failsafe abstention response for unexpected errors."""
        return SafetyAssessment(
            bust_probability=None,
            risk_level=None,
            trust_state=TrustState.UNAVAILABLE,
            abstain=True,
            reason_codes=[reason_code.value],
            metadata={"error": error_message} if error_message else {},
        )

    @staticmethod
    def _map_risk_level(prob: float) -> RiskLevel:
        """Map a calibrated probability to a categorical risk level."""
        if prob < 0.20:
            return RiskLevel.LOW
        elif prob < 0.50:
            return RiskLevel.MEDIUM
        elif prob < 0.75:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL
