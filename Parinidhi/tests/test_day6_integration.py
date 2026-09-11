"""
Operational Risk Pipeline and API Integration Test Suite.

Verifies end-to-end functionality of:
- LocationRegistry and spatial colocation without hardcoded fabrication
- ForecastBustExplainer physical driver attribution
- RegionalRiskAggregator spatial metrics with dynamic input derivation
- OperationalRiskEngine execution & strict verification pair status derivation
- ForecastBustAPI service controller methods
- Dynamic grid resolution provenance without silent guesswork
- Offline deterministic execution with zero live network calls
"""

from datetime import datetime, timezone
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from api.explainer import ForecastBustExplainer
from api.location_service import LocationRegistry, haversine_distance_km
from api.regional_aggregator import RegionalRiskAggregator
from api.risk_engine import OperationalRiskEngine
from api.routes import ForecastBustAPI
from api.schemas import (
    DataStatus,
    ForecastRiskResponse,
    RegionalRiskSummaryResponse,
    VerificationStatus,
)
from features.feature_pipeline import FEATURE_COLUMN_NAMES


@pytest.fixture
def sample_features_df():
    """Load real verified training dataset row slice for offline deterministic testing."""
    dataset_path = Path("data/features/training_dataset.parquet")
    if not dataset_path.exists():
        pytest.skip(f"Training dataset not found at {dataset_path}")
    df = pd.read_parquet(dataset_path)
    return df.head(10).copy()


@pytest.fixture
def risk_engine():
    """Initialize OperationalRiskEngine."""
    return OperationalRiskEngine()


@pytest.fixture
def api_service():
    """Initialize ForecastBustAPI service."""
    return ForecastBustAPI()


def test_1_haversine_distance_calculation():
    """Test great-circle distance calculation between known geographic coordinates."""
    # Distance between two distinct points is positive and symmetric
    dist1 = haversine_distance_km(28.6139, 77.2090, 19.0760, 72.8777)
    dist2 = haversine_distance_km(19.0760, 72.8777, 28.6139, 77.2090)
    assert dist1 > 0.0
    assert abs(dist1 - dist2) < 1e-6

    # Same point distance is 0.0
    zero_dist = haversine_distance_km(28.50, 77.25, 28.50, 77.25)
    assert abs(zero_dist) < 1e-6


def test_2_location_registry_verified_vs_unverified_resolution():
    """Test location resolution: verified Delhi vs unverified Mumbai without fabricated coordinates."""
    registry = LocationRegistry()

    # 1. Delhi has verified historical pilot grid metadata
    delhi_info = registry.get_location("delhi")
    assert delhi_info.location_id == "delhi"
    assert delhi_info.city == "Delhi"
    assert delhi_info.requested_coordinates.latitude == 28.6139
    assert delhi_info.requested_coordinates.longitude == 77.2090
    assert delhi_info.actual_grid_coordinates is not None
    assert delhi_info.actual_grid_coordinates.latitude == 28.50
    assert delhi_info.actual_grid_coordinates.longitude == 77.25
    assert delhi_info.spatial_distance_km is not None
    assert delhi_info.spatial_distance_km > 0.0

    # 2. Mumbai without source-supplied grid coordinates returns None (no silent fabrication)
    mumbai_unresolved = registry.get_location("mumbai")
    assert mumbai_unresolved.location_id == "mumbai"
    assert mumbai_unresolved.actual_grid_coordinates is None
    assert mumbai_unresolved.spatial_distance_km is None

    # 3. Mumbai WITH source-supplied grid coordinates computes valid distance
    mumbai_resolved = registry.get_location("mumbai", actual_grid_lat=19.00, actual_grid_lon=73.00)
    assert mumbai_resolved.actual_grid_coordinates is not None
    assert mumbai_resolved.actual_grid_coordinates.latitude == 19.00
    assert mumbai_resolved.actual_grid_coordinates.longitude == 73.00
    assert mumbai_resolved.spatial_distance_km is not None
    assert mumbai_resolved.spatial_distance_km > 0.0


