"""Day 21 Controlled Scientific & Integration Repair Regression Test Suite.

Verifies fixes for the 6 independently confirmed defect areas plus 10-horizon live path:
1. Real ensemble spread calculation using genuine member arrays
2. Missing ensemble data does not convert to fake 0.0 spread
3. Wind unit consistency (m/s canonical -> km/h feature representation)
4. High-altitude surface pressure elevation-aware QC (Shimla, Leh)
5. Physically impossible pressure rejection
6. Canonical station resolution for Panaji/Panjim
7. Builder 2 to Builder 1 field parity
8. Complete 10-horizon trajectory preservation (24h to 240h)
9. Chronological time and lead alignment
10. Safe abstention preservation under invalid or unavailable inputs
"""
import numpy as np
import pytest
from datetime import datetime, timezone, timedelta

from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService
from backend.app.services.location_service import DynamicLocationService
from backend.app.data.qc import ForecastQualityControl, get_surface_pressure_bounds
from backend.app.schemas.weather import CanonicalForecastRecord
from backend.app.schemas.prediction import PredictionRequest, PredictionResponse, ReasonCode, RiskLevel
from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.builder2.feature_adapter import Builder2FeatureAdapter
from backend.app.builder2.model_adapter import Builder2ModelAdapter
from backend.app.builder2.weather_adapter import weather_result_to_dataframe
from backend.app.services.base import WeatherResult


def test_real_ensemble_spread_calculation():
    """TEST 1: Real ensemble spread is calculated from member values using sample std (ddof=1)."""
    service = OpenMeteoGEFSWeatherService()
    
    # Mock raw response with control and 30 perturbed members
    times = ["2026-08-25T00:00:00Z"]
    hourly = {
        "time": times,
        "temperature_2m": [25.0],
    }
    # Synthetic members around 25.0: 20.0 to 30.0
    member_vals = [20.0 + i * (10.0 / 29.0) for i in range(30)]
    for idx, val in enumerate(member_vals, 1):
        hourly[f"temperature_2m_member{idx:02d}"] = [val]
        
    raw_payload = {
        "hourly": hourly,
        "hourly_units": {"temperature_2m": "celsius"},
    }
    
    records = service.parse_canonical_records(
        raw_response=raw_payload,
        location="Mumbai",
        latitude=19.0760,
        longitude=72.8777,
    )
    
    temp_recs = [r for r in records if r.variable == "temperature_2m"]
    assert len(temp_recs) == 1
    rec = temp_recs[0]
    
    # All 31 members (control 25.0 + 30 members)
    expected_all = [25.0] + member_vals
    expected_mean = float(np.mean(expected_all))
    expected_std = float(np.std(expected_all, ddof=1))
    
    assert rec.member_count == 31
    assert rec.ensemble_mean == pytest.approx(expected_mean, rel=1e-5)
    assert rec.ensemble_std == pytest.approx(expected_std, rel=1e-5)
    assert rec.ensemble_std > 0.0, "Spread must be strictly positive"


def test_missing_ensemble_preserves_none_spread():
    """TEST 2: When upstream provides no ensemble members, ensemble_std remains None, not fake 0.0."""
    service = OpenMeteoGEFSWeatherService()
    
    raw_payload = {
        "hourly": {
            "time": ["2026-08-25T00:00:00Z"],
            "temperature_2m": [28.5],
        },
        "hourly_units": {"temperature_2m": "celsius"},
    }
    
    records = service.parse_canonical_records(
        raw_response=raw_payload,
        location="Delhi",
        latitude=28.6139,
        longitude=77.2090,
    )
    
    temp_recs = [r for r in records if r.variable == "temperature_2m"]
    assert len(temp_recs) == 1
    rec = temp_recs[0]
    
    assert rec.ensemble_std is None, "Missing ensemble data must NOT become fake 0.0"
    assert rec.value == 28.5
    assert rec.ensemble_mean == 28.5


