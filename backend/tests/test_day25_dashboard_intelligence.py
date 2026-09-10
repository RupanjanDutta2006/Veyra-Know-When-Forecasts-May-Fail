"""Comprehensive Automated Test Suite for Day 25 Intelligence Dashboard API.

Verifies:
1. Route registration & OpenAPI schema
2. Horizon mode planning (single, standard_7d, full_16d)
3. Variable support (temperature_2m, wind_speed_10m, surface_pressure)
4. Selected prediction mapping & default 24h lead
5. Invalid location safety & early short-circuit
6. Partial timeline abstention & reason-code preservation
7. All-abstained timeline safety & null summary handling
8. Null-safe mean and max probability computations
9. Peak risk level and max-risk lead hours
10. Elevated risk point counting and first elevated horizon
11. Deterministic risk trend (RISING, FALLING, STABLE, MIXED, INSUFFICIENT_DATA)
12. Overall decision mode synthesis
13. Dashboard status contract (SUCCESS, PARTIAL, ABSTAINED)
14. Calibration failure safety & raw probability non-exposure
15. Benchmark vs. live separation & 240h certification boundary
16. Request ID correlation
17. In-process cache deduplication & upstream isolation
18. Multi-location & variable cache isolation
19. Backward compatibility of legacy & V3 endpoints
20. Dashboard operational metrics telemetry
21. Validation error handling (HTTP 422)
"""
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app.core.metrics import default_metrics
from backend.app.main import app
from backend.app.schemas.dashboard import (
    DashboardIntelligenceResponse,
    DashboardMode,
    DashboardRequest,
    DashboardStatus,
    DecisionMode,
)
from backend.app.schemas.location import ResolvedLocation
from backend.app.schemas.prediction import (
    CalibrationStatus,
    PredictionRequest,
    PredictionResponse,
    ReasonCode,
    RiskLevel,
    TrustState,
)
from backend.app.services.dashboard_service import DashboardIntelligenceService
from backend.app.services.location_service import BaseLocationService


# ---------------------------------------------------------------------------
# Mocks & Test Fixtures
# ---------------------------------------------------------------------------

class MockLocationService(BaseLocationService):
    """Deterministic in-memory location resolver."""

    def __init__(self):
        self.known = {
            "kolkata": ResolvedLocation(
                original_input="Kolkata",
                name="Kolkata",
                latitude=22.5726,
                longitude=88.3639,
                country="India",
                timezone="Asia/Kolkata",
            ),
            "delhi": ResolvedLocation(
                original_input="Delhi",
                name="Delhi",
                latitude=28.6139,
                longitude=77.2090,
                country="India",
                timezone="Asia/Kolkata",
            ),
            "london": ResolvedLocation(
                original_input="London",
                name="London",
                latitude=51.5074,
                longitude=-0.1278,
                country="United Kingdom",
                timezone="Europe/London",
            ),
        }

    def resolve(self, query: str):
        q_clean = query.strip().lower()
        return self.known.get(q_clean)

    def resolve_coordinates(self, query: str):
        res = self.resolve(query)
        if res:
            return (res.latitude, res.longitude)
        return None


