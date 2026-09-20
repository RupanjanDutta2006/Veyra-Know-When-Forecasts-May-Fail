# Day 32 — Scientific Certification Gate (C1)

**Veyra — Know When Forecasts May Fail**
*SIH26079 — AI-Based Forecast Bust Detection for Medium-Range Weather Forecasts*
*Phase 3: Operational Reliability & Meteorological Intelligence*
*Authoritative Record: Evidence-Bound Scientific Certification Gate Implementation*

---

## 1. Objective & Purpose

Day 32 implements an explicit, machine-readable **Scientific Certification Layer** (Gate C1) for Veyra.

This layer formally answers:
> *"Is this prediction or evaluation request within a scientifically certified evidence boundary derived from Veyra's frozen benchmark dataset and evaluation artifacts?"*

### Critical Distinction:
Scientific Certification is **strictly distinct** from:
- **Calibrated $P(\text{BUST})$:** The estimated probability of forecast error exceeding the stratum-specific 95th percentile bust threshold.
- **Operational Risk Level:** The operational risk categorizations (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
- **Operational Trust State:** Pipeline integrity diagnostics (`HIGH_CONFIDENCE`, `ABSTAINED`, etc.).
- **Ensemble Dispersion:** GEFS spread measurements.

Certification does NOT alter probabilities or promise forecast accuracy. It asserts whether an operational prediction request lies within the empirical evidence boundaries established in Day 22 (Dataset, Label & Threshold Certification) and Day 23 (Model Championship & Benchmark Evaluation).

---

## 2. Frozen Evidence Sources Used

The certification policy is derived strictly from repository evidence artifacts:

1. **Training Epoch & Reforecast Base (2000–2013):**
   - 547,500 rows across 730 reforecast cycles.
   - Stratum-specific 95th percentile bust threshold policy: $q = 0.95$ computed strictly on TRAIN reforecasts per `(location_id, variable, lead_bin)`.
2. **Validation Holdout (2014–2016):**
   - 116,250 rows across 155 reforecast cycles used for hyperparameter tuning and model selection.
3. **Test Holdout & Benchmark Evaluation (2017–2019):**
   - 116,250 rows across 155 reforecast cycles used for official frozen benchmark certification.
   - **V3 Test Performance:** Average Precision $AP = 0.2047$, $PR\text{-}AUC_{trap} = 0.2124$, $ROC\text{-}AUC = 0.7698$, $Brier = 0.053798$, $ECE = 0.0064$.
4. **Synoptic Station Scope (Frozen Benchmark Evidence Boundary):**
   - Exactly 25 synoptic meteorological stations across India (`Ahmedabad`, `Bengaluru`, `Bhopal`, `Bhubaneswar`, `Chandigarh`, `Chennai`, `Dehradun`, `Delhi`, `Goa` / `Panaji`, `Guwahati`, `Hyderabad`, `Jaipur`, `Kochi`, `Kolkata`, `Leh`, `Lucknow`, `Mumbai`, `Nagpur`, `Pune`, `Raipur`, `Ranchi`, `Shimla`, `Srinagar`, `Thiruvananthapuram`, `Visakhapatnam`).
   - *Operational Distinction:* Veyra's operational `LocationRegistry` and dynamic geocoding service support locations worldwide and across additional regional points. However, **operational support does NOT imply scientific benchmark certification**. Only the 25 canonical stations evaluated under the frozen 1,040-cycle / 780,000-row benchmark dataset carry scientific certification.
   - *Human-Verification Follow-Up:* A human verification audit identified an initial station-scope inflation (where 6 operational stations were incorrectly certified and `Leh` was omitted). This was formally repaired and locked to the exact frozen 25 benchmark stations.
5. **Surface Variable Scope:**
   - 3 surface variables (`temperature_2m`, `wind_speed_10m`, `surface_pressure`).
6. **Lead Horizon Scope:**
   - Lead horizons $\le 240\text{h}$ ($24\text{h}$ to $240\text{h}$ in $24\text{h}$ bins).
7. **Model & Calibrator Checksums:**
   - V3 Model Joblib SHA256: `00A8410746F4A0EECBF7E76AAA0565143FC948D0E06AEA65E7BCC4CE28A1C660`.
   - V3 Calibrator Joblib SHA256: `9F448606CE4338DED92F238A551B3A9D8E6D2CB5902E8BC687BCE5F5850AF531`.
   - Feature count: Exactly 50.
   - Calibrator type: Isotonic Regression.

---

## 3. Certification States & Reason Codes

### Certification States (`CertificationStatus`)
- **`CERTIFIED`:** The prediction/evaluation request satisfies all spatial, variable, lead-horizon, and artifact integrity criteria established in frozen benchmark evidence.
- **`OUTSIDE_CERTIFIED_SCOPE`:** The request uses valid, operationally supported parameters (e.g. valid global coordinate or extended 264h lead horizon), but lies outside the frozen benchmark evidence boundary.
- **`CERTIFICATION_UNKNOWN`:** Model or calibrator artifact SHA mismatch or corrupted metadata preventing deterministic certification.

### Reason Codes (`CertificationReasonCode`)
- `CERTIFIED_FROZEN_BENCHMARK_SCOPE`
- `UNCERTIFIED_LOCATION`
- `UNCERTIFIED_VARIABLE`
- `UNCERTIFIED_LEAD_HORIZON`
- `MODEL_ARTIFACT_MISMATCH`
- `CALIBRATOR_ARTIFACT_MISMATCH`
- `INVALID_REQUEST_PARAMETERS`

---

## 4. Architecture & Implementation

```
               +----------------------------------+
               |  PredictionRequest / Evaluation |
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               |   Certification Policy Engine    |
               | (backend/app/core/cert_policy.py)|
               +----------------------------------+
                 /              |               \
                /               |                \
    Artifact SHA Match?    Location in 25?    Lead <= 240h & Var supported?
                \               |                /
                 \              |               /
                  v             v              v
               +----------------------------------+
               | ScientificCertificationResult    |
               |  - status: CERTIFIED | OUTSIDE   |
               |  - reason: Code + Explanation    |
               |  - certified_scope metadata      |
               |  - observed_scope metadata       |
               +----------------------------------+
```

### Key Modules Created & Modified:
1. **`backend/app/schemas/certification.py` [NEW]:** Defines Pydantic models for `CertificationStatus`, `CertificationReasonCode`, `ScientificCertificationResult`, `CertificationEvaluationRequest`, `CertifiedScope`, and `ObservedScope`.
2. **`backend/app/core/certification_policy.py` [NEW]:** Deterministic policy evaluation engine enforcing benchmark bounds and artifact SHA verification.
3. **`backend/app/api/v1/endpoints/certification.py` [NEW]:** Exposes `POST /v1/certification/evaluate` and `GET /v1/certification/policy`.
4. **`backend/app/schemas/prediction.py` [MODIFY]:** Adds optional `certification` field to `PredictionResponse`.
5. **`backend/app/agents/forecast_bust_agent.py` [MODIFY]:** Populates `certification` result automatically in prediction pipeline.
6. **`frontend/src/api/types.ts` [MODIFY]:** Exports `ScientificCertificationResult` and types for frontend consumption.
7. **`frontend/src/api/client.ts` [MODIFY]:** Adds `getCertificationPolicy()` and `evaluateCertification()`.
8. **`frontend/src/components/PredictionResult.tsx` [MODIFY]:** Displays `CERTIFIED EVIDENCE SCOPE`, `OUTSIDE CERTIFIED EVIDENCE SCOPE`, or `CERTIFICATION UNKNOWN` badge.

---

## 5. Behavioral Case Matrix

| Case | Scenario | Expected Status | Reason Code |
| :--- | :--- | :---: | :--- |
| **Case 1** | Mumbai, `temperature_2m`, 24h lead, V3 model match | `CERTIFIED` | `CERTIFIED_FROZEN_BENCHMARK_SCOPE` |
| **Case 2** | Tokyo (valid resolvable city outside 25 stations) | `OUTSIDE_CERTIFIED_SCOPE` | `UNCERTIFIED_LOCATION` |
| **Case 3** | Mumbai, `temperature_2m`, 264h lead (extended horizon) | `OUTSIDE_CERTIFIED_SCOPE` | `UNCERTIFIED_LEAD_HORIZON` |
| **Case 4** | Mumbai, `relative_humidity_2m` (unsupported variable) | `OUTSIDE_CERTIFIED_SCOPE` | `UNCERTIFIED_VARIABLE` |
| **Case 5** | Model SHA mismatch / artifact corruption | `CERTIFICATION_UNKNOWN` | `MODEL_ARTIFACT_MISMATCH` |
| **Case 6** | Invalid empty location (Runtime Validation Failure) | HTTP 422 Validation Error | Distinct from Certification Failure |
| **Case 7** | Quality Control Abstention (Atlantis / synthetic ocean) | `OUTSIDE_CERTIFIED_SCOPE` | `UNCERTIFIED_LOCATION` (Abstention semantics preserved) |

---

## 6. Verification & Test Summary

- **Backend Unit & Integration Tests (`backend/tests/test_scientific_certification.py`):** 9 / 9 passed (100% Pass Rate).
- **Full Backend Regression (`pytest`):** 546 / 546 passed (100% Pass Rate).
- **Frontend Certification Tests (`frontend/src/test/ScientificCertification.test.tsx`):** 4 / 4 passed (100% Pass Rate).
- **Full Frontend Regression (`vitest`):** 100 / 100 passed across 9 test files (100% Pass Rate).
- **Production Build (`vite build`):** Compiled successfully.

---

## 7. Known Uncertified Boundaries

The following remain explicitly **UNCERTIFIED**:
1. **Post-2019 Temporal Generalization:** Live operational inference running on current weather data is an operational extrapolation, not certified by 2017–2019 holdout evidence.
2. **Unseen Station / Coordinate Generalization:** Locations outside the 25 benchmark synoptic stations are uncertified, even if geocoding succeeds.
3. **Lead Horizons 264–384h:** Extended operational lead horizons are provided for situational awareness but are not benchmark-certified.
4. **N5 Historical vs. N31 Live Equivalence:** Live 31-member GEFS ensembles differ in member size from historical 5-member reforecasts.
5. **Unsupported Variables:** Relative humidity and precipitation lack certified V3 bust detection models.

---

## 8. Development & Git History

- **Base SHA:** `77431c912c958a6b1773d5352e63f76b528654fc` (Day 31 PR #44 merge)
- **Branch:** `phase3/day32-certification-gate`
- **Commit:** `feat(day32): add evidence-bound scientific certification gate`
