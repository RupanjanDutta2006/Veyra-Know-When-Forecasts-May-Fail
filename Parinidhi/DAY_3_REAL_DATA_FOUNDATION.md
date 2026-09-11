# Veyra — Know When Forecasts May Fail
## Day-3 Builder 1 Development Overview: Real Data Foundation

**Project Name:** Veyra — Know When Forecasts May Fail  
**Role:** Builder 1 (Backend API, Orchestration, Real Data Ingestion Foundation, QC Engine & Historical Pathway)  
**Date:** August 25, 2026  
**Git Branch:** `rupanjan/solo-data-ml` (Dedicated Solo Data/ML Foundation Branch)  
**Test Status:** 50/50 Automated Tests Passing (100%)  

---

## 1. Executive Summary

On **Day 3**, to ensure the project does not remain blocked while Builder 2 ramps up, Builder 1 established the **Real Data Foundation** for Veyra on a dedicated branch (`rupanjan/solo-data-ml`).

- **What was accomplished today:**
  1. Built a **real, live forecast-data ingestion service** (`OpenMeteoGEFSWeatherService`) connecting to the public Open-Meteo GFS/GEFS ensemble API.
  2. Implemented a strict **Canonical Forecast Schema** (`CanonicalForecastRecord`, `CanonicalForecastDataset`) preserving `issue_time`, `valid_time`, and calculating exact `lead_hours`.
  3. Built a rigorous meteorological **Quality Control (QC) Engine** (`ForecastQualityControl`) that detects missing values, duplicate timestamps, invalid lead times, inconsistent units, out-of-bounds physical values, and unparseable responses.
  4. Structured strict **Raw vs. Processed Data separation** (`data/raw/`, `data/processed/`) protected by `.gitignore` so large data files are never committed to Git.
  5. Formulated the **Historical Data & Anti-Leakage Pathway** (`HistoricalForecastPair`, `HistoricalPathwayAligner`) with the scientific rule: `availability_time <= issue_time`.
  6. Connected live forecast ingestion directly behind the existing `BaseWeatherService` interface without modifying `ForecastBustAgent` or `main.py`.
  7. Added 15 new automated unit tests (bringing the total suite to **50 tests, 100% passing in 0.17s**).
  8. Conducted an end-to-end live smoke test verifying that 840 canonical forecast records for London reach the backend and pass QC.
  9. Maintained the invariant: **zero fake probabilities** (the prediction endpoint safely returns `abstain=True` with `bust_probability=null` because the ML model is not yet trained).

---

## 2. Data Source Selected & Rationale

- **Primary Source:** Open-Meteo GFS / GEFS Seamless Ensemble API (`https://ensemble-api.open-meteo.com/v1/ensemble`).
- **Why Selected:**
  - **Zero Private Credentials Required:** Free, public, high-availability open endpoint requiring no API keys.
  - **Standard Global Model:** Ingests NOAA GFS / GEFS 31-member ensemble data globally.
  - **High Temporal Resolution:** Hourly forecasts out to 16 days (384 hours).
  - **Standardized Units:** Consistent SI meteorological units (Celsius, hPa, m/s, mm, %).
  - **Clean JSON Interface:** Allows straightforward conversion into Veyra's canonical schema.

---

## 3. Initial Test Location & Variables

### Test Location:
- **Primary Location:** London (Coordinates: `51.5074° N, 0.1278° W`)
- **Supported Registry:** London, Tokyo, New York, Delhi, Berlin, Paris, or arbitrary `"latitude,longitude"` strings.

### Meteorological Variables (Phase 1 Baseline):
1. `temperature_2m` (2-meter air temperature, °C)
2. `surface_pressure` (Surface atmospheric pressure, hPa)
3. `wind_speed_10m` (10-meter wind speed, m/s)
4. `relative_humidity_2m` (2-meter relative humidity, %)
5. `precipitation` (Hourly precipitation accumulation, mm)
6. `geopotential_height_500hPa` (Z500 synoptic pressure level, m)

---

## 4. Canonical Forecast Schema

