# Day 30 — Forecast Revision & Trajectory Intelligence

**Veyra — Know When Forecasts May Fail**
*SIH26079 — AI-Based Forecast Bust Detection for Medium-Range Weather Forecasts*
*Phase 3: Operational Reliability & Meteorological Intelligence*
*Authoritative Record: Forecast Revision Contract & Safe Insufficient-History Verification*

---

## 1. Objective

The objective of Day 30 is to establish the formal **Forecast Revision and Trajectory Intelligence** contract across Veyra's operational atmospheric evaluation stack. 

When operational forecasters and meteorologists track numerical weather prediction (NWP) cycles, they observe successive forecast updates for a common target verification time:
> *"How has the forecast changed across successive issue cycles for the same valid target, and what is the trajectory of model risk?"*

Day 30 delivers the authoritative API schema, endpoint routing, scientific guardrails, and frontend integration for forecast revision analysis. Critically, Day 30 establishes the **scientific truth boundary**: because no durable, provider-verified archive of multiple prior forecast issue cycles for the exact same target currently exists in production, Veyra **honestly withholds fabricated history** and returns an explicit, safe `INSUFFICIENT_HISTORY` state while providing the genuine calibrated current-cycle $P(\text{BUST})$ analysis.

---

## 2. What Day 30 Actually Implements

1. **Authoritative Endpoint Contract:** `POST /v1/revision/trajectory` registered and integrated into OpenAPI documentation.
2. **Strict Request/Response Schemas:** Fully typed Pydantic models (`ForecastRevisionRequest`, `ForecastRevisionResponse`, `TrajectoryDiagnostics`, `EnsembleRevisionDiagnostics`, `RevisionUnits`).
3. **Current-Cycle V3 Model Inference:** Ingests live NOAA GEFS weather data and runs the authoritative V3 LightGBM Challenger with Isotonic calibration to compute current $P(\text{BUST})$, risk tier, and trust state.
4. **Honest Insufficient-History Semantics:** Returns `status = "INSUFFICIENT_HISTORY"` and reason code `REVISION_HISTORY_UNAVAILABLE` without manufacturing prior runs, synthetic deltas, or fake multi-point trajectory curves.
5. **Null-Safe Diagnostics:** Ensures previous forecast values, previous $P(\text{BUST})$, revision deltas, and trajectory points remain strictly `null` (or empty) rather than being falsely mapped to `0.0`.
6. **Explicit Delta Math Convention:** Codified formula $\Delta = \text{CURRENT} - \text{PREVIOUS}$ ready for when durable multi-cycle archives become available.
7. **Scientific Lead Scope Discrimination:** Distinguishes $\le 240\text{h}$ (`WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE`, `is_certified_horizon = true`) from $264\text{–}384\text{h}$ (`EXTENDED_OPERATIONAL_HORIZON`, `is_certified_horizon = false`).
8. **Robust Safety Abstention:** Abstains gracefully on invalid or unresolvable locations (`INVALID_LOCATION`) without server or frontend crashes.
9. **Interactive Frontend Revision Panel:** Dedicated UI tab on the Veyra dashboard rendering current risk, scope badges, scientific disclaimers, and honest insufficient-history notices.

---

## 3. Endpoint Contract

- **Method:** `POST`
- **Path:** `/v1/revision/trajectory`
- **Content-Type:** `application/json`
- **Response Codes:**
  - `200 OK`: Successful evaluation (either `INSUFFICIENT_HISTORY` with current analysis or `ABSTAINED` for safety gates).
  - `422 Unprocessable Entity`: Request validation failure (e.g. invalid variable name, negative lead hours).

---

## 4. Request Schema (`ForecastRevisionRequest`)

```json
{
  "location": "Kolkata",
  "variable": "temperature_2m",
  "lead_hours": 24,
  "issue_time": "2026-09-19T21:00:00Z",
  "valid_time": "2026-09-20T21:00:00Z"
}
```