def test_3_location_registry_unknown_location_raises_keyerror():
    """Test that unregistered location IDs fail loudly with KeyError."""
    registry = LocationRegistry()
    with pytest.raises(KeyError) as exc_info:
        registry.get_location("nonexistent_city_xyz")
    assert "Unknown location_id" in str(exc_info.value)


def test_4_explainer_physical_driver_ranking():
    """Test deterministic physical feature attribution for forecast bust risk."""
    # Case A: High 24h revision drift
    feat_high_drift = {
        "forecast_delta_24h": 2.75,
        "ensemble_std": 1.2,
        "lead_hours": 24,
        "ensemble_spread_delta_24h": 0.1,
    }
    exp_a = ForecastBustExplainer.explain_row(feat_high_drift, bust_probability=0.45, threshold=0.280)
    assert exp_a.primary_driver == "rapid_inter_cycle_revision"
    assert any(f.signal == "HIGH_REVISION_DRIFT" for f in exp_a.top_contributing_factors)

    # Case B: High ensemble spread
    feat_high_spread = {
        "forecast_delta_24h": 0.2,
        "ensemble_std": 3.8,
        "lead_hours": 48,
        "ensemble_spread_delta_24h": 1.5,
    }
    exp_b = ForecastBustExplainer.explain_row(feat_high_spread, bust_probability=0.38, threshold=0.280)
    assert exp_b.primary_driver == "high_ensemble_uncertainty"
    assert any(f.signal == "HIGH_ENSEMBLE_SPREAD" for f in exp_b.top_contributing_factors)

    # Case C: Stable non-alert forecast
    feat_stable = {
        "forecast_delta_24h": 0.1,
        "ensemble_std": 0.5,
        "lead_hours": 12,
        "ensemble_spread_delta_24h": 0.0,
    }
    exp_c = ForecastBustExplainer.explain_row(feat_stable, bust_probability=0.05, threshold=0.280)
    assert exp_c.primary_driver == "stable_ensemble_agreement"


def test_5_regional_aggregator_metrics_derived_from_inputs():
    """Test that regional aggregator outputs match exact required field names and are derived from inputs."""
    registry = LocationRegistry()
    loc_delhi = registry.get_location("delhi")
    loc_mumbai = registry.get_location("mumbai")

    from api.schemas import ForecastRiskItem, ExplanationItem, ProvenanceInfo

    prov = ProvenanceInfo("NOAA_GEFS", "0.25°", "prototype-gbm-v1", "1.0.0", "2026-08-26T00:00:00Z")
    exp = ExplanationItem("stable", "Summary", [])

    # Dynamic synthetic input values
    prob_d1 = 0.15
    prob_d2 = 0.35  # Alert trigger
    lead_d2 = 48
    prob_m1 = 0.10

    expected_peak = max(prob_d1, prob_d2, prob_m1)
    expected_worst_lead = lead_d2
    expected_alert_fraction = 1.0 / 2.0  # 1 location out of 2 has active alert

    item_d1 = ForecastRiskItem("2026-08-22T00:00:00Z", 24, 1.0, "temperature_2m", 30.0, 30.0, 1.0, "degC", prob_d1, False, "MODEL_PREDICTION", "NO_TRUTH_AVAILABLE", exp)
    item_d2 = ForecastRiskItem("2026-08-23T00:00:00Z", lead_d2, 2.0, "temperature_2m", 32.0, 31.5, 2.5, "degC", prob_d2, True, "MODEL_PREDICTION", "NO_TRUTH_AVAILABLE", exp)
    resp_delhi = ForecastRiskResponse("req-1", loc_delhi, "2026-08-21T00:00:00Z", "prototype-gbm-v1", 0.280, prov, [item_d1, item_d2])

    item_m1 = ForecastRiskItem("2026-08-22T00:00:00Z", 24, 1.0, "temperature_2m", 28.0, 28.0, 0.8, "degC", prob_m1, False, "MODEL_PREDICTION", "NO_TRUTH_AVAILABLE", exp)
    resp_mumbai = ForecastRiskResponse("req-2", loc_mumbai, "2026-08-21T00:00:00Z", "prototype-gbm-v1", 0.280, prov, [item_m1])

    summary = RegionalRiskAggregator.aggregate_region("India Pilot Domain", [resp_delhi, resp_mumbai])

    # Assert required exact field names and dynamically derived values
    assert summary.region_name == "India Pilot Domain"
    assert summary.location_count == 2
    assert abs(summary.regional_peak_bust_probability - expected_peak) < 1e-6
    assert abs(summary.regional_alert_fraction - expected_alert_fraction) < 1e-6
    assert summary.worst_risk_lead_hours == expected_worst_lead
    assert summary.dominant_risk_variable == "temperature_2m"


