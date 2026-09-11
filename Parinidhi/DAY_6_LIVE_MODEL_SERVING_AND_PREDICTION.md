# Veyra — Know When Forecasts May Fail
## Day-6 Builder 1 Development Overview: Live Model Serving & End-to-End Prediction Integration

**Project Name:** Veyra — Know When Forecasts May Fail  
**Role:** Builder 1 (Backend Architecture, Live Model Serving, Feature Parity, End-to-End Prediction)  
**Date:** August 26, 2026  
**Git Branch:** `rupanjan/day5-ml-baseline` (Active development branch for Day 5 & Day 6)  
**Test Status:** 87/87 Automated Tests Passing (100%)  

---

## 1. Executive Summary

On **Day 6**, Builder 1 successfully integrated the verified **Day-5 trained Machine Learning Model** (`models/baseline_logistic_v1.joblib`) into the live Veyra prediction pipeline without retraining or altering working Day 1–5 components.

- **Key Achievements:**
  1. **Production-Safe Model Service:** Implemented `LiveLogisticModelService` loading `models/baseline_logistic_v1.joblib` and `models/baseline_logistic_v1_metadata.json` with singleton caching, graceful failure handling, and dimension checks.
  2. **Live Feature Extraction Service:** Implemented `LiveFeatureService` transforming real `CanonicalForecastRecord`s via the persisted `FeaturePipeline` into the exact 18-feature space fitted during training.
  3. **Strict Training-Serving Parity:** Guaranteed zero training-serving skew by enforcing the exact feature ordering and scaling parameters ($\mu, \sigma$) established during Day 5.
  4. **Strict Anti-Data-Leakage Isolation:** Ground-truth reference values (ERA5), forecast errors, and bust labels remain completely isolated from live feature vectors.
  5. **Safety & Risk Integration:** Connected live inference outputs through `SafetyEvaluator`, mapping continuous probabilities into risk levels (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) with confidence states (`HIGH_CONFIDENCE`, `UNAVAILABLE`).
  6. **End-to-End Live `/v1/predict` Endpoint:** Wired live services into the default FastAPI dependency injection provider. Verified real-time forecast evaluation for London and Kolkata.
  7. **Preserved Safe Abstention:** If upstream weather ingestion, QC, or model artifacts fail, the system safely abstains with `bust_probability: null`, `abstain: true`, and standard reason codes.
  8. **Comprehensive Automated Test Suite:** Added 6 new tests in `backend/tests/test_live_serving.py`, growing the test suite to **87 tests (100% passing in 1.45s)**.
  9. **Live Serving Smoke Test:** Created and verified `scripts/smoke_test_serving.py`.

---

## 2. End-to-End Production Pipeline Flow

```text
User Request: POST /v1/predict {"location": "London"}
        ↓
1. Location Coordinate Resolution (e.g. 51.5074, -0.1278)
        ↓
2. OpenMeteoGEFSWeatherService (NOAA GEFS 31-member ensemble forecast)
        ↓
3. ForecastQualityControl (Timestamp uniqueness, boundary checks, ensemble sanity)
        ↓
4. LiveFeatureService (Transforms CanonicalForecastRecords -> 18 normalized features)
        ↓
5. LiveLogisticModelService (Loads baseline_logistic_v1.joblib -> P(bust) via sigmoid)
        ↓
6. SafetyEvaluator (Maps P(bust) -> RiskLevel & TrustState; handles fallback abstention)
        ↓
Standardized API Response:
{
  "location": "London",
  "bust_probability": 0.4845,
  "risk_level": "MEDIUM",
  "trust_state": "HIGH_CONFIDENCE",
  "abstain": false,
  "reason_codes": ["SUCCESS"],
  "model_version": "baseline-logistic-v1.0",
  "data_version": "gefs-openmeteo-v1.0"
}
```

---

## 3. Training-Serving Feature Parity (18 Features)

| Feature Name | Description | Source at Live Inference Time |
|---|---|---|
| `lead_hours` | Lead time in hours | Target forecast horizon |
| `forecast_value` | Numerical forecast value | GEFS ensemble mean / deterministic forecast |
| `latitude` | Coordinate latitude | Target location coordinate |
| `longitude` | Coordinate longitude | Target location coordinate |
| `month` | Calendar month (1–12) | Forecast valid date |
| `sin_month`, `cos_month` | Cyclic month transformation | Periodic annual seasonality |
| `sin_hour`, `cos_hour` | Cyclic issue-hour transformation | Diurnal initialization cycle (00Z, 06Z, 12Z, 18Z) |
| `var_*` (5 One-Hot Columns) | `temperature_2m`, `surface_pressure`, `wind_speed_10m`, `relative_humidity_2m`, `precipitation` | Standard meteorological variable identifiers |
| `season_*` (4 One-Hot Columns) | `winter`, `spring`, `summer`, `autumn` | Calendar meteorological season |

