"""Unit tests for ForecastBustAgent orchestrator, dependency injection, and short-circuiting."""
from unittest.mock import MagicMock
from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
    ReasonCode,
    RiskLevel,
    TrustState,
)
from backend.app.services.base import (
    BaseFeatureService,
    BaseModelService,
    BaseWeatherService,
    FeatureResult,
    ModelResult,
    WeatherResult,
)
from backend.app.services.feature_service import UnavailableFeatureService
from backend.app.services.model_service import UnavailableModelService
from backend.app.services.weather_service import UnavailableWeatherService


def test_agent_unavailable_state_default():
    """Test that default ForecastBustAgent returns safe unavailable state."""
    agent = ForecastBustAgent()
    request = PredictionRequest(location="London")
    response = agent.analyze(request)

    assert isinstance(response, PredictionResponse)
    assert response.location == "London"
    assert response.bust_probability is None
    assert response.risk_level is None
    assert response.trust_state == TrustState.UNAVAILABLE
    assert response.abstain is True
    assert ReasonCode.MODEL_NOT_READY.value in response.reason_codes
    assert response.model_version is None
    assert response.data_version is None


def test_agent_full_pipeline_mock_injection():
    """Test full sequential pipeline with injected mock weather, feature, and model services."""

    class MockWeatherService(BaseWeatherService):
        def get_forecast(self, location: str, target_date=None) -> WeatherResult:
            return WeatherResult(
                location=location,
                target_date=target_date,
                raw_data={"temp": 18.5, "humidity": 65},
                data_version="gefs-mock-v1",
                is_available=True,
                quality_flags={"qc_passed": True},
            )

    class MockFeatureService(BaseFeatureService):
        def build_features(self, weather_result: WeatherResult) -> FeatureResult:
            return FeatureResult(
                location=weather_result.location,
                features={"ensemble_spread": 1.45, "thermal_gradient": 0.8},
                feature_names=["ensemble_spread", "thermal_gradient"],
                is_ready=True,
            )

    class MockModelService(BaseModelService):
        def predict(self, feature_result: FeatureResult) -> ModelResult:
            return ModelResult(
                probability=0.35,
                model_version="prototype-gbm-v1",
                is_ready=True,
                metadata={"calibration": "isotonic"},
            )

    agent = ForecastBustAgent(
        weather_service=MockWeatherService(),
        feature_service=MockFeatureService(),
        model_service=MockModelService(),
    )
    request = PredictionRequest(location="Tokyo", target_date="2026-09-01")
    response = agent.analyze(request)

    assert response.location == "Tokyo"
    assert response.bust_probability == 0.35
    assert response.risk_level == RiskLevel.MEDIUM
    assert response.trust_state == TrustState.HIGH_CONFIDENCE
    assert response.abstain is False
    assert response.model_version == "prototype-gbm-v1"
    assert response.data_version == "gefs-mock-v1"
    assert ReasonCode.SUCCESS.value in response.reason_codes


def test_agent_weather_unavailable_short_circuits_pipeline():
    """Test that if WeatherService is unavailable, FeatureService and ModelService are NEVER called."""
    mock_weather = MagicMock(spec=BaseWeatherService)
    mock_weather.get_forecast.return_value = WeatherResult(
        location="Paris",
        is_available=False,
        metadata={"status": ReasonCode.DATA_NOT_READY.value},
        error="GEFS feed offline",
    )

    mock_feature = MagicMock(spec=BaseFeatureService)
    mock_model = MagicMock(spec=BaseModelService)

    agent = ForecastBustAgent(
        weather_service=mock_weather,
        feature_service=mock_feature,
        model_service=mock_model,
    )
    response = agent.analyze(PredictionRequest(location="Paris"))

    assert response.abstain is True
    assert response.bust_probability is None
    assert response.trust_state == TrustState.UNAVAILABLE
    assert ReasonCode.DATA_NOT_READY.value in response.reason_codes

    mock_weather.get_forecast.assert_called_once_with("Paris", None)
    mock_feature.build_features.assert_not_called()
    mock_model.predict.assert_not_called()