def test_6_strict_verification_status_derivation(risk_engine):
    """Test strict derivation of verification status based on actual pair presence and temporal bounds."""
    i_time = datetime(2026, 8, 21, 0, 0, tzinfo=timezone.utc)
    max_truth = datetime(2026, 8, 25, 18, 0, tzinfo=timezone.utc)

    # 1. Actual verified observation pair exists -> HISTORICALLY_VERIFIED
    stat_verified = risk_engine.evaluate_verification_status(
        valid_time=datetime(2026, 8, 23, 0, 0, tzinfo=timezone.utc),
        issue_time=i_time,
        max_truth_time_utc=max_truth,
        has_verified_truth_pair=True,
    )
    assert stat_verified == VerificationStatus.HISTORICALLY_VERIFIED.value

    # 2. Timestamp covered by archive cutoff BUT actual observation pair is absent -> NO_TRUTH_AVAILABLE
    stat_covered_but_absent = risk_engine.evaluate_verification_status(
        valid_time=datetime(2026, 8, 23, 0, 0, tzinfo=timezone.utc),
        issue_time=i_time,
        max_truth_time_utc=max_truth,
        has_verified_truth_pair=False,
    )
    assert stat_covered_but_absent == VerificationStatus.NO_TRUTH_AVAILABLE.value

    # 3. Future valid time relative to clock -> NO_TRUTH_AVAILABLE
    stat_future = risk_engine.evaluate_verification_status(
        valid_time=datetime(2099, 1, 1, 0, 0, tzinfo=timezone.utc),
        issue_time=i_time,
        max_truth_time_utc=None,
        has_verified_truth_pair=False,
    )
    assert stat_future == VerificationStatus.NO_TRUTH_AVAILABLE.value

    # 4. Timestamp outside truth availability cutoff -> UNVERIFIED_HORIZON_NO_TRUTH
    stat_unverified_horizon = risk_engine.evaluate_verification_status(
        valid_time=datetime(2026, 8, 28, 0, 0, tzinfo=timezone.utc),
        issue_time=i_time,
        max_truth_time_utc=max_truth,
        has_verified_truth_pair=False,
    )
    assert stat_unverified_horizon == VerificationStatus.UNVERIFIED_HORIZON_NO_TRUTH.value


def test_7_dynamic_grid_resolution_provenance_and_unknown_handling(risk_engine, sample_features_df):
    """Test that grid_resolution is dynamically recorded and returns UNKNOWN when unavailable."""
    # 1. 0.50° historical resolution
    resp_0p50 = risk_engine.process_forecast_dataframe(
        sample_features_df,
        location_id="delhi",
        forecast_source="NOAA_GEFS_S3_0p50",
        grid_resolution="0.50°",
    )
    assert resp_0p50.provenance.grid_resolution == "0.50°"

    # 2. 0.25° live mirror resolution
    resp_0p25 = risk_engine.process_forecast_dataframe(
        sample_features_df,
        location_id="delhi",
        forecast_source="NOAA_GEFS_OPENMETEO",
        grid_resolution="0.25°",
    )
    assert resp_0p25.provenance.grid_resolution == "0.25°"

    # 3. Unknown source without resolution metadata returns UNKNOWN (never guesses 0.25°)
    df_no_res = sample_features_df.copy()
    if "grid_resolution" in df_no_res.columns:
        df_no_res.drop(columns=["grid_resolution"], inplace=True)

    resp_unknown = risk_engine.process_forecast_dataframe(
        df_no_res,
        location_id="delhi",
        forecast_source="CUSTOM_ARBITRARY_SOURCE",
        grid_resolution=None,
    )
    assert resp_unknown.provenance.grid_resolution == "UNKNOWN"