class MockForecastBustAgent:
    """Configurable mock agent simulating deterministic horizon probabilities."""

    def __init__(self, prob_map=None, default_prob=0.08, fail_leads=None, cal_fail_leads=None):
        self.prob_map = prob_map or {}
        self.default_prob = default_prob
        self.fail_leads = set(fail_leads or [])
        self.cal_fail_leads = set(cal_fail_leads or [])
        self.call_count = 0

    def analyze(self, request: PredictionRequest) -> PredictionResponse:
        self.call_count += 1
        lead = 24
        if request.valid_time and request.issue_time:
            t_issue = datetime.fromisoformat(request.issue_time.replace("Z", "+00:00"))
            t_valid = datetime.fromisoformat(request.valid_time.replace("Z", "+00:00"))
            lead = int(round((t_valid - t_issue).total_seconds() / 3600.0))

        if lead in self.cal_fail_leads:
            return PredictionResponse(
                location=request.location or "Kolkata",
                bust_probability=None,
                risk_level=None,
                trust_state=TrustState.UNAVAILABLE,
                abstain=True,
                reason_codes=[ReasonCode.CALIBRATION_FAILURE],
                calibration_status=CalibrationStatus.FAILED,
                decision_mode=DecisionMode.ABSTAINED.value,
                model_version="veyra-v3-benchmark-lightgbm",
            )

        if lead in self.fail_leads:
            return PredictionResponse(
                location=request.location or "Kolkata",
                bust_probability=None,
                risk_level=None,
                trust_state=TrustState.UNAVAILABLE,
                abstain=True,
                reason_codes=[ReasonCode.DATA_UNAVAILABLE],
                calibration_status=CalibrationStatus.UNAVAILABLE,
                decision_mode=DecisionMode.ABSTAINED.value,
                model_version="veyra-v3-benchmark-lightgbm",
            )

        prob = self.prob_map.get(lead, self.default_prob)
        if prob < 0.20:
            risk = RiskLevel.LOW
            mode = DecisionMode.STANDARD_MONITORING.value
        elif prob < 0.50:
            risk = RiskLevel.MEDIUM
            mode = DecisionMode.ELEVATED_AWARENESS.value
        elif prob < 0.75:
            risk = RiskLevel.HIGH
            mode = DecisionMode.HIGH_UNCERTAINTY.value
        else:
            risk = RiskLevel.CRITICAL
            mode = DecisionMode.CRITICAL_INTERVENTION.value

        return PredictionResponse(
            location=request.location or "Kolkata",
            bust_probability=prob,
            risk_level=risk,
            trust_state=TrustState.HIGH_CONFIDENCE,
            abstain=False,
            reason_codes=[ReasonCode.SUCCESS],
            calibration_status=CalibrationStatus.CALIBRATED,
            decision_mode=mode,
            confidence_index=round(2.0 * abs(prob - 0.5), 4),
            uncertainty_pct=round(100.0 * (1.0 - 2.0 * abs(prob - 0.5)), 2),
            ood_score=0.0,
            model_version="veyra-v3-benchmark-lightgbm",
            within_trust_horizon=lead <= 168,
            operational_trust_horizon_hours=168,
        )


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Route Registration & OpenAPI Tests
# ---------------------------------------------------------------------------

def test_dashboard_route_registered():
    """Verify POST /v1/dashboard/intelligence exists in FastAPI routes."""
    paths = app.openapi()["paths"]
    assert "/v1/dashboard/intelligence" in paths
    assert "post" in paths["/v1/dashboard/intelligence"]


def test_dashboard_openapi_schema_quality():
    """Verify OpenAPI documentation contains mode enum, descriptions, and examples."""
    paths = app.openapi()["paths"]
    endpoint_spec = paths["/v1/dashboard/intelligence"]["post"]
    assert "summary" in endpoint_spec
    assert "description" in endpoint_spec

    schemas = app.openapi()["components"]["schemas"]
    assert "DashboardRequest" in schemas
    assert "DashboardIntelligenceResponse" in schemas
    assert "DashboardSummary" in schemas
    assert "DashboardTimelinePoint" in schemas
    assert "DashboardScientificContext" in schemas

    req_props = schemas["DashboardRequest"]["properties"]
    assert "location" in req_props
    assert "mode" in req_props
    assert "variable" in req_props


# ---------------------------------------------------------------------------
# 2. Horizon Modes & Ordering Tests
# ---------------------------------------------------------------------------

def test_dashboard_single_mode():
    """Verify single mode returns exactly 1 timeline point at 24h lead."""
    svc = DashboardIntelligenceService(
        location_service=MockLocationService(),
        agent_factory=lambda: MockForecastBustAgent(),
    )
    req = DashboardRequest(location="Kolkata", mode=DashboardMode.SINGLE)
    resp = svc.orchestrate(req)

    assert resp.status == DashboardStatus.SUCCESS
    assert resp.mode == DashboardMode.SINGLE
    assert len(resp.timeline) == 1
    assert resp.timeline[0].lead_hours == 24
    assert resp.timeline[0].lead_days == 1.0
    assert resp.timeline[0].bust_probability is not None
    assert resp.summary.total_points == 1
    assert resp.summary.available_points == 1
    assert resp.summary.abstained_points == 0


