"""Authoritative Day 29 Tests for Forecast Disagreement Intelligence.

Verifies:
1. Endpoint registration and contract integrity for POST /v1/disagreement/diagnostics.
2. Real ensemble dispersion statistics (spread, range, IQR, CV).
3. Variable-aware units (°C, m/s, hPa, dimensionless).
4. Horizon scientific scope (<=240h benchmark scope vs 264h-384h extended scope).
5. Null / abstention safety (no fake 0.0 on invalid locations or missing members).
6. Disagreement != P(BUST) separation.
7. Integration with Day 28 multi-location / spatial reliability points.
8. Validation bounds and error handling.
"""
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.disagreement import (
    DisagreementStatus,
    ForecastDisagreementRequest,
    ForecastDisagreementResponse,
)
from backend.app.schemas.prediction import ReasonCode, RiskLevel, TrustState
from backend.app.schemas.weather import CanonicalForecastRecord
from backend.app.services.disagreement_service import DisagreementService


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# =====================================================================
# 1. ENDPOINT REGISTRATION & BASIC CONTRACT
# =====================================================================

def test_01_disagreement_endpoint_registered(client: TestClient):
    """POST /v1/disagreement/diagnostics is registered and returns 200 for valid location."""
    res = client.post("/v1/disagreement/diagnostics", json={
        "location": "Kolkata",
        "variable": "temperature_2m",
        "lead_hours": 24,
    })
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["location"] == "Kolkata"
    assert data["variable"] == "temperature_2m"
    assert data["lead_hours"] == 24
    assert data["lead_days"] == 1.0
    assert "request_id" in data
    assert data["request_id"].startswith("disagree_")


# =====================================================================
# 2. VARIABLE-AWARE UNITS & REAL DISPERSION METRICS
# =====================================================================