def test_8_api_health_endpoint(api_service):
    """Test API health endpoint returns model metadata and healthy state."""
    health = api_service.get_health()
    assert health["status"] == "healthy"
    assert health["model_version"] == "veyra-v2-champion-lightgbm"
    assert health["decision_threshold"] == 0.060
    assert health["feature_count"] == 50


def test_9_api_list_locations_endpoint(api_service):
    """Test API list locations returns registered monitoring points."""
    res = api_service.list_locations()
    assert res["count"] >= 5
    loc_ids = [loc["location_id"] for loc in res["locations"]]
    assert "delhi" in loc_ids
    assert "mumbai" in loc_ids


def test_10_api_forecast_risk_response_contract(api_service, sample_features_df):
    """Test complete ForecastBustAPI risk computation output schema."""
    res_dict = api_service.get_forecast_risk(
        forecast_input=sample_features_df,
        location_id="delhi",
        forecast_source="NOAA_GEFS",
        grid_resolution="0.25°",
    )

    # Check top-level contract
    assert "request_id" in res_dict
    assert res_dict["location"]["location_id"] == "delhi"
    assert res_dict["location"]["city"] == "Delhi"
    assert "requested_coordinates" in res_dict["location"]
    assert "actual_grid_coordinates" in res_dict["location"]
    assert "spatial_distance_km" in res_dict["location"]

    assert res_dict["model_version"] == "veyra-v2-champion-lightgbm"
    assert res_dict["decision_threshold"] == 0.060
    assert "provenance" in res_dict
    assert res_dict["provenance"]["grid_resolution"] == "0.25°"

    # Check forecasts array
    assert len(res_dict["forecasts"]) == len(sample_features_df)
    first_item = res_dict["forecasts"][0]
    assert "valid_time" in first_item
    assert "lead_hours" in first_item
    assert "bust_probability" in first_item
    assert "bust_alert" in first_item
    assert "data_status" in first_item
    assert "verification_status" in first_item
    assert "explanation" in first_item
    assert "confidence" in first_item
    assert first_item["confidence"] is None  # Omitted until real OOD/calibration layer is built
    assert isinstance(first_item["bust_alert"], bool)
    assert 0.0 <= first_item["bust_probability"] <= 1.0


def test_11_api_regional_summary_aggregation(api_service, sample_features_df):
    """Test multi-location regional summary API endpoint."""
    inputs = {
        "delhi": sample_features_df.head(5),
        "mumbai": sample_features_df.head(5),
    }

    summary = api_service.get_regional_summary(
        region_name="India Multi-City Domain",
        location_forecast_inputs=inputs,
        forecast_source="NOAA_GEFS",
        grid_resolution="0.25°",
    )

    assert summary["region_name"] == "India Multi-City Domain"
    assert summary["location_count"] == 2
    assert "regional_peak_bust_probability" in summary
    assert "regional_alert_fraction" in summary
    assert "worst_risk_lead_hours" in summary
    assert "dominant_risk_variable" in summary
    assert len(summary["locations_summary"]) == 2


def test_12_deterministic_repeatability(api_service, sample_features_df):
    """Test that identical input DataFrame yields exact deterministic output probabilities."""
    res1 = api_service.get_forecast_risk(sample_features_df, location_id="delhi")
    res2 = api_service.get_forecast_risk(sample_features_df, location_id="delhi")

    probs1 = [f["bust_probability"] for f in res1["forecasts"]]
    probs2 = [f["bust_probability"] for f in res2["forecasts"]]

    assert probs1 == probs2
    assert [f["bust_alert"] for f in res1["forecasts"]] == [f["bust_alert"] for f in res2["forecasts"]]