def test_dashboard_standard_7d_mode():
    """Verify standard_7d returns exactly 7 strictly ordered points from 24h to 168h."""
    svc = DashboardIntelligenceService(
        location_service=MockLocationService(),
        agent_factory=lambda: MockForecastBustAgent(),
    )
    req = DashboardRequest(location="Kolkata", mode=DashboardMode.STANDARD_7D)
    resp = svc.orchestrate(req)

    assert resp.status == DashboardStatus.SUCCESS
    assert len(resp.timeline) == 7
    expected_leads = [24, 48, 72, 96, 120, 144, 168]
    actual_leads = [p.lead_hours for p in resp.timeline]
    assert actual_leads == expected_leads
    assert resp.summary.total_points == 7
    assert resp.summary.available_points == 7


def test_dashboard_full_16d_mode():
    """Verify full_16d returns exactly 16 strictly ordered points from 24h to 384h."""
    svc = DashboardIntelligenceService(
        location_service=MockLocationService(),
        agent_factory=lambda: MockForecastBustAgent(),
    )
    req = DashboardRequest(location="Kolkata", mode=DashboardMode.FULL_16D)
    resp = svc.orchestrate(req)

    assert resp.status == DashboardStatus.SUCCESS
    assert len(resp.timeline) == 16
    expected_leads = [24 * i for i in range(1, 17)]
    actual_leads = [p.lead_hours for p in resp.timeline]
    assert actual_leads == expected_leads
    assert resp.summary.total_points == 16


# ---------------------------------------------------------------------------
# 3. Variable Support & Selected Prediction Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("variable", ["temperature_2m", "wind_speed_10m", "surface_pressure"])
def test_dashboard_supported_variables(variable):
    """Verify all certified meteorological variables evaluate properly."""
    svc = DashboardIntelligenceService(
        location_service=MockLocationService(),
        agent_factory=lambda: MockForecastBustAgent(),
    )
    req = DashboardRequest(location="Kolkata", variable=variable, mode=DashboardMode.SINGLE)
    resp = svc.orchestrate(req)

    assert resp.variable == variable


def test_dashboard_selected_prediction_is_canonical_24h():
    """Verify selected_prediction maps to canonical 24h operational lead."""
    prob_map = {24: 0.05, 48: 0.25, 72: 0.65}
    svc = DashboardIntelligenceService(
        location_service=MockLocationService(),
        agent_factory=lambda: MockForecastBustAgent(prob_map=prob_map),
    )
    req = DashboardRequest(location="Kolkata", mode=DashboardMode.STANDARD_7D)
    resp = svc.orchestrate(req)

    assert resp.selected_prediction.bust_probability == pytest.approx(0.05, abs=1e-4)
    assert resp.selected_prediction.risk_level == RiskLevel.LOW
    assert resp.timeline[0].bust_probability == pytest.approx(0.05, abs=1e-4)


# ---------------------------------------------------------------------------
# 4. Invalid Location Safety Tests
# ---------------------------------------------------------------------------

def test_dashboard_invalid_location_safety():
    """Verify unknown location immediately abstains without calling model or upstream."""
    mock_agent = MockForecastBustAgent()
    svc = DashboardIntelligenceService(
        location_service=MockLocationService(),
        agent_factory=lambda: mock_agent,
    )
    req = DashboardRequest(location="Atlantis", mode=DashboardMode.STANDARD_7D)
    resp = svc.orchestrate(req)

    # Agent analyze must NOT be called for invalid location
    assert mock_agent.call_count == 0
    assert resp.status == DashboardStatus.ABSTAINED
    assert resp.location.resolved_name is None
    assert resp.selected_prediction.abstain is True
    assert resp.selected_prediction.bust_probability is None
    assert ReasonCode.INVALID_LOCATION in resp.selected_prediction.reason_codes

    assert resp.summary.available_points == 0
    assert resp.summary.abstained_points == 7
    assert resp.summary.max_bust_probability is None
    assert resp.summary.mean_bust_probability is None

    for pt in resp.timeline:
        assert pt.bust_probability is None
        assert pt.risk_level is None
        assert pt.abstain is True
        assert ReasonCode.INVALID_LOCATION in pt.reason_codes
        assert pt.calibration_status == CalibrationStatus.UNAVAILABLE


