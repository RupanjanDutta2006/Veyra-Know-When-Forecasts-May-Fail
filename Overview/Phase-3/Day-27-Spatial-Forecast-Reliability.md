# Day 27 — Spatial Forecast Reliability

## 1. Objective

The primary objective of Day 27 is to extend Veyra's point-level forecast reliability intelligence into an interactive spatial reliability view across real, backend-evaluated geographic locations.

Day 27 is:
- **NOT** a model-training day.
- **NOT** a calibration day.
- **NOT** a threshold-tuning day.
- **NOT** a generic weather heatmap or interpolation project.

The system evaluates discrete, authoritative stations using the frozen V3 LightGBM model and isotonic calibrator. The spatial view directly answers:
> *"How does forecast reliability differ across the locations that Veyra actually evaluated?"*

It strictly avoids implying or fabricating continuous reliability fields between unevaluated geographic coordinates.

---

## 2. Starting Baseline

Day 27 commenced strictly on top of the frozen, post-merge verified Day 26 Release Candidate (`RC_READY`) baseline:

- **Day 26 Merge Commit**: `2ca4b5f94a7ea9cd79e010c38d7e63d07489b3cc`
- **Day 26 Feature Commit Ancestor**: `298c850e32cec54fd8224151c2499a6ce7617f5a`
- **Feature Branch**: `phase3/day27-spatial-reliability`
- **Untracked File Preserved**: `batch_verification_25.csv` (strictly uncommitted and unmodified)
- **Authoritative V3 Model SHA-256**: `00A8410746F4A0EECBF7E76AAA0565143FC948D0E06AEA65E7BCC4CE28A1C660`
- **Authoritative V3 Calibrator SHA-256**: `9F448606CE4338DED92F238A551B3A9D8E6D2CB5902E8BC687BCE5F5850AF531`
- **Feature Schema Count**: Exactly 50 canonical features in `models/v3/feature_names.json`
- **Pre-Day 27 Test Baseline**: 456 backend tests passing, 57 frontend tests passing, production build passing.

### Repository Architecture & File Manifest (Relative Links)

- **Backend Schemas**: [`backend/app/schemas/spatial.py`](../../backend/app/schemas/spatial.py)
- **Backend Service**: [`backend/app/services/spatial_service.py`](../../backend/app/services/spatial_service.py)
- **Backend Endpoint**: [`backend/app/api/v1/endpoints/spatial.py`](../../backend/app/api/v1/endpoints/spatial.py)
- **API Router Registration**: [`backend/app/api/v1/router.py`](../../backend/app/api/v1/router.py)
- **Telemetry & Process Metrics**: [`backend/app/core/metrics.py`](../../backend/app/core/metrics.py)
- **Backend Test Suite**: [`backend/tests/test_spatial_reliability.py`](../../backend/tests/test_spatial_reliability.py)
- **Frontend Type Definitions**: [`frontend/src/api/types.ts`](../../frontend/src/api/types.ts)
- **Frontend API Client**: [`frontend/src/api/client.ts`](../../frontend/src/api/client.ts)
- **Frontend Navigation**: [`frontend/src/components/Navigation.tsx`](../../frontend/src/components/Navigation.tsx)
- **Frontend Spatial Panel**: [`frontend/src/components/SpatialReliabilityPanel.tsx`](../../frontend/src/components/SpatialReliabilityPanel.tsx)
- **Frontend Root Application**: [`frontend/src/App.tsx`](../../frontend/src/App.tsx)
- **Frontend Vitest Suite**: [`frontend/src/test/SpatialReliability.test.tsx`](../../frontend/src/test/SpatialReliability.test.tsx)
- **Documentation Master Index**: [`Overview/README.md`](../README.md)

---

## 3. Scientific Design Principles

