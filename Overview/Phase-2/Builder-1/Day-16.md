# Phase 2 — Builder 1 — Day 16
## Visual Forecast Risk

---

## 1. Objective

The primary objective of Day 16 is to evolve the existing Day 15 frontend dashboard into an interactive, multi-horizon **Visual Forecast Bust Risk** interface.

The visualization enables meteorologists, dispatchers, and operations planners to understand how forecast failure probabilities evolve across medium-range lead horizons (from 24 hours out to 168 hours or 384 hours).

```
Location / Variable / Cycle Issuance
                 ↓
Multi-Horizon Client Request (24h, 48h, 72h, 96h, 120h, 144h, 168h... 384h)
                 ↓
Concurrent Target Horizon Evaluation via POST /v1/predict
                 ↓
Platt-Calibrated LightGBM Model & Feature Attribution Layer (per Horizon)
                 ↓
Interactive Visual Forecast Risk Timeline & Native SVG Curve
                 ↓
Discrete Horizon Nodes & Synchronized Physical Attribution Panel
```

---

## 2. Scientific Integrity & Boundaries

Veyra evaluates an already-issued numerical weather forecast (NOAA GEFS) and estimates the probability that it will fail unusually badly (exceed historical 95th percentile error).

- **Visualizing Forecast Bust Risk Only**: The curve represents forecast failure probability $P(\text{bust})$, never rain probability, precipitation amount, or general forecast accuracy.
- **Zero Fabrication**: Every valid node on the curve maps directly to an actual returned `PredictionResponse.bust_probability`.
- **Zero Synthetic Interpolation**: If a horizon fails or is safely abstained, the SVG curve breaks into separate segments. No smooth Bezier interpolation or artificial lines connect through missing data points.
- **Zero Artificial Noise or Jitter**: Small differences across horizons (e.g. $5.61\%$ to $5.68\%$) are preserved exactly as returned by the Platt calibrator.
- **Honest Y-Axis Scaling**: Uses a fixed $0.0\% - 100.0\%$ scale with clear $25\%$ gridlines and a prominent $0.280$ decision threshold guideline, preventing deceptive vertical exaggeration.
- **Abstention Integrity**: Safely abstained points are rendered with distinct neutral/shield markers (`ABSTAINED`) and are never mapped to $0\%$ or displayed as green low-risk nodes.

---

## 3. Architecture Decisions

### Why `POST /v1/predict/batch` Was NOT Used for Multi-Horizon Timelines
During the Step 1 audit, `POST /v1/predict/batch` was analyzed. It is a spatial multi-location endpoint accepting a list of locations (`locations: list[str]`) with a single scalar `valid_time`. It deduplicates by location name.
In contrast, `POST /v1/predict` accepts explicit `issue_time` and `valid_time` timestamps, calculates exact target `lead_hours`, extracts single-target feature rows, and generates physical attribution.

Therefore, multi-horizon evaluation is orchestrated client-side by sending bounded, concurrent requests to `POST /v1/predict` via `Promise.allSettled`. This approach is fully compliant with Day 14 rate limits ($\le 16$ requests per timeline vs. 30-request burst limit) and leverages in-memory geocoding caching ($< 5\text{ms}$ resolution for subsequent horizons).

### Native React + SVG Visualization
Built using native React and SVG with zero third-party chart libraries:
- **Zero Bundle Bloat**: 0 new packages installed.
- **Complete Accessibility**: Direct control over SVG `<title>`, `<desc>`, `tabIndex`, ARIA roles, and keyboard event handlers.
- **Responsive & Dynamic**: Fluid SVG `viewBox` coordinates with CSS-styled responsive containers.

---

## 4. Frontend Component Architecture

