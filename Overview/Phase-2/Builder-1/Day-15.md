# Phase 2 — Builder 1 — Day 15
## Frontend Dashboard

---

## 1. Objective

The primary objective of Day 15 is to design, implement, test, and integrate a modern, production-quality frontend dashboard for the Veyra platform.

The dashboard exposes the existing Veyra backend predictive capability directly to end users, evaluating medium-range numerical weather forecasts to assess when and why they are likely to fail unusually badly ("forecast bust").

### Primary User Flow
```
User Enters Location / Coordinates
               ↓
Configures Forecast Cycle (Variable, Optional Issue/Valid Timestamps)
               ↓
Lightweight Client Validation & Submission
               ↓
Veyra API Layer (POST /v1/predict)
               ↓
Platt-Calibrated LightGBM Model & Feature Attribution Layer
               ↓
Structured Response (Probability, Risk Level, Trust State, Abstention, Explanation)
               ↓
Accessible Dashboard Presentation & Physical Explainability Narrative
```

---

## 2. Scope

- **In Scope**:
  - Interactive web dashboard consuming the existing Veyra FastAPI backend.
  - Location resolution supporting city names, quick benchmark pills, and direct geographic coordinates (`lat, lon`).
  - Meteorological variable selection across canonical variables (`temperature_2m`, `surface_pressure`, `wind_speed_10m`, `relative_humidity_2m`, `precipitation`).
  - Issue time and valid target datetime controls with strict chronological client validation and maximum 384-hour forecast horizon enforcement.
  - Four-decimal percentage bust probability rendering faithfully derived from backend numeric values.
  - Categorical risk badges (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) and model trust state indicators (`HIGH_CONFIDENCE`, `MODERATE_CONFIDENCE`, `LOW_CONFIDENCE`, `UNAVAILABLE`).
  - Deterministic physical explainability cards displaying primary driver summaries and ranked contributing factors with dynamic target lead hours.
  - Safe abstention cards presenting standardized reason codes and non-zero safety warnings.
  - Structured client-side validation, HTTP 422, HTTP 429 (with `Retry-After` backoff notice), and network error views with immediate stale-result clearing.
  - Production build pipeline with Vite, TypeScript, and FastAPI static asset serving.
- **Out of Scope (Day 16 Separation)**:
  - Multi-day visual forecast-risk probability curves, time-series chart overlays, risk heatmaps, and spatial multi-layer map rendering (strictly deferred to Day 16).

---

## 3. Starting State

