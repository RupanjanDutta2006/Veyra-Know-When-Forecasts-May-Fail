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
    assert response.risk_level == RiskLevel.ELEVATED
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
    """Test categorical risk level mapping across calibrated probability intervals."""
    from backend.app.safety.abstention import SafetyEvaluator

    evaluator = SafetyEvaluator()
    assert evaluator._map_risk_level(0.00) == RiskLevel.LOW
    assert evaluator._map_risk_level(0.059) == RiskLevel.LOW
    assert evaluator._map_risk_level(0.060) == RiskLevel.ELEVATED
    assert evaluator._map_risk_level(0.350) == RiskLevel.ELEVATED
    assert evaluator._map_risk_level(0.599) == RiskLevel.ELEVATED
    assert evaluator._map_risk_level(0.600) == RiskLevel.CRITICAL
    assert evaluator._map_risk_level(0.990) == RiskLevel.CRITICAL