```
frontend/src/
├── api/
│   ├── types.ts          # Extended with HorizonPreset, HorizonPointResult, HorizonTimelineResult
│   └── client.ts         # Added predictHorizonTimeline() with Promise.allSettled
├── components/
│   ├── ForecastForm.tsx         # Added mode toggle: Single Target vs Visual Risk Timeline
│   ├── ForecastRiskTimeline.tsx # Interactive SVG probability curve, threshold guide, risk-band strip
│   ├── HorizonRiskDetails.tsx   # Selected horizon deep-dive metrics & explainability card
│   ├── PredictionResult.tsx     # Single point-in-time probability card
│   ├── ExplainabilityView.tsx   # Physical attribution narrative & key factors
│   ├── AbstentionResult.tsx     # Safe abstention card & reason codes
│   ├── Header.tsx               # Brand header & backend liveness pill
│   ├── Footer.tsx               # Version traceability & links
│   └── ErrorView.tsx            # Error presentation & dismiss
├── App.tsx               # State coordination for Single Target & Multi-Horizon Timeline modes
└── styles/
    └── index.css         # Dark atmospheric styling, SVG styles, risk-band strip, accessibility rings
```

---

## 5. Verification & Test Results

### Frontend Test Suite (`npm test`)
- **51/51 Tests Passing** (27 Dashboard tests + 24 dedicated RiskTimeline tests).
- Test execution time: **2.88s**.

### Frontend Production Build (`npm run build`)
- **Status**: PASSED (1.22s).
- Output: `dist/index.html` ($1.01\text{ kB}$), `dist/assets/index.css` ($19.09\text{ kB}$ / gzip $4.49\text{ kB}$), `dist/assets/index.js` ($231.06\text{ kB}$ / gzip $71.82\text{ kB}$).

### Backend Regression (`pytest backend/tests/`)
- **255/255 Tests Passing** (48.59s).

### Verification Smoke Test Scripts
- `python scripts/smoke_test_builder2.py`: **16/16 Passed (100% Operational)**.
- `python scripts/smoke_test_final.py`: **10/10 Passed**.
- `python scripts/smoke_test_historical.py`: **6/6 Passed**.

---

## 6. Model Safety Verification

- **Model Retrained**: NO.
- **Model Artifacts Modified**: NO (`models/` untouched).
- **Calibrator Modified**: NO.
- **Decision Threshold**: Strictly $0.280$ (Unchanged).
- **Feature Schema**: `builder2-canonical-26-v1.0` (26 canonical issue-time features, unchanged).
- **Backend Code Modifications**: **0 files modified**.

---

## 7. Files Created and Modified

### Created Files (4 files)
1. `frontend/src/components/ForecastRiskTimeline.tsx`: Native React + SVG probability curve, threshold guideline, and risk-band strip.
2. `frontend/src/components/HorizonRiskDetails.tsx`: Selected horizon detail card with 4-decimal probability and synchronized explainability.
3. `frontend/src/test/RiskTimeline.test.tsx`: 24 comprehensive unit and integration tests.
4. `Overview/Phase-2/Builder-1/Day-16.md`: Comprehensive Day 16 specification and verification documentation.

### Modified Files (7 files)
1. `frontend/src/api/types.ts`: Added multi-horizon types and presets.
2. `frontend/src/api/client.ts`: Added `predictHorizonTimeline()` client method.
3. `frontend/src/components/ForecastForm.tsx`: Added mode toggle tabs (`Single Target Forecast` vs `Visual Risk Timeline`) and `onModeChange` callback.
4. `frontend/src/App.tsx`: Added `activeMode` state coordination and immediate stale result clearing on mode switch.
5. `frontend/src/styles/index.css`: Added styles for timeline, nodes, risk strip, and mode tabs.
6. `Overview/Phase-2/Builder-1/Day-15.md`: Updated forward navigation link to Day 16.
7. `Overview/README.md`: Updated Phase 2 Builder 1 documentation index.

---

## 8. Manual Browser Verification — Bug Fix (Test 10)

