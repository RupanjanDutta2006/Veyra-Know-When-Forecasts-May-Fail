"""Unit tests for Real Forecast Data Ingestion and Historical Pathway."""
import json
from unittest.mock import MagicMock
from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.data.historical_pathway import (
    HistoricalForecastPair,
    HistoricalPathwayAligner,
)
from backend.app.schemas.prediction import PredictionRequest, ReasonCode, TrustState
from backend.app.schemas.weather import CanonicalForecastDataset, CanonicalForecastRecord
from backend.app.services.base import BaseWeatherService, WeatherResult
from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService


def _get_mock_vendor_payload() -> dict:
    """Return a deterministic sample payload matching Open-Meteo GFS response."""
    return {
        "latitude": 51.5,
        "longitude": -0.12,
        "generationtime_ms": 1.2,
        "timezone": "UTC",
        "hourly": {
            "time": [
                "2026-08-25T00:00",
                "2026-08-25T06:00",
                "2026-08-25T12:00",
                "2026-08-25T18:00",
            ],
            "temperature_2m": [15.2, 17.8, 22.4, 19.1],
            "surface_pressure": [1013.2, 1012.8, 1011.5, 1012.0],
            "wind_speed_10m": [3.5, 4.2, 5.8, 4.0],
            "relative_humidity_2m": [82.0, 75.0, 58.0, 68.0],
            "precipitation": [0.0, 0.0, 0.2, 0.0],
        },
        "hourly_units": {
            "time": "iso8601",
            "temperature_2m": "°C",
            "surface_pressure": "hPa",
            "wind_speed_10m": "m/s",
            "relative_humidity_2m": "%",
            "precipitation": "mm",
        },
    }


def test_openmeteo_service_coordinate_resolution():
    """Test resolution of named cities and coordinate strings."""
    service = OpenMeteoGEFSWeatherService()
    assert service.resolve_coordinates("London") == (51.5074, -0.1278)
    assert service.resolve_coordinates("tokyo") == (35.6762, 139.6503)
    assert service.resolve_coordinates("40.7128, -74.0060") == (40.7128, -74.0060)
    assert service.resolve_coordinates("UnknownCityXYZ") is None


def test_openmeteo_service_query_url_builder():
    """Test URL generation with and without target date."""
    service = OpenMeteoGEFSWeatherService()
    url = service.build_query_url(51.5074, -0.1278)
    assert "latitude=51.5074" in url
    assert "longitude=-0.1278" in url
    assert "models=gfs_seamless" in url

    url_with_date = service.build_query_url(51.5074, -0.1278, target_date="2026-09-01")
    assert "start_date=2026-09-01" in url_with_date
    assert "end_date=2026-09-01" in url_with_date


def test_openmeteo_service_canonical_parsing():
    """Test that vendor JSON response is parsed cleanly into CanonicalForecastRecords."""
    service = OpenMeteoGEFSWeatherService()
    payload = _get_mock_vendor_payload()
    records = service.parse_canonical_records(payload, "London", 51.5074, -0.1278)

    assert len(records) == 20  # 4 timestamps * 5 variables
    first_record = records[0]
    assert isinstance(first_record, CanonicalForecastRecord)
    assert first_record.location == "London"
    assert first_record.variable == "temperature_2m"
    assert first_record.unit == "celsius"
    assert first_record.value == 15.2


def test_openmeteo_service_get_forecast_offline():
    """Test get_forecast using mock HTTP client to ensure zero network dependency in unit tests."""
    mock_http = MagicMock(return_value=_get_mock_vendor_payload())
    service = OpenMeteoGEFSWeatherService(http_client=mock_http)
    result = service.get_forecast("London")

    assert isinstance(result, WeatherResult)
    assert result.is_available is True
    assert result.quality_flags["qc_passed"] is True
    assert result.data_version == "gfs-ensemble-openmeteo-v2.0"
    assert result.metadata["record_count"] == 20
    mock_http.assert_called_once()


def test_openmeteo_service_unknown_location_fails():
    """Test that querying an invalid location safely returns is_available=False with INVALID_LOCATION."""
    service = OpenMeteoGEFSWeatherService()
    result = service.get_forecast("InvalidCityNameThatDoesNotExist")

    assert result.is_available is False
    assert result.metadata["status"] == ReasonCode.INVALID_LOCATION.value
    assert result.quality_flags["invalid_location"] is True


def test_agent_integration_with_real_weather_service():
    """Test that ForecastBustAgent seamlessly accepts OpenMeteoGEFSWeatherService without code modification."""
    mock_http = MagicMock(return_value=_get_mock_vendor_payload())
    weather_service = OpenMeteoGEFSWeatherService(http_client=mock_http)

    # Injected into agent while model remains unready
    agent = ForecastBustAgent(weather_service=weather_service)
    request = PredictionRequest(location="London")
    response = agent.analyze(request)

    # Weather ingestion succeeded, but model is not yet trained -> safe abstention
    assert response.location == "London"
    assert response.bust_probability is None
    assert response.risk_level is None
    assert response.trust_state == TrustState.UNAVAILABLE
    assert response.abstain is True
    assert response.data_version == "gfs-ensemble-openmeteo-v2.0"


def test_historical_pathway_error_and_bust_labeling():
    """Test historical forecast-reference alignment and bust threshold assignment."""
    pair = HistoricalPathwayAligner.align_pair(
        location="London",
        latitude=51.5074,
        longitude=-0.1278,
        variable="temperature_2m",
        unit="celsius",
        issue_time="2026-08-20T00:00:00Z",
        valid_time="2026-08-23T12:00:00Z",
        lead_hours=84,
        forecast_value=28.5,
        reference_time="2026-08-23T12:00:00Z",
        reference_value=23.0,
        bust_threshold=4.0,  # Bust if abs(error) >= 4.0 °C
    )

    assert pair.forecast_error == 5.5
    assert pair.is_bust is True
    assert pair.is_ground_truth_label is True
    assert HistoricalPathwayAligner.assert_no_data_leakage(pair) is True


def test_historical_pathway_anti_leakage_check():
    """Test that future verification data dated before issue time is caught as an error."""
    invalid_pair = HistoricalForecastPair(
        location="London",
        latitude=51.5074,
        longitude=-0.1278,
        variable="temperature_2m",
        unit="celsius",
        forecast_issue_time="2026-08-25T00:00:00Z",
        forecast_valid_time="2026-08-20T00:00:00Z",  # Valid in the past relative to issue!
        forecast_lead_hours=-120,
        forecast_value=20.0,
        reference_verification_time="2026-08-20T00:00:00Z",
        reference_value=20.0,
    )
    assert HistoricalPathwayAligner.assert_no_data_leakage(invalid_pair) is False