- `location` (str, required): Geographic query (e.g. city name or coordinates).
- `variable` (str, required): Target meteorological variable (`temperature_2m`, `wind_speed_10m`, `surface_pressure`).
- `lead_hours` (int, optional, default=24): Forecast horizon in hours ($1 \le \text{lead} \le 384$).
- `issue_time` (str, optional): ISO-8601 timestamp representing issue anchor.
- `valid_time` (str, optional): ISO-8601 timestamp representing verification target.

---

## 5. Response Schema (`ForecastRevisionResponse`)

```json
{
  "status": "INSUFFICIENT_HISTORY",
  "location": "Kolkata",
  "resolved_name": "Kolkata",
  "latitude": 22.5726,
  "longitude": 88.3639,
  "variable": "temperature_2m",
  "lead_hours": 24,
  "lead_days": 1.0,
  "current_issue_time": null,
  "previous_issue_time": null,
  "valid_time": "2026-09-20T21:00:00Z",
  "trajectory": null,
  "ensemble_revision": null,
  "trajectory_points": [],
  "current_value": null,
  "previous_value": null,
  "revision_delta": null,
  "units": {
    "value": "°C",
    "revision_delta": "°C",
    "absolute_revision": "°C",
    "ensemble_mean": "°C",
    "ensemble_spread": "°C"
  },
  "bust_probability": 0.0033393627382774455,
  "previous_bust_probability": null,
  "bust_probability_delta": null,
  "risk_level": "LOW",
  "trust_state": "HIGH_CONFIDENCE",
  "calibration_status": "CALIBRATED",
  "scientific_scope": "WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE",
  "is_certified_horizon": true,
  "history_is_durable": false,
  "history_source": null,
  "abstain": false,
  "reason_codes": [
    "SUCCESS",
    "REVISION_HISTORY_UNAVAILABLE"
  ],
  "request_id": "rev_839df415148c"
}
```

---

## 6. Current V3 Analysis Path

When a revision trajectory request is received:
1. Geolocation is resolved via `DynamicLocationService`.
2. Target valid time and lead horizon are validated.
3. The authoritative inference pipeline (`ForecastBustAgent`) is invoked.
4. Live weather features (50-feature schema) are constructed from NOAA GEFS data.
5. The frozen V3 LightGBM Challenger predicts the raw probability.
6. The frozen Isotonic Calibrator produces the calibrated $P(\text{BUST})$.
7. Operational risk tier (`LOW`, `MEDIUM`, `HIGH`) and trust state (`HIGH_CONFIDENCE`, `MONITOR_METRICS`, `UNAVAILABLE`) are assigned.

---

## 7. Revision-History Scientific Requirement

Scientific credibility mandates that revision analysis reflects **genuine, provider-verified previous forecast runs** generated during earlier model execution cycles (e.g. 00Z vs 06Z vs 12Z vs 18Z cycles) for the exact same target valid timestamp.

---

## 8. Durable History Availability: NO

In the current production architecture:
- No durable multi-cycle historical forecast database or timeseries storage is attached.
- Open-Meteo's standard forecast endpoint provides the latest available cycle for forward lead hours, but does not provide indexed previous runs for identical valid targets.
- Therefore, **durable historical forecast cycles are NOT available** (`history_is_durable = false`).

---

## 9. Why History Is Not Fabricated

To ensure strict scientific integrity:
- **No Mock Trajectories:** We do not invent previous numerical values.
- **No In-Memory Accumulation as Provenance:** Process-local memory is transient and violates distributed provenance guarantees; it is not treated as official historical evidence.
- **No Fake Multi-Point Curves:** The frontend does not draw synthetic revision lines connecting arbitrary numbers.
- **No Silent Zero Defaulting:** Missing revision delta is reported as `null`, never converted to `0.0`.

---

## 10. INSUFFICIENT_HISTORY Behavior

When durable historical cycles are absent, the service:
- Sets `status = RevisionStatus.INSUFFICIENT_HISTORY`.
- Appends `REVISION_HISTORY_UNAVAILABLE` to `reason_codes`.
- Populates genuine current-cycle risk metrics ($P(\text{BUST})$, risk level, trust state).
- Leaves all historical comparison fields as `null`.