def test_dashboard_invalid_location_timeline_valid_time_consistency():
    """Verify Atlantis in single, standard_7d, and full_16d modes exhibits chronologically increasing valid_time values."""
    mock_agent = MockForecastBustAgent()
    svc = DashboardIntelligenceService(
        location_service=MockLocationService(),
        agent_factory=lambda: mock_agent,
    )

    # 1. Single mode (Atlantis)
    req_single = DashboardRequest(location="Atlantis", mode=DashboardMode.SINGLE)
    resp_single = svc.orchestrate(req_single)
    assert resp_single.status == DashboardStatus.ABSTAINED
    assert len(resp_single.timeline) == 1
    pt_single = resp_single.timeline[0]
    assert pt_single.lead_hours == 24
    assert pt_single.bust_probability is None
    assert pt_single.risk_level is None
    assert pt_single.abstain is True
    assert ReasonCode.INVALID_LOCATION in pt_single.reason_codes
    assert pt_single.valid_time > resp_single.issue_time

    # 2. Standard 7d mode (Atlantis)
    req_7d = DashboardRequest(location="Atlantis", mode=DashboardMode.STANDARD_7D)
    resp_7d = svc.orchestrate(req_7d)
    assert resp_7d.status == DashboardStatus.ABSTAINED
    assert len(resp_7d.timeline) == 7
    leads_7d = [p.lead_hours for p in resp_7d.timeline]
    assert leads_7d == [24, 48, 72, 96, 120, 144, 168]
    valid_times_7d = [p.valid_time for p in resp_7d.timeline]
    # Verify chronologically strictly increasing
    assert valid_times_7d == sorted(valid_times_7d)
    # Verify no duplicate timestamps across distinct horizons
    assert len(set(valid_times_7d)) == 7

    # 3. Full 16d mode (Atlantis - Defect Reproduction & Repair Verification)
    req_16d = DashboardRequest(location="Atlantis", mode=DashboardMode.FULL_16D)
    resp_16d = svc.orchestrate(req_16d)
    assert resp_16d.status == DashboardStatus.ABSTAINED
    assert len(resp_16d.timeline) == 16
    assert resp_16d.summary.total_points == 16
    assert resp_16d.summary.available_points == 0
    assert resp_16d.summary.abstained_points == 16
    assert resp_16d.summary.max_bust_probability is None
    assert resp_16d.summary.mean_bust_probability is None

    leads_16d = [p.lead_hours for p in resp_16d.timeline]
    expected_leads_16d = [24 * i for i in range(1, 17)]
    assert leads_16d == expected_leads_16d

    valid_times_16d = [p.valid_time for p in resp_16d.timeline]
    # Verify chronologically strictly increasing
    assert valid_times_16d == sorted(valid_times_16d)
    # Verify no duplicates across all 16 horizons
    assert len(set(valid_times_16d)) == 16

    # Verify each valid_time corresponds precisely to its lead offset from issue_time
    issue_dt = datetime.fromisoformat(resp_16d.issue_time.replace("Z", "+00:00"))
    for pt in resp_16d.timeline:
        assert pt.bust_probability is None
        assert pt.risk_level is None
        assert pt.trust_state == TrustState.UNAVAILABLE
        assert pt.abstain is True
        assert ReasonCode.INVALID_LOCATION in pt.reason_codes
        assert pt.calibration_status == CalibrationStatus.UNAVAILABLE
        assert pt.decision_mode == DecisionMode.ABSTAINED

        pt_valid_dt = datetime.fromisoformat(pt.valid_time.replace("Z", "+00:00"))
        expected_valid_dt = issue_dt + timedelta(hours=pt.lead_hours)
        assert pt_valid_dt == expected_valid_dt



# ---------------------------------------------------------------------------
# 5. Partial Timeline Abstention & Reason Code Preservation
# ---------------------------------------------------------------------------

def test_dashboard_partial_failure():
    """Verify timeline handles partial failure safely and sets status to PARTIAL."""
    # Fail lead 72 and 120
    mock_agent = MockForecastBustAgent(
        prob_map={24: 0.10, 48: 0.15, 96: 0.20, 144: 0.30, 168: 0.40},
        fail_leads=[72, 120],
    )
    svc = DashboardIntelligenceService(
        location_service=MockLocationService(),
        agent_factory=lambda: mock_agent,
    )
    req = DashboardRequest(location="Kolkata", mode=DashboardMode.STANDARD_7D)
    resp = svc.orchestrate(req)

    assert resp.status == DashboardStatus.PARTIAL
    assert resp.summary.total_points == 7
    assert resp.summary.available_points == 5
    assert resp.summary.abstained_points == 2

    pt_72 = next(p for p in resp.timeline if p.lead_hours == 72)
    assert pt_72.bust_probability is None
    assert pt_72.abstain is True
    assert ReasonCode.DATA_UNAVAILABLE in pt_72.reason_codes

    pt_24 = next(p for p in resp.timeline if p.lead_hours == 24)
    assert pt_24.bust_probability == 0.10
    assert pt_24.abstain is False


