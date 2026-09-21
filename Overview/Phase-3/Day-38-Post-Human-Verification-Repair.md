# Day 38 — Post-Human-Verification Narrow Repair Record
## HV-001 Certification-Scope Presentation Truth + HV-002 Invalid-Location Stale Coordinates

---

### Executive Summary

During human-supervised verification of the Day 38 cross-provider milestone baseline, two user-facing truth-consistency defects were identified:

1. **HV-001 (Certification-Scope Presentation Truth)**: The Reliability Sentinel UI previously presented any forecast horizon with <= 240h with wording such as "Certified Scope" in the Telemetry header and Timeline legend, even when the evaluated geographic location (e.g. Patna) was not one of the 25 frozen certified synoptic stations.
2. **HV-002 (Invalid-Location Stale Coordinate Retention)**: When changing an active target location from a valid station (e.g. Delhi with coordinates 28.6139°N, 77.2090°E) to an invalid/unresolvable location (e.g. `asdfghjkl-not-a-real-place`), the backend correctly returned safe abstention (`INVALID_LOCATION`), but the frontend form retained the old valid coordinates, displaying a misleading association between the unresolved name and the previous coordinates.

Both defects have been repaired with a narrow, zero-regression frontend state and presentation fix. The frozen V3 scientific model and calibrator artifacts remain 100% untouched.

---

### 1. HV-001: Certification-Scope Presentation Repair

#### 1.1 Human Verification Reproduction
- **Input**: Location = `Patna`, Variable = `temperature_2m`, Lead = `24h`.
- **Observed**: Verification Telemetry header rendered `24h Horizon • Certified Scope` and timeline legend rendered `≤240h Certified Scope`.
- **Defect**: Patna is not one of the 25 certified stations in India. While 24h is within the frozen benchmark lead horizon range (<= 240h), the prediction as a whole is `OUTSIDE_CERTIFIED_SCOPE`.

#### 1.2 Root Cause Analysis
The backend certification policy (`backend/app/core/certification_policy.py`) correctly evaluated the request and returned `OUTSIDE_CERTIFIED_SCOPE`. However, in the frontend:
- `VerificationPanel.tsx` checked only `selectedPoint.is_certified_horizon` (which indicates whether lead_hours <= 240) and labeled it `Certified Scope` vs `Operational Scope`.
- `TimelineChart.tsx` legend labeled the benchmark zone as `≤240h Certified Scope`.

#### 1.3 Implementation Repair
1. **Lead Scope vs Prediction Certification Disambiguation**:
   - `VerificationPanel.tsx`: Updated Telemetry Header badge to explicitly state `{leadHours}h Horizon • Within Frozen Benchmark Lead Scope (≤240h)` for <= 240h, and `{leadHours}h Horizon • Extended Operational Horizon (>240h)` for > 240h.
   - Added a dedicated Scientific Certification Banner rendering authoritative prediction status:
     - `CERTIFIED` (25-Station Evidence Scope) when within the 25-station benchmark domain.
     - `OUTSIDE CERTIFIED SCOPE` (Outside Benchmark Scope) with explicit rationale when outside evidence scope.
     - `CERTIFICATION UNKNOWN` as safe fallback.
   - `TimelineChart.tsx`: Updated legend labels to `≤240h Benchmark Lead Scope` and `>240h Operational Lead Scope`.

---

### 2. HV-002: Invalid-Location Stale Coordinate Repair

#### 2.1 Human Verification Reproduction
1. Start with valid `Delhi` -> Coordinates populated: Latitude `28.6139`, Longitude `77.209`.
2. Replace location input with `asdfghjkl-not-a-real-place`.
3. Submit audit -> Prediction enters `INVALID_LOCATION` safe abstention.
4. **Defect**: Latitude and Longitude fields continued to display `28.6139` and `77.209`, creating a false association. Old Delhi marker remained displayed on the map.

