# Day 18 — Deployment & Production Readiness

## 1. Objective

The primary objective of Day 18 is to establish complete local deployment readiness and production hardening for the Veyra platform. This encompasses auditing runtime dependencies and architecture options, implementing production-grade server configuration and entry points, securing CORS headers against unauthorized origins, eliminating hardcoded URLs from client bundles, verifying filesystem-independent ML model artifact resolution, constructing a validated environment variable template with zero secret leakage, providing non-intrusive health checks, executing a local production simulation with static SPA serving, verifying failure modes deterministically, and recording production-like manual browser verification — strictly concluding prior to external cloud deployment.

---

## 2. Starting State

- **Active Branch**: `phase2/builder1-day18` initialized from updated `main` (`7b86798`) incorporating Day 17 upstream efficiency hardening.
- **Day 17 State Confirmed**:
  - `BoundedTTLCache` (LRU + TTL caching) and `SingleFlight` (in-flight request deduplication) active in `OpenMeteoGEFSWeatherService`.
  - Upstream request amplification resolved (1 single fetch per 7-day or 16-day visual timeline).
  - Bounded `Retry-After` sleep capped at 2.0s.
  - Decision threshold strictly $0.280$, feature schema `builder2-canonical-26-v1.0`, zero model retraining or artifact mutation.

---

## 3. Deployment Audit

A thorough audit of the repository components determined the runtime characteristics:

| Component | Technology | Runtime Requirements | Network / File Dependencies |
| :--- | :--- | :--- | :--- |
| **Backend API** | FastAPI, Uvicorn, Pydantic v2 | Python 3.10+ (Tested on 3.13.5) | Outbound HTTPS to Open-Meteo (`ensemble-api.open-meteo.com`); Read access to `models/` directory. |
| **ML Inference** | Scikit-Learn, LightGBM, Joblib | Pure CPU (LightGBM binary engine) | Local persisted joblib models (`models/day4/lightgbm_bust_model.joblib`, `models/day4/probability_calibrator.joblib`, `model_metadata.json`). |
| **Frontend UI** | React 19, TypeScript, Vite | Node 18+ (Build time); Browser (Client runtime) | Compiled static assets (`index.html`, `assets/index-*.js`, `assets/index-*.css`); Inbound HTTP/HTTPS to API `/v1/*`. |
| **Static Mounting** | FastAPI `StaticFiles` | In-process file serving | Serves `frontend/dist/` assets at `/assets` and SPA at `/dashboard` and `/dashboard/`. |

---

## 4. Recommended Architecture

The audit evaluated two primary deployment architectures:

### Option A: Decoupled / Separate Deployment
- **Frontend**: Hosted on CDN / Static Edge (Vercel, Netlify, Cloudflare Pages, S3/CloudFront).
- **Backend**: Hosted on Container / Python Web Service (Render, Railway, Fly.io, AWS ECS, GCP Cloud Run).
- **Evaluation**: Requires managing 2 services and DNS records; requires explicit cross-origin CORS configuration (`CORS_ORIGINS`).

### Option B: Unified Single-Service Deployment (Recommended Default)
- **Architecture**: Frontend is built at deploy time (`npm run build`), and FastAPI serves both the versioned JSON API (`/v1/*`) and the static production dashboard (`/dashboard`).
- **Evaluation**: Zero CORS friction (same-origin), single service management, lowest operational complexity, single configuration surface, minimal cold-start overhead.

### Decision: Dual-Ready Architecture
The codebase was hardened to be **Dual-Ready**:
- **Default (Option B)**: Unified single-service mode works out of the box with zero configuration (`VITE_API_BASE_URL` empty, same-origin relative API calls).
- **Decoupled (Option A)**: Fully supported by setting `VITE_API_BASE_URL=https://api.yourdomain.com` at frontend build time and `CORS_ORIGINS=https://your-frontend.com` on the backend.

---

## 5. Backend Production Configuration

1. **Host & Port Binding**:
   - Added `HOST` (default `0.0.0.0`) and `PORT` (default `8000`) settings to `Settings` in `backend/app/core/config.py`.
   - Supports platform-injected port bindings (e.g. `$PORT` on Render, Fly.io, Railway, Heroku).
2. **Production Entrypoint**:
   - Added `if __name__ == "__main__":` block to `backend/app/main.py` executing `uvicorn.run("backend.app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)` without `--reload` in production.
3. **Information Leakage Protection**:
   - Centralized exception handlers in `backend/app/core/error_handlers.py` strip file paths (`[PATH]`) and internal exception tracebacks from all 500 error responses.