1. **Discrete Evaluated Points**: Real inference is executed strictly for requested discrete coordinates or station queries. No continuous or interpolated field is rendered.
2. **Authoritative V3 Pipeline Reuse**: Every location is evaluated via the identical, frozen V3 inference pipeline:
   $$\text{Location} \rightarrow \text{Live Weather Ingestion} \rightarrow \text{Standardization/QC} \rightarrow \text{50 V3 Features} \rightarrow \text{LightGBM V3} \rightarrow \text{Isotonic Calibrator} \rightarrow P(\text{BUST})$$
3. **Certified Label Definition**:
   > A bust event occurs when forecast absolute error meets or exceeds ($\ge$) the applicable stratum-specific threshold derived from the training partition under the certified Day 22 labeling methodology.
4. **Frozen Operational Risk Tiers**:
   - **LOW**: $P(\text{BUST}) < 0.20$
   - **MEDIUM**: $0.20 \le P(\text{BUST}) < 0.50$
   - **HIGH**: $0.50 \le P(\text{BUST}) < 0.75$
   - **CRITICAL**: $P(\text{BUST}) \ge 0.75$
5. **Strict Non-Weather Semantics**: Marker risk denotes *forecast-bust reliability intelligence* (risk of the numerical weather prediction failing unusually badly), **not** weather severity, temperature magnitude, storm risk, or rain probability.
6. **Failure Isolation & Non-Coercion**: An invalid or unresolvable location (e.g., Atlantis) safely abstains with `latitude=null, longitude=null` and never corrupts the overall batch or coerces to `(0, 0)`.
7. **Calibration Failure Safety**: Calibration failure suppresses normal probability and risk serving; uncalibrated probabilities are never displayed as calibrated.

---

## 4. Existing Architecture Audit

Before modifying code, an audit of the codebase established:
1. **Map Engine**: `ForecastMap.tsx` used `react-leaflet` and `leaflet`. Leaflet vector markers (`CircleMarker`) provide hardware-accelerated, crisp discrete markers without requiring unvalidated raster tiles.
2. **Inference Orchestration**: `ForecastBustAgent` and `DynamicLocationService` are already hardened with SingleFlight coalescing and in-process caching.
3. **Multi-Location Ingestion**: `backend/app/services/multi_location_service.py` provides bounds checking (`MAX_MULTI_LOCATION_BATCH_SIZE = 50`) which was integrated into the spatial request validator.
4. **Horizon Scope**: Horizons $\le 240\text{h}$ fall within the frozen benchmark lead scope (`FROZEN_BENCHMARK_LEAD_SCOPE`, "Within Frozen Benchmark Lead Scope"), while horizons $264\text{h}$–$384\text{h}$ represent extended operational horizons (`EXTENDED_OPERATIONAL_HORIZON`, "Extended Operational Horizon").

---

## 5. Spatial API Contract

A dedicated, typed backend endpoint was registered at `POST /v1/spatial/reliability`:

### Request Schema (`SpatialReliabilityRequest`)
```json
{
  "locations": ["Kolkata", "Delhi", "Mumbai", "Chennai"],
  "variable": "temperature_2m",
  "lead_hours": 24,
  "issue_time": null
}
```
- **Validation**:
  - `locations`: Non-empty list of non-blank strings, bounded between 1 and 50 locations.
  - `variable`: Validated against `SUPPORTED_VARIABLES` (`temperature_2m`, `wind_speed_10m`, `surface_pressure`).
  - `lead_hours`: Bounded between 24 and 384 hours. Rejected with HTTP 422 if $<24$ or $>384$.
  - Extra fields forbidden (`extra: "forbid"`).

### Response Schema (`SpatialReliabilityResponse`)
```json
{
  "status": "SUCCESS",
  "variable": "temperature_2m",
  "lead_hours": 24,
  "lead_days": 1.0,
  "issue_time": "2026-09-19T06:00:00Z",
  "is_certified_horizon": true,
  "scientific_scope": "FROZEN_BENCHMARK_LEAD_SCOPE",
  "points": [ ... ],
  "summary": { ... },
  "request_id": "req_b2db7e8e0a1d"
}
```

