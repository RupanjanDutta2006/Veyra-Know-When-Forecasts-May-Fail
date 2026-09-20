# Day 33 — OOD Policy + Alias / Model Determinism (C2 + C3)

**Phase**: 3 — Scientific Integration & Quality Gates  
**Gates Addressed**: Gate C2 (Out-of-Distribution Policy) & Gate C3 (Alias and Model Determinism)  
**Status**: COMPLETE, VERIFIED & FROZEN  
**Starting Main SHA**: `58f620d59e2a7dbd32d89144a86af2042ff6882e`  

---

## 1. Overview & Objectives

Day 33 formalizes and locks two core scientific and operational contracts:
1. **Gate C2 (Explicit Out-of-Distribution Policy)**: Defines machine-readable OOD diagnostic evaluation based on physical domain support bounds from the 20-year NOAA GEFS benchmark dataset, strictly preserving the scientific separation between OOD diagnostics, scientific certification (Gate C1), calibrated P(BUST), and operational safety abstention.
2. **Gate C3 (Alias and Model Determinism)**: Enforces bitwise deterministic location alias resolution (e.g. `Panaji` $\leftrightarrow$ `Goa`, `Leh` $\leftrightarrow$ `Ladakh`) and model identifier selection (e.g. `veyra-v3-benchmark-lightgbm`, `lightgbm`, `lgbm`, `default` $\rightarrow$ `builder2_v3`), locking cryptographic artifact provenance.

---

## 2. Scientific Governance Principles

### Separation of Core Concepts
1. **Calibrated P(BUST)**: Isotonic probability calibration mapping raw GBDT margins to historical 95th percentile bust frequencies.
2. **Operational Risk Band**: Categorical decision thresholds (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
3. **Scientific Certification (Gate C1)**: Day 32 evidence boundary restricted to the frozen 25 synoptic stations, 3 core variables, $\le 240\text{h}$ lead times, and verified artifact SHA-256 digests.
4. **OOD Diagnostics (Gate C2)**: Physical parameter envelope checks indicating whether atmospheric inputs fall within or outside nominal training support. **Diagnostic only; does not force abstention or modify calibrated probabilities.**
5. **Safety Abstention**: Triggered only by upstream provider failures (`DATA_UNAVAILABLE`), quality control violations (`QC_FAILED`), or probability calibration breakdowns (`CALIBRATION_FAILURE`).
6. **Provider Health & Weather Severity**: Distinct telemetry from model risk or bust probabilities.

---

## 3. Implementation Details

### Gate C2: Machine-Readable OOD Policy
- **Module**: `backend/app/core/ood_policy.py`
- **Schemas**: `backend/app/schemas/ood.py`
- **Policy Version**: `v3.0.0-physical-support`
- **OOD States**:
  - `IN_DISTRIBUTION`: Forecast parameters lie strictly within physical bounding envelopes ($T \in [200, 350]\text{ K}$, $WS \in [0, 60]\text{ m/s}$, $SP \in [50000, 110000]\text{ Pa}$) and diagnostic score $< 45.0$.
  - `OUT_OF_DISTRIBUTION`: Parameters exceed nominal physical bounds or diagnostic novelty $\ge 45.0$.
  - `OOD_UNKNOWN`: Insufficient evidence, non-numeric values, or unmodeled variables.
- **Abstention Guarantee**: `causes_abstention = False`.

### Gate C3: Model and Location Determinism
- **Module**: `backend/app/core/model_determinism.py`
- **Schemas**: `backend/app/schemas/provenance.py`
- **Canonical Model Map**:
  - `None`, `""`, `"default"`, `"veyra-v3-benchmark-lightgbm"`, `"lightgbm"`, `"lgbm"` $\rightarrow$ `builder2_v3` (Authoritative LightGBM Challenger).
  - `"prototype-gbm-v1"` $\rightarrow$ `builder2_gbm` (Legacy Prototype).
  - `"baseline-logistic-v1.0"`, `"logistic"`, `"baseline"` $\rightarrow$ `baseline_logistic` (Baseline Logistic).
  - Unknown identifiers $\rightarrow$ HTTP 422 / ValueError.
- **Authoritative Provenance**:
  - Model SHA-256: `00a8410746f4a0eecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660`
  - Calibrator SHA-256: `9f448606ce4338ded92f238a551b3a9d8e6d2cb5902e8bc687bce5f5850af531`
  - Feature Count: 50 ordered features
  - Calibrator Type: `IsotonicRegression`
  - Decision Threshold: 0.060

---

## 4. API Endpoints

- `GET /v1/ood/policy`: Retrieves authoritative OOD bounding parameters and governance metadata.
- `POST /v1/predict`: Includes `ood_diagnostics` and `model_provenance` fields on `PredictionResponse`.

---

## 5. Verification Results

- **Focused Day 33 Tests**: 22 passed (`backend/tests/test_day33_ood_model_determinism.py`)
- **Full Backend Suite**: 577 passed (0 failed, 0 errors)
- **Frontend Unit Suite**: 100 passed across 9 test files
- **Frontend Production Build**: `tsc && vite build` built cleanly with zero errors in 18.64s.

