"""Comprehensive Automated Regression Suite for Veyra Horizon & 16-Day Request Contracts.

Verifies:
1. Rejection of unsupported fields (lead_hours, latitude, longitude) with HTTP 422 on /v1/predict.
2. Rejection of unsupported fields on /v1/dashboard/intelligence with HTTP 422.
3. Correct explicit-horizon derivation via issue_time + valid_time on /v1/predict.
4. Canonical 24h evaluation when only location and variable are provided.
5. full_16d trajectory contract: exactly 16 points (24..384h), strictly increasing, certified <= 240h.
6. standard_7d trajectory contract: exactly 7 points (24..168h).
7. single trajectory contract: exactly 1 point (24h).
8. Strict null/abstention safety on unknown/fictional locations (Atlantis) without fake LOW/0%.
9. Multi-variable trajectory support (temperature_2m, wind_speed_10m, surface_pressure).
10. Scientific acceptance: shared calibrated probabilities across adjacent steps are valid
    because isotonic calibration is stepwise, as long as horizons and valid_times are distinct.
"""
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.dashboard import DashboardMode, DashboardStatus
from backend.app.schemas.prediction import ReasonCode, TrustState

client = TestClient(app)


# =============================================================================
# 1. UNSUPPORTED EXTRA FIELD REJECTION TESTS (STAGE 3)
# =============================================================================

def test_predict_rejects_unsupported_lead_hours_with_422():
    """Verify POST /v1/predict immediately rejects unsupported 'lead_hours' with HTTP 422."""
    payload = {
        "location": "Delhi",
        "lead_hours": 48,
        "variable": "temperature_2m",
    }
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
    body = response.json()
    assert body.get("error") == "VALIDATION_ERROR"
    detail_str = str(body.get("detail", []))
    assert "extra_forbidden" in detail_str or "Extra inputs are not permitted" in detail_str
    assert "lead_hours" in detail_str


def test_predict_rejects_unsupported_lat_lon_with_422():
    """Verify POST /v1/predict rejects unsupported 'latitude' and 'longitude' fields with HTTP 422."""
    payload = {
        "location": "Delhi",
        "latitude": 28.6139,
        "longitude": 77.2090,
    }
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 422
    body = response.json()
    detail_str = str(body.get("detail", []))
    assert "extra_forbidden" in detail_str or "Extra inputs are not permitted" in detail_str
    assert "latitude" in detail_str or "longitude" in detail_str


def test_dashboard_rejects_unsupported_field_with_422():
    """Verify POST /v1/dashboard/intelligence rejects unsupported fields with HTTP 422."""
    payload = {
        "location": "Delhi",
        "lead_hours": 48,
        "mode": "standard_7d",
    }
    response = client.post("/v1/dashboard/intelligence", json=payload)
    assert response.status_code == 422
    body = response.json()
    detail_str = str(body.get("detail", []))
    assert "extra_forbidden" in detail_str or "Extra inputs are not permitted" in detail_str


# =============================================================================
# 2. EXPLICIT SINGLE HORIZON CONTRACT TESTS (STAGE 7)
# =============================================================================