def test_agent_feature_unavailable_short_circuits_pipeline():
    """Test that if FeatureService fails, ModelService is NEVER called."""
    mock_weather = MagicMock(spec=BaseWeatherService)
    mock_weather.get_forecast.return_value = WeatherResult(
        location="Berlin",
        is_available=True,
        data_version="v1.0",
    )

    mock_feature = MagicMock(spec=BaseFeatureService)
    mock_feature.build_features.return_value = FeatureResult(
        location="Berlin",
        is_ready=False,
        metadata={"status": ReasonCode.FEATURES_NOT_READY.value},
        error="Feature computation failed",
    )

    mock_model = MagicMock(spec=BaseModelService)

    agent = ForecastBustAgent(
        weather_service=mock_weather,
        feature_service=mock_feature,
        model_service=mock_model,
    )
    response = agent.analyze(PredictionRequest(location="Berlin"))

    assert response.abstain is True
    assert response.bust_probability is None
    assert ReasonCode.FEATURES_NOT_READY.value in response.reason_codes

    mock_weather.get_forecast.assert_called_once()
    mock_feature.build_features.assert_called_once()
    mock_model.predict.assert_not_called()


def test_agent_model_unavailable_abstains_safely():
    """Test that if ModelService is unavailable, agent safely abstains with MODEL_NOT_READY."""
    mock_weather = MagicMock(spec=BaseWeatherService)
    mock_weather.get_forecast.return_value = WeatherResult(
        location="Rome",
        is_available=True,
    )

    mock_feature = MagicMock(spec=BaseFeatureService)
    mock_feature.build_features.return_value = FeatureResult(
        location="Rome",
        is_ready=True,
    )

    mock_model = MagicMock(spec=BaseModelService)
    mock_model.predict.return_value = ModelResult(
        probability=None,
        is_ready=False,
        metadata={"status": ReasonCode.MODEL_NOT_READY.value},
    )

    agent = ForecastBustAgent(
        weather_service=mock_weather,
        feature_service=mock_feature,
        model_service=mock_model,
    )
    response = agent.analyze(PredictionRequest(location="Rome"))

    assert response.abstain is True
    assert response.bust_probability is None
    assert ReasonCode.MODEL_NOT_READY.value in response.reason_codes


def test_agent_qc_failed_weather_reason_code():
    """Test that QC check failure in weather data returns QC_FAILED reason code."""
    mock_weather = MagicMock(spec=BaseWeatherService)
    mock_weather.get_forecast.return_value = WeatherResult(
        location="Madrid",
        is_available=False,
        quality_flags={"qc_passed": False},
    )

    agent = ForecastBustAgent(weather_service=mock_weather)
    response = agent.analyze(PredictionRequest(location="Madrid"))

    assert response.abstain is True
    assert ReasonCode.QC_FAILED.value in response.reason_codes


def test_agent_exception_resilience():
    """Test that unexpected service exceptions are safely caught without crashing the agent."""
    mock_weather = MagicMock(spec=BaseWeatherService)
    mock_weather.get_forecast.side_effect = RuntimeError("Network socket timeout")

    agent = ForecastBustAgent(weather_service=mock_weather)
    response = agent.analyze(PredictionRequest(location="Dublin"))

    assert response.abstain is True
    assert response.bust_probability is None
    assert response.trust_state == TrustState.UNAVAILABLE


def test_agent_risk_level_thresholds():
    """Test categorical risk level mapping across probability intervals."""
    from backend.app.safety.abstention import SafetyEvaluator

    evaluator = SafetyEvaluator()
    assert evaluator._map_risk_level(0.05) == RiskLevel.LOW
    assert evaluator._map_risk_level(0.19) == RiskLevel.LOW
    assert evaluator._map_risk_level(0.20) == RiskLevel.MEDIUM
    assert evaluator._map_risk_level(0.49) == RiskLevel.MEDIUM
    assert evaluator._map_risk_level(0.50) == RiskLevel.HIGH
    assert evaluator._map_risk_level(0.74) == RiskLevel.HIGH
    assert evaluator._map_risk_level(0.75) == RiskLevel.CRITICAL
    assert evaluator._map_risk_level(0.99) == RiskLevel.CRITICAL


