# Veyra Horizon Request Contract & Developer Guide

## Executive Summary
This document defines the authoritative API request and horizon contracts for **Veyra — Know When Forecasts May Fail**. It explains the technical root cause of the previous 16-day script discrepancy, details the exact request schemas for single and multi-horizon evaluations, and establishes operational rules for probability interpretation, safety boundaries, and client tooling.

---

## 1. Why the Old Terminal Script Was Misleading

### The Symptom
Older or manual developer verification scripts looped over lead hours (from 24 to 384 in steps of 24) and repeatedly invoked:
```http
POST /v1/predict
Content-Type: application/json

{
  "location": "Delhi",
  "latitude": 28.6139,
  "longitude": 77.2090,
  "lead_hours": 48,
  "variable": "temperature_2m"
}
```
The terminal script printed the loop counter as the horizon label:
```text
Day  1 ( 24h): P(Bust) = 0.010356731875719217
Day  2 ( 48h): P(Bust) = 0.010356731875719217
Day  3 ( 72h): P(Bust) = 0.010356731875719217
...
Day 16 (384h): P(Bust) = 0.010356731875719217
```
This created a false perception that the V3 ML model returned the same probability for all 16 days.

### The Root Cause
1. **Schema Contract**: `lead_hours`, `latitude`, and `longitude` were never fields of `PredictionRequest`.
2. **Silent Discard**: By default, Pydantic v2 ignored extra fields (`extra="ignore"`), discarding `lead_hours`, `latitude`, and `longitude` silently without an error.
3. **Canonical Default Fallback**: Without explicit `issue_time` and `valid_time` parameters, the feature extraction layer (`Builder2V3FeatureAdapter`) defaulted to the canonical operational horizon: `DEFAULT_OPERATIONAL_LEAD_HOURS = 24`.
4. **Client Attribution Error**: Every iteration of the loop was evaluated by the backend as a 24-hour prediction, while the client script attributed each result to 48h, 72h, etc.
5. **The Trajectory Itself Is Intact**: Calling the authoritative multi-horizon endpoint `POST /v1/dashboard/intelligence` with `mode: "full_16d"` returned 16 distinct, calibrated probabilities matching real atmospheric divergence across horizons.

---

## 2. Prevention of Silent Extra-Field Misuse

To prevent developers or scripts from repeating this error:
- `PredictionRequest` and `DashboardRequest` now enforce `model_config = {"extra": "forbid"}`.
- Sending unsupported fields (such as `lead_hours`, `latitude`, `longitude`, or typos) immediately yields an **HTTP 422 Unprocessable Entity** response with detail `extra_forbidden`:
```json
{
  "detail": [
    {
      "type": "extra_forbidden",
      "loc": ["body", "lead_hours"],
      "msg": "Extra inputs are not permitted",
      "input": 48
    }
  ],
  "error": "VALIDATION_ERROR",
  "request_id": "req_..."
}
```

---

## 3. Authoritative API Contracts

### Contract A: Single / Canonical 24-Hour Prediction
Used for evaluating standard next-day operational risk for a location.

```http
POST /v1/predict
Content-Type: application/json

{
  "location": "Delhi",
  "variable": "temperature_2m"
}
```
**Response Contract:**
Returns a `PredictionResponse` evaluating the canonical 24h horizon with `lead_hours: 24`.

---

### Contract B: Explicit Single Horizon
Used when evaluating bust risk for a specific forecast verification timestamp.

```http
POST /v1/predict
Content-Type: application/json

{
  "location": "Delhi",
  "variable": "temperature_2m",
  "issue_time": "2026-09-11T00:00:00Z",
  "valid_time": "2026-09-13T00:00:00Z"
}
```
**Validation & Calculation Rules:**
- `lead_hours` is derived strictly by the backend as `(valid_time - issue_time) / 3600.0`.
- In the example above, `(2026-09-13T00:00:00Z - 2026-09-11T00:00:00Z) = 48 hours`.
- `valid_time` must be strictly after `issue_time` (`lead_hours > 0`).
- Maximum supported horizon is 384 hours (16 days). Exceeding 384h returns HTTP 422.
- The response returns `lead_hours: 48` and `valid_time: "2026-09-13T00:00:00Z"`.

---

### Contract C: Standard 7-Day Trajectory
Used for medium-range operational monitoring across Day 1 to Day 7.

