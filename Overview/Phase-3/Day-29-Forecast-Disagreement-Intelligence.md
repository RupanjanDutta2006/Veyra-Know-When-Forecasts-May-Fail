# Day 29 — Forecast Disagreement Intelligence

**Veyra — Know When Forecasts May Fail**
*SIH26079 — AI-Based Forecast Bust Detection for Medium-Range Weather Forecasts*
*Phase 3: Operational Reliability & Meteorological Intelligence*
*Authoritative Record: Forecast Disagreement & Ensemble Dispersion Layer*

---

## 1. Objective

The objective of Day 29 is to establish **Forecast Disagreement Intelligence** across Veyra's operational atmospheric evaluation stack. While Veyra natively predicts $P(\text{BUST})$—the calibrated posterior probability that a forecast absolute error will meet or exceed ($\ge$) the stratum-specific 95th percentile historical error threshold—operators also need insight into internal forecast evidence dispersion:

> *"How much disagreement or internal spread exists in the available forecast/ensemble evidence associated with this forecast evaluation?"*

Day 29 delivers quantitative, scientifically defensible disagreement diagnostics derived strictly from **real numerical ensemble data** (NOAA GEFS 31-member perturbation distribution) already ingested in Veyra's forecast pipeline, preserving strict mathematical and visual separation between **forecast disagreement (dispersion)** and **calibrated failure probability $P(\text{BUST})$**.

### Core Boundaries & Guardrails
- **No Fabricated Disagreement Scores:** No synthetic 0–100% "disagreement scores" or arbitrary risk tiers (e.g. no artificial "HIGH DISAGREEMENT" tier).
- **No Synthetic Multi-Model Comparison:** Veyra ingests operational NOAA GEFS (Global Ensemble Forecast System) 31-member data; no fabricated ECMWF/ICON comparisons are constructed.
- **Disagreement $\neq P(\text{BUST})$:** Internal ensemble dispersion describes numerical trajectory divergence and solution spread among available GEFS members; it is not a probability of forecast failure. High spread does not automatically imply a bust; low spread does not guarantee forecast accuracy.
- **Physical Dimensional Units:** Every spread metric is reported in its native variable units (°C for 2m temperature, m/s for 10m wind speed, hPa for surface pressure; dimensionless for ratios and coefficients).
- **No Model Retraining or Calibrator Mutation:** Frozen V3 LightGBM (50 features) and isotonic calibrator remain untouched.

---

## 2. Starting Baseline

Day 29 commenced from the certified and frozen Day 28 baseline:
- **Baseline Git Commit:** `4609f70e69bbf9889afdd25950a67579f6b80bea` (Day 28 post-merge scientific terminology correction)
- **Feature Commit:** `51f2de4ab91cc3648dc434709b1dde399b46b75b`
- **Correction Commit:** `4940da5c6c0dfca16fa2b913897dff6fe6b64ec1`
- **PRs:** Day 28 Feature PR #38, Day 28 Correction PR #39
- **Authoritative Model Artifact:** `models/v3/lightgbm_v3_challenger.joblib`
  - SHA256: `00A8410746F4A0EECBF7E76AAA0565143FC948D0E06AEA65E7BCC4CE28A1C660`
- **Authoritative Calibrator Artifact:** `models/v3/probability_calibrator_v3.joblib`
  - SHA256: `9F448606CE4338DED92F238A551B3A9D8E6D2CB5902E8BC687BCE5F5850AF531`
- **Authoritative Calibration Method:** Isotonic Calibration (`CALIBRATED_ISOTONIC`)
- **Authoritative Feature Count:** 50 input features
- **Starting Test Suite:** 490 / 490 backend tests passed, 77 / 77 frontend tests passed

---

## 3. Architecture & Data Audit

Prior to implementation, a thorough audit of Veyra's forecast ingestion and feature engineering pipelines was conducted to identify real ensemble dispersion signals:

1. **NOAA GEFS Ingestion Pipeline (`backend/app/services/forecast_service.py`):**
   - Retrieves live 31-member numerical ensemble trajectories via Open-Meteo GEFS API.
   - Computes canonical forecast records (`CanonicalForecastRecord`) containing raw perturbation member statistics.
