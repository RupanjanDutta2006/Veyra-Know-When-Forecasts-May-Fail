"""Day 6 Live Model Serving & End-to-End Prediction Smoke Test for Veyra."""
import os
import sys

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.safety.abstention import SafetyEvaluator
from backend.app.schemas.prediction import PredictionRequest
from backend.app.schemas.weather import CanonicalForecastDataset, CanonicalForecastRecord
from backend.app.services.base import WeatherResult
from backend.app.services.feature_service import LiveFeatureService
from backend.app.services.model_service import LiveLogisticModelService
from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService


def run_serving_smoke_test() -> bool:
    print("=" * 65)
    print(" VEYRA DAY 6 — LIVE MODEL SERVING & PREDICTION SMOKE TEST")
    print("=" * 65)

    # 1. Initialize live production services
    weather_service = OpenMeteoGEFSWeatherService()
    feature_service = LiveFeatureService()
    model_service = LiveLogisticModelService()
    safety_evaluator = SafetyEvaluator()

    agent = ForecastBustAgent(
        weather_service=weather_service,
        feature_service=feature_service,
        model_service=model_service,
        safety_evaluator=safety_evaluator,
    )

    print(f"[1/6] Services initialized:")
    print(f"      - Weather Service: {weather_service.__class__.__name__}")
    print(f"      - Feature Service: {feature_service.__class__.__name__} (Ready: {feature_service.is_ready})")
    print(f"      - Model Service:   {model_service.__class__.__name__} (Loaded: {model_service.is_ready}, Version: {model_service.model_version})")
    print(f"      - Safety Service:  {safety_evaluator.__class__.__name__}")

    # 2. Test live forecast ingestion for London
    location = "London"
    print(f"\n[2/6] Querying live forecast for '{location}'...")
    weather_result = weather_service.get_forecast(location)

    if not weather_result.is_available:
        print(f"      [!] Live API unavailable ({weather_result.error}). Using deterministic offline weather fixture.")
        # Fallback fixture to ensure smoke test executes end-to-end even if offline
        records = [
            CanonicalForecastRecord(
                location=location,
                latitude=51.5074,
                longitude=-0.1278,
                issue_time="2026-08-26T00:00:00Z",
                valid_time="2026-08-29T12:00:00Z",
                lead_hours=84,
                variable=var,
                unit="celsius" if "temp" in var else "hPa" if "pressure" in var else "m/s" if "wind" in var else "%" if "humidity" in var else "mm",
                value=22.5 + i * 1.5,
                source="NOAA_GEFS_OPENMETEO",
            )
            for i, var in enumerate(["temperature_2m", "surface_pressure", "wind_speed_10m", "relative_humidity_2m", "precipitation"])
        ]
        ds = CanonicalForecastDataset(
            location=location, latitude=51.5074, longitude=-0.1278, issue_time="2026-08-26T00:00:00Z", source="NOAA_GEFS_OPENMETEO", records=records
        )
        weather_result = WeatherResult(location=location, raw_data=ds.model_dump(), is_available=True, quality_flags={"qc_passed": True}, data_version="gefs-openmeteo-v1.0")

    print(f"      - Weather Available: {weather_result.is_available}")
    print(f"      - QC Status:         {weather_result.quality_flags.get('qc_passed', False)}")
    print(f"      - Data Version:      {weather_result.data_version}")

    # 3. Test live feature construction
    print(f"\n[3/6] Extracting inference features...")
    feature_result = feature_service.build_features(weather_result)
    print(f"      - Features Ready:    {feature_result.is_ready}")
    print(f"      - Feature Count:     {len(feature_result.feature_names)}")
    print(f"      - Schema Version:    {feature_result.metadata.get('schema_version', 'N/A')}")
    print(f"      - Sample Features:   lead_hours={feature_result.features.get('lead_hours')}, fc_val={feature_result.features.get('forecast_value')}")

    # 4. Test live model inference
    print(f"\n[4/6] Running model prediction with persisted Logistic Regression model...")
    model_result = model_service.predict(feature_result)
    print(f"      - Model Ready:       {model_result.is_ready}")
    print(f"      - P(BUST):           {model_result.probability}")
    print(f"      - Model Version:     {model_result.model_version}")
    print(f"      - Aggregation:       {model_result.metadata.get('aggregation')}")

    # 5. Test Safety Evaluation
    print(f"\n[5/6] Evaluating Safety & Trust Layer...")
    safety_assessment = safety_evaluator.evaluate(
        weather_result=weather_result,
        feature_result=feature_result,
        model_result=model_result,
    )
    print(f"      - Abstain:           {safety_assessment.abstain}")
    print(f"      - Trust State:       {safety_assessment.trust_state.value}")
    print(f"      - Risk Level:        {safety_assessment.risk_level.value if safety_assessment.risk_level else 'N/A'}")
    print(f"      - Reason Codes:      {safety_assessment.reason_codes}")

    # 6. Test full agent analyze response
    print(f"\n[6/6] End-to-End ForecastBustAgent Execution for '{location}':")
    req = PredictionRequest(location=location)
    response = agent.analyze(req)

    print("\n--- STANDARDIZED PREDICTION RESPONSE ---")
    print(f"  location:         \"{response.location}\"")
    print(f"  bust_probability: {response.bust_probability}")
    print(f"  risk_level:       \"{response.risk_level.value if response.risk_level else None}\"")
    print(f"  trust_state:      \"{response.trust_state.value}\"")
    print(f"  abstain:          {response.abstain}")
    print(f"  reason_codes:     {response.reason_codes}")
    print(f"  model_version:    \"{response.model_version}\"")
    print(f"  data_version:     \"{response.data_version}\"")
    print("----------------------------------------")

    # Assertions for smoke test validation
    assert response.bust_probability is not None, "Bust probability must not be None on successful inference"
    assert 0.0 <= response.bust_probability <= 1.0, f"Probability out of bounds: {response.bust_probability}"
    assert response.abstain is False, "Abstain should be False for successful high confidence prediction"
    assert response.model_version == "baseline-logistic-v1.0", "Model version mismatch"

    print("\n[+] DAY 6 LIVE SERVING SMOKE TEST COMPLETED SUCCESSFULLY.")
    return True


if __name__ == "__main__":
    success = run_serving_smoke_test()
    sys.exit(0 if success else 1)