All ingested vendor data is mapped into [backend/app/schemas/weather.py](file:///backend/app/schemas/weather.py):

```python
class CanonicalForecastRecord(BaseModel):
    location: str
    latitude: float
    longitude: float
    issue_time: str           # Model initialization run cycle (e.g. 2026-08-25T00:00:00Z)
    valid_time: str           # Target verification step (e.g. 2026-08-28T12:00:00Z)
    lead_hours: int           # Calculated strictly as (valid_time - issue_time) in hours
    variable: str             # e.g., "temperature_2m"
    unit: str                 # e.g., "celsius"
    value: Optional[float]    # Control / deterministic value
    source: str               # "NOAA_GEFS_OPENMETEO"
    member_count: Optional[int]
    ensemble_mean: Optional[float]
    ensemble_std: Optional[float]
    ensemble_min: Optional[float]
    ensemble_max: Optional[float]
    q10: Optional[float]
    q90: Optional[float]
    quality_flags: dict[str, Any]
```

---

## 5. Quality Control (QC) Rules

Implemented in [backend/app/data/qc.py](file:///backend/app/data/qc.py):

| QC Check | Threshold / Rule | Failure Action |
|---|---|---|
| **Empty Dataset** | Record count == 0 | Returns `DATA_UNAVAILABLE` |
| **Missing Fields** | Null location, issue_time, or valid_time | Returns `QC_FAILED` |
| **Duplicate Timestamps** | Multiple entries for same `(valid_time, variable)` | Returns `QC_FAILED` |
| **Invalid Timestamps** | Non-ISO-8601 string formatting | Returns `QC_FAILED` |
| **Invalid Lead Times** | `lead_hours < 0` or `lead_hours != (valid - issue)` | Returns `QC_FAILED` |
| **Unit Consistency** | Variable unit != expected standard unit | Returns `QC_FAILED` |
| **Physical Limits** | Temperature: `[-90, 60] °C`<br>Pressure: `[800, 1100] hPa`<br>Wind: `[0, 150] m/s`<br>Humidity: `[0, 100] %`<br>Precipitation: `[0, 1000] mm` | Returns `QC_FAILED` |
| **Ensemble Inconsistency** | `ensemble_min > ensemble_max` | Returns `QC_FAILED` |

> **Scientific Rule:** The QC engine **never invents or interpolates replacement values**. If QC fails, the pipeline safely returns an explicit `QC_FAILED` abstention.

---

## 6. Raw vs. Processed Data Storage

- `data/raw/` — Untouched raw responses from vendor feeds (ignored by Git via `.gitignore`).
- `data/processed/` — Standardized canonical datasets for feature extraction (ignored by Git via `.gitignore`).
- Git repository remains lightweight (zero large binaries, netCDF, grib2, or parquet files committed).

---

## 7. Historical Pathway & Anti-Data-Leakage Rule

Defined in [backend/app/data/historical_pathway.py](file:///backend/app/data/historical_pathway.py):

### Scientific Invariant:
$$\text{availability\_time}(\text{Reference Ground Truth}) \le \text{issue\_time}(\text{Forecast})$$
**MUST NEVER OCCUR FOR LIVE INFERENCE.**

- **Historical Forecast + Reference Alignment:**
  - `forecast_error = forecast_value - reference_value`
  - `is_bust = abs(forecast_error) >= bust_threshold`
  - Verification reference data (ERA5 / station observation) is strictly tagged with `is_ground_truth_label=True` and isolated from live feature calculations.

---

## 8. Plug-and-Play Integration with `ForecastBustAgent`

`OpenMeteoGEFSWeatherService` implements `BaseWeatherService` and plugs seamlessly into `ForecastBustAgent`:

```python
from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService
from backend.app.schemas.prediction import PredictionRequest

# Inject real weather service
weather_service = OpenMeteoGEFSWeatherService()
agent = ForecastBustAgent(weather_service=weather_service)

# Query prediction
request = PredictionRequest(location="London")
response = agent.analyze(request)

# Weather data is ingested & passed QC, but model is unready -> safe abstention
assert response.bust_probability is None
assert response.abstain is True
assert response.trust_state == "UNAVAILABLE"
```

---

## 9. Live Smoke Test Instructions

To execute a live end-to-end network smoke test querying real GFS forecast data for London:

```bash
python scripts/smoke_test_weather.py
```

**Expected Output:**
```text
============================================================
 VEYRA WEATHER INGESTION SMOKE TEST — Location: London
============================================================
[1/3] Resolving coordinates and querying live forecast feed...
[2/3] Response received from provider: gefs-openmeteo-v1.0
      - Available: True
      - QC Passed: True
[3/3] Parsed 840 Canonical Forecast Records successfully.

--- SAMPLE CANONICAL RECORDS (First 3 Time-Steps) ---
  Record #1: Var=temperature_2m       | Val=16.3 celsius  | Issue=2026-08-25T00:00:00Z | Valid=2026-08-25T00:00:00Z | Lead=0h
  Record #2: Var=surface_pressure     | Val=1012.7 hPa    | Issue=2026-08-25T00:00:00Z | Valid=2026-08-25T00:00:00Z | Lead=0h
  Record #3: Var=wind_speed_10m       | Val=17.9 m/s      | Issue=2026-08-25T00:00:00Z | Valid=2026-08-25T00:00:00Z | Lead=0h
-----------------------------------------------------

[+] SMOKE TEST COMPLETED SUCCESSFULLY: Real data reaches backend and passes QC.
```

---

## 10. Builder 2 Future Replacement & Merge Strategy

When Builder 2 creates their dedicated branch (`builder2/weather-ml`):
- Builder 2 can either use this `OpenMeteoGEFSWeatherService` directly or provide a specialized NCMRWF/GEFS downloader implementing `BaseWeatherService`.
- Because all interfaces adhere to `BaseWeatherService` and return `WeatherResult`, we can selectively compare and benchmark implementations without any refactoring.

---

## 11. Automated Test Results (50 Tests Passing)

```text
Platform: win32 | Python: 3.13.5 | Pytest: 9.1.1
Root Directory: C:\Users\RUPANJAN\OneDrive\SIH 2\Actual Project\Veyra_Know When Forecasts May Fail\Veyra — Know When Forecasts May Fail

Results:
  - backend/tests/test_agent.py               8 PASSED
  - backend/tests/test_health.py              2 PASSED
  - backend/tests/test_predict.py            11 PASSED
  - backend/tests/test_qc.py                  7 PASSED
  - backend/tests/test_schemas.py             6 PASSED
  - backend/tests/test_services.py            8 PASSED
  - backend/tests/test_weather_ingestion.py   8 PASSED
  ============================= 50 passed in 0.17s =============================
```