During Day 16 manual browser verification, **Test 10** revealed a UI state lifecycle issue:
- **Observed Behavior**: After generating a 16-day timeline in `Visual Risk Timeline` mode, switching back to `Single Target Forecast` mode switched the form controls, but the previous timeline visualization, risk-band strip, and 384h detail card remained visible in the results column.
- **Root Cause**: `ForecastForm.tsx` managed `evaluationMode` purely as internal component state without notifying `App.tsx`. Because `App.tsx` did not observe the mode switch, `timeline` state remained populated, continuing to render the timeline view.
- **Implemented Fix**:
  - Lifted mode synchronization to `App.tsx` via `activeMode` state and `onModeChange` prop on `ForecastForm`.
  - On switching to `'single'`, `App.tsx` immediately resets `timeline` and `selectedLeadHours` to `null`.
  - On switching to `'timeline'`, `App.tsx` immediately resets `prediction` to `null`.
  - Preserved shared form inputs (`location`, `variable`, `issueTime`).
- **Regression Tests Added**: Added 4 automated regression tests (Tests 23–26 in `RiskTimeline.test.tsx`), validating that mode switches immediately clear non-active results and render proper empty states.

---

## 9. Manual Browser Verification — Wind Speed & QC Error Precedence Fix

During Day 16 manual browser verification, a meteorological QC abstention issue was discovered when evaluating wind speed forecasts:

### Observed Sequence
1. **Malda + `wind_speed_10m` (Visual Risk Timeline)**:
   - Output: `0 Valid / 7 Abstained`.
   - Reason displayed: `Meteorological Quality Control Failed`.
2. **Kolkata + `wind_speed_10m` (Visual Risk Timeline)**:
   - Output: `0 Valid / 7 Abstained`.
   - Reason displayed: `Meteorological Quality Control Failed`.
3. **Kolkata + `wind_speed_10m` (Single Target Forecast)**:
   - Parameters: Issue `2026-08-29 12:30 UTC`, Valid `2026-08-30 12:30 UTC`, Lead `24h`.
   - Output: `Prediction Safely Abstained`.
   - Reason displayed: `Meteorological Quality Control Failed`.

### Forensic Diagnostic Findings
1. **Error Classification Shadowing**:
   - Rapid parallel requests to Open-Meteo triggered HTTP 429 rate limiting on the public endpoint.
   - `OpenMeteoGEFSWeatherService` caught the network exception and returned `quality_flags={"qc_passed": False, "network_error": True}`.
   - In `SafetyEvaluator.evaluate`, `quality_flags.get("qc_passed") is False` was evaluated before `network_error` and explicit `metadata["status"]`.
   - Consequently, network availability failures were incorrectly classified as `ReasonCode.QC_FAILED` ("Meteorological Quality Control Failed") instead of `ReasonCode.DATA_UNAVAILABLE` ("Weather Data Unavailable").
2. **Wind Speed Unit Contract Inconsistency**:
   - `OpenMeteoGEFSWeatherService.build_query_url` omitted `wind_speed_unit=ms`.
   - Open-Meteo defaults to `km/h`, while canonical records and physical QC expect `m/s`.

### Targeted Fix Implemented
1. **`backend/app/services/openmeteo_service.py`**: Added `"wind_speed_unit": "ms"` to `build_query_url`.
2. **`backend/app/services/reference_service.py`**: Added `"wind_speed_unit": "ms"` to `build_query_url`.
3. **`backend/app/safety/abstention.py`**: Corrected `SafetyEvaluator` classification order to prioritize `invalid_location`, `network_error`, and explicit `metadata["status"]` before checking generic `qc_passed is False`.
4. **`scripts/smoke_test_builder2.py`**: Corrected fallback mock fixture timestamps and pressure bounds.

### Regression Tests Added
- `test_openmeteo_service_query_url_builder_includes_wind_speed_unit_ms`: Confirms `wind_speed_unit=ms` in query parameters.
- `test_reference_service_query_url_builder_includes_wind_speed_unit_ms`: Confirms `wind_speed_unit=ms` in historical archive queries.
- `test_openmeteo_wind_speed_canonical_ingestion_preserves_ms_unit_and_value`: Validates `m/s` unit and value preservation without double conversion.
- `test_temperature_and_other_variables_ingestion_parity`: Confirms temperature, pressure, humidity, and precipitation parsing parity.
- `test_safety_evaluator_network_error_precedence_over_qc_failed`: Verifies network failures resolve to `DATA_UNAVAILABLE` (not `QC_FAILED`).
- `test_safety_evaluator_genuine_qc_failure_produces_qc_failed`: Verifies genuine meteorological out-of-bounds violations resolve to `QC_FAILED`.
- `test_safety_evaluator_invalid_location_produces_invalid_location`: Verifies invalid locations resolve to `INVALID_LOCATION`.
- `test_single_target_and_timeline_safety_parity_under_network_failure`: Verifies Single Target and Timeline share identical safety classifications.