def test_02_temperature_units_and_dispersion(client: TestClient):
    """Temperature diagnostics have °C units and strictly positive or valid dispersion."""
    res = client.post("/v1/disagreement/diagnostics", json={
        "location": "Delhi",
        "variable": "temperature_2m",
        "lead_hours": 24,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in (DisagreementStatus.AVAILABLE.value, DisagreementStatus.UNAVAILABLE.value)
    if data["status"] == DisagreementStatus.AVAILABLE.value:
        diag = data["diagnostics"]
        units = data["units"]
        assert diag is not None
        assert units is not None
        assert units["spread"] == "°C"
        assert units["range"] == "°C"
        assert units["iqr"] == "°C"
        assert units["mean"] == "°C"
        assert units["cv"] == "dimensionless"
        assert units["spread_to_iqr_ratio"] == "dimensionless"
        assert diag["ensemble_spread"] >= 0.0
        assert diag["ensemble_range"] >= 0.0
        assert diag["ensemble_iqr"] >= 0.0
        assert diag["ensemble_cv"] >= 0.0
        assert data["member_count"] is not None
        assert data["member_count"] >= 1


def test_03_wind_speed_units_and_dispersion(client: TestClient):
    """Wind speed diagnostics have m/s units."""
    res = client.post("/v1/disagreement/diagnostics", json={
        "location": "Mumbai",
        "variable": "wind_speed_10m",
        "lead_hours": 24,
    })
    assert res.status_code == 200
    data = res.json()
    if data["status"] == DisagreementStatus.AVAILABLE.value:
        assert data["units"]["spread"] == "m/s"
        assert data["units"]["range"] == "m/s"
        assert data["units"]["iqr"] == "m/s"
        assert data["units"]["mean"] == "m/s"
        assert data["diagnostics"]["ensemble_spread"] >= 0.0


def test_04_surface_pressure_units_and_dispersion(client: TestClient):
    """Surface pressure diagnostics have hPa units."""
    res = client.post("/v1/disagreement/diagnostics", json={
        "location": "Chennai",
        "variable": "surface_pressure",
        "lead_hours": 24,
    })
    assert res.status_code == 200
    data = res.json()
    if data["status"] == DisagreementStatus.AVAILABLE.value:
        assert data["units"]["spread"] == "hPa"
        assert data["units"]["range"] == "hPa"
        assert data["units"]["iqr"] == "hPa"
        assert data["units"]["mean"] == "hPa"
        assert data["diagnostics"]["ensemble_spread"] >= 0.0


# =====================================================================
# 3. HORIZON SCIENTIFIC SCOPE (<=240h vs >240h)
# =====================================================================

def test_05_lead_24h_benchmark_scope(client: TestClient):
    """24h lead is WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE."""
    res = client.post("/v1/disagreement/diagnostics", json={
        "location": "Kolkata",
        "variable": "temperature_2m",
        "lead_hours": 24,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["is_certified_horizon"] is True
    assert data["scientific_scope"] == "WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE"


def test_06_lead_240h_boundary_benchmark_scope(client: TestClient):
    """240h lead boundary is WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE."""
    res = client.post("/v1/disagreement/diagnostics", json={
        "location": "Kolkata",
        "variable": "temperature_2m",
        "lead_hours": 240,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["is_certified_horizon"] is True
    assert data["scientific_scope"] == "WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE"


def test_07_lead_264h_extended_operational_scope(client: TestClient):
    """264h lead is EXTENDED_OPERATIONAL_HORIZON."""
    res = client.post("/v1/disagreement/diagnostics", json={
        "location": "Kolkata",
        "variable": "temperature_2m",
        "lead_hours": 264,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["is_certified_horizon"] is False
    assert data["scientific_scope"] == "EXTENDED_OPERATIONAL_HORIZON"


def test_08_lead_384h_extended_operational_scope(client: TestClient):
    """384h lead is EXTENDED_OPERATIONAL_HORIZON."""
    res = client.post("/v1/disagreement/diagnostics", json={
        "location": "Kolkata",
        "variable": "temperature_2m",
        "lead_hours": 384,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["is_certified_horizon"] is False
    assert data["scientific_scope"] == "EXTENDED_OPERATIONAL_HORIZON"


# =====================================================================
# 4. SAFETY, NULL HANDLING & ABSTENTION (NO ZERO CONVERSION)
# =====================================================================

def test_09_invalid_location_abstains_without_zero(client: TestClient):
    """Invalid location (Atlantis) abstains safely: null probability, null spread (NOT 0.0)."""
    res = client.post("/v1/disagreement/diagnostics", json={
        "location": "Atlantis",
        "variable": "temperature_2m",
        "lead_hours": 24,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == DisagreementStatus.ABSTAINED.value
    assert data["abstain"] is True
    assert ReasonCode.INVALID_LOCATION.value in data["reason_codes"]
    assert data["bust_probability"] is None
    assert data["risk_level"] is None
    assert data["diagnostics"] is None, "Abstained location must NOT have fake 0.0 spread"
    assert data["units"] is None


def test_10_missing_ensemble_preserves_unavailable_without_zero():
    """Unit test: When CanonicalForecastRecord has ensemble_std=None, status is UNAVAILABLE, not 0.0."""
    service = DisagreementService()
    req = ForecastDisagreementRequest(
        location="Kolkata",
        variable="temperature_2m",
        lead_hours=24,
    )
    # Mock weather service returning record with ensemble_std=None
    class MockWeatherResult:
        is_available = True
        error = None
        raw_data = {
            "records": [{
                "variable": "temperature_2m",
                "lead_hours": 24,
                "value": 28.5,
                "ensemble_mean": 28.5,
                "ensemble_std": None,  # Genuine missing spread
                "member_count": None,
            }]
        }

    class MockAgent:
        def analyze(self, pred_req):
            from backend.app.schemas.prediction import PredictionResponse
            return PredictionResponse(
                location="Kolkata",
                bust_probability=0.05,
                risk_level=RiskLevel.LOW,
                trust_state=TrustState.HIGH_CONFIDENCE,
                abstain=False,
                reason_codes=[],
                calibration_status="CALIBRATED",
            )
        def get_weather_data(self, loc, target):
            return MockWeatherResult()

    service._agent = MockAgent()
    resp = service.evaluate_disagreement(req)
    assert resp.status == DisagreementStatus.UNAVAILABLE
    assert resp.diagnostics is None, "Missing ensemble spread must remain None, not fake 0.0"
    assert resp.bust_probability == 0.05
    assert resp.risk_level == RiskLevel.LOW


# =====================================================================
# 5. DISAGREEMENT != P(BUST) SEPARATION
# =====================================================================

def test_11_disagreement_and_bust_probability_separated(client: TestClient):
    """P(BUST) and ensemble spread are separate distinct fields without deterministic coupling."""
    res = client.post("/v1/disagreement/diagnostics", json={
        "location": "Kolkata",
        "variable": "temperature_2m",
        "lead_hours": 24,
    })
    assert res.status_code == 200
    data = res.json()
    # P(BUST) is a probability (0.0 to 1.0)
    if data["bust_probability"] is not None:
        assert 0.0 <= data["bust_probability"] <= 1.0
    # Diagnostics contain physical spread with units
    if data["diagnostics"] is not None:
        assert "ensemble_spread" in data["diagnostics"]
        assert "ensemble_range" in data["diagnostics"]
        # No arbitrary "disagreement risk level" exists
        assert "disagreement_risk" not in data
        assert "disagreement_score" not in data


# =====================================================================
# 6. SPATIAL RELIABILITY INTEGRATION
# =====================================================================

def test_12_spatial_reliability_includes_disagreement_fields(client: TestClient):
    """Spatial reliability points now expose real ensemble dispersion diagnostics."""
    res = client.post("/v1/spatial/reliability", json={
        "locations": ["Kolkata", "Delhi"],
        "variable": "temperature_2m",
        "lead_hours": 24,
    })
    assert res.status_code == 200
    data = res.json()
    points = data["points"]
    assert len(points) == 2
    for pt in points:
        if not pt["abstain"]:
            assert "ensemble_spread" in pt
            assert "spread_unit" in pt
            assert pt["spread_unit"] == "°C"


# =====================================================================
# 7. INPUT VALIDATION & ERROR HANDLING
# =====================================================================

def test_13_unsupported_variable_rejected_with_422(client: TestClient):
    """Unsupported meteorological variable is rejected with 422."""
    res = client.post("/v1/disagreement/diagnostics", json={
        "location": "Kolkata",
        "variable": "tornado_index",
        "lead_hours": 24,
    })
    assert res.status_code == 422


def test_14_lead_hours_out_of_bounds_rejected_with_422(client: TestClient):
    """Lead hours <= 0 or > 384 are rejected with 422."""
    res_zero = client.post("/v1/disagreement/diagnostics", json={
        "location": "Kolkata",
        "variable": "temperature_2m",
        "lead_hours": 0,
    })
    assert res_zero.status_code == 422

    res_too_high = client.post("/v1/disagreement/diagnostics", json={
        "location": "Kolkata",
        "variable": "temperature_2m",
        "lead_hours": 400,
    })
    assert res_too_high.status_code == 422


def test_15_empty_location_rejected_with_422(client: TestClient):
    """Empty or whitespace-only location is rejected with 422."""
    res = client.post("/v1/disagreement/diagnostics", json={
        "location": "   ",
        "variable": "temperature_2m",
        "lead_hours": 24,
    })
    assert res.status_code == 422