> **Horizon Scope Semantics & Compatibility**:
> - `is_certified_horizon` (boolean): Retained for API backwards compatibility. It provides **temporal horizon scope metadata** indicating whether the requested lead horizon ($\le 240\text{h}$) falls within the temporal scope evaluated during the Day 23 frozen benchmark (`true`). For extended operational horizons ($264\text{h}$–$384\text{h}$), it evaluates to `false`.
> - **Scientifically Bounded Interpretation**: The fact that a lead time is within the frozen benchmark lead scope does **NOT** establish independent geographic or current-live performance certification for every plotted location. Live station performance remains uncertified against historical reforecast equivalence.
> - `scientific_scope` (string): Canonical scope descriptor: `FROZEN_BENCHMARK_LEAD_SCOPE` (Human-readable: *"Within Frozen Benchmark Lead Scope"*) or `EXTENDED_OPERATIONAL_HORIZON` (Human-readable: *"Extended Operational Horizon"*).

---

## 6. Spatial Reliability Service

Implemented in [`backend/app/services/spatial_service.py`](../../backend/app/services/spatial_service.py):
- **Query Deduplication**: Analyzes duplicate location strings (case-insensitive) in input requests, evaluates unique stations exactly once, and maps outputs back to preserve 1:1 input ordering.
- **Issue Cycle Standardization**: Primes the operational forecast cycle timestamp from the first valid station to ensure all locations are evaluated against a consistent synoptic base run.
- **Summary Metrics Computation**: Computes `max_bust_probability`, `mean_bust_probability`, `max_risk_level`, `max_risk_location`, and `elevated_risk_locations` exclusively over valid, non-abstained points.
- **Deterministic Tie-Breaking**: For identical maximum bust probabilities across stations, the first input occurrence is deterministically designated as `max_risk_location`.

---

## 7. Location & Coordinate Handling

- Coordinates are resolved via authoritative `DynamicLocationService`.
- If a query cannot be resolved (e.g. `"Atlantis"`), the service:
  - Sets `latitude = null` and `longitude = null`.
  - Sets `bust_probability = null` and `risk_level = null`.
  - Sets `abstain = true` and `trust_state = UNAVAILABLE`.
  - Attaches `reason_codes = ["INVALID_LOCATION"]`.
  - Never fabricates placeholder coordinates such as `(0, 0)` or `(null, null)`.
  - The frontend separates unresolvable points into a dedicated "Unresolvable / Abstained Locations" drawer.

---

## 8. V3 Inference Reuse

Zero duplicate ML inference logic was introduced. `SpatialReliabilityService` invokes `ForecastBustAgent.analyze()`, which executes:
1. Feature extraction through `V3FeaturePipeline` (50 canonical features).
2. LightGBM booster evaluation (`lightgbm_v3_challenger.joblib`).
3. Probability calibration via `IsotonicRegression` (`probability_calibrator_v3.joblib`).
4. Operational risk classification and rule-based physical explanation.

Parity tests confirm complete bitwise parity between direct `analyze()` calls and spatial endpoint outputs.

---

## 9. Map Visualization

The frontend interactive map is implemented in [`frontend/src/components/SpatialReliabilityPanel.tsx`](../../frontend/src/components/SpatialReliabilityPanel.tsx) using `react-leaflet`:
- **Discrete Markers Only**: Renders individual `CircleMarker` vector elements per valid station coordinate.
- **NO Interpolation**: Continuous contours, blurred heatmaps, and synthetic spatial grids are strictly avoided.
- **Interactive Inspection**: Clicking or tapping any marker updates the Station Intelligence card and opens a descriptive popup.
- **Dynamic Bounding**: Automatically fits map bounds to the bounding box of evaluated stations.

---

## 10. Marker Semantics

Markers reflect calibrated forecast bust risk tiers:
- **LOW** (Green, `#10b981`): $P(\text{BUST}) < 0.20$
- **MEDIUM** (Amber, `#f59e0b`): $0.20 \le P(\text{BUST}) < 0.50$
- **HIGH** (Red, `#ef4444`): $0.50 \le P(\text{BUST}) < 0.75$
- **CRITICAL** (Purple, `#8b5cf6`): $P(\text{BUST}) \ge 0.75$
- **ABSTAINED** (Neutral Gray, `#6b7280`): Missing/failed prediction.

