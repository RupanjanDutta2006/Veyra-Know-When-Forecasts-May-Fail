"""Unit tests for Service Interfaces, Typed Results, and Safety Evaluation."""
from backend.app.safety.abstention import SafetyAssessment, SafetyEvaluator
from backend.app.schemas.prediction import (
    ReasonCode,
    RiskLevel,
    TrustState,
)
from backend.app.services.base import (
    FeatureResult,
    ModelResult,
    WeatherResult,
)
from backend.app.services.feature_service import UnavailableFeatureService
from backend.app.services.model_service import UnavailableModelService
from backend.app.services.weather_service import UnavailableWeatherService


def test_unavailable_weather_service_contract():
    """Test UnavailableWeatherService returns safe unavailable container."""
    service = UnavailableWeatherService(data_version="gefs-v0.1")
    result = service.get_forecast(location="Madrid", target_date="2026-09-01")

    assert isinstance(result, WeatherResult)
    assert result.location == "Madrid"
    assert result.target_date == "2026-09-01"
    assert result.is_available is False
    assert result.raw_data == {}
    assert result.data_version == "gefs-v0.1"

    # Backward compatibility alias test
    alias_result = service.fetch_forecast_data("Madrid", "2026-09-01")
    assert alias_result.location == "Madrid"


def test_unavailable_feature_service_contract():
    """Test UnavailableFeatureService returns safe unavailable feature container."""
    service = UnavailableFeatureService()
    weather_data = WeatherResult(location="Rome", is_available=False)
    result = service.build_features(weather_data)

    assert isinstance(result, FeatureResult)
    assert result.location == "Rome"
    assert result.is_ready is False
    assert result.features == {}

    # Backward compatibility alias test
    alias_result = service.extract_features(weather_data)
    assert alias_result.location == "Rome"


def test_unavailable_model_service_contract():
    """Test UnavailableModelService returns null probability without hallucinating values."""
    service = UnavailableModelService(model_version="stub-v0")
    feature_result = FeatureResult(location="Berlin", is_ready=False)
    result = service.predict(feature_result)

    assert isinstance(result, ModelResult)
    assert result.probability is None
    assert result.is_ready is False
    assert result.model_version == "stub-v0"


def test_safety_evaluator_abstains_on_weather_failure():
    """Test that safety evaluator returns DATA_NOT_READY when weather data fails."""
    evaluator = SafetyEvaluator()
    weather = WeatherResult(
        location="Oslo",
        is_available=False,
        error="Connection lost",
    )
    assessment = evaluator.evaluate(weather_result=weather)

    assert isinstance(assessment, SafetyAssessment)
    assert assessment.abstain is True
    assert assessment.bust_probability is None
    assert assessment.trust_state == TrustState.UNAVAILABLE
    assert ReasonCode.DATA_NOT_READY.value in assessment.reason_codes


def test_safety_evaluator_abstains_on_feature_failure():
    """Test that safety evaluator returns FEATURES_NOT_READY when features fail."""
    evaluator = SafetyEvaluator()
    weather = WeatherResult(location="Vienna", is_available=True)
    features = FeatureResult(location="Vienna", is_ready=False, error="Feature transform error")
    assessment = evaluator.evaluate(weather_result=weather, feature_result=features)

    assert assessment.abstain is True
    assert assessment.bust_probability is None
    assert ReasonCode.FEATURES_NOT_READY.value in assessment.reason_codes


def test_safety_evaluator_abstains_on_model_unready():
    """Test that safety evaluator returns MODEL_NOT_READY when model is unready."""
    evaluator = SafetyEvaluator()
    weather = WeatherResult(location="Prague", is_available=True)
    features = FeatureResult(location="Prague", is_ready=True)
    model = ModelResult(probability=None, is_ready=False)
    assessment = evaluator.evaluate(
        weather_result=weather,
        feature_result=features,
        model_result=model,
    )

    assert assessment.abstain is True
    assert assessment.bust_probability is None
    assert ReasonCode.MODEL_NOT_READY.value in assessment.reason_codes


def test_safety_evaluator_handles_out_of_bounds_probability():
    """Test that probabilities outside [0, 1] cause safe abstention with QC_FAILED."""
    evaluator = SafetyEvaluator()
    weather = WeatherResult(location="Athens", is_available=True)
    features = FeatureResult(location="Athens", is_ready=True)
    invalid_model = ModelResult(probability=1.45, is_ready=True)

    assessment = evaluator.evaluate(
        weather_result=weather,
        feature_result=features,
        model_result=invalid_model,
    )

    assert assessment.abstain is True
    assert assessment.bust_probability is None
    assert assessment.trust_state == TrustState.ABSTAINED
    assert ReasonCode.QC_FAILED.value in assessment.reason_codes


def test_safety_evaluator_create_error_assessment():
    """Test failsafe error assessment factory."""
    assessment = SafetyEvaluator.create_error_assessment(
        reason_code=ReasonCode.INTERNAL_ERROR,
        error_message="Database lock timeout",
    )
    assert assessment.abstain is True
    assert assessment.bust_probability is None
    assert assessment.trust_state == TrustState.UNAVAILABLE
    assert ReasonCode.INTERNAL_ERROR.value in assessment.reason_codes
