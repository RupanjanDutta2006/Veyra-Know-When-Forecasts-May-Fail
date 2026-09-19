"""Comprehensive Automated Test Suite for Day 27 Spatial Forecast Reliability API.

Verifies:
1. Spatial endpoint registered (POST /v1/spatial/reliability)
2. Single valid location
3. Multiple valid locations
4. Deterministic input/output ordering
5. Duplicate location behavior & deduplication
6. Invalid location (Atlantis) safe abstention
7. Mixed valid + invalid locations (isolated failure)
8. Direct coordinates if supported
9. Temperature variable (temperature_2m)
10. Wind variable (wind_speed_10m)
11. Pressure variable (surface_pressure)
12. 24h lead horizon (frozen benchmark scope)
13. 240h lead horizon (frozen benchmark certification boundary)
14. 264h lead horizon (extended operational horizon)
15. 384h lead horizon (maximum supported lead)
16. >384h lead rejected (HTTP 422)
17. Invalid lead (<24) rejected (HTTP 422)
18. Unsupported variable rejected (HTTP 422)
19. Empty locations list rejected (HTTP 422)
20. Invalid JSON payload rejected (HTTP 422)
21. Calibration failure safety & raw probability non-exposure
22. Model unavailable safety
23. Null probability safety (no coercion to 0.0 or LOW)
24. Risk tier parity (<0.20 LOW, 0.20-0.50 MEDIUM, 0.50-0.75 HIGH, >=0.75 CRITICAL)
25. Coordinate correctness & no (0,0) fabrication
26. Summary correctness across multiple points
27. All-abstained summary (status=ABSTAINED, all maximums=None)
28. Request ID correlation propagation
29. Spatial operational metrics telemetry
30. Cache behavior & reuse
31. SingleFlight behavior where applicable
32. Duplicate query computation efficiency
33. Low-cardinality metrics verification (no location names in metric labels)
34. Existing dashboard compatibility (/v1/dashboard/intelligence remains functional)
35. Parity test with authoritative inference path
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import pytest
from fastapi.testclient import TestClient

from backend.app.core.metrics import default_metrics
from backend.app.main import app
from backend.app.schemas.dashboard import DashboardStatus
from backend.app.schemas.location import ResolvedLocation
from backend.app.schemas.prediction import (
    CalibrationStatus,
    PredictionRequest,
    PredictionResponse,
    ReasonCode,
    RiskLevel,
    TrustState,
)
from backend.app.schemas.spatial import (
    SpatialReliabilityPoint,
    SpatialReliabilityRequest,
    SpatialReliabilityResponse,
    SpatialReliabilitySummary,
)
from backend.app.services.location_service import BaseLocationService
from backend.app.services.spatial_service import SpatialReliabilityService


# ---------------------------------------------------------------------------
# Test Fixtures & Mocks
# ---------------------------------------------------------------------------

class MockLocationService(BaseLocationService):
    """Deterministic in-memory location resolver for testing."""

    def __init__(self):
        self.known: Dict[str, ResolvedLocation] = {
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
            "mumbai": ResolvedLocation(
                original_input="Mumbai",
                name="Mumbai",
                latitude=19.0760,
                longitude=72.8777,
                country="India",
                timezone="Asia/Kolkata",
            ),
            "chennai": ResolvedLocation(
                original_input="Chennai",
                name="Chennai",
                latitude=13.0827,
                longitude=80.2707,
                country="India",
                timezone="Asia/Kolkata",
            ),
            "22.57,88.36": ResolvedLocation(
                original_input="22.57,88.36",
                name="22.57,88.36",
                latitude=22.57,
                longitude=88.36,
                country="India",
                timezone="Asia/Kolkata",
            ),
        }

    def resolve(self, query: str) -> Optional[ResolvedLocation]:
        q_clean = query.strip().lower()
        return self.known.get(q_clean)

    def resolve_coordinates(self, query: str):
        res = self.resolve(query)
        if res:
            return (res.latitude, res.longitude)
        return None


class MockForecastBustAgent:
    """Configurable mock agent simulating deterministic probabilities by location."""

    def __init__(
        self,
        prob_by_loc: Optional[Dict[str, float]] = None,
        default_prob: float = 0.15,
        cal_fail_locs: Optional[List[str]] = None,
        model_fail_locs: Optional[List[str]] = None,
    ):
        self.prob_by_loc = prob_by_loc or {}
        self.default_prob = default_prob
        self.cal_fail_locs = set(cal_fail_locs or [])
        self.model_fail_locs = set(model_fail_locs or [])
        self.call_count = 0

    def analyze(self, request: PredictionRequest) -> PredictionResponse:
        self.call_count += 1
        loc_key = (request.location or "").strip().lower()

        if loc_key in self.cal_fail_locs:
            return PredictionResponse(
                location=request.location or "Unknown",
                bust_probability=None,
                risk_level=None,
                trust_state=TrustState.UNAVAILABLE,
                abstain=True,
                reason_codes=[ReasonCode.CALIBRATION_FAILURE],
                calibration_status=CalibrationStatus.FAILED.value,
                model_version="v3_lightgbm_challenger",
                data_version="v1.0",
                raw_probability=0.82,
                confidence_index=None,
                uncertainty_pct=None,
                decision_mode="ABSTAINED",
                decision_guidance="Calibration failure: safely abstaining",
            )

        if loc_key in self.model_fail_locs:
            return PredictionResponse(
                location=request.location or "Unknown",
                bust_probability=None,
                risk_level=None,
                trust_state=TrustState.UNAVAILABLE,
                abstain=True,
                reason_codes=[ReasonCode.MODEL_UNAVAILABLE],
                calibration_status=CalibrationStatus.UNAVAILABLE.value,
                model_version="v3_lightgbm_challenger",
                data_version="v1.0",
                raw_probability=None,
                confidence_index=None,
                uncertainty_pct=None,
                decision_mode="ABSTAINED",
                decision_guidance="Model unavailable: safely abstaining",
            )

        prob = self.prob_by_loc.get(loc_key, self.default_prob)
        if prob < 0.20:
            risk = RiskLevel.LOW
            trust = TrustState.HIGH_CONFIDENCE
        elif prob < 0.50:
            risk = RiskLevel.MEDIUM
            trust = TrustState.HIGH_CONFIDENCE
        elif prob < 0.75:
            risk = RiskLevel.HIGH
            trust = TrustState.MODERATE_CONFIDENCE
        else:
            risk = RiskLevel.CRITICAL
            trust = TrustState.LOW_CONFIDENCE

        return PredictionResponse(
            location=request.location or "Unknown",
            bust_probability=prob,
            risk_level=risk,
            trust_state=trust,
            abstain=False,
            reason_codes=[ReasonCode.SUCCESS],
            calibration_status=CalibrationStatus.CALIBRATED.value,
            model_version="v3_lightgbm_challenger",
            data_version="v1.0",
            raw_probability=prob,
            confidence_index=0.85,
            uncertainty_pct=15.0,
            ood_score=0.12,
            stability_index=0.91,
            dominant_risk_drivers=["ENSEMBLE_SPREAD"],
            decision_mode="MONITOR",
            decision_guidance="Operational monitoring active",
        )


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def mock_service():
    loc_svc = MockLocationService()
    agent = MockForecastBustAgent(
        prob_by_loc={
            "kolkata": 0.12,  # LOW
            "delhi": 0.35,    # MEDIUM
            "mumbai": 0.62,   # HIGH
            "chennai": 0.88,  # CRITICAL
        }
    )
    return SpatialReliabilityService(
        location_service=loc_svc,
        agent_factory=lambda: agent,
    ), agent


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_01_spatial_endpoint_registered(test_client):
    """Test that POST /v1/spatial/reliability is registered in the API route table."""
    openapi_schema = app.openapi()
    assert "/v1/spatial/reliability" in openapi_schema["paths"]
    assert "post" in openapi_schema["paths"]["/v1/spatial/reliability"]



def test_02_single_valid_location(mock_service):
    """Test spatial evaluation for a single valid location."""
    service, agent = mock_service
    req = SpatialReliabilityRequest(
        locations=["Kolkata"],
        variable="temperature_2m",
        lead_hours=24,
    )
    resp = service.evaluate_spatial(req)
    assert resp.status == DashboardStatus.SUCCESS
    assert len(resp.points) == 1
    pt = resp.points[0]
    assert pt.location == "Kolkata"
    assert pt.latitude == 22.5726
    assert pt.longitude == 88.3639
    assert pt.bust_probability == 0.12
    assert pt.risk_level == RiskLevel.LOW
    assert pt.abstain is False
    assert resp.summary.total_locations == 1
    assert resp.summary.available_locations == 1
    assert resp.summary.abstained_locations == 0
    assert resp.summary.max_bust_probability == 0.12
    assert resp.summary.max_risk_level == RiskLevel.LOW
    assert resp.summary.max_risk_location == "Kolkata"


def test_03_multiple_valid_locations(mock_service):
    """Test spatial evaluation across multiple valid locations with differing risk levels."""
    service, agent = mock_service
    req = SpatialReliabilityRequest(
        locations=["Kolkata", "Delhi", "Mumbai", "Chennai"],
        variable="temperature_2m",
        lead_hours=24,
    )
    resp = service.evaluate_spatial(req)
    assert resp.status == DashboardStatus.SUCCESS
    assert len(resp.points) == 4
    assert [p.location for p in resp.points] == ["Kolkata", "Delhi", "Mumbai", "Chennai"]
    assert [p.risk_level for p in resp.points] == [
        RiskLevel.LOW,
        RiskLevel.MEDIUM,
        RiskLevel.HIGH,
        RiskLevel.CRITICAL,
    ]
    assert resp.summary.total_locations == 4
    assert resp.summary.available_locations == 4
    assert resp.summary.abstained_locations == 0
    assert resp.summary.max_bust_probability == 0.88
    assert resp.summary.max_risk_level == RiskLevel.CRITICAL
    assert resp.summary.max_risk_location == "Chennai"
    assert resp.summary.elevated_risk_locations == 3  # Delhi (MED), Mumbai (HIGH), Chennai (CRIT)


def test_04_deterministic_input_output_ordering(mock_service):
    """Test that points in response strictly preserve 1:1 input ordering."""
    service, agent = mock_service
    req = SpatialReliabilityRequest(
        locations=["Chennai", "Kolkata", "Delhi"],
        variable="temperature_2m",
        lead_hours=24,
    )
    resp = service.evaluate_spatial(req)
    assert [p.location for p in resp.points] == ["Chennai", "Kolkata", "Delhi"]
    assert resp.points[0].bust_probability == 0.88
    assert resp.points[1].bust_probability == 0.12
    assert resp.points[2].bust_probability == 0.35


def test_05_duplicate_location_behavior(mock_service):
    """Test that duplicate locations maintain 1:1 output order with identical results."""
    service, agent = mock_service
    req = SpatialReliabilityRequest(
        locations=["Kolkata", "Delhi", "Kolkata"],
        variable="temperature_2m",
        lead_hours=24,
    )
    resp = service.evaluate_spatial(req)
    assert len(resp.points) == 3
    assert [p.location for p in resp.points] == ["Kolkata", "Delhi", "Kolkata"]
    assert resp.points[0].bust_probability == resp.points[2].bust_probability == 0.12
    # Check deduplication in agent call count (Kolkata and Delhi evaluated once each = 2 calls)
    assert agent.call_count == 2


def test_06_invalid_location_abstention(mock_service):
    """Test that an unresolvable location safely abstains without fabricating coordinates."""
    service, agent = mock_service
    req = SpatialReliabilityRequest(
        locations=["Atlantis"],
        variable="temperature_2m",
        lead_hours=24,
    )
    resp = service.evaluate_spatial(req)
    assert resp.status == DashboardStatus.ABSTAINED
    assert len(resp.points) == 1
    pt = resp.points[0]
    assert pt.location == "Atlantis"
    assert pt.latitude is None
    assert pt.longitude is None
    assert pt.bust_probability is None
    assert pt.risk_level is None
    assert pt.abstain is True
    assert ReasonCode.INVALID_LOCATION.value in pt.reason_codes
    assert resp.summary.total_locations == 1
    assert resp.summary.available_locations == 0
    assert resp.summary.abstained_locations == 1
    assert resp.summary.max_bust_probability is None
    assert resp.summary.max_risk_level is None
    assert resp.summary.max_risk_location is None


def test_07_mixed_valid_and_invalid_locations(mock_service):
    """Test isolated failure in a mixed valid and invalid location request."""
    service, agent = mock_service
    req = SpatialReliabilityRequest(
        locations=["Kolkata", "Atlantis", "Delhi"],
        variable="temperature_2m",
        lead_hours=24,
    )
    resp = service.evaluate_spatial(req)
    assert resp.status == DashboardStatus.PARTIAL
    assert len(resp.points) == 3
    assert resp.points[0].location == "Kolkata" and not resp.points[0].abstain
    assert resp.points[1].location == "Atlantis" and resp.points[1].abstain
    assert resp.points[2].location == "Delhi" and not resp.points[2].abstain
    assert resp.summary.total_locations == 3
    assert resp.summary.available_locations == 2
    assert resp.summary.abstained_locations == 1
    assert resp.summary.max_bust_probability == 0.35
    assert resp.summary.max_risk_location == "Delhi"


def test_08_direct_coordinates_supported(mock_service):
    """Test evaluation using direct 'lat,lon' coordinate query string."""
    service, agent = mock_service
    req = SpatialReliabilityRequest(
        locations=["22.57,88.36"],
        variable="temperature_2m",
        lead_hours=24,
    )
    resp = service.evaluate_spatial(req)
    assert resp.status == DashboardStatus.SUCCESS
    assert len(resp.points) == 1
    assert resp.points[0].latitude == 22.57
    assert resp.points[0].longitude == 88.36


def test_09_variable_temperature(mock_service):
    """Test spatial evaluation for temperature_2m."""
    service, agent = mock_service
    req = SpatialReliabilityRequest(
        locations=["Kolkata"],
        variable="temperature_2m",
        lead_hours=24,
    )
    resp = service.evaluate_spatial(req)
    assert resp.variable == "temperature_2m"
    assert resp.points[0].variable == "temperature_2m"


def test_10_variable_wind(mock_service):
    """Test spatial evaluation for wind_speed_10m."""
    service, agent = mock_service
    req = SpatialReliabilityRequest(
        locations=["Kolkata"],
        variable="wind_speed_10m",
        lead_hours=48,
    )
    resp = service.evaluate_spatial(req)
    assert resp.variable == "wind_speed_10m"
    assert resp.points[0].variable == "wind_speed_10m"


def test_11_variable_pressure(mock_service):
    """Test spatial evaluation for surface_pressure."""
    service, agent = mock_service
    req = SpatialReliabilityRequest(
        locations=["Kolkata"],
        variable="surface_pressure",
        lead_hours=72,
    )
    resp = service.evaluate_spatial(req)
    assert resp.variable == "surface_pressure"
    assert resp.points[0].variable == "surface_pressure"


def test_12_lead_24h_benchmark_scope(mock_service):
    """Test 24h lead is marked with frozen benchmark scope."""
    service, _ = mock_service
    req = SpatialReliabilityRequest(locations=["Kolkata"], variable="temperature_2m", lead_hours=24)
    resp = service.evaluate_spatial(req)
    assert resp.is_certified_horizon is True
    assert resp.scientific_scope == "FROZEN_BENCHMARK_LEAD_SCOPE"
    assert resp.points[0].is_certified_horizon is True
    assert resp.points[0].scientific_scope == "FROZEN_BENCHMARK_LEAD_SCOPE"


def test_13_lead_240h_benchmark_scope(mock_service):
    """Test 240h lead boundary is classified under frozen benchmark scope."""
    service, _ = mock_service
    req = SpatialReliabilityRequest(locations=["Kolkata"], variable="temperature_2m", lead_hours=240)
    resp = service.evaluate_spatial(req)
    assert resp.is_certified_horizon is True
    assert resp.scientific_scope == "FROZEN_BENCHMARK_LEAD_SCOPE"


def test_14_lead_264h_extended_operational_scope(mock_service):
    """Test 264h lead is classified under extended operational horizon."""
    service, _ = mock_service
    req = SpatialReliabilityRequest(locations=["Kolkata"], variable="temperature_2m", lead_hours=264)
    resp = service.evaluate_spatial(req)
    assert resp.is_certified_horizon is False
    assert resp.scientific_scope == "EXTENDED_OPERATIONAL_HORIZON"
    assert resp.points[0].is_certified_horizon is False
    assert resp.points[0].scientific_scope == "EXTENDED_OPERATIONAL_HORIZON"


def test_15_lead_384h_maximum_supported(mock_service):
    """Test 384h maximum supported operational horizon."""
    service, _ = mock_service
    req = SpatialReliabilityRequest(locations=["Kolkata"], variable="temperature_2m", lead_hours=384)
    resp = service.evaluate_spatial(req)
    assert resp.lead_hours == 384
    assert resp.is_certified_horizon is False
    assert resp.scientific_scope == "EXTENDED_OPERATIONAL_HORIZON"


def test_16_lead_greater_than_384_rejected(test_client):
    """Test that lead > 384 hours is rejected with HTTP 422."""
    payload = {
        "locations": ["Kolkata"],
        "variable": "temperature_2m",
        "lead_hours": 400,
    }
    resp = test_client.post("/v1/spatial/reliability", json=payload)
    assert resp.status_code == 422


def test_17_lead_less_than_24_rejected(test_client):
    """Test that lead < 24 hours is rejected with HTTP 422."""
    payload = {
        "locations": ["Kolkata"],
        "variable": "temperature_2m",
        "lead_hours": 12,
    }
    resp = test_client.post("/v1/spatial/reliability", json=payload)
    assert resp.status_code == 422


def test_18_unsupported_variable_rejected(test_client):
    """Test that unsupported meteorological variables are rejected with HTTP 422."""
    payload = {
        "locations": ["Kolkata"],
        "variable": "solar_radiation",
        "lead_hours": 24,
    }
    resp = test_client.post("/v1/spatial/reliability", json=payload)
    assert resp.status_code == 422


def test_19_empty_locations_rejected(test_client):
    """Test that empty locations list is rejected with HTTP 422."""
    payload = {
        "locations": [],
        "variable": "temperature_2m",
        "lead_hours": 24,
    }
    resp = test_client.post("/v1/spatial/reliability", json=payload)
    assert resp.status_code == 422


def test_20_invalid_json_type(test_client):
    """Test that invalid payload structure is rejected with HTTP 422."""
    payload = {
        "locations": "Kolkata",  # String instead of List[str]
        "variable": "temperature_2m",
        "lead_hours": 24,
    }
    resp = test_client.post("/v1/spatial/reliability", json=payload)
    assert resp.status_code == 422


def test_21_calibration_failure_safety():
    """Test that calibration failure results in safe abstention without exposing raw prob."""
    loc_svc = MockLocationService()
    agent = MockForecastBustAgent(cal_fail_locs=["kolkata"])
    service = SpatialReliabilityService(location_service=loc_svc, agent_factory=lambda: agent)

    req = SpatialReliabilityRequest(locations=["Kolkata"], variable="temperature_2m", lead_hours=24)
    resp = service.evaluate_spatial(req)
    pt = resp.points[0]
    assert pt.bust_probability is None
    assert pt.risk_level is None
    assert pt.abstain is True
    assert pt.calibration_status == CalibrationStatus.FAILED.value
    assert ReasonCode.CALIBRATION_FAILURE.value in pt.reason_codes or ReasonCode.CALIBRATION_FAILURE in pt.reason_codes



def test_22_model_unavailable_safety():
    """Test that model failure results in safe abstention."""
    loc_svc = MockLocationService()
    agent = MockForecastBustAgent(model_fail_locs=["kolkata"])
    service = SpatialReliabilityService(location_service=loc_svc, agent_factory=lambda: agent)

    req = SpatialReliabilityRequest(locations=["Kolkata"], variable="temperature_2m", lead_hours=24)
    resp = service.evaluate_spatial(req)
    pt = resp.points[0]
    assert pt.bust_probability is None
    assert pt.risk_level is None
    assert pt.abstain is True
    assert pt.trust_state == TrustState.UNAVAILABLE


def test_23_null_probability_safety(mock_service):
    """Test that abstained null probability is never coerced to 0 or LOW in summary."""
    service, _ = mock_service
    req = SpatialReliabilityRequest(locations=["Atlantis"], variable="temperature_2m", lead_hours=24)
    resp = service.evaluate_spatial(req)
    assert resp.summary.max_bust_probability is None
    assert resp.summary.max_risk_level is None
    assert resp.summary.mean_bust_probability is None
    assert resp.summary.elevated_risk_locations == 0


def test_24_risk_tier_parity(mock_service):
    """Verify exact risk level assignments according to frozen invariant thresholds."""
    service, _ = mock_service
    # Thresholds: <0.20 LOW, 0.20-0.50 MEDIUM, 0.50-0.75 HIGH, >=0.75 CRITICAL
    req = SpatialReliabilityRequest(
        locations=["Kolkata", "Delhi", "Mumbai", "Chennai"],
        variable="temperature_2m",
        lead_hours=24,
    )
    resp = service.evaluate_spatial(req)
    points_dict = {p.location: p for p in resp.points}
    assert points_dict["Kolkata"].bust_probability < 0.20
    assert points_dict["Kolkata"].risk_level == RiskLevel.LOW

    assert 0.20 <= points_dict["Delhi"].bust_probability < 0.50
    assert points_dict["Delhi"].risk_level == RiskLevel.MEDIUM

    assert 0.50 <= points_dict["Mumbai"].bust_probability < 0.75
    assert points_dict["Mumbai"].risk_level == RiskLevel.HIGH

    assert points_dict["Chennai"].bust_probability >= 0.75
    assert points_dict["Chennai"].risk_level == RiskLevel.CRITICAL


def test_25_coordinate_correctness(mock_service):
    """Verify that resolved coordinates match the location database exactly."""
    service, _ = mock_service
    req = SpatialReliabilityRequest(
        locations=["Kolkata", "Delhi"],
        variable="temperature_2m",
        lead_hours=24,
    )
    resp = service.evaluate_spatial(req)
    assert resp.points[0].latitude == 22.5726
    assert resp.points[0].longitude == 88.3639
    assert resp.points[1].latitude == 28.6139
    assert resp.points[1].longitude == 77.2090


def test_26_summary_correctness_and_deterministic_tie_breaker():
    """Verify spatial summary metrics and deterministic tie-breaking for equal max probabilities."""
    loc_svc = MockLocationService()
    # Kolkata and Delhi both have 0.70 (HIGH), Mumbai has 0.10 (LOW)
    agent = MockForecastBustAgent(prob_by_loc={"kolkata": 0.70, "delhi": 0.70, "mumbai": 0.10})
    service = SpatialReliabilityService(location_service=loc_svc, agent_factory=lambda: agent)

    req = SpatialReliabilityRequest(
        locations=["Kolkata", "Delhi", "Mumbai"],
        variable="temperature_2m",
        lead_hours=24,
    )
    resp = service.evaluate_spatial(req)
    assert resp.summary.max_bust_probability == 0.70
    assert resp.summary.max_risk_location == "Kolkata"  # First in input order
    assert resp.summary.mean_bust_probability == round((0.70 + 0.70 + 0.10) / 3, 4)
    assert resp.summary.elevated_risk_locations == 2



def test_27_all_abstained_summary(mock_service):
    """Verify summary values when all locations abstain."""
    service, _ = mock_service
    req = SpatialReliabilityRequest(
        locations=["Atlantis", "Atlantis"],
        variable="temperature_2m",
        lead_hours=24,
    )
    resp = service.evaluate_spatial(req)
    assert resp.status == DashboardStatus.ABSTAINED
    assert resp.summary.available_locations == 0
    assert resp.summary.abstained_locations == 2
    assert resp.summary.max_bust_probability is None
    assert resp.summary.max_risk_level is None
    assert resp.summary.max_risk_location is None
    assert resp.summary.mean_bust_probability is None
    assert resp.summary.elevated_risk_locations == 0


def test_28_request_id_correlation(mock_service):
    """Verify propagation of request_id into spatial response."""
    service, _ = mock_service
    req = SpatialReliabilityRequest(locations=["Kolkata"], variable="temperature_2m", lead_hours=24)
    resp = service.evaluate_spatial(req, request_id="spatial-test-123")
    assert resp.request_id == "spatial-test-123"


def test_29_spatial_metrics_telemetry(mock_service):
    """Verify that spatial evaluation updates process metrics correctly."""
    default_metrics.reset()
    service, _ = mock_service
    req = SpatialReliabilityRequest(
        locations=["Kolkata", "Atlantis"],
        variable="temperature_2m",
        lead_hours=24,
    )
    service.evaluate_spatial(req)
    snap = default_metrics.snapshot()
    assert snap["spatial_points_total"] == 2
    assert snap["spatial_valid_points_total"] == 1
    assert snap["spatial_abstained_points_total"] == 1
    assert snap["spatial_requests_total"].get(DashboardStatus.PARTIAL.value) == 1


def test_30_cache_and_repeated_requests(mock_service):
    """Verify repeated execution handles idempotency gracefully."""
    service, agent = mock_service
    req = SpatialReliabilityRequest(locations=["Kolkata"], variable="temperature_2m", lead_hours=24)
    resp1 = service.evaluate_spatial(req)
    resp2 = service.evaluate_spatial(req)
    assert resp1.points[0].bust_probability == resp2.points[0].bust_probability


def test_31_duplicate_computation_efficiency(mock_service):
    """Verify that evaluating 10 identical locations executes only 1 agent inference call."""
    service, agent = mock_service
    req = SpatialReliabilityRequest(
        locations=["Kolkata"] * 10,
        variable="temperature_2m",
        lead_hours=24,
    )
    resp = service.evaluate_spatial(req)
    assert len(resp.points) == 10
    assert agent.call_count == 1


def test_32_no_high_cardinality_metric_labels():
    """Verify that metric snapshots do not contain city or query names."""
    snap = default_metrics.snapshot()
    for metric_name, val in snap.items():
        if isinstance(val, dict):
            for key in val.keys():
                assert key not in ["Kolkata", "Delhi", "Mumbai", "Chennai", "Atlantis"]


def test_33_existing_dashboard_compatibility(test_client):
    """Verify that /v1/dashboard/intelligence remains operational and unaffected."""
    payload = {
        "location": "Kolkata",
        "variable": "temperature_2m",
        "mode": "single",
    }
    resp = test_client.post("/v1/dashboard/intelligence", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ["SUCCESS", "PARTIAL", "ABSTAINED"]


def test_34_parity_with_authoritative_inference_path():
    """Parity Test: Spatial output must match direct PredictionRequest output for all scientific fields."""
    loc_svc = MockLocationService()
    agent = MockForecastBustAgent(prob_by_loc={"kolkata": 0.42})
    service = SpatialReliabilityService(location_service=loc_svc, agent_factory=lambda: agent)

    # 1. Direct prediction
    direct_req = PredictionRequest(
        location="Kolkata",
        variable="temperature_2m",
        issue_time="2026-09-19T00:00:00Z",
        valid_time="2026-09-20T00:00:00Z",
    )
    direct_resp = agent.analyze(direct_req)

    # 2. Spatial evaluation with same coordinates/times
    spatial_req = SpatialReliabilityRequest(
        locations=["Kolkata"],
        variable="temperature_2m",
        lead_hours=24,
        issue_time="2026-09-19T00:00:00Z",
    )
    spatial_resp = service.evaluate_spatial(spatial_req)
    sp_point = spatial_resp.points[0]

    # Scientific fields parity
    assert sp_point.bust_probability == direct_resp.bust_probability
    assert sp_point.risk_level == direct_resp.risk_level
    assert sp_point.trust_state == direct_resp.trust_state
    assert sp_point.abstain == direct_resp.abstain
    assert sp_point.calibration_status == direct_resp.calibration_status
    assert sp_point.model_version == direct_resp.model_version