Accessible labels (`aria-label`) convey the risk level and station name in plain text.

---

## 11. Abstention & Null Safety

- **Backend**: Abstained predictions retain `bust_probability = null` and `risk_level = null`. Summary aggregations exclude abstained points. If all points abstain, `status = ABSTAINED`, and max/mean probability fields evaluate to `null`.
- **Frontend**: Explicit `p != null` checks prevent coercion of `null` to `0.0%` or `"LOW"`. Unplottable points appear in the side drawer with explicit reason codes (`INVALID_LOCATION`, `CALIBRATION_FAILURE`).

---

## 12. Horizon Scope

- **$\le 240\text{h}$ (Days 1–10)**: Categorized as `FROZEN_BENCHMARK_LEAD_SCOPE` (Human-readable: *"Within Frozen Benchmark Lead Scope"*). Displays green badge. Note that lead scope indicates the forecast lead time falls within the temporal scope evaluated by the Day 23 frozen benchmark; it does **NOT** establish independent geographic or current-live certification for every plotted location.
- **$264\text{h}$–$384\text{h}$ (Days 11–16)**: Categorized as `EXTENDED_OPERATIONAL_HORIZON` (Human-readable: *"Extended Operational Horizon"*). Displays amber badge indicating extended operational-only serving without historical reforecast benchmark evaluation.

---

## 13. Performance & Upstream Protection

- **Duplicate Input Deduplication**: Sending 10 repeated queries for `"Kolkata"` executes exactly 1 upstream agent call.
- **In-Process Cache & SingleFlight**: Concurrent queries for identical coordinates and issue cycles are coalesced.
- **Batch Size Cap**: Bounded to 50 locations per request.
- **Observed Latency**:
  - Cold live multi-station fetch (25 stations): ~10.7 s.
  - Cached/re-evaluated multi-station fetch: ~1.8 s.

---

## 14. Observability

Low-cardinality process metrics were added to [`backend/app/core/metrics.py`](../../backend/app/core/metrics.py):
- `spatial_requests_total{status="SUCCESS|PARTIAL|ABSTAINED"}`
- `spatial_points_total`
- `spatial_valid_points_total`
- `spatial_abstained_points_total`

Location and city names are strictly excluded from metric labels to prevent cardinality explosion.

---

## 15. Backend Tests