---

## 11. Null Previous Forecast Semantics

- `previous_value = null`
- `previous_issue_time = null`
- `revision_delta = null`
- `trajectory = null`
- `trajectory_points = []`

Operators and downstream systems understand that null explicitly means *"historical data absent"* rather than *"zero change occurred"*.

---

## 12. Null Previous P(BUST) Semantics

- `previous_bust_probability = null`
- `bust_probability_delta = null`

This prevents downstream automated decision tools from computing erroneous risk acceleration rates from non-existent baseline probabilities.

---

## 13. Delta Convention: CURRENT - PREVIOUS

The established mathematical convention codified in `calculate_trajectory_diagnostics` is:

$$\Delta = \text{CURRENT} - \text{PREVIOUS}$$

- $\Delta > 0$: Forecast value or risk has **increased** (`INCREASED`).
- $\Delta < 0$: Forecast value or risk has **decreased** (`DECREASED`).
- $\Delta = 0$: Forecast value or risk is **unchanged** (`UNCHANGED`).

---

## 14. Timestamp Validation

- Request timestamps must adhere strictly to ISO-8601 format (e.g., `YYYY-MM-DDTHH:MM:SSZ`).
- Lead hours are checked: $\text{lead\_hours} = \frac{\text{valid\_dt} - \text{issue\_dt}}{3600}$.
- Zero or negative lead hours are rejected with HTTP 422.

---

## 15. GEFS / Provider Provenance Boundary

- Ensemble dispersion metrics originate from the genuine NOAA GEFS 31-member perturbation distribution.
- Day 30 maintains clear provenance boundaries: NOAA GEFS perturbation dispersion provides current intra-cycle uncertainty, but is **not** cross-cycle revision history.

---

## 16. Calibration Safety

- Model: Frozen LightGBM Booster (`models/v3/lightgbm_v3_challenger.joblib`).
- Calibrator: Frozen Isotonic Regression (`models/v3/probability_calibrator_v3.joblib`).
- **Calibration Failure Policy:** If probability calibration fails (e.g. non-finite output or artifact corruption), Veyra **strictly abstains** (`probability = null`, `status = CALIBRATION_FAILURE`). Raw uncalibrated probabilities are **never** exposed as calibrated $P(\text{BUST})$.

---

## 17. P(BUST) vs Revision Distinction

| Dimension | Calibrated $P(\text{BUST})$ | Forecast Revision ($\Delta$) |
| :--- | :--- | :--- |
| **Scientific Meaning** | Posterior probability of $|e| \ge q_{95}$ | Numerical shift between consecutive issue runs |
| **Output Type** | Calibrated probability in $[0.0, 1.0]$ | Physical metric delta in variable units |
| **Input Driver** | 50-feature unit-space atmospheric matrix | Consecutive cycle NWP forecasts |
| **Independence** | Independent of revision availability | Independent of $P(\text{BUST})$ magnitude |

---

## 18. P(BUST) vs Day-29 Ensemble Dispersion Distinction

- **Day 29 Ensemble Dispersion:** Intra-cycle spread among 31 simultaneous GEFS perturbation members ($\sigma$, IQR, Range, CV).
- **Day 30 Forecast Revision:** Inter-cycle shift across temporal NWP issue runs ($\Delta = \text{Cycle}_t - \text{Cycle}_{t-1}$).
- **V3 Model $P(\text{BUST})$:** Calibrated probability of forecast bust at the valid target time.

---

## 19. $\le 240\text{h}$ Frozen Benchmark Lead Scope

- Lead horizons from $1\text{h}$ to $240\text{h}$ (10 days) fall within the **Frozen Benchmark Lead Scope**.
- Tagged with:
  - `scientific_scope = "WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE"`
  - `is_certified_horizon = true`

---

## 20. $264\text{–}384\text{h}$ Extended Operational Scope