2. **Feature Engineering Engine (`backend/app/ml/v3/feature_pipeline.py`):**
   - Extracts real statistical dispersion features across the 31 ensemble members:
     - Sample standard deviation ($\sigma$, Bessel corrected with $ddof=1$)
     - Ensemble range ($\text{max} - \text{min}$)
     - Interquartile Range (IQR, $Q_{75} - Q_{25}$)
     - Coefficient of Variation ($CV = \sigma / |\mu|$)
     - Spread to IQR ratio ($\sigma / \text{IQR}$)
     - Ensemble mean ($\mu$), minimum, and maximum
3. **50-Feature V3 Model Schema:**
   - Authoritative V3 features already ingest normalized versions of these dispersion metrics (e.g. `ensemble_std`, `ensemble_range`, `ensemble_iqr`, `ensemble_cv`, `spread_to_iqr_ratio`).
   - The underlying physical values in native meteorological units exist in the live inference pipeline and are directly accessible without additional external provider calls.

---

## 4. Real Disagreement Signals Discovered & Selected

| Metric | Field Name | Formulation | Physical Units | Selected? | Operational Utility |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **Ensemble Spread** | `ensemble_spread` | $\sigma = \sqrt{\frac{1}{N-1}\sum_{i=1}^N (x_i - \mu)^2}$ | °C, m/s, hPa | **YES** | Primary metric of forecast trajectory dispersion |
| **Ensemble Std** | `ensemble_std` | Alias of `ensemble_spread` | °C, m/s, hPa | **YES** | Contract alias for programmatic consumers |
| **Ensemble Range** | `ensemble_range` | $x_{\text{max}} - x_{\text{min}}$ | °C, m/s, hPa | **YES** | Full envelope difference across all 31 members |
| **Interquartile Range** | `ensemble_iqr` | $Q_{75} - Q_{25}$ | °C, m/s, hPa | **YES** | Robust 50% core dispersion, insensitive to extreme outliers |
| **Coeff. of Variation** | `ensemble_cv` | $\sigma / (\|\mu\| + 10^{-6})$ | Dimensionless | **YES** | Relative dispersion normalized by mean magnitude |
| **Spread-to-IQR Ratio** | `spread_to_iqr_ratio` | $\sigma / (\text{IQR} + 10^{-6})$ | Dimensionless | **YES** | Diagnostic of distribution tail heaviness |
| **Ensemble Mean** | `ensemble_mean` | $\mu = \frac{1}{N}\sum_{i=1}^N x_i$ | °C, m/s, hPa | **YES** | Central ensemble consensus trajectory |
| **Ensemble Extremes** | `ensemble_min`, `ensemble_max` | $\min(x), \max(x)$ | °C, m/s, hPa | **YES** | Boundary bounds of ensemble envelope |
| **Member Count** | `member_count` | $N$ (active perturbation members) | Integer (31) | **YES** | Provenance verifying full GEFS ensemble ingestion |

---

## 5. Signals Rejected & Why

| Signal | Rationale for Rejection |
| :--- | :--- |
| **Synthetic "Disagreement Score" (0–100%)** | Arbitrary normalization without physical grounding; masks atmospheric reality with artificial percentages. |
| **Arbitrary Disagreement Risk Tiers** | Labeling spread as "HIGH RISK" or "LOW RISK" violates scientific separation between spread and failure probability. |
| **Multi-Model Consensus (ECMWF vs GFS vs ICON)** | Veyra's production pipeline currently ingests NOAA GEFS ensembles; fabricating multi-model comparisons would be fraudulent. |
| **Forecast Certainty / Guaranteed Accuracy** | Unscientific phrasing that misleads operators into assuming zero atmospheric uncertainty. |
| **Continuous Spatial Interpolation** | Spread cannot be smoothly interpolated between distant terrain stations without physical microclimate modeling. |

---

## 6. Backend Architecture

The backend implementation resides in dedicated, modular services without redundant inference pipelines:

1. **`backend/app/schemas/disagreement.py`**:
   - Pydantic schema contracts: `ForecastDisagreementRequest`, `ForecastDisagreementResponse`, `DisagreementDiagnostics`, `DisagreementUnits`, `DisagreementStatus`.
2. **`backend/app/services/disagreement_service.py`**:
   - Centralized `DisagreementService` managing geocoding resolution, canonical GEFS record retrieval, statistical dispersion calculations, units mapping, calibrated $P(\text{BUST})$ association, and horizon scope tagging.
3. **`backend/app/api/v1/endpoints/disagreement.py`**:
   - REST endpoint: `POST /v1/disagreement/diagnostics`
4. **`backend/app/schemas/spatial.py` & `backend/app/services/spatial_service.py`**:
   - Extended `SpatialReliabilityPoint` to incorporate real ensemble dispersion fields (`ensemble_spread`, `ensemble_range`, `ensemble_iqr`, `ensemble_cv`, `spread_unit`, `member_count`), maintaining backend parity with Day 28 multi-location intelligence.

---

## 7. API Contract

### Request: `POST /v1/disagreement/diagnostics`

```json
{
  "location": "Kolkata",
  "variable": "temperature_2m",
  "lead_hours": 24,
  "issue_time": null
}
```

### Response (Success)

```json
{
  "status": "AVAILABLE",
  "location": "Kolkata",
  "resolved_name": "Kolkata",
  "latitude": 22.5726,
  "longitude": 88.3639,
  "variable": "temperature_2m",
  "lead_hours": 24,
  "lead_days": 1.0,
  "issue_time": "2026-09-19T06:00:00Z",
  "valid_time": "2026-09-20T06:00:00Z",
  "diagnostics": {
    "ensemble_spread": 0.522,
    "ensemble_std": 0.522,
    "ensemble_range": 2.0,
    "ensemble_iqr": 1.5,
    "ensemble_cv": 0.01946,
    "spread_to_iqr_ratio": 0.3479,
    "ensemble_mean": 26.82,
    "ensemble_min": 25.7,
    "ensemble_max": 27.7
  },
  "units": {
    "spread": "°C",
    "range": "°C",
    "iqr": "°C",
    "mean": "°C",
    "cv": "dimensionless",
    "spread_to_iqr_ratio": "dimensionless"
  },
  "member_count": 31,
  "has_full_ensemble": true,
  "bust_probability": 0.01768,
  "risk_level": "LOW",
  "trust_state": "HIGH_CONFIDENCE",
  "calibration_status": "CALIBRATED_ISOTONIC",
  "scientific_scope": "WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE",
  "is_certified_horizon": true,
  "abstain": false,
  "reason_codes": ["SUCCESS"],
  "request_id": "disagree_70c1e7d38fc7"
}
```

### Response (Operational Abstention on Unresolved Location)

```json
{
  "status": "ABSTAINED",
  "location": "Atlantis",
  "resolved_name": null,
  "latitude": null,
  "longitude": null,
  "variable": "temperature_2m",
  "lead_hours": 24,
  "lead_days": 1.0,
  "issue_time": null,
  "valid_time": null,
  "diagnostics": null,
  "units": null,
  "member_count": null,
  "has_full_ensemble": null,
  "bust_probability": null,
  "risk_level": null,
  "trust_state": "UNAVAILABLE",
  "calibration_status": "UNAVAILABLE",
  "scientific_scope": "WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE",
  "is_certified_horizon": true,
  "abstain": true,
  "reason_codes": ["LOCATION_NOT_RESOLVED: Atlantis"],
  "request_id": "disagree_8ffab3379d6f"
}
```

---

## 8. Variable-Aware Units

Disagreement metrics strictly reflect the physical units of the underlying meteorological quantity:
- **`temperature_2m`**: `°C`
- **`wind_speed_10m`**: `m/s`
- **`surface_pressure`**: `hPa`
- **`ensemble_cv` & `spread_to_iqr_ratio`**: `dimensionless`

Units update dynamically upon variable selection and are never mixed across variables.