Created [`backend/tests/test_spatial_reliability.py`](../../backend/tests/test_spatial_reliability.py) with **34 comprehensive test cases**:
1. `test_01_spatial_endpoint_registered`: Route presence in OpenAPI specification.
2. `test_02_single_valid_location`: Single location evaluation and summary.
3. `test_03_multiple_valid_locations`: Multi-station evaluation across risk tiers.
4. `test_04_deterministic_input_output_ordering`: Strict 1:1 input order preservation.
5. `test_05_duplicate_location_behavior`: Input order preserved and agent calls deduplicated.
6. `test_06_invalid_location_abstention`: Safe abstention without coordinate fabrication for Atlantis.
7. `test_07_mixed_valid_and_invalid_locations`: Failure isolation with partial status.
8. `test_08_direct_coordinates_supported`: Coordinate query strings (`22.57,88.36`).
9. `test_09_variable_temperature`: `temperature_2m` evaluation.
10. `test_10_variable_wind`: `wind_speed_10m` evaluation.
11. `test_11_variable_pressure`: `surface_pressure` evaluation.
12. `test_12_lead_24h_benchmark_scope`: 24h lead within frozen benchmark lead scope.
13. `test_13_lead_240h_benchmark_scope`: 240h frozen benchmark lead scope boundary.
14. `test_14_lead_264h_extended_operational_scope`: 264h extended operational horizon.
15. `test_15_lead_384h_maximum_supported`: 384h maximum operational horizon.
16. `test_16_lead_greater_than_384_rejected`: Rejection of 400h with HTTP 422.
17. `test_17_lead_less_than_24_rejected`: Rejection of 12h with HTTP 422.
18. `test_18_unsupported_variable_rejected`: Rejection of unsupported variables with HTTP 422.
19. `test_19_empty_locations_rejected`: Rejection of empty location list with HTTP 422.
20. `test_20_invalid_json_type`: Rejection of malformed JSON with HTTP 422.
21. `test_21_calibration_failure_safety`: Safe abstention on calibration failure without raw probability exposure.
22. `test_22_model_unavailable_safety`: Safe abstention on model unavailability.
23. `test_23_null_probability_safety`: Preservation of null metrics on all-abstained requests.
24. `test_24_risk_tier_parity`: Strict adherence to frozen risk tier boundaries.
25. `test_25_coordinate_correctness`: Coordinate matching with station registry.
26. `test_26_summary_correctness_and_deterministic_tie_breaker`: Mean, peak, and tie-breaking logic.
27. `test_27_all_abstained_summary`: All-abstained status and summary integrity.
28. `test_28_request_id_correlation`: Request ID propagation.
29. `test_29_spatial_metrics_telemetry`: Metric increment verification.
30. `test_30_cache_and_repeated_requests`: Idempotency across repeated queries.
31. `test_31_duplicate_computation_efficiency`: 10 identical inputs resulting in 1 agent call.
32. `test_32_no_high_cardinality_metric_labels`: Zero location labels in metrics.
33. `test_33_existing_dashboard_compatibility`: Verification that `/v1/dashboard/intelligence` is unaffected.
34. `test_34_parity_with_authoritative_inference_path`: Direct parity verification with `ForecastBustAgent`.

**Result**: **34 / 34 PASSED** in 2.50s.

---

## 16. Frontend Tests

Created [`frontend/src/test/SpatialReliability.test.tsx`](../../frontend/src/test/SpatialReliability.test.tsx) with **9 Vitest test cases**:
1. Renders spatial reliability header and scientific principles notice.
2. Renders discrete markers corresponding to evaluated valid points.
3. Displays summary metrics matching backend summary.
4. Updates selected station card when clicking a marker.
5. Safely handles mixed valid and unresolvable/abstained locations without plotting at `(0, 0)`.
6. Handles null probability safety without coercion to `0%` or `LOW`.
7. Triggers a new backend evaluation when changing variable.
8. Distinguishes benchmark lead scope ($\le 240\text{h}$) from extended operational horizon ($>240\text{h}$).
9. Displays error alert when API call fails.

**Result**: **9 / 9 PASSED**.
**Full Frontend Vitest Suite**: **66 / 66 PASSED** (5 test files).

---

## 17. Manual API Verification

Executed `scratch/manual_api_verification.py` across 8 representative test cases against the live FastAPI application:

| Case | Query Description | Variable | Lead | Status | Scientific Scope | Peak P(BUST) | Max Location | Valid/Abst |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Case A** | Kolkata, Delhi, Mumbai, Chennai | `temperature_2m` | 24h | SUCCESS | FROZEN_BENCHMARK_LEAD_SCOPE | 0.9% | Chennai | 4 / 0 |
| **Case B** | Kolkata, Delhi, Mumbai, Chennai | `wind_speed_10m` | 24h | SUCCESS | FROZEN_BENCHMARK_LEAD_SCOPE | 11.7% | Chennai | 4 / 0 |
| **Case C** | Kolkata, Delhi, Mumbai, Chennai | `surface_pressure` | 24h | SUCCESS | FROZEN_BENCHMARK_LEAD_SCOPE | 7.6% | Chennai | 4 / 0 |
| **Case D** | Scope verification | `temperature_2m` | 24h | SUCCESS | FROZEN_BENCHMARK_LEAD_SCOPE | 0.9% | Chennai | 4 / 0 |
| **Case E** | Benchmark Limit Horizon | `temperature_2m` | 240h | SUCCESS | FROZEN_BENCHMARK_LEAD_SCOPE | 1.5% | Delhi | 4 / 0 |
| **Case F** | Extended Horizon Boundary | `temperature_2m` | 264h | SUCCESS | EXTENDED_OPERATIONAL_HORIZON | 1.5% | Delhi | 4 / 0 |
| **Case G** | Maximum Operational Horizon | `temperature_2m` | 384h | SUCCESS | EXTENDED_OPERATIONAL_HORIZON | 5.8% | Delhi | 4 / 0 |
| **Case H** | Mixed Valid + Invalid (`Atlantis`) | `temperature_2m` | 24h | PARTIAL | FROZEN_BENCHMARK_LEAD_SCOPE | 0.5% | Kolkata | 2 / 1 |

