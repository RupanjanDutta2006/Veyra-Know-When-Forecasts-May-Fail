# VEYRA — PHASE 4 INTEGRATION PLAN
## Builder 1 UI / Product ↔ Builder 2 V2 Scientific Engine

**Document:** `PHASE4_INTEGRATION_PLAN.md`  
**Target:** End-to-End Integration of Audited Builder 2 V2 Engine into Builder 1  
**Target Repositories:**
- **Builder 1:** `C:\Users\parin\OneDrive\Desktop\veyra` (Product, Orchestration, API, UI Contracts)
- **Builder 2:** `C:\Users\parin\OneDrive\Desktop\forecast-bust-sentinel` (NOAA S3 Ingestion, 50-Feature Physical Pipeline, V2 LightGBM Champion, Platt Calibrator, OOD Novelty, Reliability Index)

---

## 1. Architecture Map Before Integration

```
BUILDER 1 (veyra):
[ User / Web Dashboard ]
           │
           ▼
[ FastAPI (backend/app/main.py) ]
           │
           ▼ (POST /v1/predict)
[ ForecastBustAgent (backend/app/agents/forecast_bust_agent.py) ]
           │
           ├─► WeatherService (OpenMeteoGEFSWeatherService)
           ├─► Builder2FeatureAdapter (26 Canonical Features)
           ├─► Builder2ModelAdapter ──► builder2/model_service.py ──► models/day4 (prototype-gbm-v1) [STALE]
           └─► SafetyEvaluator (Abstention Engine)

BUILDER 2 (forecast-bust-sentinel):
[ Direct Ingestion: NOAA S3 Retrospective GEFSv12 ]
           │ (Byte-Range ecCodes C-API Decode)
           ▼
[ 50-Feature Physical Pipeline (features/forecast_intelligence_features.py) ]
           │ (Zero coordinates, Zero target proxies)
           ▼
[ V2 Champion Booster (models/v2/lightgbm_v2_champion.joblib) ]
           │
           ▼
[ Platt Calibrator (models/v2/probability_calibrator_v2.joblib) ]
           │
           ▼
[ ForecastIntelligenceService (models/forecast_intelligence_service.py) ]
           │
           ▼
[ ForecastReliabilityResult (P(bust), Confidence Index, Overconfidence, OOD, Fingerprint, Drivers) ]
```

---

## 2. Architecture Map After Integration

```
[ User / Dashboard / Client ]
           │
           ▼
[ Web Service / REST API: ForecastBustAPI / FastAPI ]
           │
           ▼
[ OperationalRiskEngine (api/risk_engine.py) / Builder2ModelAdapter ]
           │
           ▼
[ Authoritative Engine: ForecastIntelligenceService (models/forecast_intelligence_service.py) ]
           │
           ├─► Ingestion: NOAAS3ReforecastAdapter (O(1) Global ecCodes GRIB Decode across 25 Stations)
           ├─► Feature Engine: ForecastIntelligenceFeaturePipeline (50 Pure Physical Features)
           ├─► Model Inference: V2 LightGBM Champion (models/v2/lightgbm_v2_champion.joblib)
           ├─► Calibration: Platt Sigmoid (models/v2/probability_calibrator_v2.joblib)
           ├─► Risk Evaluation: Exact Threshold Gates (tau* = 0.060, Critical = 0.600)
           ├─► Diagnostic Suite:
           │   ├── Structural Overconfidence Risk: (|Delta_rev| * sqrt(lead+1)) / (sigma + 0.1)
           │   ├── Trajectory Stability Index: 100 * exp(-lambda * |Delta| / (sigma + 0.1))
           │   ├── Training OOD Novelty: Mahalanobis Distance on Baseline Envelope
           │   ├── Analytical Failure Fingerprint: 6 Mathematical Archetypes
           │   └── Uncertainty Estimation: Bootstrap Sub-Ensemble Margin (+/- 3.37%)
           │
           ▼
[ Serialized Response: ForecastRiskResponse / PredictionResponse ]
           │
           ▼
[ User Interface / Verification Layer ]
  - Displays Calibrated P(bust)%
  - Categorical Risk Tier (LOW / ELEVATED / CRITICAL)
  - Reliability Index: XX/100 (Explicitly Non-Probabilistic)
  - Failure Fingerprint (Analytical Mathematical Classification)
  - Dominant Physical Risk Drivers
```