---

## 9. $P(\text{BUST})$ vs. Disagreement Separation

The interface enforces strict cognitive and visual separation:
1. **Calibrated Failure Risk Container**:
   - Displays calibrated $P(\text{BUST})$ percentage, risk badge (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), model version (`V3 LightGBM`), and serving calibrator (`Isotonic Calibrator`).
   - Educational text defines $P(\text{BUST})$ as the empirical probability of exceeding the operational error threshold.
2. **Observed Ensemble Spread Container**:
   - Displays sample standard deviation ($\sigma$), range, IQR, and member count (31 members).
   - Educational note clarifies that dispersion represents ensemble trajectory divergence across member runs, not probability of failure.

---

## 10. Null & Abstention Safety

- When a location cannot be resolved (e.g. "Atlantis") or upstream ensemble data is missing, the backend returns `diagnostics: null` and `status: ABSTAINED`.
- The frontend renders an explicit **Operational Abstention Enforced** alert with exact reason codes.
- **Zero Null-to-Zero Conversion**: Missing diagnostics render as `N/A`, never as `0`, `0%`, or "perfect agreement".

---

## 11. Horizon Scientific Scope

Horizon scope semantics established in Day 24–28 are strictly maintained:
- **$\le 240$h (1–10 Days)**: Tagged as `WITHIN FROZEN BENCHMARK LEAD SCOPE` (green badge), signifying evaluation within the certified benchmark validation domain.
- **$264$h–$384$h (11–16 Days)**: Tagged as `EXTENDED OPERATIONAL HORIZON` (amber badge), clarifying situational awareness beyond certified benchmark leads.

---

## 12. Frontend Implementation

- **`frontend/src/components/ForecastDisagreementPanel.tsx`**:
  - Full-featured standalone panel with station presets (Kolkata, Delhi, Mumbai, Chennai, Bengaluru), custom location input, variable select, lead horizon select, and real-time audit triggers.
  - Cross-navigation buttons to Day 28 Multi-Location View and Day 27 Spatial Map.
- **`frontend/src/components/Navigation.tsx`**:
  - Integrated `Forecast Disagreement` button with `#6366f1` `Day 29` badge.
- **`frontend/src/App.tsx`**:
  - Registered `'disagreement'` active view with seamless cross-module state passing.
- **`frontend/src/components/MultiLocationPanel.tsx`**:
  - Added "Disagreement Intel" header button and "Inspect Forecast Disagreement" drawer action to deep-link directly into Day 29 analysis for any evaluated station.

---

## 13. Test Verification & Results

### Backend Focused Test Suite (`backend/tests/test_disagreement_intelligence.py`)
15 focused test cases covering contract registration, physical units, lead horizon scopes, invalid location abstention, missing ensemble safety, separation of concerns, and validation bounds:
- **Result:** `15 passed in 30.08s` (100% pass rate)

### Full Backend Regression Suite
- **Total Tests Collected:** 505 items across 32 test files
- **Result:** `505 passed in 265.15s (0:04:25)` (100% pass rate)
- Baseline was 490; increased by +15 new Day 29 tests with zero regressions.

### Frontend Test Suite (`frontend/src/test/ForecastDisagreement.test.tsx` + Full Suite)
7 dedicated frontend unit and integration tests covering rendering, metric display, variable switching, horizon scope badges, null/abstention handling, and cross-navigation:
- **Total Frontend Tests:** 84 items across 7 test files
- **Result:** `84 passed in 2.96s` (100% pass rate)
- Baseline was 77; increased by +7 new Day 29 tests.

### Frontend Production Build
- Command: `npm run build` (`tsc && vite build`)
- Result: `built in 6.30s` (zero TypeScript errors, production bundle compiled cleanly).

---

## 14. Live API Verification

Live API requests were executed against the active FastAPI backend service:

| Request Parameters | HTTP | Status | $P(\text{BUST})$ | Risk | Spread | Units | Scope |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| Kolkata, `temperature_2m`, 24h | 200 | `AVAILABLE` | 0.0177 (1.8%) | `LOW` | 0.522 | °C | `WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE` |
| Kolkata, `wind_speed_10m`, 24h | 200 | `AVAILABLE` | 0.0113 (1.1%) | `LOW` | 1.133 | m/s | `WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE` |
| Kolkata, `surface_pressure`, 24h | 200 | `AVAILABLE` | 0.0894 (8.9%) | `LOW` | 0.576 | hPa | `WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE` |
| Kolkata, `temperature_2m`, 240h | 200 | `AVAILABLE` | 0.0092 (0.9%) | `LOW` | 0.378 | °C | `WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE` |
| Kolkata, `temperature_2m`, 264h | 200 | `AVAILABLE` | 0.0145 (1.5%) | `LOW` | 0.430 | °C | `EXTENDED_OPERATIONAL_HORIZON` |
| Kolkata, `temperature_2m`, 384h | 200 | `AVAILABLE` | 0.0470 (4.7%) | `LOW` | 0.646 | °C | `EXTENDED_OPERATIONAL_HORIZON` |
| Atlantis, `temperature_2m`, 24h | 200 | `ABSTAINED` | `null` | `null` | `null` | `null` | `WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE` |

---

## 15. Browser E2E Verification

The browser subagent performed complete end-to-end interactive verification in the frontend application environment:
1. **Navigation:** Verified `Forecast Disagreement` tab with `Day 29` badge in top navbar.
2. **Initial Render:** Confirmed header, NOAA GEFS 31-member badge, scope alert, dual cards ($P(\text{BUST})$ vs Observed Spread), and detailed metrics grid.
3. **Kolkata 24h Temp:** Displayed `1.8% P(BUST)`, `LOW RISK`, `0.52 °C` spread.
4. **Variable Switching:** Switched to `10m Wind Speed (m/s)`, confirmed dynamic unit update to `m/s` and spread of `0.58 m/s`.
5. **Extended Horizon:** Switched to 264h lead horizon; confirmed dynamic scope update to `EXTENDED OPERATIONAL HORIZON (264–384h)`.
6. **Safety Abstention:** Entered "Atlantis"; confirmed `OPERATIONAL ABSTENTION ENFORCED` banner, `N/A P(BUST)`, `ABSTAINED RISK`, and `N/A` spread without zeroes.
7. **Preset Recovery:** Clicked preset "Delhi" and "Kolkata", restoring clean operational evaluations.

---

## 16. Backend / Frontend Value Parity

Exact numeric parity was confirmed between backend JSON responses and UI displays:
- **Backend Kolkata 24h Temp:** $P(\text{BUST}) = 0.01768$ (1.8%), Spread $= 0.522$ °C.
- **Frontend Display:** $P(\text{BUST}) = 1.8\%$, Observed Spread $= 0.52\text{ °C}$.
- No synthetic transformation, scaling, or rounding distortion occurs between server and client.

---

## 17. Final Artifact Integrity & Preservation

- **Authoritative V3 Model:** `models/v3/lightgbm_v3_challenger.joblib`
  - SHA256: `00A8410746F4A0EECBF7E76AAA0565143FC948D0E06AEA65E7BCC4CE28A1C660` *(VERIFIED MATCH)*
- **Authoritative V3 Calibrator:** `models/v3/probability_calibrator_v3.joblib`
  - SHA256: `9F448606CE4338DED92F238A551B3A9D8E6D2CB5902E8BC687BCE5F5850AF531` *(VERIFIED MATCH)*
- **Model Features:** 50 input features *(VERIFIED MATCH)*
- **Calibration Terminology:** Isotonic (`CALIBRATED_ISOTONIC`)
- **Untracked Local Data:** `batch_verification_25.csv` remains untracked, unstaged, and untouched.
- **Legacy Artifacts:** `models/day4/` directory untouched.

---

## 18. Final Verdict

$$\mathbf{DAY29\_COMPLETE\_AND\_FROZEN}$$

Day 29 Forecast Disagreement Intelligence is fully implemented, verified across all unit, regression, live API, and browser gates, scientifically audited, documented, and ready for Git delivery.