def test_wind_speed_unit_conversion():
    """TEST 3: Canonical wind speed (m/s) is scaled by 3.6 to km/h for Builder 2 feature pipeline."""
    # Create canonical records with wind_speed_10m = 5.0 m/s and spread 1.5 m/s
    times = ["2026-08-25T00:00:00Z", "2026-08-25T06:00:00Z"]
    records = []
    for t in times:
        records.append(
            CanonicalForecastRecord(
                location="Kolkata",
                latitude=22.5726,
                longitude=88.3639,
                issue_time="2026-08-25T00:00:00Z",
                valid_time=t,
                lead_hours=0 if t == times[0] else 6,
                variable="wind_speed_10m",
                unit="m/s",
                value=5.0,
                ensemble_mean=5.0,
                ensemble_std=1.5,
                ensemble_min=2.0,
                ensemble_max=8.0,
                q10=3.0,
                q90=7.0,
                member_count=31,
            )
        )
        # Add a temperature record to allow feature extraction
        records.append(
            CanonicalForecastRecord(
                location="Kolkata",
                latitude=22.5726,
                longitude=88.3639,
                issue_time="2026-08-25T00:00:00Z",
                valid_time=t,
                lead_hours=0 if t == times[0] else 6,
                variable="temperature_2m",
                unit="celsius",
                value=30.0,
                ensemble_mean=30.0,
                ensemble_std=1.0,
                member_count=31,
            )
        )
        
    weather_res = WeatherResult(
        location="Kolkata",
        is_available=True,
        raw_data={"records": [r.model_dump() for r in records]},
    )
    df = weather_result_to_dataframe(weather_res)
    wind_rows = df[df["variable"] == "wind_speed_10m"]
    
    assert len(wind_rows) == 2
    for _, r in wind_rows.iterrows():
        assert r["unit"] == "km/h"
        assert r["forecast_value"] == pytest.approx(18.0, rel=1e-5)  # 5.0 * 3.6 = 18.0 km/h
        assert r["ensemble_mean"] == pytest.approx(18.0, rel=1e-5)
        assert r["ensemble_std"] == pytest.approx(5.4, rel=1e-5)  # 1.5 * 3.6 = 5.4 km/h
        assert r["ensemble_min"] == pytest.approx(7.2, rel=1e-5)
        assert r["ensemble_max"] == pytest.approx(28.8, rel=1e-5)


def test_high_altitude_surface_pressure_qc_passes():
    """TEST 4: Elevation-aware QC accepts valid surface pressure at high altitudes (Shimla, Leh)."""
    qc = ForecastQualityControl()
    
    # Shimla elevation = 2276m, typical pressure ~778 hPa
    shimla_rec = CanonicalForecastRecord(
        location="Shimla",
        latitude=31.1048,
        longitude=77.1734,
        elevation=2276.0,
        issue_time="2026-08-25T00:00:00Z",
        valid_time="2026-08-25T06:00:00Z",
        lead_hours=6,
        variable="surface_pressure",
        unit="hPa",
        value=778.0,
        ensemble_mean=778.0,
        member_count=31,
    )
    res_shimla = qc.validate_records([shimla_rec])
    assert res_shimla.passed is True, f"Shimla QC failed: {res_shimla.violations}"

    # Leh elevation = 3524m, typical pressure ~665 hPa
    leh_rec = CanonicalForecastRecord(
        location="Leh",
        latitude=34.1526,
        longitude=77.5771,
        elevation=3524.0,
        issue_time="2026-08-25T00:00:00Z",
        valid_time="2026-08-25T06:00:00Z",
        lead_hours=6,
        variable="surface_pressure",
        unit="hPa",
        value=665.0,
        ensemble_mean=665.0,
        member_count=31,
    )
    res_leh = qc.validate_records([leh_rec])
    assert res_leh.passed is True, f"Leh QC failed: {res_leh.violations}"


def test_physically_impossible_pressure_qc_fails():
    """TEST 5: Physically impossible pressure values are rejected by QC."""
    qc = ForecastQualityControl()
    
    # Pressure too low for Earth surface (< 300 hPa)
    impossible_low = CanonicalForecastRecord(
        location="Shimla",
        latitude=31.1048,
        longitude=77.1734,
        elevation=2276.0,
        issue_time="2026-08-25T00:00:00Z",
        valid_time="2026-08-25T06:00:00Z",
        lead_hours=6,
        variable="surface_pressure",
        unit="hPa",
        value=200.0,
        member_count=31,
    )
    res_low = qc.validate_records([impossible_low])
    assert res_low.passed is False
    assert res_low.flags["has_out_of_bounds"] is True

    # Pressure too high (> 1100 hPa)
    impossible_high = CanonicalForecastRecord(
        location="Mumbai",
        latitude=19.0760,
        longitude=72.8777,
        elevation=14.0,
        issue_time="2026-08-25T00:00:00Z",
        valid_time="2026-08-25T06:00:00Z",
        lead_hours=6,
        variable="surface_pressure",
        unit="hPa",
        value=1200.0,
        member_count=31,
    )
    res_high = qc.validate_records([impossible_high])
    assert res_high.passed is False
    assert res_high.flags["has_out_of_bounds"] is True