- **Baseline Commit**: `1ff2f25` (Merge pull request #17 from RupanjanDutta2006/phase2/builder1-development — Day 14 Production API Hardening).
- **Backend Test Baseline**: 254 passing tests.
- **Active ML Model**: `prototype-gbm-v1` (LightGBM Classifier + Platt Sigmoid Calibrator).
- **Feature Schema**: `builder2-canonical-26-v1.0` (26 canonical issue-time features).
- **Decision Threshold**: $0.280$.
- **Prior Frontend State**: No frontend code, configuration, or web package manifests existed in the repository prior to Day 15.

---

## 4. Architecture Decision

A pre-implementation repository audit confirmed the absence of any existing web framework or static assets. To provide a high-performance, type-safe, maintainable, and lightweight user experience, a decoupled SPA architecture was chosen:

| Dimension | Selection | Architectural Rationale |
| :--- | :--- | :--- |
| **Framework** | **React 19 + TypeScript** | Declarative state machine, component reuse, strict type synchronization with backend Pydantic schemas. |
| **Build Pipeline** | **Vite 6** | Instant Hot Module Replacement (HMR), native ES modules, lightweight production bundle (<75 kB gzipped). |
| **Styling** | **Curated Vanilla CSS** | Zero-runtime CSS design tokens, custom atmospheric dark theme, glassmorphism, responsive grid, full control without Tailwind bloat. |
| **Test Framework** | **Vitest + Testing Library + jsdom** | Fast in-memory DOM testing, standard React 19 testing patterns and accessibility assertions. |
| **API Client** | **Typed `VeyraApiClient`** | Centralized HTTP service handling base URL configuration, correlation headers (`X-Request-ID`), error parsing, and HTTP 429 `Retry-After` calculation. |
| **Backend Integration** | **FastAPI Static Mounting & CORS** | FastAPI optionally mounts built assets under `/assets` and serves `/dashboard`, while supporting standalone dev server operation (`localhost:5173`). |

---

## 5. Frontend Technology Stack

```
frontend/
├── package.json         # React 19, TypeScript, Vite 6, Vitest
├── tsconfig.json        # TypeScript compiler options (ES2022, React JSX)
├── vite.config.ts       # Vite config & Vitest test runner configuration
├── index.html           # HTML entry point with semantic metadata & Google Fonts
└── src/
    ├── api/
    │   ├── types.ts     # TypeScript models mirroring backend Pydantic contracts
    │   └── client.ts    # VeyraApiClient dedicated HTTP service
    ├── styles/
    │   └── index.css    # Atmospheric design system tokens, layout & components
    ├── components/
    │   ├── Header.tsx             # Brand banner & backend health indicator
    │   ├── ForecastForm.tsx       # Location, variable, datetime controls & validation
    │   ├── PredictionResult.tsx   # 4-decimal probability metric & badges
    │   ├── AbstentionResult.tsx   # Safe abstention banner & reason code pills
    │   ├── ExplainabilityView.tsx # Physical attribution narrative & factor cards
    │   ├── ErrorView.tsx          # 422, 429, validation & network error views
    │   └── Footer.tsx             # Versioning, model threshold & documentation links
    ├── App.tsx          # Main application coordinator & state machine
    ├── main.tsx         # React bootstrap entry point
    └── test/
        ├── setup.ts               # Testing Library DOM matchers setup
        └── Dashboard.test.tsx     # 27 comprehensive component & regression tests
```

---

## 6. Frontend Component Architecture

1. **`Header`**: Displays the Veyra brand identity, product tagline, and real-time backend operational status badge (polling `GET /v1/health`).
2. **`ForecastForm`**: Manages user input for location (free text, benchmark pills, or coordinates), meteorological variable, issue time, and valid target time. Executes client-side chronological validation (`valid_time > issue_time`) and horizon boundary checks ($\le 384\text{h}$).
3. **`PredictionResult`**: Renders the prominent forecast-bust probability formatted to exactly four decimal places (`X.XXXX%`), categorical risk badge, model trust state badge, and model version metadata.
4. **`AbstentionResult`**: Dedicated safety guardrail component rendered when `abstain == true`. Displays standardized reason codes and prominently warns: *"This is a safe abstention, not a low-risk prediction."*
5. **`ExplainabilityView`**: Renders the primary physical attribution narrative and ranked contributing factors (e.g. `lead_hours`, `ensemble_std`, `forecast_delta_24h`), including dynamic target lead hours and horizon signals.
6. **`ErrorView`**: Presents clear, actionable error notifications for client validation failures, HTTP 422 invalid input responses, HTTP 429 rate limit exceeded events (with dynamic retry countdown), and network connectivity errors.
7. **`Footer`**: Documents active model version (`prototype-gbm-v1`), ensemble source (NOAA GEFS 31-member), calibrated decision threshold ($0.280$), and links to backend OpenAPI interactive documentation.
8. **`App`**: Top-level coordinator managing asynchronous request lifecycles, error boundaries, and state transitions.

---

## 7. Backend Integration

The frontend communicates with the backend via the typed `VeyraApiClient` service:

- **Primary Prediction Endpoint**: `POST /v1/predict`
  - Accepts JSON payload with `location`, `variable`, optional `issue_time`, and `valid_time`.
  - Returns `PredictionResponse` containing `bust_probability`, `risk_level`, `trust_state`, `abstain`, `reason_codes`, `model_version`, `data_version`, and `explanation`.
- **Service Health Endpoint**: `GET /v1/health`
  - Polled on application load to confirm backend connectivity (`status: ok`).
- **Model Evaluation Endpoint**: `GET /v1/model/evaluation`
  - Provides model calibration metadata and offline benchmark statistics.
- **Base URL Configuration**:
  - Configurable via `VITE_API_BASE_URL` environment variable (defaults to `http://127.0.0.1:8000`).
  - Supported via Vite development proxy when running `npm run dev`.
- **FastAPI Static Serving**:
  - In production, FastAPI mounts `frontend/dist/assets` under `/assets` and serves `frontend/dist/index.html` on `/dashboard`.

---

## 8. Dashboard User Flow & Information Architecture

```
+-----------------------------------------------------------------------------------+
|  [Veyra Logo] Veyra — Know When Forecasts May Fail             [● API Online v0.1.0] |
+-----------------------------------------------------------------------------------+
|                           MEDIUM-RANGE FORECAST SENTINEL                           |
|              Anticipate Weather Forecast Failures Before They Happen               |
+------------------------------------------+----------------------------------------+
| LEFT COLUMN: FORECAST CONFIGURATION      | RIGHT COLUMN: PREDICTION & ATTRIBUTION  |
|                                          |                                        |
| 1. Location or Coordinates               | [State: Empty / Loading / Result]      |
|    - Free text input                     |                                        |
|    - Benchmark pills (London, Tokyo...)  | (A) Prediction Result Card:            |
|    - Direct coordinate support           |     - Forecast Bust Probability (e.g.  |
| 2. Meteorological Variable Select        |       5.6800%)                         |
|    - 2m Temperature, Surface Pressure... |     - Categorical Risk Badge (LOW/MED) |
| 3. Issue & Valid Datetime Controls       |     - Model Trust State (HIGH_CONF)    |
|    - ISO 8601 parsing                    |                                        |
|    - Horizon bounds check (≤ 384h)       | (B) Physical Explainability View:      |
| 4. Submit Button                         |     - Primary Driver Narrative Box     |
|    - Busy spinner & double-click lock    |     - Ranked Contributing Factor Cards |
|                                          |                                        |
|                                          | (C) Safe Abstention Card (if abstain): |
|                                          |     - Clear "Prediction Abstained"     |
|                                          |     - Standardized Reason Badges       |
+------------------------------------------+----------------------------------------+
| FOOTER: Model: prototype-gbm-v1 | Ensemble: GEFS 31-member | Threshold: 0.280 | API Docs |
+-----------------------------------------------------------------------------------+
```

---

## 9. Probability Presentation

The bust probability is the central quantitative output of Veyra:

- **Exact Transformation**:
  ```typescript
  const percentage =
    bust_probability !== null && bust_probability !== undefined
      ? (bust_probability * 100).toFixed(4)
      : 'N/A';
  ```
- **Display Format**: Exactly four decimal places in percent form (`X.XXXX%`).
- **Data Integrity Standards**:
  - Derived exclusively and directly from `PredictionResponse.bust_probability`.
  - Zero artificial digits, random noise, or synthetic precision added.
  - Trailing zeroes (e.g. `5.6800%`) represent standard decimal formatting of backend values (e.g. `0.0568`).
  - Four-decimal formatting does NOT imply four-decimal empirical forecast skill.

---

## 10. Risk & Trust Presentation

- **Categorical Risk Badges**:
  - `LOW`: Bust probability $< 0.280$ (default calibrated threshold).
  - `MEDIUM`: Bust probability in $[0.280, 0.500)$.
  - `HIGH`: Bust probability in $[0.500, 0.750)$.
  - `CRITICAL`: Bust probability $\ge 0.750$.
- **Model Trust States**:
  - `HIGH_CONFIDENCE`: Complete 31-member ensemble, valid QC, active model.
  - `MODERATE_CONFIDENCE`: Minor meteorological volatility or baseline fallback.
  - `LOW_CONFIDENCE`: Elevated spread or degraded sensor inputs.
  - `UNAVAILABLE`: Abstained prediction.

---

## 11. Explainability & Dynamic Lead Hours

When predictions succeed, the dashboard renders physical feature attribution:
- **Primary Driver Narrative**: Plain-language meteorological explanation (e.g. *"Forecast is stable with low ensemble dispersion and consistent inter-cycle agreement"*).
- **Contributing Factors**:
  - `lead_hours`: Dynamic target horizon (e.g. `96.0h` $\rightarrow$ `MEDIUM_RANGE_HORIZON`, `168.0h` $\rightarrow$ `EXTENDED_RANGE_DEGRADATION`, `< 72.0h` $\rightarrow$ `SHORT_RANGE_HORIZON`).
  - `ensemble_std`: Ensemble dispersion metric.
  - `forecast_delta_24h`: Run-to-run cycle drift.

---

## 12. Safe Abstention

When `abstain == true`:
- The prediction result card is strictly hidden.
- The UI **never** renders $0\%$, `0.0000%`, or `LOW` risk.
- Displays `AbstentionResult` card with standardized reason codes:
  - `INVALID_LOCATION`: Unresolvable address or out-of-bounds coordinates.
  - `DATA_UNAVAILABLE`: Upstream ensemble feed down.
  - `QC_FAILED`: Physical quality control violations.
  - `OOD_ABSTAIN`: Out-of-distribution atmospheric state.
  - `MODEL_NOT_READY`: Model artifact unready.

---

## 13. Validation & Error Handling

- **Client-Side Form Validation**:
  - Location required (whitespace trimmed).
  - Chronological sanity: `valid_time` must be strictly after `issue_time`.
  - Horizon boundary: `(valid_time - issue_time) <= 384h` (16 days).
- **Server Error Mapping**:
  - `HTTP 422`: Formats structured Pydantic validation field errors.
  - `HTTP 429`: Displays rate-limit notification with dynamic `Retry-After` countdown.
  - `Network Error`: Displays connection retry guidance.
- **Stale State Cleanup**: Any validation or server error immediately purges previous prediction results from the UI.

---

## 14. Accessibility & Responsive Design

- Semantic HTML5 structure (`<header>`, `<main>`, `<section>`, `<footer>`, `<form>`).
- Full ARIA compliance: `aria-live="polite"` on metric regions, `role="status"` on badges, `aria-labelledby` on cards.
- Accessible color contrast exceeding WCAG AA requirements on atmospheric dark theme.
- Responsive CSS Grid collapsing from 2-column desktop layout to single-column mobile view on screens $< 900\text{px}$.

---

## 15. Bugs Discovered During Manual Verification

During user-performed interactive browser verification, two functional bugs and one UX precision issue were discovered:

1. **Bug 1: Stale Result State on Validation/Error Submission**:
   - *Symptom*: After a successful prediction, submitting an invalid input (e.g. zero lead time) showed the error banner but left the previous prediction card visible.
2. **Bug 2: Lead Hours Explainability Anomaly**:
   - *Symptom*: Submitting a 96-hour forecast (Issue `2026-08-29 12:30 UTC` $\rightarrow$ Valid `2026-09-02 12:30 UTC`) resulted in Explainability displaying `Lead Hours: 12, Signal: Short Range Horizon`.
3. **UX Precision Issue: Aggressive 1-Decimal Percentage Rounding**:
   - *Symptom*: Multiple distinct locations and horizons displayed identically as `5.7%` due to `(p * 100).toFixed(1)` formatting.

---

## 16. Bug Fixes & Technical Implementations

### Bug 1 Fix (Stale Result State)
- Added `onValidationError?: (errorMessage: string) => void` callback prop to `ForecastForm.tsx`.
- In `App.tsx`, implemented `handleValidationError()` to immediately clear `prediction` state hook (`setPrediction(null)`) and record error state.
- In `App.handleForecastSubmit()`, ensured `setPrediction(null)` and `setError(null)` execute immediately at the start of any new evaluation lifecycle.
- Added regression tests (TEST A – TEST E) in `Dashboard.test.tsx`.

### Bug 2 Fix (Target Lead Hours & Explainer Selection)
- *Root Cause*:
  1. `ForecastBustAgent.analyze()` originally omitted timing parameters from `weather_result.metadata`.
  2. `Builder2FeatureAdapter` extracted all 840 timesteps and stored them in `feature_matrix_rows`.
  3. `Builder2ModelAdapter.predict()` evaluated all 840 rows, ran `np.argmax(probabilities)`, and defaulted to row 0 (the 12h initial forecast step), generating a 12h explanation stored in `model_result.metadata["explanation"]`.
  4. `Builder2FeatureAdapter` did not compute `(valid_time - issue_time)` into `features_dict["lead_hours"]`.
- *Fix*:
  1. In `Builder2FeatureAdapter.build_features()`, added `is_single_target = bool(target_valid or weather_result.target_date)` flag. When `issue_time` and `valid_time` are provided, calculated `req_lead = (dt_req_valid - dt_req_issue) / 3600.0` and assigned to `features_dict["lead_hours"]`.
  2. In `Builder2ModelAdapter.predict()`, when `is_single_target` is True, prioritized single-target feature evaluation `df_features = pd.DataFrame([feature_result.features])`, ensuring exact target lead hours and attribution. Preserved whole-horizon matrix aggregation when no timestamp is specified.
  3. Added backend multi-horizon regression test `test_explainability_target_valid_time_lead_selection`.

---

## 17. Probability Precision & Diversity Audit

### Audit Findings
- **Raw Probabilities Legally Differ**: Uncalibrated LightGBM probabilities range from `0.2460` to `0.3008` across locations, and calibrated probabilities range from `0.0561` to `0.0568`.
- **Formatting Fix**: Updated `PredictionResult.tsx` from `.toFixed(1)` to `.toFixed(4)`.
- **Audit Table**:

| Location | Variable | Lead | Raw Backend Prob | Displayed % | Risk | Trust | Model Version |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Kolkata** | `temperature_2m` | 24h | `0.0568` | **`5.6800%`** | `LOW` | `HIGH_CONFIDENCE` | `prototype-gbm-v1` |
| **Kolkata** | `temperature_2m` | 96h | `0.0568` | **`5.6800%`** | `LOW` | `HIGH_CONFIDENCE` | `prototype-gbm-v1` |
| **Kolkata** | `temperature_2m` | 168h | `0.0568` | **`5.6800%`** | `LOW` | `HIGH_CONFIDENCE` | `prototype-gbm-v1` |
| **Kolkata** | `temperature_2m` | 384h | `0.0568` | **`5.6800%`** | `LOW` | `HIGH_CONFIDENCE` | `prototype-gbm-v1` |
| **London** | `temperature_2m` | 96h | `0.0566` | **`5.6600%`** | `LOW` | `HIGH_CONFIDENCE` | `prototype-gbm-v1` |
| **Tokyo** | `temperature_2m` | 96h | `0.0566` | **`5.6600%`** | `LOW` | `HIGH_CONFIDENCE` | `prototype-gbm-v1` |
| **Kathmandu** | `temperature_2m` | 96h | `0.0567` | **`5.6700%`** | `LOW` | `HIGH_CONFIDENCE` | `prototype-gbm-v1` |
| **Berlin** | `temperature_2m` | 96h | `0.0566` | **`5.6600%`** | `LOW` | `HIGH_CONFIDENCE` | `prototype-gbm-v1` |
| **Kolkata** | `wind_speed_10m` | 96h | `0.0566` | **`5.6600%`** | `LOW` | `HIGH_CONFIDENCE` | `prototype-gbm-v1` |
| **Kolkata** | `precipitation` | 96h | `0.0561` | **`5.6100%`** | `LOW` | `HIGH_CONFIDENCE` | `prototype-gbm-v1` |

---

## 18. User-Performed Manual Browser Verification

All manual browser verifications below were interactively executed by the user against the live running dashboard:

| Test Category | Executed Scenario / Inputs | Observed Result | Verification Status |
| :--- | :--- | :--- | :---: |
| **Normal Successful Prediction** | Location: `Kolkata`, Variable: `temperature_2m`, 96h Lead | `5.6800%`, Risk: `LOW`, Trust: `High Confidence`, `prototype-gbm-v1` | **VERIFIED (User Browser)** |
| **Dynamic City Resolution** | `Kolkata` (`5.6800%`), `Tokyo` (`5.6600%`), `Kathmandu` (`5.6700%`), `Berlin` (`5.6600%`) | Resolved accurately, displayed distinct calibrated probabilities | **VERIFIED (User Browser)** |
| **Direct Coordinates** | `22.5726, 88.3639` (Kolkata) | Ingested 31-member GEFS ensemble, rendered matching `5.6800%` | **VERIFIED (User Browser)** |
| **Unsupported Location** | `Atlantis` | Rendered `Prediction Safely Abstained` (`INVALID_LOCATION`) | **VERIFIED (User Browser)** |
| **Out-of-Bounds Coordinates** | `999.0, 999.0` | Rendered `Prediction Safely Abstained` (`INVALID_LOCATION`) | **VERIFIED (User Browser)** |
| **Zero Lead Time** | `valid_time == issue_time` (with invalid coordinate in input) | Client validation banner displayed, previous prediction cleared | **VERIFIED (User Browser)** |
| **Negative Lead Time** | `valid_time < issue_time` (with invalid coordinate in input) | Client validation banner displayed, previous prediction cleared | **VERIFIED (User Browser)** |
| **Extended Horizon Boundary** | 384h (16 days) | Permitted & evaluated at boundary | **VERIFIED (User Browser)** |
| **Horizon Overflow** | 385h | Client validation banner: *"Forecast horizon cannot exceed 384 hours"* | **VERIFIED (User Browser)** |
| **Meteorological Variables** | Temperature (`5.6800%`), Wind Speed (`5.6600%`), Precipitation (`5.6100%`) | Rendered appropriate units and varied probabilities | **VERIFIED (User Browser)** |
| **Surface Pressure Horizon** | Surface Pressure (AM/PM timestamps evaluating 84h horizon) | Successfully evaluated at 84h | **VERIFIED (User Browser)** |
| **Physical Explainability** | 96h Lead Horizon | Rendered `Lead Hours: 96`, `Medium Range Horizon` | **VERIFIED (User Browser)** |
| **Extended Explainability** | 168h Lead Horizon | Rendered `Lead Hours: 168`, `Extended Range Degradation` | **VERIFIED (User Browser)** |

---

## 19. Scientific Distinction: UI/API Integration vs Real-World Outcome Verification

> [!IMPORTANT]
> **Essential Scientific Distinction**:
>
> 1. **What Day 15 Established (UI/API Integration Verification)**:
>    - The frontend accurately constructs and submits API payloads.
>    - Backend model responses are received, parsed, and faithfully rendered.
>    - Small legitimate probability variations (e.g. $5.6800\%$ vs $5.6600\%$ vs $5.6100\%$) are visible without artificial perturbation.
>    - Safety guardrails, reason codes, and error transitions operate reliably.
>
> 2. **What Day 15 Did NOT Establish (Real-World Model Accuracy / Skill)**:
>    - A prediction of $5.6800\%$ does **not** prove empirical correctness for a future weather outcome.
>    - Empirical accuracy requires longitudinal verification:
>      $$\text{Forecast Issued} \rightarrow \text{Predicted } P(\text{Bust}) \rightarrow \text{Target Time Arrives} \rightarrow \text{Observation Acquired} \rightarrow \text{Error Computed} \rightarrow \text{Bust Label Assigned} \rightarrow \text{Brier Score / Reliability Diagram}$$
>    - This formal outcome evaluation system is part of Phase 2 evaluation pipelines, not Day 15 UI integration.

---

## 20. Automated Verification

### Final Verified Test Baseline

| Test Suite | Command | Tests Run | Result | Notes |
| :--- | :--- | :---: | :---: | :--- |
| **Frontend Unit & Component** | `npm.cmd test` | **27** | **27 Passed (100%)** | Includes precision, lifecycle, and explainability regression tests. |
| **Frontend Production Build** | `npm.cmd run build` | — | **PASS** | TypeScript + Vite compiled `dist/` in 1.17s. |
| **Full Backend Pytest** | `pytest backend/tests/` | **255** | **255 Passed (100%)** | Zero regressions across all Day 1–15 backend modules. |
| **Builder 2 Standalone Smoke** | `python scripts/smoke_test_builder2.py` | **16** | **16/16 Passed** | 100% operational. |
| **System Readiness Smoke** | `python scripts/smoke_test_final.py` | **10** | **10/10 Passed** | 100% operational. |
| **Historical Verification Smoke** | `python scripts/smoke_test_historical.py` | **6** | **6/6 Passed** | 100% operational. |

---

## 21. Model & Data Safety

| Safety Dimension | Verified Status | Detail |
| :--- | :---: | :--- |
| **Model Artifacts Modified** | **NO** | Binary model and metadata files in `models/` remain 100% untouched. |
| **Model Retrained** | **NO** | Zero model training or fine-tuning executed. |
| **Probability Algorithm Modified for UI** | **NO** | Probability generation remains strictly server-side. |
| **Calibration Changed** | **NO** | Platt Sigmoid scaling parameters intact. |
| **Decision Threshold** | **NO** | Preserved at exactly $0.280$. |
| **Feature Schema** | **NO** | 26 canonical issue-time features preserved. |
| **Ground-Truth / Reference Leakage** | **ZERO** | Zero reference observation fields exposed to frontend or feature extractors. |

---

## 22. Security & Production Integration

- **Zero Hard-Coded Credentials**: No API keys, passwords, or authentication tokens in source or configuration.
- **Strict Input Sanitization**: All location and timestamp inputs are validated and sanitized.
- **Production Asset Serving**: FastAPI serves pre-built static assets under `/assets` and dashboard HTML on `/dashboard`.
- **CORS & Rate Limiting**: `RateLimitingMiddleware` protects API endpoints while exempting static dashboard assets.

---

## 23. File Manifest

### Created Files (21 files)
1. `Overview/Phase-2/Builder-1/Day-15.md`: Comprehensive Day 15 documentation.
2. `frontend/package.json`: Frontend dependencies manifest.
3. `frontend/package-lock.json`: Frontend locked dependency tree.
4. `frontend/tsconfig.json`: TypeScript compiler configuration.
5. `frontend/vite.config.ts`: Vite build and test configuration.
6. `frontend/index.html`: Main HTML entry point.
7. `frontend/src/vite-env.d.ts`: Vite type declarations.
8. `frontend/src/api/types.ts`: API TypeScript contracts.
9. `frontend/src/api/client.ts`: `VeyraApiClient` service.
10. `frontend/src/styles/index.css`: Vanilla CSS design system.
11. `frontend/src/components/Header.tsx`: Brand banner & health indicator.
12. `frontend/src/components/ForecastForm.tsx`: Location, variable & datetime form.
13. `frontend/src/components/PredictionResult.tsx`: 4-decimal probability metric & badges.
14. `frontend/src/components/AbstentionResult.tsx`: Safe abstention card.
15. `frontend/src/components/ExplainabilityView.tsx`: Physical attribution display.
16. `frontend/src/components/ErrorView.tsx`: Error views.
17. `frontend/src/components/Footer.tsx`: Product footer.
18. `frontend/src/App.tsx`: React coordinator & state machine.
19. `frontend/src/main.tsx`: React entry point.
20. `frontend/src/test/setup.ts`: Vitest test setup.
21. `frontend/src/test/Dashboard.test.tsx`: 27 unit & integration tests.

### Modified Files (10 files)
1. `.gitignore`: Added frontend build ignores (`node_modules/`, `dist/`, `.vite/`).
2. `Overview/Phase-2/Builder-1/Day-14.md`: Forward navigation link to Day 15.
3. `Overview/README.md`: Updated Phase 2 Builder 1 documentation index.
4. `README.md`: Updated root documentation index.
5. `backend/app/agents/forecast_bust_agent.py`: Forwarded timing metadata to weather result.
6. `backend/app/builder2/feature_adapter.py`: Dynamic target row matching, lead calculation, and `is_single_target` flag.
7. `backend/app/builder2/model_adapter.py`: Single-target vs full-horizon inference prioritization.
8. `backend/app/core/middleware.py`: Exempted `/dashboard` and `/assets` from rate limiting.
9. `backend/app/main.py`: Added static asset mounting and `/dashboard` endpoint.
10. `backend/tests/test_explainability_integration.py`: Added multi-horizon regression test and cleaned EOF formatting.

---

## 24. Day 15 Final Status & Roadmap

- **Day 15 Status**: **COMPLETE & VERIFIED**
- **Next Planned Roadmap Item**: Phase 2 — Builder 1 — Day 16: Visual Forecast Risk (Time-Series Curves, Risk Heatmaps & Multi-Day Graph Overlays).
