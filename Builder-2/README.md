# Veyra — Know When Forecasts May Fail

> **Veyra** is an AI-powered forecast-bust sentinel that evaluates already-issued medium-range weather forecasts and estimates the probability that the forecast will fail unusually badly ("forecast bust").

---

## 🏗️ Architecture & Pipeline Flow

```text
Location Request (e.g., "London" or "25.2048, 55.2708")
      ↓
1. Location Coordinate Resolution
      ↓
2. OpenMeteoGEFSWeatherService (NOAA GEFS 31-member ensemble ingestion)
      ↓
3. ForecastQualityControl (Physical sanity, timestamp uniqueness, ensemble bounds)
      ↓
4. LiveFeatureService (Transforms CanonicalForecastRecords -> 18 normalized features)
      ↓
5. LiveLogisticModelService (Evaluates persisted baseline-logistic-v1.0 via predict_proba)
      ↓
6. SafetyEvaluator (Maps P(bust) -> RiskLevel & TrustState; enforces safe abstention)
      ↓
Standardized API Response (HTTP 200)
```

---

## 🚀 Quickstart & Setup

### 1. Prerequisites & Installation
Ensure Python 3.10+ is installed on your system.

```bash
# Clone the repository
git clone https://github.com/RupanjanDutta2006/Veyra-Know-When-Forecasts-May-Fail.git
cd "Veyra — Know When Forecasts May Fail"

# Install all required runtime and test dependencies
python -m pip install -r requirements.txt
```

### 2. Start the Backend Server
```bash
python -m uvicorn backend.app.main:app --reload --port 8000
```

Once running:
- **Interactive Swagger Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Service Health Check:** [http://127.0.0.1:8000/v1/health](http://127.0.0.1:8000/v1/health)
- **Prediction Endpoint:** `POST http://127.0.0.1:8000/v1/predict`

---

## 📡 API Contract

### Health Check: `GET /v1/health`
**Response (200 OK):**
```json
{
  "status": "ok",
  "service": "forecast-bust-sentinel",
  "version": "0.1.0"
}
```

### Predict Forecast Bust: `POST /v1/predict`

#### 1. Valid Request Example:
```json
{
  "location": "London"
}
```

#### 2. Standardized Successful Response:
```json
{
  "location": "London",
  "bust_probability": 0.4845,
  "risk_level": "MEDIUM",
  "trust_state": "HIGH_CONFIDENCE",
  "abstain": false,
  "reason_codes": [
    "SUCCESS"
  ],
  "model_version": "baseline-logistic-v1.0",
  "data_version": "gefs-openmeteo-v1.0"
}
```

#### 3. Standardized Safe Abstention Response (e.g. Unresolved Location):
```json
{
  "location": "Atlantis",
  "bust_probability": null,
  "risk_level": null,
  "trust_state": "UNAVAILABLE",
  "abstain": true,
  "reason_codes": [
    "INVALID_LOCATION"
  ],
  "model_version": null,
  "data_version": null
}
```

---

## 📍 Supported Locations

Veyra accepts both registered city names and raw coordinate pairs:

- **Named Locations:** `London`, `Tokyo`, `New York`, `Delhi`, `Kolkata`, `Mumbai`, `Berlin`, `Paris`, `Singapore`, `Sydney`, `Dubai`, `Geneva` (case-insensitive, whitespace-trimmed).
- **Explicit Geographic Coordinates:** `"latitude, longitude"` string (e.g., `"25.2048, 55.2708"` or `"22.5726, 88.3639"`).

---

## 🧪 Testing & Verification

### Run Full Automated Pytest Suite (92 Tests)
```bash
python -m pytest
```

### Run Specialized Smoke Tests
```bash
# Day 3: Real GEFS Weather Ingestion Smoke Test
python scripts/smoke_test_weather.py

# Day 4: Historical ERA5 Alignment & Bust-Labeling Smoke Test
python scripts/smoke_test_historical.py

# Day 5: Leakage-Safe Feature Engineering & Baseline ML Smoke Test
python scripts/smoke_test_ml.py

# Day 6: Live Model Serving & Endpoint Smoke Test
python scripts/smoke_test_serving.py

# Day 7: Final End-to-End System Readiness Smoke Test
python scripts/smoke_test_final.py
```

---

## 🧠 Model Architecture & Persistence

- **Artifact Binary:** `models/baseline_logistic_v1.joblib`
- **Metadata Document:** `models/baseline_logistic_v1_metadata.json`
- **Classifier:** `LogisticRegressionBustModel` (`C=1.0`, `class_weight='balanced'`, `max_iter=1000`)
- **Probability Output:** Real continuous probabilities $P(\text{bust}) \in [0.0, 1.0]$ evaluated via the logistic sigmoid link function.
- **Inference-Safe Features (18):**
  - Temporal / Lead: `lead_hours`, `forecast_value`, `latitude`, `longitude`, `month`
  - Cyclic Harmonics: `sin_month`, `cos_month`, `sin_hour`, `cos_hour`
  - Variable One-Hot (5): `var_temperature_2m`, `var_surface_pressure`, `var_wind_speed_10m`, `var_relative_humidity_2m`, `var_precipitation`
  - Season One-Hot (4): `season_winter`, `season_spring`, `season_summer`, `season_autumn`

---

## 🛡️ Safety, OOD & Abstention Policies

- **Zero Fake Predictions:** If upstream weather ingestion, quality control checks, feature normalization, or model artifacts fail, Veyra strictly abstains (`bust_probability: null`, `abstain: true`).
- **Risk Level Categorization:**
  - $P(\text{bust}) < 0.20 \implies \text{LOW}$
  - $0.20 \le P(\text{bust}) < 0.50 \implies \text{MEDIUM}$
  - $0.50 \le P(\text{bust}) < 0.75 \implies \text{HIGH}$
  - $P(\text{bust}) \ge 0.75 \implies \text{CRITICAL}$
- **Trust States:** `HIGH_CONFIDENCE`, `MONITORED`, `DEGRADED`, `UNAVAILABLE`, `ABSTAINED`.

---

## ⚠️ Known Baseline Limitations

1. **Geographically Limited Historical Training Baseline:**  
   The baseline model (`baseline-logistic-v1.0`) was fitted on an initial benchmark historical dataset from a single reference coordinate series. Consequently, spatial features (`latitude`, `longitude`) have small or zero coefficients in this baseline, causing probabilities across different global locations to be very close. This is a training data limitation of the baseline model, not an inference serving bug.
2. **Uncalibrated Baseline Probabilities:**  
   The baseline model outputs raw logistic sigmoid probabilities (`is_calibrated: false`). Advanced non-linear classifiers (LightGBM/XGBoost) and formal calibration (Isotonic/Platt scaling) are planned for Builder 2.

---

## 🔌 Builder 2 Handoff & Integration Interfaces

Builder 2 can easily extend or replace any pipeline stage by implementing the typed contracts in `backend/app/services/base.py`:

- **`BaseWeatherService`**: Ingest alternative ensemble or deterministic weather providers.
- **`BaseFeatureService`**: Add spatial gradients, ensemble spread, atmospheric instability indices.
- **`BaseModelService`**: Plug in gradient-boosted decision trees (LightGBM/XGBoost) with calibrated probability outputs.
- **`BaseSafetyService`**: Enhance out-of-distribution (OOD) distance metrics and adaptive trust gates.

Pass custom implementations into `ForecastBustAgent` via dependency injection without modifying the core application orchestrator.