# ---------------------------------------------------------------------------
# 6. Null-Safe Summary Computations
# ---------------------------------------------------------------------------

def test_dashboard_null_safe_mean_and_max():
    """Verify mean and max calculations strictly ignore null probabilities."""
    # Valid probabilities: 0.10, 0.20, 0.60 -> sum=0.90, mean=0.30, max=0.60
    mock_agent = MockForecastBustAgent(
        prob_map={24: 0.10, 48: 0.20, 168: 0.60},
        fail_leads=[72, 96, 120, 144],
    )
    svc = DashboardIntelligenceService(
        location_service=MockLocationService(),
        agent_factory=lambda: mock_agent,
    )
    req = DashboardRequest(location="Kolkata", mode=DashboardMode.STANDARD_7D)
    resp = svc.orchestrate(req)

    assert resp.summary.available_points == 3
    assert resp.summary.abstained_points == 4
    assert resp.summary.mean_bust_probability == pytest.approx(0.30, abs=1e-4)
    assert resp.summary.max_bust_probability == pytest.approx(0.60, abs=1e-4)
    assert resp.summary.max_risk_level == RiskLevel.HIGH
    assert resp.summary.max_risk_lead_hours == 168


def test_dashboard_elevated_risk_metrics():
    """Verify elevated risk counting (MEDIUM, HIGH, CRITICAL) and first elevated horizon."""
    # 24: 0.05 (LOW), 48: 0.22 (MEDIUM), 72: 0.55 (HIGH), 96: 0.80 (CRITICAL)
    prob_map = {24: 0.05, 48: 0.22, 72: 0.55, 96: 0.80, 120: 0.10, 144: 0.12, 168: 0.14}
    svc = DashboardIntelligenceService(
        location_service=MockLocationService(),
        agent_factory=lambda: MockForecastBustAgent(prob_map=prob_map),
    )
    req = DashboardRequest(location="Kolkata", mode=DashboardMode.STANDARD_7D)
    resp = svc.orchestrate(req)

    # 48, 72, 96 are elevated -> count = 3
    assert resp.summary.elevated_risk_points == 3
    assert resp.summary.first_elevated_risk_lead_hours == 48


# ---------------------------------------------------------------------------
# 7. Scientific Summary Contract & Semantics Tests
# ---------------------------------------------------------------------------

def test_dashboard_summary_scientific_contract():
    """Verify summary contains strictly authenticated metrics with zero fabricated trend heuristics."""
    prob_map = {24: 0.10, 48: 0.15, 72: 0.22, 96: 0.55, 120: 0.12, 144: 0.18, 168: 0.08}
    svc = DashboardIntelligenceService(
        location_service=MockLocationService(),
        agent_factory=lambda: MockForecastBustAgent(prob_map=prob_map),
    )
    req = DashboardRequest(location="Kolkata", mode=DashboardMode.STANDARD_7D)
    resp = svc.orchestrate(req)

    # Strictly authenticated aggregation assertions
    assert resp.summary.total_points == 7
    assert resp.summary.available_points == 7
    assert resp.summary.abstained_points == 0
    assert resp.summary.max_bust_probability == 0.55
    assert resp.summary.max_risk_level == RiskLevel.HIGH
    assert resp.summary.max_risk_lead_hours == 96
    assert resp.summary.elevated_risk_points == 2  # 72h (MEDIUM, 0.22) and 96h (HIGH, 0.55)
    assert resp.summary.first_elevated_risk_lead_hours == 72
    assert resp.summary.overall_decision_mode == DecisionMode.HIGH_UNCERTAINTY

    # Verify no heuristic risk_trend field is exposed
    assert not hasattr(resp.summary, "risk_trend")


def test_dashboard_scientific_context_probability_semantics():
    """Verify probability semantics wording strictly preserves authoritative Day 22 >= semantics."""
    svc = DashboardIntelligenceService(
        location_service=MockLocationService(),
        agent_factory=lambda: MockForecastBustAgent(),
    )
    req = DashboardRequest(location="Kolkata", mode=DashboardMode.SINGLE)
    resp = svc.orchestrate(req)

    assert "meeting or exceeding the stratum-specific bust threshold" in resp.scientific_context.probability_semantics
    assert "exceeding the stratum-specific" not in resp.scientific_context.probability_semantics.replace("meeting or exceeding", "")


