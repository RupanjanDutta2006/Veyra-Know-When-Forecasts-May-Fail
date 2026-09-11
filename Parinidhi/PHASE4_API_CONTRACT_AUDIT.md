# VEYRA PHASE 4 — API CONTRACT PROVENANCE & V2 INFORMATION PRESERVATION AUDIT REPORT
## Contract Preservation, Data Provenance, and Full V2 Intelligence Schema Certification

**Document:** `PHASE4_API_CONTRACT_AUDIT.md`  
**Date:** 2026-09-04  
**Target Repositories:** Builder 1 (`veyra`) & Builder 2 (`forecast-bust-sentinel`)  
**Final Status:** **🟢 READY FOR MANUAL + BROWSER VALIDATION**  

---

## 1. Data-Version Root Cause & Authoritative Provenance

### Root Cause Analysis
- **Observed Behavior:** Real prediction initially reported `"data_version": "gefs-openmeteo-v1.0"` while semantic audit expected `"gfs-ensemble-openmeteo-v2.0"`.
- **Tracing the Ingestion Pipeline:**
  1. In `OpenMeteoGEFSWeatherService.__init__` (`backend/app/services/openmeteo_service.py`), the default parameter was historically set to `data_version: str = "gefs-openmeteo-v1.0"`.
  2. `WeatherResult.data_version` propagated this string into `ForecastBustAgent.build_response()`.
  3. Meanwhile, Builder 2's historical backtesting pipeline used NOAA S3 GRIB2 reforecasts (`noaa-gefs-retrospective`).
- **Exact Provenance Definition:**
  - **Live Operational Pipeline:** Public Open-Meteo REST API ingesting the live 31-member NOAA GFS/GEFS seamless ensemble at $0.25^\circ$ resolution.
  - **Standardized Version String:** `"gfs-ensemble-openmeteo-v2.0"`.
  - **Retrospective Scientific Pipeline:** Direct AWS S3 byte-range extraction of historical NOAA GEFSv12 retrospective cycles ($00\text{Z}$) evaluated against ERA5 ground truth.

---

## 2. Root Cause Analysis: V2 Intelligence Information Loss

- **Symptom:** Builder 1's `/v1/predict` endpoint previously exposed only 8 basic fields (`location`, `bust_probability`, `risk_level`, `trust_state`, `abstain`, `reason_codes`, `model_version`, `data_version`), dropping rich V2 diagnostics.
- **Trace Findings:**
  1. **Builder 2 (`POST /api/forecast-risk`):** Returns the full V2 payload with `confidence_index`, `uncertainty_pct`, `ood_score`, `revision`, `stability_index`, `structural_overconfidence`, `failure_fingerprint`, and `dominant_risk_drivers`.
  2. **Builder 1 Adapter (`Builder2ModelAdapter`):** Properly captured all these fields into `ModelResult.metadata`.
  3. **Builder 1 Response Construction (`ForecastBustAgent.build_response` & Pydantic `PredictionResponse`):** `ForecastBustAgent` did not forward metadata fields, and `PredictionResponse` schema had not declared them.
- **Exact Resolution:**
  - Enriched `PredictionResponse` in `backend/app/schemas/prediction.py` with all 16 authoritative V2 fields.
  - Updated `ForecastBustAgent.build_response` to extract and forward all V2 fields from `ModelResult.metadata` when available, and cleanly assign `None` when abstaining.

---

## 3. Field Comparison Matrix