#### 2.2 Root Cause Analysis
- `LocationForm.tsx`: Props `lat` and `lon` were typed strictly as `number`, defaulting empty coordinates to Delhi defaults or 0.
- `App.tsx`: `handleAudit` updated `setLat` and `setLon` only inside `if (data.location?.latitude != null)`, lacking an `else` branch to clear coordinates when geocoding failed.
- Free-text edits on the location input did not invalidate previously resolved coordinate state.

#### 2.3 Implementation Repair
1. **Nullable Coordinates**: `lat` and `lon` states in `App.tsx` and props in `LocationForm.tsx` / `ForecastMap.tsx` updated to `number | null`.
2. **Coordinate Invalidation on Input Change**: Typing custom location queries immediately clears resolved coordinates unless matching coordinate regex or preset.
3. **Abstention Clearing**: When `data.location?.latitude == null`, `handleAudit` explicitly resets `setLat(null)` and `setLon(null)`.
4. **Map Marker Truth**: `ForecastMap.tsx` only renders the location marker when valid non-null coordinates exist. Unresolved locations display empty placeholder `Unresolved` without fabricating `(0,0)`.

---

### 3. Frozen Scientific Invariants Verification

The frozen V3 scientific model and calibrator artifacts were verified before and after repair:

| Artifact | Expected SHA256 | Verified SHA256 | Status |
| :--- | :--- | :--- | :--- |
| `models/v3/lightgbm_v3_challenger.joblib` | `00a8410746f4a0eecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660` | `00a8410746f4a0eecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660` | **MATCH** |
| `models/v3/probability_calibrator_v3.joblib` | `9f448606ce4338ded92f238a551b3a9d8e6d2cb5902e8bc687bce5f5850af531` | `9f448606ce4338ded92f238a551b3a9d8e6d2cb5902e8bc687bce5f5850af531` | **MATCH** |

---

### 4. Verification & Regression Coverage

#### 4.1 Automated Backend Suite
```text
python -m pytest backend/tests -q
684 passed in 255.67s
```

#### 4.2 Automated Frontend Suite
```text
npm.cmd test -- --run
Test Files: 9 passed
Tests: 109 passed (5 added tests covering HV-001 & HV-002)
```

#### 4.3 Production Build
```text
npm.cmd run build
✓ 1930 modules transformed.
dist/index.html                   1.07 kB │ gzip:   0.56 kB
dist/assets/index-ChkEuqgs.css   31.48 kB │ gzip:  10.15 kB
dist/assets/index-CuI4aOu1.js   698.05 kB │ gzip: 207.51 kB
✓ built in 6.19s
```

---

### 5. Non-Blocking QA Dispositions

- **QA-W001 (React act(...) test warnings)**: `QA-W001_DEFERRED_NON_BLOCKING` — preserved test-only behavior without polluting production diff.
- **QA-W002 (Vite bundle size >500kB warning)**: `QA-W002_DEFERRED_NON_BLOCKING` — no bundling reconfiguration or code-splitting introduced to preserve release stability.

---

### 6. Acceptance Matrix

| Test Case | Scenario | Expected Outcome | Verified Result |
| :--- | :--- | :--- | :--- |
| **Case A** | Delhi <= 240h | `CERTIFIED`, Benchmark Lead Scope (<= 240h) | **PASS** |
| **Case B** | Delhi 240h | `CERTIFIED`, Benchmark Lead Scope (<= 240h) | **PASS** |
| **Case C** | Delhi 264h | `OUTSIDE CERTIFIED SCOPE`, Extended Operational Horizon (>240h) | **PASS** |
| **Case D** | Patna 24h | `OUTSIDE CERTIFIED SCOPE`, Within Benchmark Lead Scope (<= 240h) | **PASS** |
| **Case E** | New Delhi | Resolves deterministically to Delhi; `CERTIFIED` | **PASS** |
| **Case F** | Delhi -> Invalid Location | `INVALID_LOCATION`, Coordinates cleared/unresolved, no stale Delhi marker | **PASS** |
| **Case G** | Invalid Location -> Kolkata | Restores Kolkata coordinates (22.57°N, 88.36°E); normal operational state | **PASS** |
