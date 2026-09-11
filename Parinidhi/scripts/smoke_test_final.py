"""Day 7 Final Integration & System Readiness Smoke Test for Veyra."""
import os
import sys

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.ml.artifacts import ModelArtifactManager
from backend.app.ml.features import FORBIDDEN_LEAKAGE_FIELDS
from backend.app.safety.abstention import SafetyEvaluator
from backend.app.schemas.prediction import PredictionRequest, ReasonCode, RiskLevel, TrustState
from backend.app.schemas.weather import CanonicalForecastDataset, CanonicalForecastRecord
from backend.app.services.base import WeatherResult
from backend.app.services.feature_service import LiveFeatureService
from backend.app.services.model_service import LiveLogisticModelService
from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService


def run_final_smoke_test() -> bool:
    print("=" * 70)
    print(" VEYRA DAY 7 — FINAL SYSTEM READINESS & INTEGRATION SMOKE TEST")
    print("=" * 70)

    # [1] Backend / Service Initialization
    print("[1/10] Initializing production services...")
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
    print(f"       - Weather Service: {weather_service.__class__.__name__}")
    print(f"       - Feature Service: {feature_service.__class__.__name__} (Ready: {feature_service.is_ready})")
    print(f"       - Model Service:   {model_service.__class__.__name__} (Loaded: {model_service.is_ready})")
    print(f"       - Safety Service:  {safety_evaluator.__class__.__name__}")
    assert feature_service.is_ready, "FeatureService must be ready"
    assert model_service.is_ready, "ModelService must be ready"

    # [2] Model Artifact Load & Metadata Verification
    print("\n[2/10] Verifying persisted model artifact & metadata...")
    mgr = ModelArtifactManager(artifacts_dir="models")
    loaded_model, loaded_pipe, metadata = mgr.load_artifact("baseline_logistic_v1")
    print(f"       - Model Version:        {metadata.get('model_version')}")
    print(f"       - Feature Schema:       {metadata.get('feature_schema_version')}")
    print(f"       - Model Type:           {metadata.get('model_type')}")
    print(f"       - Training Samples:     {metadata.get('train_samples')}")
    print(f"       - Validation F1:        {metadata.get('val_metrics', {}).get('f1_score')}")
    assert metadata.get("model_version") == "baseline-logistic-v1.0"
    assert len(metadata.get("feature_names", [])) == 18

    # [3] Live Supported-Location Forecast Query (London & Kolkata)
    test_locations = ["London", "Kolkata", "Tokyo"]
    print(f"\n[3/10] Testing live forecast queries for {test_locations}...")
    for loc in test_locations:
        w_res = weather_service.get_forecast(loc)
        print(f"       - '{loc}': Available={w_res.is_available}, QC={w_res.quality_flags.get('qc_passed')}, Records={len(w_res.raw_data.get('records', []))}")
        assert w_res.is_available, f"Weather must be available for {loc}"
        assert w_res.quality_flags.get("qc_passed"), f"QC must pass for {loc}"

    # [4] 18-Feature Schema & Preprocessing Parity
    print("\n[4/10] Validating 18-feature inference transformation...")
    w_london = weather_service.get_forecast("London")
    feat_london = feature_service.build_features(w_london)
    print(f"       - Feature Count:        {len(feat_london.feature_names)}")
    print(f"       - Feature Schema Match: {feat_london.feature_names == metadata.get('feature_names')}")
    assert len(feat_london.feature_names) == 18
    assert feat_london.feature_names == metadata.get("feature_names")

    # [5] Real P(BUST) Probability Generation
    print("\n[5/10] Evaluating real P(BUST) via persisted Logistic Regression...")
    model_res = model_service.predict(feat_london)
    print(f"       - Raw P(BUST):          {model_res.probability}")
    print(f"       - Model Version:        {model_res.model_version}")
    assert model_res.probability is not None
    assert 0.0 <= model_res.probability <= 1.0

    # [6] Safety & Trust Layer Evaluation
    print("\n[6/10] Evaluating Safety & Trust Layer mapping...")
    safety_res = safety_evaluator.evaluate(
        weather_result=w_london,
        feature_result=feat_london,
        model_result=model_res,
    )
    print(f"       - Abstain:              {safety_res.abstain}")
    print(f"       - Trust State:          {safety_res.trust_state.value}")
    print(f"       - Risk Level:           {safety_res.risk_level.value}")
    print(f"       - Reason Codes:         {safety_res.reason_codes}")
    assert safety_res.abstain is False
    assert safety_res.trust_state == TrustState.HIGH_CONFIDENCE
    assert safety_res.reason_codes == [ReasonCode.SUCCESS.value]

    # [7] Unsupported-Location Safe Abstention
    print("\n[7/10] Testing unsupported location safe abstention ('Atlantis')...")
    resp_unsupported = agent.analyze(PredictionRequest(location="Atlantis"))
    print(f"       - Location:             {resp_unsupported.location}")
    print(f"       - Abstain:              {resp_unsupported.abstain}")
    print(f"       - Trust State:          {resp_unsupported.trust_state.value}")
    print(f"       - Probability:          {resp_unsupported.bust_probability}")
    print(f"       - Reason Codes:         {resp_unsupported.reason_codes}")
    assert resp_unsupported.abstain is True
    assert resp_unsupported.bust_probability is None
    assert resp_unsupported.trust_state == TrustState.UNAVAILABLE
    assert ReasonCode.INVALID_LOCATION.value in resp_unsupported.reason_codes

    # [8] Full Version Traceability
    print("\n[8/10] Verifying end-to-end version traceability...")
    resp_london = agent.analyze(PredictionRequest(location="London"))
    print(f"       - Response Model Ver:   {resp_london.model_version}")
    print(f"       - Response Data Ver:    {resp_london.data_version}")
    assert resp_london.model_version == "baseline-logistic-v1.0"
    assert resp_london.data_version == "gefs-openmeteo-v1.0"

    # [9] Anti-Data-Leakage Audit
    print("\n[9/10] Auditing live features for forbidden leakage fields...")
    for forbidden in FORBIDDEN_LEAKAGE_FIELDS:
        assert forbidden not in feat_london.features, f"Forbidden leakage field {forbidden} found in live features"
        assert forbidden not in feat_london.feature_names, f"Forbidden leakage field {forbidden} found in feature names"
    print("       - Ground-truth / Reference leakage: ZERO (PASS)")

    # [10] Final Readiness Confirmation
    print("\n[10/10] Final System Verification:")
    print("       [+] Live weather ingestion: OPERATIONAL")
    print("       [+] Quality control:        OPERATIONAL")
    print("       [+] Feature engineering:    OPERATIONAL (18 features)")
    print("       [+] Baseline ML serving:    OPERATIONAL (baseline-logistic-v1.0)")
    print("       [+] Safety & Abstention:    OPERATIONAL")
    print("       [+] Standardized API:       OPERATIONAL")

    print("\n" + "=" * 70)
    print(" [+] VEYRA DAY 7 FINAL SMOKE TEST: ALL 10 PHASES PASSED")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_final_smoke_test()
    sys.exit(0 if success else 1)