All 8 cases returned HTTP 200 with complete scientific field integrity. In Case H, `Atlantis` yielded `latitude=null, longitude=null, abstain=true` and was safely isolated without corrupting Kolkata or Delhi.

---

## 18. Manual Browser Verification

A dedicated browser subagent performed end-to-end verification on the local test server (`/dashboard`):
1. **Initial Load**: Dashboard loaded cleanly with navigation.
2. **Navigation Tab**: Clicked **`Spatial Reliability`** (with Day 27 badge).
3. **Map Rendering**: 25 stations evaluated and rendered as discrete circular markers color-coded by risk tier.
4. **Interactive Marker Inspection**: Clicked **Guwahati** ($26.1445^\circ\text{N}, 91.7362^\circ\text{E}$); marker popup opened and Station Intelligence panel populated with $P(\text{BUST}) = 0.3\%$, `LOW RISK`, `HIGH_CONFIDENCE`.
5. **Horizon Switching**: Switched horizon to $264\text{h}$ (11 Days); clicked Refresh; header badge dynamically updated to `EXTENDED OPERATIONAL HORIZON (264h-384h)`.
6. **Return Navigation**: Switched back to `Reliability Sentinel`; single-station timeline and verification panel remained fully functional.
7. **Visual Demonstration**:
   - Screenshot 1: Benchmark spatial reliability view with Guwahati details.
   - Screenshot 2: Extended operational view at 264h horizon.
   - Video Recording: `spatial_reliability_demo_1789807221294.webp`.

---

## 19. Regression Verification

- **Full Backend Pytest Suite**: **490 / 490 PASSED** in 253.39s (baseline was 456, +34 new Day 27 tests).
- **Full Frontend Vitest Suite**: **66 / 66 PASSED** (baseline was 57, +9 new Day 27 tests).
- **Frontend Production Build**: `tsc && vite build` succeeded in 5.50s with zero errors or warnings.
- **Existing Endpoints Verified**:
  - `GET /v1/health` $\rightarrow$ 200 OK
  - `POST /v1/predict` $\rightarrow$ 200 OK
  - `POST /v1/predict/batch` $\rightarrow$ 200 OK
  - `GET /v1/model/evaluation` $\rightarrow$ 200 OK
  - `GET /v1/model/evaluation/v3` $\rightarrow$ 200 OK
  - `GET /v1/metrics` $\rightarrow$ 200 OK
  - `POST /v1/dashboard/intelligence` $\rightarrow$ 200 OK
  - `POST /v1/spatial/reliability` $\rightarrow$ 200 OK

---

## 20. Artifact Integrity

All frozen scientific artifacts were strictly protected and verified:

| Artifact | Expected SHA-256 | Actual SHA-256 | Verification Status |
| :--- | :--- | :--- | :--- |
| `models/v3/lightgbm_v3_challenger.joblib` | `00A8410746F4A0EECBF7E76AAA0565143FC948D0E06AEA65E7BCC4CE28A1C660` | `00A8410746F4A0EECBF7E76AAA0565143FC948D0E06AEA65E7BCC4CE28A1C660` | **MATCH (UNTOUCHED)** |
| `models/v3/probability_calibrator_v3.joblib` | `9F448606CE4338DED92F238A551B3A9D8E6D2CB5902E8BC687BCE5F5850AF531` | `9F448606CE4338DED92F238A551B3A9D8E6D2CB5902E8BC687BCE5F5850AF531` | **MATCH (UNTOUCHED)** |
| `models/v3/feature_names.json` | 50 Features | 50 Features | **MATCH (UNTOUCHED)** |
| `models/v3/training_manifest.json` | Untouched | Untouched | **MATCH (UNTOUCHED)** |
| `models/day4/` | Untouched | Untouched | **MATCH (UNTOUCHED)** |
| `batch_verification_25.csv` | Untracked file | Untracked file | **UNTOUCHED / UNSTAGED** |

---

## 21. Scientific Limitations

1. **Discrete Station Evaluation**: Evaluated spatial values are discrete evaluated points only; they do not represent a spatially continuous or validated geographic risk surface.
2. **No Geographic Interpolation**: Veyra strictly executes no continuous spatial interpolation across unevaluated terrain, mountains, or unmonitored regions.
3. **Marker Semantics**: Marker risk denotes *forecast-bust risk* (probability of NWP model failure $\ge q_{95}$), **not** weather severity, temperature magnitude, storm risk, or rain probability.
4. **Abstention & Null Non-Coercion**: Null/abstained values are never converted to 0.0% or "LOW"; unresolvable points safely abstain.
5. **Calibration Failure Safety**: Calibration failure suppresses normal probability and risk serving; uncalibrated outputs are never served.
6. **Temporal Horizon Scope Semantics**: Lead horizons $\le 240\text{h}$ fall within `FROZEN_BENCHMARK_LEAD_SCOPE` (*"Within Frozen Benchmark Lead Scope"*). Horizons $264\text{h}$–$384\text{h}$ represent `EXTENDED_OPERATIONAL_HORIZON` (*"Extended Operational Horizon"*). The lead being within benchmark scope does **NOT** establish independent geographic or live-station certification for every plotted coordinate.
7. **Sample Size & Equivalence Limits**: N=5 historical reforecast training stations vs N=31 live ensemble members equivalence remains uncertified.
8. **Generalization Limitations**: Post-2019 validation and unmonitored station generalization remain uncertified.
9. **Zero Retraining Invariant**: The V3 LightGBM challenger model (`lightgbm_v3_challenger.joblib`) and probability calibrator (`probability_calibrator_v3.joblib`) were strictly unmodified.
10. **Feature Parity Invariant**: Exactly 50 canonical features maintained in `models/v3/feature_names.json`.

---

## 22. PPT / Demo Readiness

Day 27 is fully prepared for final presentation materials:
- **Slide Title Recommendation**: *Spatial Forecast Reliability Intelligence*
- **Slide Summary**: *"Veyra extends point-level forecast reliability into a spatial view by evaluating supported locations through the same calibrated V3 inference pipeline, while preserving abstention and scientific scope."*
- **Visual Evidence**:
  - `day27_spatial_reliability_guwahati_1789807487920.png` demonstrates discrete evaluated station markers, Guwahati station diagnostics ($P(\text{BUST})=0.3\%$), and the `WITHIN FROZEN BENCHMARK LEAD SCOPE` badge.
  - `extended_operational_264h_spatial_reliability_1789807606192.png` demonstrates the 11-day ($264\text{h}$) operational evaluation with the dynamic `EXTENDED OPERATIONAL HORIZON` indicator.
  - `spatial_reliability_demo_1789807221294.webp` provides the complete browser video recording.

---

## 23. Known Follow-Ups

- Future research may evaluate scientifically justified spatial or regime-aware diagnostics under a separately reviewed scope.
- **Frontend Optimization**: Chunk code-splitting for Leaflet vendor bundles during future production packaging.

---

## 24. Final Day 27 Verdict

$$\mathbf{DAY27\_COMPLETE}$$

All functional, scientific, architectural, testing, and documentation requirements for Phase 3 Day 27 have been implemented and verified.