4. **Security Headers & Request Correlation**:
   - `SecurityHeadersMiddleware` attaches `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, and `Referrer-Policy: strict-origin-when-cross-origin`.
   - `RequestCorrelationMiddleware` attaches and propagates sanitized `X-Request-ID` across all requests.

---

## 6. Frontend Production Configuration

1. **API Base URL Resolution**:
   - Updated `frontend/src/api/client.ts`:
     ```typescript
     const DEFAULT_BASE_URL =
       import.meta.env?.VITE_API_BASE_URL !== undefined && import.meta.env.VITE_API_BASE_URL !== ''
         ? import.meta.env.VITE_API_BASE_URL
         : '';
     ```
   - In Vite local development: uses relative paths proxied to `http://127.0.0.1:8000`.
   - In unified production: uses relative paths (`/v1/...`) on the same origin without hardcoded localhost URLs.
   - In decoupled production: uses configured `VITE_API_BASE_URL`.
2. **Footer Navigation**:
   - Updated `frontend/src/components/Footer.tsx` API documentation link from hardcoded `http://127.0.0.1:8000/docs` to relative `/docs`.

---

## 7. Model Artifact Deployment Safety

- **Working Directory Independence**:
  - `ForecastBustModelService`, `ModelArtifactManager`, `EvaluationIntegrationService`, and `Builder2ModelAdapter` inspect both direct paths (`models/day4`) and repository-anchored paths (`Path(__file__).resolve().parents[3] / model_dir`).
  - Loading succeeds regardless of whether the Python runtime is started from the repository root, `backend/`, or an arbitrary container working directory.
- **Model Cleanliness**:
  - Zero retraining, zero modifications to `models/day4/lightgbm_bust_model.joblib`, `probability_calibrator.joblib`, or metadata.
  - Decision threshold strictly preserved at `0.280`.

---

## 8. Environment Variables

Created `.env.example` documenting all configuration options with safe non-sensitive default values:

| Variable | Classification | Default Value | Purpose |
| :--- | :--- | :--- | :--- |
| `HOST` | Optional | `0.0.0.0` | Production server bind address |
| `PORT` | Optional | `8000` | Production server listen port |
| `DEBUG` | Optional | `False` | Enable/disable hot reloading and debug diagnostics |
| `LOG_LEVEL` | Optional | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `STRUCTURED_LOGGING` | Optional | `True` | Structured JSON log formatting |
| `ENABLE_SECURITY_HEADERS` | Optional | `True` | Attach standard OWASP security headers |
| `ENABLE_REQUEST_CORRELATION` | Optional | `True` | Attach and propagate `X-Request-ID` |
| `CORS_ORIGINS` | Optional | `localhost:5173,127.0.0.1:5173,...` | Comma-separated allowed CORS origins |
| `CORS_ALLOW_ALL` | Optional | `False` | Wildcard CORS flag (disables credentials) |
| `BUILDER2_MODEL_DIR` | Optional | `models/day4` | Path to active model artifacts |
| `WEATHER_CACHE_ENABLED` | Optional | `True` | Short-lived forecast TTL cache |
| `WEATHER_CACHE_MAX_SIZE` | Optional | `512` | Maximum entries in forecast LRU cache |
| `WEATHER_CACHE_TTL_SECONDS` | Optional | `120` | Forecast cache time-to-live in seconds |
| `WEATHER_DEDUP_ENABLED` | Optional | `True` | Concurrent SingleFlight request deduplication |
| `RATE_LIMIT_ENABLED` | Optional | `True` | In-process rate limiting |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | Optional | `120` | Rate limiter window capacity |
| `RATE_LIMIT_BURST_SIZE` | Optional | `30` | Rate limiter short burst capacity |
| `VITE_API_BASE_URL` | Optional (Frontend) | `""` (Empty string) | Public backend API URL for decoupled hosting |

---

## 9. CORS / Origin Security

- `backend/app/main.py` uses `settings.CORS_ORIGINS` and `settings.CORS_ALLOW_ALL`.
- If explicit origins are specified: `allow_origins=settings.CORS_ORIGINS`, `allow_credentials=True`.
- If wildcard mode is specified: `allow_origins=["*"]`, `allow_credentials=False` (enforcing W3C Fetch standard compliance).
- Tested and verified: OPTIONS preflights against unauthorized origins return no `Access-Control-Allow-Origin` header.

---

## 10. Health / Readiness

- Endpoint: `GET /v1/health`
- Response: `{"status": "ok", "service": "forecast-bust-sentinel", "version": "0.1.0"}`
- Verified: Health check executes purely in memory and makes **zero external network requests**, preventing upstream quota consumption by container liveness probes.

---

## 11. Production-Like Local Verification

1. **Frontend Production Build**: `npm run build` executed cleanly in 1.24s, generating `frontend/dist/index.html` (1.04 kB), `assets/index-*.css` (19.09 kB), and `assets/index-*.js` (230.98 kB).
2. **Static Mounting Simulation**: Tested via FastAPI `TestClient`:
   - `GET /dashboard` $\rightarrow$ `HTTP 200 OK` (`text/html; charset=utf-8`, serving `<div id="root"></div>`).
   - `GET /dashboard/` $\rightarrow$ `HTTP 200 OK` (`text/html; charset=utf-8`).
   - `GET /assets/...` $\rightarrow$ `HTTP 200 OK` (Static CSS/JS bundles).
   - `GET /v1/health` $\rightarrow$ `HTTP 200 OK`.
   - `POST /v1/predict` $\rightarrow$ `HTTP 200 OK`.