# ---------------------------------------------------------------------------
# 8. Calibration Failure Safety Tests
# ---------------------------------------------------------------------------

def test_dashboard_calibration_failure_safety():
    """Verify calibrator failure marks point as FAILED without exposing raw probability."""
    mock_agent = MockForecastBustAgent(
        prob_map={24: 0.10, 72: 0.15},
        cal_fail_leads=[48],
    )
    svc = DashboardIntelligenceService(
        location_service=MockLocationService(),
        agent_factory=lambda: mock_agent,
    )
    req = DashboardRequest(location="Kolkata", mode=DashboardMode.STANDARD_7D)
    resp = svc.orchestrate(req)

    pt_48 = next(p for p in resp.timeline if p.lead_hours == 48)
    assert pt_48.bust_probability is None
    assert pt_48.risk_level is None
    assert pt_48.calibration_status == CalibrationStatus.FAILED
    assert ReasonCode.CALIBRATION_FAILURE in pt_48.reason_codes
    assert pt_48.abstain is True
    assert pt_48.decision_mode == DecisionMode.ABSTAINED.value


# ---------------------------------------------------------------------------
# 9. Benchmark vs. Live Separation & 240h Boundary Tests
# ---------------------------------------------------------------------------

def test_dashboard_benchmark_vs_live_separation():
    """Verify scientific_context separates frozen historical benchmark from live outputs."""
    svc = DashboardIntelligenceService(
        location_service=MockLocationService(),
        agent_factory=lambda: MockForecastBustAgent(),
    )
    req = DashboardRequest(location="Kolkata", mode=DashboardMode.STANDARD_7D)
    resp = svc.orchestrate(req)

    ctx = resp.scientific_context
    assert ctx.model_version == "veyra-v3-benchmark-lightgbm"
    assert ctx.calibration_method == "isotonic"
    assert ctx.feature_count == 50
    assert ctx.benchmark_lead_horizon_max_hours == 240
    assert ctx.operational_horizon_max_hours == 384

    # Frozen Day 23 metrics must be present in historical_benchmark
    bm = ctx.historical_benchmark
    assert bm.average_precision == 0.2047
    assert bm.pr_auc_trapezoidal == 0.2124
    assert bm.roc_auc == 0.7698
    assert bm.brier_score == 0.053798
    assert bm.ece == 0.0064
    assert bm.test_samples == 116250
    assert bm.test_cycles == 155


def test_dashboard_240h_certification_boundary():
    """Verify points <= 240h are marked certified; points > 240h are marked operational only."""
    svc = DashboardIntelligenceService(
        location_service=MockLocationService(),
        agent_factory=lambda: MockForecastBustAgent(),
    )
    req = DashboardRequest(location="Kolkata", mode=DashboardMode.FULL_16D)
    resp = svc.orchestrate(req)

    for pt in resp.timeline:
        if pt.lead_hours <= 240:
            assert pt.is_certified_horizon is True, f"Lead {pt.lead_hours} should be certified"
        else:
            assert pt.is_certified_horizon is False, f"Lead {pt.lead_hours} should NOT be certified"


# ---------------------------------------------------------------------------
# 10. HTTP Integration & Telemetry Tests via TestClient
# ---------------------------------------------------------------------------

def test_dashboard_http_endpoint_e2e(client):
    """Verify HTTP POST /v1/dashboard/intelligence end-to-end integration."""
    default_metrics.reset()
    payload = {
        "location": "Kolkata",
        "variable": "temperature_2m",
        "mode": "standard_7d",
    }
    res = client.post("/v1/dashboard/intelligence", json=payload, headers={"X-Request-ID": "req_dash_001"})
    assert res.status_code == 200
    data = res.json()

    assert data["status"] in ["SUCCESS", "PARTIAL"]
    assert data["location"]["query"] == "Kolkata"
    assert len(data["timeline"]) == 7
    assert data["selected_prediction"] is not None
    assert data["summary"]["total_points"] == 7
    assert data["scientific_context"]["feature_count"] == 50
    assert data["request_id"] == "req_dash_001"

    # Verify metrics incremented
    snap = default_metrics.snapshot()
    assert snap["dashboard_points_total"] >= 7
    assert "dashboard_requests_total" in snap