def test_safety_evaluator_network_error_precedence_over_qc_failed():
    """TEST C: Network/upstream failure with network_error=True and qc_passed=False resolves to DATA_UNAVAILABLE, not QC_FAILED."""
    from backend.app.safety.abstention import SafetyEvaluator

    evaluator = SafetyEvaluator()
    w_result = WeatherResult(
        location="Kolkata",
        is_available=False,
        quality_flags={"qc_passed": False, "network_error": True},
        metadata={"status": ReasonCode.DATA_UNAVAILABLE.value},
        error="HTTP Error 429: Too Many Requests",
    )

    assessment = evaluator.evaluate(weather_result=w_result)
    assert assessment.abstain is True
    assert assessment.trust_state == TrustState.UNAVAILABLE
    assert assessment.bust_probability is None
    assert ReasonCode.DATA_UNAVAILABLE.value in assessment.reason_codes
    assert ReasonCode.QC_FAILED.value not in assessment.reason_codes


def test_safety_evaluator_genuine_qc_failure_produces_qc_failed():
    """TEST D: Genuine meteorological QC failure without network error resolves strictly to QC_FAILED."""
    from backend.app.safety.abstention import SafetyEvaluator

    evaluator = SafetyEvaluator()
    w_result = WeatherResult(
        location="London",
        is_available=False,
        quality_flags={"qc_passed": False, "has_out_of_bounds": True},
        metadata={"status": ReasonCode.QC_FAILED.value, "violations": ["wind_speed_10m exceeds bounds"]},
        error="Quality control checks failed",
    )

    assessment = evaluator.evaluate(weather_result=w_result)
    assert assessment.abstain is True
    assert assessment.trust_state == TrustState.UNAVAILABLE
    assert assessment.bust_probability is None
    assert ReasonCode.QC_FAILED.value in assessment.reason_codes
    assert ReasonCode.DATA_UNAVAILABLE.value not in assessment.reason_codes


def test_safety_evaluator_invalid_location_produces_invalid_location():
    """TEST E: Invalid location query resolves strictly to INVALID_LOCATION."""
    from backend.app.safety.abstention import SafetyEvaluator

    evaluator = SafetyEvaluator()
    w_result = WeatherResult(
        location="Atlantis123",
        is_available=False,
        quality_flags={"invalid_location": True, "qc_passed": False},
        metadata={"status": ReasonCode.INVALID_LOCATION.value},
        error="Location could not be resolved to coordinates",
    )

    assessment = evaluator.evaluate(weather_result=w_result)
    assert assessment.abstain is True
    assert assessment.trust_state == TrustState.UNAVAILABLE
    assert ReasonCode.INVALID_LOCATION.value in assessment.reason_codes
    assert ReasonCode.QC_FAILED.value not in assessment.reason_codes


def test_single_target_and_timeline_safety_parity_under_network_failure():
    """TEST G: Verify Single Target and multi-horizon calls share identical correct DATA_UNAVAILABLE classification."""
    mock_weather = MagicMock(spec=BaseWeatherService)
    mock_weather.get_forecast.return_value = WeatherResult(
        location="Malda",
        is_available=False,
        quality_flags={"qc_passed": False, "network_error": True},
        metadata={"status": ReasonCode.DATA_UNAVAILABLE.value},
        error="HTTP Error 429: Too Many Requests",
    )

    agent = ForecastBustAgent(weather_service=mock_weather)

    # 1. Single Target prediction
    req_single = PredictionRequest(location="Malda", variable="wind_speed_10m", issue_time="2026-08-29T12:30:00Z", valid_time="2026-08-30T12:30:00Z")
    res_single = agent.analyze(req_single)

    assert res_single.abstain is True
    assert ReasonCode.DATA_UNAVAILABLE.value in res_single.reason_codes
    assert ReasonCode.QC_FAILED.value not in res_single.reason_codes

    # 2. Multi-horizon sequence (simulating timeline items)
    for lead in [24, 72, 168, 384]:
        req_lead = PredictionRequest(location="Malda", variable="wind_speed_10m", issue_time="2026-08-29T12:30:00Z", valid_time=f"2026-09-01T12:30:00Z")
        res_lead = agent.analyze(req_lead)
        assert res_lead.abstain is True
        assert ReasonCode.DATA_UNAVAILABLE.value in res_lead.reason_codes
        assert ReasonCode.QC_FAILED.value not in res_lead.reason_codes