---

## 12. Failure / Recovery Verification

Dedicated failure scenarios tested in `backend/tests/test_deployment_readiness.py`:

- **Missing Environment Variables**: Safely defaults to production values without startup failure.
- **Missing Model Artifacts**: Model adapter gracefully falls back to `is_ready=False` and `probability=None` without crashing the process.
- **Malformed Request Payload**: Returns structured 422 JSON (`error: "VALIDATION_ERROR"`).
- **Excess Traffic / Abuse**: Rate limiter returns structured 429 JSON (`error: "RATE_LIMIT_EXCEEDED"`, with `Retry-After` header).
- **Disabled Cache / Dedup**: Weather service operates safely with direct upstream fetches when caching is toggled off.
- **Unhandled 500 Exceptions**: Sanitized error response returned without stack traces or path leakage.

---

## 13. Security Review

- **Committed Secrets**: ZERO (Verified via git audit).
- **CORS Configuration**: Configurable per environment, wildcard credentials forbidden.
- **Error Information Leakage**: Sanitized.
- **Host / Port Defaults**: Hardened.
- **Outbound Timeouts**: Bounded on all network calls.

---

## 14. Automated Test Results

- **Day 18 Deployment Readiness Suite (`pytest backend/tests/test_deployment_readiness.py -v`)**:
  - **14/14 Tests Passed (100%)** in 0.36s.
- **Full Backend Pytest Suite (`pytest backend/tests/ -v`)**:
  - **292/292 Tests Passed (100%)** in 55.83s.
- **Frontend Vitest Suite (`npx vitest run`)**:
  - **51/51 Tests Passed (100%)** in 4.18s.
- **Frontend Production Build (`tsc && vite build`)**:
  - **Passed in 1.41s**.
- **Smoke Test Suites**:
  - `python scripts/smoke_test_builder2.py`: **16/16 Stages Passed (100% Operational)**.
  - `python scripts/smoke_test_final.py`: **10/10 Phases Passed**.
  - `python scripts/smoke_test_historical.py`: **6/6 Phases Passed**.

---

## 15. Manual Browser Verification (Production-Style Local Run)

The user executed manual verification by building the frontend (`npm.cmd run build`) and starting the backend server without reload (`python -m backend.app.main`):

| Test Case | Scenario | Parameters | Result | Observed Verification |
| :--- | :--- | :--- | :--- | :--- |
| **Manual Test 1** | Production Dashboard | `http://127.0.0.1:8000/dashboard` | **PASS** | Production-built React dashboard loaded; CSS/assets rendered; API Online v0.1.0 displayed. |
| **Manual Test 2** | Health Endpoint | `http://127.0.0.1:8000/v1/health` | **PASS** | JSON response: `{"status": "ok", "service": "forecast-bust-sentinel", "version": "0.1.0"}`. |
| **Manual Test 3** | Valid Production E2E Prediction | Kolkata, `temperature_2m`, Single Target | **PASS** | Prediction completed; $P(\text{bust}) = 5.6800\%$; Risk: LOW; Trust: High Confidence; Model: `prototype-gbm-v1`; Explainability rendered. |
| **Manual Test 4** | Invalid Location Safety | Atlantis, `temperature_2m`, Single Target | **PASS** | Prediction Safely Abstained; Reason: Unresolvable Location / Coordinates; no fake probabilities rendered. |
| **Manual Test 5** | Invalid Location Timeline Safety | Atlantis, `wind_speed_10m`, 7-Day Timeline | **PASS** | All 7 horizons safely abstained; zero fake probabilities; abstention state and reason preserved. |
| **Manual Test 6** | Valid Production Timeline | Kolkata, `wind_speed_10m`, 7-Day Timeline | **PASS** | All 7 horizons rendered validly (24h–168h); 24h horizon: $P = 5.6700\%$, Risk: LOW, Trust: HIGH_CONFIDENCE, Model: `prototype-gbm-v1`, Explainability rendered; 0 QC/network errors. |

---

## 16. Model Safety

- **Model Retrained**: NO.
- **Model Artifacts Modified**: NO (`models/` clean).
- **Calibrator Modified**: NO.
- **Decision Threshold**: Strictly $0.280$ (Unchanged).
- **Feature Schema**: `builder2-canonical-26-v1.0` (26 canonical features, untouched).
- **Anti-Data Leakage**: Verified zero future observation or ground-truth leakage.

---

## 17. External Deployment Status

**STATUS: PENDING USER APPROVAL**

*No external cloud resources, DNS, serverless functions, or container services were modified or deployed during this turn.*

---

## 18. Remaining Limitations

- External cloud provider selection (e.g. Render, Railway, Fly.io, Vercel, AWS ECS) and live cloud deployment execution require user review and explicit deployment authorization.

---

## 19. Day 18 Status

**DAY 18 LOCAL PRODUCTION READINESS FULLY VERIFIED — READY FOR EXTERNAL DEPLOYMENT PLANNING**