```http
POST /v1/dashboard/intelligence
Content-Type: application/json

{
  "location": "Delhi",
  "variable": "temperature_2m",
  "mode": "standard_7d"
}
```
**Timeline Points (7 total):**
- 24, 48, 72, 96, 120, 144, 168 hours.
- All 7 points are within the certified benchmark scope (`is_certified_horizon = true`).

---

### Contract D: Full 16-Day Trajectory
The authoritative endpoint for comprehensive medium- to extended-range multi-horizon risk trajectories.

```http
POST /v1/dashboard/intelligence
Content-Type: application/json

{
  "location": "Delhi",
  "variable": "temperature_2m",
  "mode": "full_16d"
}
```
**Timeline Points (16 total):**
- Exactly 16 points: 24, 48, 72, 96, 120, 144, 168, 192, 216, 240, 264, 288, 312, 336, 360, 384 hours.
- Strictly increasing `valid_time` in 24-hour steps (`valid_time = issue_time + lead_hours`).

---

## 4. Scientific Calibration & Probability Interpretation

### Stepwise Isotonic Calibration
The V3 production pipeline calibrates raw LightGBM probability outputs using **Isotonic Regression** fitted on the certified validation partition.

> [!IMPORTANT]
> Isotonic calibration produces a piecewise constant (stepwise monotonic) mapping function.
> Consequently:
> - Adjacent lead horizons (e.g. 72h and 96h, or 216h and 240h) may legitimately map to the **exact same calibrated probability** if their raw ensemble dispersion scores fall within the same isotonic step.
> - **DO NOT** assert or expect that `len(set(probabilities)) == 16`. Equal probabilities across adjacent steps are scientifically valid and expected.
> - What MUST be unique and strictly increasing are `lead_hours` and `valid_time`.

---

## 5. Strict Null / Abstention Safety Rules

When data is missing, quality control fails, or a location cannot be resolved:
1. **Never Convert Null to Zero**: An uncomputed or abstained probability must remain `null` in JSON and display as `ABSTAIN` or `NULL` in terminal output.
2. **Never Fabricate Risk**: If the model abstains, `risk_level` must be `null` in JSON and display as `NULL` in terminal output. It must **never** default to `LOW`.
3. **Never Fabricate Trust**: `trust_state` must be `UNAVAILABLE` or `ABSTAINED`, never `SUPPORTED` or `HIGH_CONFIDENCE`.
4. **Preserve Reason Codes**: Always preserve and inspect `reason_codes` (e.g., `INVALID_LOCATION`, `DATA_UNAVAILABLE`, `OOD_ABSTAIN`).

---

## 6. Certified Benchmark Scope vs. Operational Extension

| Horizon Range | Status | Meaning |
| :--- | :--- | :--- |
| **24h – 240h** (Days 1–10) | **CERTIFIED** (`is_certified_horizon = true`) | Formally certified on the frozen Day 23 championship test partition (2017–2019, 116,250 samples across 25 canonical stations in India). |
| **264h – 384h** (Days 11–16) | **OPERATIONAL ONLY** (`is_certified_horizon = false`) | Inferred live from NOAA GEFS 16-day operational cycles. Provided for situational awareness but uncertified by frozen historical benchmark test partitions. |

---

## 7. Official PowerShell Verification Script

The repository provides a canonical, hardened verification tool at `scripts/verify_16day_trajectory.ps1`.

### Basic Execution (Delhi Temperature):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_16day_trajectory.ps1 -Location "Delhi" -Variable "temperature_2m"
```

### Different Locations & Variables:
```powershell
# Kolkata Wind Speed
powershell -ExecutionPolicy Bypass -File scripts\verify_16day_trajectory.ps1 -Location "Kolkata" -Variable "wind_speed_10m"

# Mumbai Surface Pressure
powershell -ExecutionPolicy Bypass -File scripts\verify_16day_trajectory.ps1 -Location "Mumbai" -Variable "surface_pressure"

# Negative Control (Atlantis) — verifies pure safe abstention without fake LOW
powershell -ExecutionPolicy Bypass -File scripts\verify_16day_trajectory.ps1 -Location "Atlantis"
```

---

## 8. Summary Comparison of Endpoints

| Endpoint | Intended Use | Supported Horizons | Accepts `lead_hours`? |
| :--- | :--- | :--- | :--- |
| `POST /v1/predict` | Single horizon evaluation | 24h default, or single target via `issue_time` + `valid_time` | **NO** (HTTP 422) |
| `POST /v1/dashboard/intelligence` | Multi-horizon timelines & summary | `single` (24h), `standard_7d` (24–168h), `full_16d` (24–384h) | **NO** (set via `mode`) |