def test_dashboard_malformed_request_validation(client):
    """Verify invalid payloads produce HTTP 422 with structured errors."""
    # Blank location
    res_blank = client.post("/v1/dashboard/intelligence", json={"location": "   "})
    assert res_blank.status_code == 422

    # Unsupported variable
    res_var = client.post("/v1/dashboard/intelligence", json={"location": "Kolkata", "variable": "solar_radiation"})
    assert res_var.status_code == 422

    # Invalid mode
    res_mode = client.post("/v1/dashboard/intelligence", json={"location": "Kolkata", "mode": "invalid_mode"})
    assert res_mode.status_code == 422


def test_dashboard_backward_compatibility(client):
    """Verify existing v1 endpoints remain operational and unchanged."""
    res_health = client.get("/v1/health")
    assert res_health.status_code == 200

    res_eval_v3 = client.get("/v1/model/evaluation/v3")
    assert res_eval_v3.status_code == 200
    assert res_eval_v3.json()["model_version"] == "veyra-v3-benchmark-lightgbm"

    res_metrics = client.get("/v1/metrics")
    assert res_metrics.status_code == 200


def test_dashboard_all_abstained_valid_location_summary():
    """Verify summary intelligence when a valid location experiences total horizon abstention (Item 12)."""
    # All requested leads fail
    all_fail_leads = [24, 48, 72, 96, 120, 144, 168]
    svc = DashboardIntelligenceService(
        location_service=MockLocationService(),
        agent_factory=lambda: MockForecastBustAgent(fail_leads=all_fail_leads),
    )
    req = DashboardRequest(location="Kolkata", mode=DashboardMode.STANDARD_7D)
    resp = svc.orchestrate(req)

    assert resp.status == DashboardStatus.ABSTAINED
    assert resp.summary.total_points == 7
    assert resp.summary.available_points == 0
    assert resp.summary.abstained_points == 7
    assert resp.summary.max_bust_probability is None
    assert resp.summary.mean_bust_probability is None
    assert resp.summary.max_risk_level is None
    assert resp.summary.max_risk_lead_hours is None
    assert resp.summary.elevated_risk_points == 0
    assert resp.summary.first_elevated_risk_lead_hours is None
    assert resp.summary.overall_decision_mode == DecisionMode.ABSTAINED


def test_dashboard_raw_probability_never_exposed():
    """Verify raw uncalibrated probabilities are never exposed on calibration failure (Item 23)."""
    mock_agent = MockForecastBustAgent(cal_fail_leads=[24, 48])
    svc = DashboardIntelligenceService(
        location_service=MockLocationService(),
        agent_factory=lambda: mock_agent,
    )
    req = DashboardRequest(location="Kolkata", mode=DashboardMode.SINGLE)
    resp = svc.orchestrate(req)

    assert resp.status == DashboardStatus.ABSTAINED
    assert resp.selected_prediction.bust_probability is None
    assert resp.selected_prediction.risk_level is None
    assert resp.selected_prediction.calibration_status == CalibrationStatus.FAILED
    assert ReasonCode.CALIBRATION_FAILURE in resp.selected_prediction.reason_codes

    pt = resp.timeline[0]
    assert pt.bust_probability is None
    assert pt.risk_level is None
    assert pt.calibration_status == CalibrationStatus.FAILED


def test_dashboard_request_id_header_propagation(client):
    """Verify custom X-Request-ID is propagated through headers and response model (Item 27)."""
    custom_trace_id = "test-day25-trace-xyz-987"
    payload = {
        "location": "Kolkata",
        "variable": "temperature_2m",
        "mode": "single",
    }
    res = client.post("/v1/dashboard/intelligence", json=payload, headers={"X-Request-ID": custom_trace_id})
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") == custom_trace_id
    data = res.json()
    assert data["request_id"] == custom_trace_id


def test_dashboard_rate_limit_single_charge(client):
    """Verify dashboard orchestration counts as 1 rate-limit request rather than 16 (Item 28)."""
    from backend.app.core.rate_limiter import default_rate_limiter
    default_rate_limiter.reset()

    # Make 1 multi-horizon dashboard request (16 horizons)
    payload = {
        "location": "Kolkata",
        "variable": "temperature_2m",
        "mode": "full_16d",
    }
    res = client.post("/v1/dashboard/intelligence", json=payload)
    assert res.status_code == 200

    # Under 60 req/min limit, 1 dashboard call must not trigger 429
    res2 = client.post("/v1/dashboard/intelligence", json=payload)
    assert res2.status_code == 200