- Lead horizons from $264\text{h}$ to $384\text{h}$ (11 to 16 days) represent the **Extended Operational Horizon**.
- Tagged with:
  - `scientific_scope = "EXTENDED_OPERATIONAL_HORIZON"`
  - `is_certified_horizon = false`
- The UI and API clearly indicate that these leads are outside the frozen benchmark lead scope.

---

## 21. Invalid-Location Behavior

When an unresolvable or fictitious location (e.g., `"Atlantis"`) is provided:
- Geocoding resolver returns `None`.
- `RevisionService` records an abstention metric and returns `status = "ABSTAINED"`, `abstain = true`, `reason_codes = ["INVALID_LOCATION"]`.
- Coordinates, probabilities, risk tiers, and trajectory points remain `null`.
- The system returns HTTP 200 with structured abstention metadata without crashing.

---

## 22. Frontend Behavior

The Veyra React dashboard (`frontend/src/components/ForecastRevisionPanel.tsx`) features:
1. **Interactive Controls:** Location input, preset buttons (Kolkata, Delhi, Mumbai, Bengaluru, Chennai), variable selector, lead horizon dropdown (24h to 384h).
2. **Current-Cycle Risk Display:** Renders calibrated $P(\text{BUST})$ (e.g. `0.3%`), risk badge (`LOW`), trust state badge (`HIGH_CONFIDENCE`), and calibration status (`CALIBRATED`).
3. **Scientific Scope Badges:** Color-coded badges indicating `Within Frozen Benchmark Lead Scope (<= 240h)` or `Extended Operational Horizon (264h–384h)`.
4. **Honest Insufficient History Card:** Displays `INSUFFICIENT COMPARABLE ISSUE-CYCLE HISTORY` with explicit notices explaining that missing evidence is rendered as `N/A` rather than fake numbers.
5. **Strict Separation Disclaimer:** Explains that Revision $\neq$ Disagreement $\neq P(\text{BUST})$.
6. **Graceful Abstention Handling:** Renders amber abstention alert banners on unresolvable locations without uncaught errors.

---

## 23. Backend / Frontend Parity

Parity audit between FastAPI backend payload and React frontend DOM verified exact concordance:
- Location name, variable, and lead hours match.
- $P(\text{BUST})$ formatted faithfully (0.00334 backend $\rightarrow$ 0.3% UI).
- Risk level (`LOW`) and trust state (`HIGH_CONFIDENCE`) match.
- Scientific scope strings match exactly.
- Reason codes match.
- All unpopulated historical values render as `N/A` / `null` without fabrication.

---

## 24. Automated Test Results

| Test Suite | Total Collected | Passed | Failed | Skipped | Pass Rate | Duration |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Backend Suite (`pytest`)** | 537 | 537 | 0 | 0 | **100%** | 368.72s |
| **Frontend Suite (`vitest`)** | 96 | 96 | 0 | 0 | **100%** | 25.06s |
| **Total Combined** | **633** | **633** | **0** | **0** | **100%** | — |

---

## 25. Live Verification Evidence

| Case | Location | Variable | Lead | HTTP | $P(\text{BUST})$ | Risk | Scope | Status | Reason Code |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- | :---: | :--- |
| **A** | Kolkata | `temperature_2m` | 24h | 200 | 0.33% | LOW | Benchmark Scope ($\le 240\text{h}$) | `INSUFFICIENT_HISTORY` | `SUCCESS`, `REVISION_HISTORY_UNAVAILABLE` |
| **B** | Kolkata | `wind_speed_10m` | 24h | 200 | 2.09% | LOW | Benchmark Scope ($\le 240\text{h}$) | `INSUFFICIENT_HISTORY` | `SUCCESS`, `REVISION_HISTORY_UNAVAILABLE` |
| **C** | Kolkata | `surface_pressure` | 24h | 200 | 5.95% | LOW | Benchmark Scope ($\le 240\text{h}$) | `INSUFFICIENT_HISTORY` | `SUCCESS`, `REVISION_HISTORY_UNAVAILABLE` |
| **D** | Kolkata | `temperature_2m` | 240h | 200 | 0.20% | LOW | Benchmark Scope ($\le 240\text{h}$) | `INSUFFICIENT_HISTORY` | `SUCCESS`, `REVISION_HISTORY_UNAVAILABLE` |
| **E** | Kolkata | `temperature_2m` | 264h | 200 | 0.20% | LOW | Extended Horizon ($> 240\text{h}$) | `INSUFFICIENT_HISTORY` | `SUCCESS`, `REVISION_HISTORY_UNAVAILABLE` |
| **F** | Atlantis | `temperature_2m` | 24h | 200 | null | null | Benchmark Scope ($\le 240\text{h}$) | `ABSTAINED` | `INVALID_LOCATION` |