---

## 3. Canonical API Contract & Route Specification

### Canonical Endpoint
- **Primary Service Class:** `api.routes.ForecastBustAPI` wrapping `api.risk_engine.OperationalRiskEngine`.
- **Primary Engine:** `models.forecast_intelligence_service.ForecastIntelligenceService`.
- **Loaded Artifacts:**
  - `models/v2/lightgbm_v2_champion.joblib`
  - `models/v2/probability_calibrator_v2.joblib`
  - `models/v2/feature_names.json`
- **Zero Legacy Tolerance:** `prototype-gbm-v1`, `models/day4`, and `baseline_logistic_v1` are completely removed from all operational execution paths.

### Request Payload Contract
```json
{
  "location_id": "delhi",
  "forecast_source": "NOAA_GEFS",
  "grid_resolution": "0.25°",
  "forecast_data": [
    {
      "location": "delhi",
      "variable": "temperature_2m",
      "issue_time": "2017-03-15T00:00:00Z",
      "valid_time": "2017-03-15T06:00:00Z",
      "lead_hours": 6,
      "forecast_value": 25.0,
      "ensemble_mean": 25.0,
      "ensemble_std": 0.5,
      "member_count": 11,
      "unit": "degC"
    }
  ]
}
```

### Response Payload Contract (Strict Semantic Separation)
```json
{
  "request_id": "req-7b89f2a1b9c0",
  "location": {
    "location_id": "delhi",
    "city": "Delhi",
    "requested_coordinates": {"latitude": 28.6139, "longitude": 77.2090},
    "actual_grid_coordinates": {"latitude": 28.5, "longitude": 77.25},
    "spatial_distance_km": 13.25
  },
  "issue_time": "2017-03-15T00:00:00+00:00",
  "model_version": "veyra-v2-champion-lightgbm",
  "decision_threshold": 0.060,
  "forecasts": [
    {
      "valid_time": "2017-03-15T06:00:00+00:00",
      "lead_hours": 6,
      "variable": "temperature_2m",
      "forecast_value": 25.0,
      "ensemble_mean": 25.0,
      "ensemble_std": 0.5,
      "unit": "degC",
      "bust_probability": 0.0777,
      "bust_alert": true,
      "risk_level": "ELEVATED",
      "confidence_index": 92.2,
      "structural_overconfidence": 0.0,
      "stability_index": 100.0,
      "ood_score": 12.4,
      "failure_fingerprint": "STABLE_SYNOPTIC_CONSENSUS",
      "uncertainty_pct": 3.37,
      "dominant_risk_drivers": []
    }
  ]
}
```

---

## 4. Implementation Steps

1. **Verification of Model Routing**: Ensure `ForecastIntelligenceService` is the single source of truth for both `ForecastBustAPI` and `Builder2ModelAdapter`.
2. **Builder 1 Adapter Synchronization**: Update Builder 1's `backend/app/builder2/model_adapter.py` to route to V2 champion.
3. **End-to-End Test Suite**: Execute full verification over real NOAA GEFSv12 reforecast data, testing:
   - Real NOAA S3 data acquisition (2017-03-14 and 2017-03-15)
   - 25-location registry completeness and spatial mapping
   - Unit integrity (Kelvin -> Celsius, Pa -> hPa, m/s -> km/h)
   - Semantic field separation and probability bounds
   - Exact threshold boundaries (0.0599, 0.0600, 0.5999, 0.6000)
   - Loud failure on corrupted/missing model artifacts
   - Determinism and row permutation invariance
4. **Final Regression & Cleanliness Verification**:
   - Run `scratch\env_eccodes\python.exe -m pytest -m "not smoke"`
   - Check Builder 1 and Builder 2 `git status --short`.
5. **Produce Final Report**: `PHASE4_END_TO_END_INTEGRATION_REPORT.md`.
