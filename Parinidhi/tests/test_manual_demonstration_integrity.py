"""
Tests verifying the integrity, consistency, and zero-leakage contracts of the manual inference demonstration.
"""

import os
from pathlib import Path
import json
import subprocess
import numpy as np
import pandas as pd
import pytest

from models.forecast_intelligence_service import ForecastIntelligenceService
from features.forecast_intelligence_features import (
    SUPERCHARGED_PHYSICAL_FEATURES,
    ForecastIntelligenceFeaturePipeline,
    TrainingOODScorer,
)
from models.intelligence_schemas import ForecastReliabilityResult


def test_manual_inference_loads_v2_artifacts():
    """Verify ForecastIntelligenceService loads V2 champion model and calibrator without fallback."""
    service = ForecastIntelligenceService()
    assert service.model is not None
    assert service.calibrator is not None
    assert service.model_version == "veyra-v2-champion-lightgbm"
    assert len(service.feature_names) == 50
    assert "latitude" not in service.feature_names
    assert "longitude" not in service.feature_names
    assert "hist_expected_error" not in service.feature_names
    assert "spread_skill_ratio" not in service.feature_names


def test_no_target_encoding_or_historical_error_in_v2_features():
    """Verify V2 model feature list contains zero target proxies."""
    v2_features_path = Path("models/v2/feature_names.json")
    assert v2_features_path.exists()
    features = json.loads(v2_features_path.read_text(encoding="utf-8"))
    
    prohibited = ["hist_expected_error", "spread_skill_ratio", "latitude", "longitude", "station_id", "elevation"]
    for p in prohibited:
        assert p not in features, f"Prohibited feature {p} found in V2 model feature list!"


def test_forecast_reliability_result_bounds_and_risk_mapping():
    """Verify probability bounds [0, 1] and risk level mapping across dummy batch."""
    df_dummy = pd.DataFrame([
        {
            "location": "delhi",
            "variable": "temperature_2m",
            "issue_time": "2017-03-14 00:00:00Z",
            "valid_time": "2017-03-14 06:00:00Z",
            "lead_hours": 6,
            "forecast_value": 25.0,
            "ensemble_mean": 25.0,
            "ensemble_std": 0.5,
            "ensemble_range": 1.2,
            "ensemble_iqr": 0.6,
            "member_count": 5,
            "unit": "degC",
        }
    ])
    
    service = ForecastIntelligenceService(operational_threshold=0.060)
    results = service.evaluate_forecast(df_dummy)
    assert len(results) == 1
    r = results[0]
    
    assert 0.0 <= r.bust_probability <= 1.0
    assert 0.0 <= r.confidence_index <= 100.0
    assert 0.0 <= r.stability_index <= 100.0
    
    expected_risk = "CRITICAL" if r.bust_probability >= 0.60 else ("ELEVATED" if r.bust_probability >= 0.060 else "LOW")
    assert r.risk_level == expected_risk


def test_risk_drivers_contain_valid_rules_and_no_unknown():
    """Verify that all generated risk drivers contain valid formatted rules without 'Rule: Unknown'."""
    df_batch = pd.DataFrame([
        {
            "location": "mumbai",
            "variable": "wind_speed_10m",
            "issue_time": "2017-03-15 00:00:00Z",
            "valid_time": "2017-03-15 18:00:00Z",
            "lead_hours": 72,
            "forecast_value": 15.0,
            "ensemble_mean": 15.0,
            "ensemble_std": 1.0,
            "ensemble_range": 3.0,
            "ensemble_iqr": 1.5,
            "member_count": 11,
            "unit": "km/h",
        }
    ])
    
    service = ForecastIntelligenceService()
    results = service.evaluate_forecast(df_batch)
    for r in results:
        for d in r.dominant_risk_drivers:
            assert d.signal_name in ["structural_overconfidence_risk", "forecast_instability", "lead_horizon_decay", "ood_anomaly", "overconfidence_signal"]
            assert d.risk_direction in ["ELEVATED_RISK", "CRITICAL_RISK", "ATTENUATION"]
            assert len(d.description) > 5


def test_builder1_remains_untouched():
    """Verify Builder 1 repository has only authorized Phase 4 integration files modified."""
    b1_path = Path(r"C:\Users\parin\OneDrive\Desktop\veyra")
    if b1_path.exists():
        res = subprocess.run(["git", "-C", str(b1_path), "status", "--short"], capture_output=True, text=True)
        assert res.returncode == 0
        lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        allowed_files = {
            "M backend/app/agents/forecast_bust_agent.py",
            "M backend/app/api/v1/endpoints/predict.py",
            "M backend/app/builder2/feature_adapter.py",
            "M backend/app/builder2/model_adapter.py",
            "M backend/app/core/config.py",
            "M backend/app/safety/abstention.py",
            "M backend/app/schemas/prediction.py",
            "M backend/app/services/openmeteo_service.py",
        }
        for line in lines:
            assert line in allowed_files, f"Unauthorized file modified in Builder 1: {line}"