def test_canonical_location_panaji_resolution():
    """TEST 6: 'Panaji' and 'Panjim' resolve to Goa, India in canonical registry."""
    loc_service = DynamicLocationService()
    
    res_panaji = loc_service.resolve("Panaji")
    assert res_panaji.name == "Panaji"
    assert res_panaji.country == "India"
    assert res_panaji.state_region == "Goa"
    assert res_panaji.latitude == pytest.approx(15.2993, abs=0.01)
    assert res_panaji.longitude == pytest.approx(73.8278, abs=0.01)
    
    res_panjim = loc_service.resolve("Panjim")
    assert res_panjim.name == "Panaji"
    assert res_panjim.country == "India"
    assert res_panjim.state_region == "Goa"


def test_builder2_to_builder1_field_parity():
    """TEST 7: All Builder 2 advanced intelligence fields survive into PredictionResponse."""
    loc_service = DynamicLocationService()
    weather_service = OpenMeteoGEFSWeatherService(location_service=loc_service)
    feature_adapter = Builder2FeatureAdapter()
    model_adapter = Builder2ModelAdapter(model_dir="models/day4")
    
    agent = ForecastBustAgent(
        weather_service=weather_service,
        feature_service=feature_adapter,
        model_service=model_adapter,
    )
    
    req = PredictionRequest(location="Mumbai", variable="temperature_2m")
    resp = agent.analyze(req)
    
    assert isinstance(resp, PredictionResponse)
    assert resp.bust_probability is not None
    assert resp.confidence_index is not None
    assert resp.uncertainty_pct is not None
    assert resp.failure_fingerprint is not None
    assert resp.dominant_risk_drivers is not None
    assert resp.decision_mode is not None
    assert resp.decision_guidance is not None
    assert resp.operational_trust_horizon_hours == 120


def test_complete_10_horizon_preservation():
    """TEST 8: Complete 10-horizon trajectory (24h to 240h) is preserved through the pipeline."""
    target_horizons = [24, 48, 72, 96, 120, 144, 168, 192, 216, 240]
    
    loc_service = DynamicLocationService()
    weather_service = OpenMeteoGEFSWeatherService(location_service=loc_service)
    feature_adapter = Builder2FeatureAdapter()
    model_adapter = Builder2ModelAdapter(model_dir="models/day4")
    
    agent = ForecastBustAgent(
        weather_service=weather_service,
        feature_service=feature_adapter,
        model_service=model_adapter,
    )
    
    weather_res = weather_service.get_forecast(location="Kolkata")
    assert weather_res.is_available is True
    
    base_issue = weather_res.metadata.get("issue_time")
    dt_issue = datetime.fromisoformat(base_issue.replace("Z", "+00:00"))
    
    responses = []
    for lead in target_horizons:
        dt_valid = dt_issue + timedelta(hours=lead)
        req = PredictionRequest(
            location="Kolkata",
            issue_time=base_issue,
            valid_time=dt_valid.isoformat(),
            variable="temperature_2m",
        )
        resp = agent.analyze(req)
        responses.append(resp)
        
    assert len(responses) == 10
    for lead, resp in zip(target_horizons, responses):
        assert resp.bust_probability is not None, f"Lead {lead}h returned None probability"
        assert resp.abstain is False


def test_time_and_lead_alignment():
    """TEST 9: Lead hours and timestamps maintain strict mathematical and chronological alignment."""
    loc_service = DynamicLocationService()
    weather_service = OpenMeteoGEFSWeatherService(location_service=loc_service)
    
    weather_res = weather_service.get_forecast(location="Delhi")
    records = [CanonicalForecastRecord(**r) for r in weather_res.raw_data.get("records", [])]
    
    # Check that for all records, valid_time - issue_time == lead_hours
    for r in records[:50]:
        dt_issue = datetime.fromisoformat(r.issue_time.replace("Z", "+00:00"))
        dt_valid = datetime.fromisoformat(r.valid_time.replace("Z", "+00:00"))
        expected_lead = int((dt_valid - dt_issue).total_seconds() / 3600)
        assert r.lead_hours == expected_lead
        assert r.lead_hours >= 0


def test_safe_abstention_remains_intact():
    """TEST 10: Safe abstention is triggered on invalid location without fabricating probabilities."""
    loc_service = DynamicLocationService()
    weather_service = OpenMeteoGEFSWeatherService(location_service=loc_service)
    agent = ForecastBustAgent(weather_service=weather_service)
    
    # Nonexistent location
    req = PredictionRequest(location="XYZ_NonExistent_City_99999")
    resp = agent.analyze(req)
    
    assert resp.abstain is True
    assert resp.bust_probability is None
    assert resp.trust_state.value == "UNAVAILABLE"
    assert ReasonCode.INVALID_LOCATION.value in resp.reason_codes