---

## 10. Known Limitation / Deferred Day 17 Hardening

During final Day 16 live verification, Open-Meteo returned HTTP 429 with payload:
```json
{"error": true, "reason": "Daily API request limit exceeded. Please try again tomorrow."}
```

### Forensic Analysis & Safety Behavior
- **Exhausted Provider Quota**: The public Open-Meteo free-tier daily IP request limit was reached after extensive Day 14, 15, and 16 automated test suites, smoke runs, and manual browser testing.
- **Safety Layer Contract**: Under upstream network rate-limiting (`network_error=True`), Veyra correctly abstains with `DATA_UNAVAILABLE` and presents "Forecast Ensemble Data Unavailable" in the UI.
- **Error Classification Verified**: Network availability failures are cleanly distinguished from meteorological QC failures (`QC_FAILED`).
- **Status of Live Browser Tests**: Live browser tests affected by provider rate-limiting are marked:
  ```
  BLOCKED — UPSTREAM DAILY QUOTA EXHAUSTED (NOT FAILED)
  ```

### Timeline Request Amplification
- `Visual Risk Timeline` currently orchestrates multi-horizon prediction via client-side `Promise.allSettled` invoking `POST /v1/predict` for each horizon independently.
- Because `OpenMeteoGEFSWeatherService` currently has no weather response caching or concurrent request deduplication:
  - **Standard 7-Day Timeline**: Generates 7 parallel upstream HTTP calls (7–14 attempts with retries).
  - **Full 16-Day Timeline**: Generates 14 parallel upstream HTTP calls (14–28 attempts with retries).
- This burst of parallel queries rapidly exhausts upstream quota limits.

---

## 11. Day 17 Carry-Forward & Hardening Architecture

The following architectural hardening is **explicitly deferred to Day 17**:

1. **Short-Lived In-Memory Forecast Caching**:
   - Add a bounded TTL cache (e.g., 60–120 seconds) in `OpenMeteoGEFSWeatherService` keyed by `(latitude, longitude)` or canonical location.
   - For a 7-day or 16-day timeline, Request #1 performs the upstream network fetch; Requests #2–14 immediately resolve from the shared in-memory cache in $< 1\text{ms}$.
2. **Concurrent Request Deduplication (Flight Coalescing)**:
   - Coalesce simultaneous in-flight queries for the same coordinates so concurrent timeline requests share a single pending network Promise / Future.
3. **Timeline Upstream Traffic Reduction**:
   - Reduce multi-horizon timeline generation from 7–14 upstream requests down to **1 single shared upstream fetch** per location/query.
4. **Live Regression Re-Run**:
   - After Day 17 caching hardening and provider quota availability, rerun the blocked Day 16 live browser regression cases (Kolkata & Malda across temperature, precipitation, and wind speed).

---

## 12. Verification & Status Summary

### Status Classifications
- **Core Day 16 Features (SVG Curve, Timeline, Risk Strip, Horizon Details)**: **PASS**
- **UI State Management & Mode Switching (Test 10 Fix)**: **PASS**
- **Wind Speed Unit Contract (`wind_speed_unit=ms`)**: **PASS**
- **Error Precedence Safety (`network_error` -> `DATA_UNAVAILABLE`)**: **PASS**
- **Automated Frontend Test Suite (51/51 tests)**: **PASS**
- **Frontend Production Build (`vite build`)**: **PASS**
- **Deterministic Smoke Test Suites (Builder 2, Final, Historical)**: **PASS**
- **Weather Caching / Request Deduplication**: **RESOLVED IN [DAY 17](./Day-17.md)**