| Field | Description | Builder 2 Source | Builder 1 (Before) | Builder 1 (After Fix) |
| :--- | :--- | :--- | :--- | :--- |
| `location` | Target monitoring station | `delhi` | `Delhi` | `Delhi` |
| `bust_probability` | Calibrated bust probability $\in [0, 1]$ | `0.0996` | `0.0996` | `0.0996` |
| `risk_level` | Operational tier (`LOW` / `ELEVATED` / `CRITICAL`) | `ELEVATED` | `LOW` *(stale)* | `ELEVATED` |
| `trust_state` | Sentinel reliability state | `HIGH_CONFIDENCE` | `HIGH_CONFIDENCE` | `HIGH_CONFIDENCE` |
| `confidence_index` | Non-probabilistic heuristic ($0-100$) | `95.0` | **DROPPED** | `95.0` |
| `uncertainty_pct` | Bootstrap error margin ($\pm\%$) | `3.37` | **DROPPED** | `3.37` |
| `ood_distance` | Mahalanobis novelty distance | `0.0` | **DROPPED** | `0.0` |
| `revision` | Cycle-over-cycle shift magnitude | `None` *(T0)* | **DROPPED** | `None` |
| `stability` | Trajectory stability index ($0-100$) | `100.0` | **DROPPED** | `100.0` |
| `structural_overconfidence` | Overconfidence physical diagnostic | `0.0` | **DROPPED** | `0.0` |
| `failure_fingerprint` | Mathematical failure archetype | `STABLE_SYNOPTIC_CONSENSUS` | **DROPPED** | `STABLE_SYNOPTIC_CONSENSUS` |
| `dominant_risk_drivers` | Primary physical risk contributors | `[]` | **DROPPED** | `[]` |
| `model_version` | Authoritative ML model identifier | `veyra-v2-champion-lightgbm` | `veyra-v2-champion-lightgbm` | `veyra-v2-champion-lightgbm` |
| `data_version` | Live data pipeline version | `gfs-ensemble-openmeteo-v2.0` | `gefs-openmeteo-v1.0` *(stale)* | `gfs-ensemble-openmeteo-v2.0` |
| `abstain` | Pipeline abstention flag | `false` | `false` | `false` |
| `reason_codes` | Standard reason status | `["SUCCESS"]` | `["SUCCESS"]` | `["SUCCESS"]` |

---

## 4. OpenAPI / Swagger Schema Verification

The Builder 1 OpenAPI schema (`http://localhost:8000/openapi.json`) was generated and verified:
```json
{
  "PredictionResponse": {
    "properties": [
      "location", "bust_probability", "risk_level", "trust_state",
      "confidence_index", "uncertainty_pct", "ood_distance", "revision",
      "stability", "structural_overconfidence", "failure_fingerprint",
      "dominant_risk_drivers", "model_version", "data_version",
      "abstain", "reason_codes"
    ]
  }
}
```
All 16 fields are documented in Swagger UI (`/docs`).

---

## 5. Live E2E Request Proof (Delhi Live GEFS)

**Request:** `POST http://localhost:8000/v1/predict` $\rightarrow$ `{"location": "Delhi"}`  
**Response (HTTP 200):**
```json
{
  "location": "Delhi",
  "bust_probability": 0.0996,
  "risk_level": "ELEVATED",
  "trust_state": "HIGH_CONFIDENCE",
  "confidence_index": 95.0,
  "uncertainty_pct": 3.37,
  "ood_distance": 0.0,
  "revision": null,
  "stability": 100.0,
  "structural_overconfidence": 0.0,
  "failure_fingerprint": "STABLE_SYNOPTIC_CONSENSUS",
  "dominant_risk_drivers": [],
  "model_version": "veyra-v2-champion-lightgbm",
  "data_version": "gfs-ensemble-openmeteo-v2.0",
  "abstain": false,
  "reason_codes": [
    "SUCCESS"
  ]
}
```

---

## 6. Repository Integrity & Test Verification

- **Builder 1 Tracked Modifications:**
  - `backend/app/agents/forecast_bust_agent.py` (V2 field forwarding)
  - `backend/app/api/v1/endpoints/predict.py` (HTTP client routing)
  - `backend/app/builder2/feature_adapter.py` (Forecast dataframe rows)
  - `backend/app/builder2/model_adapter.py` (HTTP REST client)
  - `backend/app/core/config.py` (BUILDER2_API_URL config)
  - `backend/app/safety/abstention.py` (V2 risk level boundary map)
  - `backend/app/schemas/prediction.py` (V2 response schema + ELEVATED enum)
  - `backend/app/services/openmeteo_service.py` (gfs-ensemble-openmeteo-v2.0 version)
- **Builder 2 Pytest Suite:** **523 passed, 0 failed in 17.23s** (100% green).
- **V2 Information Preservation E2E Suite:** **100% green**.

---

## 7. Final Verdict

$$\mathbf{FINAL\quad VERDICT:\quad READY\quad FOR\quad MANUAL\quad +\quad BROWSER\quad VALIDATION}$$