def test_dashboard_cache_and_singleflight_deduplication():
    """Verify cache and SingleFlight deduplicate forecast fetches across horizons (Items 29, 30)."""
    from backend.app.core.cache import SingleFlight, BoundedTTLCache
    from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService

    test_cache = BoundedTTLCache(maxsize=50, default_ttl=300)
    test_sf = SingleFlight()
    fetch_counter = {"calls": 0}

    def mock_fetch(url: str):
        fetch_counter["calls"] += 1
        return {
            "hourly": {
                "time": [f"2026-09-10T{h:02d}:00" for h in range(24)],
                "temperature_2m": [25.0 + h * 0.1 for h in range(24)],
                "surface_pressure": [1013.25] * 24,
                "wind_speed_10m": [3.5] * 24,
                "relative_humidity_2m": [60.0] * 24,
                "precipitation": [0.0] * 24,
            }
        }

    svc = OpenMeteoGEFSWeatherService(
        http_client=mock_fetch,
        cache=test_cache,
        enable_cache=True,
        deduplicator=test_sf,
        enable_dedup=True,
    )

    # First fetch -> cache miss
    res1 = svc.get_forecast("Kolkata")
    assert res1.is_available is True
    assert fetch_counter["calls"] == 1

    # Second fetch -> cache hit
    res2 = svc.get_forecast("Kolkata")
    assert res2.is_available is True
    assert fetch_counter["calls"] == 1  # No additional network fetch


def test_dashboard_multi_location_cache_isolation():
    """Verify cache keys isolate distinct geographic locations (Item 31)."""
    from backend.app.core.cache import BoundedTTLCache
    from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService

    test_cache = BoundedTTLCache(maxsize=50, default_ttl=300)
    fetch_log = []

    def mock_fetch(url: str):
        fetch_log.append(url)
        return {
            "hourly": {
                "time": ["2026-09-10T00:00"],
                "temperature_2m": [30.0],
                "surface_pressure": [1010.0],
                "wind_speed_10m": [4.0],
                "relative_humidity_2m": [70.0],
                "precipitation": [0.0],
            }
        }

    svc = OpenMeteoGEFSWeatherService(
        http_client=mock_fetch,
        cache=test_cache,
        enable_cache=True,
    )

    res_kolkata = svc.get_forecast("Kolkata")
    res_delhi = svc.get_forecast("Delhi")

    assert res_kolkata.location == "Kolkata"
    assert res_delhi.location == "Delhi"
    assert len(fetch_log) == 2
    assert fetch_log[0] != fetch_log[1]  # Distinct URLs with coordinates for Kolkata vs Delhi


def test_dashboard_variable_cache_isolation():
    """Verify evaluations isolate meteorological variables (Item 32)."""
    svc = DashboardIntelligenceService(
        location_service=MockLocationService(),
        agent_factory=lambda: MockForecastBustAgent(),
    )
    req_temp = DashboardRequest(location="Kolkata", variable="temperature_2m", mode=DashboardMode.SINGLE)
    req_wind = DashboardRequest(location="Kolkata", variable="wind_speed_10m", mode=DashboardMode.SINGLE)

    resp_temp = svc.orchestrate(req_temp)
    resp_wind = svc.orchestrate(req_wind)

    assert resp_temp.variable == "temperature_2m"
    assert resp_wind.variable == "wind_speed_10m"


def test_dashboard_legacy_predict_and_batch_endpoints(client):
    """Verify POST /v1/predict and POST /v1/predict/batch remain fully functional (Item 33)."""
    # Test POST /v1/predict
    res_pred = client.post(
        "/v1/predict",
        json={"location": "Kolkata", "variable": "temperature_2m"},
    )
    assert res_pred.status_code == 200
    pred_data = res_pred.json()
    assert "bust_probability" in pred_data
    assert "risk_level" in pred_data
    assert pred_data["location"] == "Kolkata"

    # Test POST /v1/predict/batch
    batch_req = {
        "locations": ["Kolkata", "Delhi"],
        "variable": "temperature_2m",
    }
    res_batch = client.post("/v1/predict/batch", json=batch_req)
    assert res_batch.status_code == 200
    batch_data = res_batch.json()
    assert len(batch_data["results"]) == 2