---

## 4. Live Serving Smoke Test Execution

```bash
python scripts/smoke_test_serving.py
```

**Output:**
```text
=================================================================
 VEYRA DAY 6 — LIVE MODEL SERVING & PREDICTION SMOKE TEST
=================================================================
[1/6] Services initialized:
      - Weather Service: OpenMeteoGEFSWeatherService
      - Feature Service: LiveFeatureService (Ready: True)
      - Model Service:   LiveLogisticModelService (Loaded: True, Version: baseline-logistic-v1.0)
      - Safety Service:  SafetyEvaluator

[2/6] Querying live forecast for 'London'...
      - Weather Available: True
      - QC Status:         True
      - Data Version:      gefs-openmeteo-v1.0

[3/6] Extracting inference features...
      - Features Ready:    True
      - Feature Count:     18
      - Schema Version:    veyra-features-v1.0
      - Sample Features:   lead_hours=-0.5, fc_val=-0.2805

[4/6] Running model prediction with persisted Logistic Regression model...
      - Model Ready:       True
      - P(BUST):           0.4845
      - Model Version:     baseline-logistic-v1.0
      - Aggregation:       mean

[5/6] Evaluating Safety & Trust Layer...
      - Abstain:           False
      - Trust State:       HIGH_CONFIDENCE
      - Risk Level:        MEDIUM
      - Reason Codes:      ['SUCCESS']

[6/6] End-to-End ForecastBustAgent Execution for 'London':

--- STANDARDIZED PREDICTION RESPONSE ---
  location:         "London"
  bust_probability: 0.4845
  risk_level:       "MEDIUM"
  trust_state:      "HIGH_CONFIDENCE"
  abstain:          False
  reason_codes:     ['SUCCESS']
  model_version:    "baseline-logistic-v1.0"
  data_version:     "gefs-openmeteo-v1.0"
----------------------------------------

[+] DAY 6 LIVE SERVING SMOKE TEST COMPLETED SUCCESSFULLY.
```

---

## 5. Automated Test Results (87 Tests Passing)

```bash
python -m pytest
```

```text
Platform: win32 | Python: 3.13.5 | Pytest: 9.1.1
Root Directory: C:\Users\RUPANJAN\OneDrive\SIH 2\Actual Project\Veyra_Know When Forecasts May Fail\Veyra — Know When Forecasts May Fail

Results Breakdown:
  - backend/tests/test_agent.py                 8 PASSED (Day 1-2 Agent pipeline suite)
  - backend/tests/test_bust_labeling.py         5 PASSED (Day 4 Bust labeling suite)
  - backend/tests/test_health.py                2 PASSED (Day 1 Health API suite)
  - backend/tests/test_historical_alignment.py  6 PASSED (Day 4 Alignment & Error suite)
  - backend/tests/test_historical_dataset.py    4 PASSED (Day 4 Dataset suite)
  - backend/tests/test_live_serving.py          6 PASSED (Day 6 Live Model Serving suite)
  - backend/tests/test_ml_features.py           4 PASSED (Day 5 Feature Engineering suite)
  - backend/tests/test_ml_model_and_eval.py     4 PASSED (Day 5 ML Model & Eval suite)
  - backend/tests/test_ml_splitting.py          3 PASSED (Day 5 Temporal Splitting suite)
  - backend/tests/test_predict.py              11 PASSED (Day 1-2 & 6 Prediction endpoint suite)
  - backend/tests/test_qc.py                    7 PASSED (Day 3 Quality Control suite)
  - backend/tests/test_schemas.py               6 PASSED (Day 1-3 Schemas suite)
  - backend/tests/test_services.py              8 PASSED (Day 2 Base Services suite)
  - backend/tests/test_unit_conversion.py       5 PASSED (Day 4 Unit Conversion suite)
  - backend/tests/test_weather_ingestion.py     8 PASSED (Day 3 Weather Ingestion suite)
  ============================= 87 passed in 1.45s =============================
```