---

## 26. Browser Verification Evidence

- **Browser Subagent Session:** Complete interactive browser session executed on `http://localhost:5173/`.
- **Navigation:** Seamless navigation across Single Point, Timeline, Multi-Location, Spatial Reliability, Disagreement, and Revision tabs.
- **Visual Validation:** Verified loading states, risk cards, scope indicators, insufficient-history banners, and invalid location abstention alerts.
- **Console Log Result:** 0 console errors logged across all interactions.

---

## 27. Artifact Hashes

| Artifact | File Path | SHA256 Checksum | Status |
| :--- | :--- | :--- | :---: |
| **V3 Model** | `models/v3/lightgbm_v3_challenger.joblib` | `00A8410746F4A0EECBF7E76AAA0565143FC948D0E06AEA65E7BCC4CE28A1C660` | **MATCH** |
| **V3 Calibrator** | `models/v3/probability_calibrator_v3.joblib` | `9F448606CE4338DED92F238A551B3A9D8E6D2CB5902E8BC687BCE5F5850AF531` | **MATCH** |

---

## 28. Feature Count & Calibration

- **Authoritative Feature Count:** 50 features (`models/v3/feature_names.json`).
- **Calibrator Type:** `sklearn.isotonic.IsotonicRegression` (`CALIBRATED_ISOTONIC`).
- **Operational Decision Threshold:** $\tau = 0.060$.

---

## 29. Known Limitations

1. **Absence of Durable Cycle Archive:** Multi-cycle trajectory curves cannot be computed until a persistent historical forecast store is deployed.
2. **External NWP Provider Rate Limits:** Live weather ingestion depends on Open-Meteo GEFS API quotas; provider 429 errors trigger safe upstream abstention.
3. **Single Provider (NOAA GEFS):** Ensemble dispersion is derived solely from NOAA GEFS 31 perturbation members rather than multi-center NWP consensus.

---

## 30. Future Durable Revision-Store Requirement

As detailed in `Backend_Verification_Gaps_and_Next_Roadmap_FINAL.md`, a future milestone will implement a durable, distributed forecast-cycle archive (`ForecastRevisionStore`) that persistently ingests and indexes successive 00Z/06Z/12Z/18Z NWP runs, enabling full trajectory curves, revision velocity, and cycle-over-cycle risk acceleration tracking.

---

## 31. Scientific Claim Boundaries

- **P(BUST) Definition:** Calibrated posterior probability that the already-issued forecast will exhibit an absolute error meeting or exceeding the 95th percentile historical error threshold ($|e| \ge q_{95}$).
- **No 100% Accuracy Claim:** Weather forecasting contains intrinsic atmospheric chaos; Veyra predicts failure risk probabilities, not deterministic certainties.
- **No Official Authority Warning Claim:** Veyra is an AI-based forecast verification intelligence layer, not an official national meteorological warning service.
- **Scientific Claim Integrity:** Day 30 makes no claim of historical trajectory intelligence when durable history is absent.

---

## 32. Final Day-30 Verdict

**DAY30_CODE_AND_SCIENCE_VERIFIED_DEPLOYMENT_ALIGNMENT_PENDING**

All scientific contracts, calibration safety requirements, artifact checksums, automated regression suites, live API matrix cases, browser flows, and backend/frontend parity checks have **PASSED with 100% precision**. Day 30 is complete, audited, and ready for formal freeze.