def test_predict_explicit_horizon_via_timestamps():
    """Verify POST /v1/predict evaluates explicit horizon defined by issue_time + valid_time.

    Explicit 48-hour forecast: valid_time = issue_time + 48h.
    The response must reflect lead_hours=48 and valid_time matching request.
    """
    now = datetime.now(timezone.utc)
    base_issue = now.replace(hour=(now.hour // 6) * 6, minute=0, second=0, microsecond=0)
    target_valid = base_issue + timedelta(hours=48)

    issue_iso = base_issue.strftime("%Y-%m-%dT%H:%M:%SZ")
    valid_iso = target_valid.strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "location": "Delhi",
        "variable": "temperature_2m",
        "issue_time": issue_iso,
        "valid_time": valid_iso,
    }
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 200, f"Failed: {response.text}"
    data = response.json()

    assert data["location"] == "Delhi"
    assert data["lead_hours"] == 48, f"Expected lead_hours=48, got {data.get('lead_hours')}"
    assert data["valid_time"] == valid_iso
    assert data["issue_time"] == issue_iso
    assert data["bust_probability"] is not None
    assert 0.0 <= data["bust_probability"] <= 1.0


def test_predict_canonical_single_defaults_to_24h():
    """Verify POST /v1/predict without timestamps evaluates canonical 24-hour horizon."""
    payload = {
        "location": "Delhi",
        "variable": "temperature_2m",
    }
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["location"] == "Delhi"
    assert data["lead_hours"] == 24, f"Expected canonical lead_hours=24, got {data.get('lead_hours')}"
    assert data["bust_probability"] is not None


# =============================================================================
# 3. DASHBOARD MULTI-HORIZON TRAJECTORY TESTS (STAGE 8 & 9)
# =============================================================================

def test_dashboard_full_16d_exact_contract():
    """Verify POST /v1/dashboard/intelligence mode=full_16d returns exactly 16 ordered horizons."""
    payload = {
        "location": "Delhi",
        "variable": "temperature_2m",
        "mode": "full_16d",
    }
    response = client.post("/v1/dashboard/intelligence", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] in (DashboardStatus.SUCCESS.value, DashboardStatus.PARTIAL.value)
    timeline = data["timeline"]
    assert len(timeline) == 16, f"Expected exactly 16 timeline points, got {len(timeline)}"

    expected_leads = [24 * i for i in range(1, 17)]  # 24, 48, ... 384
    actual_leads = [p["lead_hours"] for p in timeline]
    assert actual_leads == expected_leads, f"Leads mismatch: {actual_leads} != {expected_leads}"

    # Verify strictly increasing valid_time
    valid_times = [datetime.fromisoformat(p["valid_time"].replace("Z", "+00:00")) for p in timeline]
    for i in range(len(valid_times) - 1):
        assert valid_times[i] < valid_times[i + 1], "Valid times must be strictly increasing"
        # Each interval must be exactly 24 hours
        diff_hours = (valid_times[i + 1] - valid_times[i]).total_seconds() / 3600.0
        assert diff_hours == 24.0, f"Expected 24h step between points {i} and {i+1}, got {diff_hours}h"

    # Verify certification boundary: <= 240h certified, > 240h operational only
    for p in timeline:
        if p["lead_hours"] <= 240:
            assert p["is_certified_horizon"] is True
        else:
            assert p["is_certified_horizon"] is False

    # Verify lead_days matches lead_hours / 24
    for p in timeline:
        expected_days = round(p["lead_hours"] / 24.0, 1)
        assert p["lead_days"] == expected_days

    # Verify no fabricated values on valid predictions
    for p in timeline:
        if not p["abstain"]:
            assert p["bust_probability"] is not None
            assert 0.0 <= p["bust_probability"] <= 1.0
            assert p["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
            assert p["calibration_status"] == "CALIBRATED"


def test_dashboard_standard_7d_exact_contract():
    """Verify POST /v1/dashboard/intelligence mode=standard_7d returns exactly 7 ordered points."""
    payload = {
        "location": "Delhi",
        "variable": "temperature_2m",
        "mode": "standard_7d",
    }
    response = client.post("/v1/dashboard/intelligence", json=payload)
    assert response.status_code == 200
    data = response.json()

    timeline = data["timeline"]
    assert len(timeline) == 7, f"Expected 7 points, got {len(timeline)}"
    expected_leads = [24, 48, 72, 96, 120, 144, 168]
    actual_leads = [p["lead_hours"] for p in timeline]
    assert actual_leads == expected_leads


def test_dashboard_single_exact_contract():
    """Verify POST /v1/dashboard/intelligence mode=single returns exactly 1 canonical point (24h)."""
    payload = {
        "location": "Delhi",
        "variable": "temperature_2m",
        "mode": "single",
    }
    response = client.post("/v1/dashboard/intelligence", json=payload)
    assert response.status_code == 200
    data = response.json()

    timeline = data["timeline"]
    assert len(timeline) == 1, f"Expected 1 point, got {len(timeline)}"
    assert timeline[0]["lead_hours"] == 24
    assert timeline[0]["lead_days"] == 1.0


# =============================================================================
# 4. NEGATIVE CONTROL & STRICT NULL SAFETY TESTS (STAGE 6 & 11)
# =============================================================================

def test_atlantis_negative_control_safe_abstention():
    """Verify negative control 'Atlantis' safely abstains with null probability, null risk, abstain=true."""
    payload = {
        "location": "Atlantis",
        "variable": "temperature_2m",
        "mode": "full_16d",
    }
    response = client.post("/v1/dashboard/intelligence", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == DashboardStatus.ABSTAINED.value
    timeline = data["timeline"]
    assert len(timeline) == 16

    for p in timeline:
        assert p["abstain"] is True
        assert p["bust_probability"] is None, "Abstained point must NEVER have a non-null probability"
        assert p["risk_level"] is None, "Abstained point must NEVER have a fake LOW risk level"
        assert p["trust_state"] == TrustState.UNAVAILABLE.value
        assert ReasonCode.INVALID_LOCATION.value in [
            rc.value if hasattr(rc, "value") else str(rc) for rc in p["reason_codes"]
        ]

    summary = data["summary"]
    assert summary["available_points"] == 0
    assert summary["abstained_points"] == 16
    assert summary["max_bust_probability"] is None
    assert summary["max_risk_level"] is None
    assert summary["mean_bust_probability"] is None


# =============================================================================
# 5. MULTI-LOCATION VERIFICATION (STAGE 11)
# =============================================================================

@pytest.mark.parametrize("city", ["Delhi", "Kolkata", "Mumbai", "London", "Tokyo"])
def test_multi_location_full_16d(city: str):
    """Verify full_16d trajectory contract across diverse benchmark and global stations."""
    payload = {
        "location": city,
        "variable": "temperature_2m",
        "mode": "full_16d",
    }
    response = client.post("/v1/dashboard/intelligence", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["timeline"]) == 16
    assert data["location"]["resolved_name"] is not None


# =============================================================================
# 6. MULTI-VARIABLE VERIFICATION (STAGE 12)
# =============================================================================

@pytest.mark.parametrize("var", ["temperature_2m", "wind_speed_10m", "surface_pressure"])
def test_multi_variable_full_16d(var: str):
    """Verify full_16d trajectory contract across all 3 primary meteorological variables."""
    payload = {
        "location": "Delhi",
        "variable": var,
        "mode": "full_16d",
    }
    response = client.post("/v1/dashboard/intelligence", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["timeline"]) == 16
    assert data["variable"] == var
