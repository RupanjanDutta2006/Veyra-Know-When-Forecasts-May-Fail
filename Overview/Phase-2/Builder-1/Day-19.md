# Veyra — Phase 2 / Builder 1 / Day 19: Production Monitoring, Observability & Operational Reliability

## Document Header & Metadata
- **Project**: Veyra — Know When Forecasts May Fail
- **Phase**: Phase 2 (Hardening, Scale & Production Readiness)
- **Track**: Builder 1 (Backend Systems, Observability & Architecture)
- **Day**: Day 19
- **Status**: Complete & Fully Verified
- **Branch**: `phase2/builder1-day19`
- **Model Invariants**:
  - Model Directory: `models/day4` (Unchanged)
  - Model Name: `prototype-gbm-v1`
  - Decision Threshold: `0.280` (Strictly Unchanged)
  - Calibrator: Platt Sigmoid (Unchanged)
  - Feature Schema: `builder2-canonical-26-v1.0` (26 features, Unchanged)
  - Clean `git status models/` & `git diff models/`: Verified clean

---

## 1. Overview & Objectives
Day 19 implements robust, thread-safe, low-overhead, in-process production observability, structured logging, distributed request correlation, telemetry, and operational runbooks for the Veyra Forecast-Bust Sentinel platform.

### Key Objectives
1. **Accurate Monotonic Latency Measurement**: Eliminate system clock skew by migrating duration measurements to `time.perf_counter()`.
2. **Distributed Trace Correlation**: Preserve and generate sanitized, length-bounded `X-Request-ID` headers across the entire HTTP lifecycle, error payloads, and logs.
3. **Structured Operational Logging**: Implement Dual-mode (Key-Value text and JSON lines) structured access logging with zero secrets or sensitive payload leakage.
4. **Upstream Provider Telemetry**: Classify Open-Meteo GEFS API outcomes (`SUCCESS`, `TIMEOUT`, `HTTP_429`, `HTTP_5XX`, `MALFORMED_RESPONSE`, `NETWORK_ERROR`) with bounded retry and backoff counters.
5. **Cache & Deduplication Visibility**: Instrument in-flight request coalescing (`SingleFlight`) and cache operations (`HIT`, `MISS`, `EXPIRED`, `EVICTION`) with zero lock contention.
6. **Prediction & Abstention Telemetry**: Categorize inference outcomes (`COMPLETED`, `ABSTAINED`) and track exact reason codes (`INVALID_LOCATION`, `DATA_UNAVAILABLE`, `QC_FAILED`, `DATA_NOT_READY`).
7. **Non-Intrusive Health Probes**: Guarantee `GET /v1/health` executes purely in-memory with zero external provider calls.
8. **Operational Runbooks**: Establish concrete incident diagnosis, triage, escalation, and mitigation runbooks for operational reliability.
9. **Strict External Monitoring Truth**: Accurately state external monitoring deployment status without fabricating cloud uptime or synthetic traffic metrics.

---

## 2. System Architecture & Observability Topology

```text
[ Client / Frontend Dashboard / API Consumer ]
                     │
                     │ HTTP Request (Optional Header: X-Request-ID)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ FastAPI Application Middleware Stack                        │
│                                                             │
│  1. RequestCorrelationMiddleware                            │
│     - Sanitizes/Generates X-Request-ID                      │
│     - Attaches X-Request-ID to Request & Response           │
│                                                             │
│  2. RateLimitingMiddleware                                  │
│     - Sliding-window in-process throttle                    │
│     - Emits HTTP 429 + Retry-After + Metrics on excess      │
│                                                             │
│  3. StructuredLoggingMiddleware                             │
│     - Measures monotonic duration (time.perf_counter)       │
│     - Emits structured log event (text KV or JSON lines)    │
│     - Increments ProcessMetrics counters                    │
│                                                             │
│  4. SecurityHeadersMiddleware                               │
│     - Enforces X-Content-Type-Options, HSTS, X-Frame-Options│
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ Veyra Orchestration Layer (ForecastBustAgent)               │
│                                                             │
│  - Pipeline Telemetry: duration_ms, model_version, variable │
│  - Outcome Counters: COMPLETED vs ABSTAINED                 │
│  - Reason Code Counters: INVALID_LOCATION, QC_FAILED, etc.  │
└──────┬──────────────────────┬──────────────────────┬────────┘
       │                      │                      │
       ▼                      ▼                      ▼
┌──────────────┐      ┌──────────────┐      ┌─────────────────┐
│ Dynamic Loc  │      │ Open-Meteo   │      │ ML Model &      │
│ & Geocoding  │      │ GEFS Service │      │ Safety Engine   │
│              │      │              │      │                 │
│ - Bounded    │      │ - Cache Hit/ │      │ - Platt Calib   │
│   LRU Cache  │      │   Miss/Evict │      │ - Threshold     │
│ - Resolution │      │ - SingleFlt  │      │   0.280 check   │
│   Telemetry  │      │ - Error Enum │      │ - Explainability│
└──────────────┘      └──────────────┘      └─────────────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │ Thread-Safe In-Process      │
              │ Metrics (ProcessMetrics)    │
              │                             │
              │ - http_requests_total       │
              │ - upstream_requests_total   │
              │ - cache_hits/misses/evict   │
              │ - singleflight_coalesced    │
              │ - abstentions_total         │
              │ - GET /v1/metrics snapshot  │
              └─────────────────────────────┘
```

---

## 3. Monotonic Latency & Performance Timing
All elapsed duration measurements across the backend have been standardized to Python's `time.perf_counter()`.
- **Clock Drift Immunity**: Unlike `time.time()`, `time.perf_counter()` is monotonically non-decreasing and immune to NTP time adjustments, Leap seconds, and system clock resets.
- **Precision**: Sub-millisecond timing accuracy recorded in milliseconds (`duration_ms = round((time.perf_counter() - start_time) * 1000, 2)`).
- **Instrumentation Sites**:
  - `StructuredLoggingMiddleware` (Full HTTP request-response cycle).
  - `OpenMeteoGEFSWeatherService._fetch_raw_forecast` (External upstream network duration).
  - `ForecastBustAgent.analyze` (Full prediction pipeline orchestrator duration).

---

## 4. Request Correlation & Distributed Tracing Contract (`X-Request-ID`)
Every incoming request is tagged with an end-to-end correlation identifier.

### Behavior Specification
1. **Client-Supplied Header**: If the client provides a valid `X-Request-ID` matching `^[A-Za-z0-9_\-\.]{1,64}$`, it is preserved and propagated.
2. **Invalid / Malformed / Oversized Header**: If missing, containing whitespace, newlines, or invalid characters, or exceeding 64 characters, the server sanitizes and replaces it with a cryptographically clean UUID (`req_<12-hex-chars>`).
3. **Response Header**: The active `X-Request-ID` is unconditionally returned in the HTTP response headers.
4. **Structured Error Schema**: In all error responses (400, 422, 429, 500), `request_id` is embedded in the JSON payload body.
5. **Frontend Client**: The frontend API client (`frontend/src/api/client.ts`) captures and stores `request_id` from response headers and error bodies.

---

## 5. Structured Logging Architecture
Logging is emitted through standard Python `logging` with structured formatting compatible with modern log collectors (Datadog, AWS CloudWatch, Grafana Loki, Papertrail).

### Configuration (`LOG_FORMAT`)
- **`text` (Default)**: Human-readable key-value format.
  `2026-08-30 19:22:21,015 [INFO] veyra.access: event=request_complete method=POST path=/v1/predict status=200 duration_ms=12.20 client_ip=testclient request_id=req_d18e1b22b74c`
- **`json`**: Machine-parseable single-line JSON records.
  `{"event": "request_complete", "method": "POST", "path": "/v1/predict", "status": 200, "duration_ms": 12.20, "client_ip": "127.0.0.1", "request_id": "req_d18e1b22b74c"}`

---

## 6. Log Format & Key Definitions (Strict No Secrets Policy)
To guarantee zero sensitive data exposure:
- **No Credentials / API Keys**: Authentication tokens or secrets are never logged.
- **No Raw Feature Arrays**: 26-feature floats and ensemble matrices are excluded from access logs.
- **No Unsanitized Tracebacks**: 500 internal errors emit sanitized error messages; full raw tracebacks are never exposed to API consumers.

---

## 7. Upstream Open-Meteo Observability & Error Classification
Upstream HTTP calls to Open-Meteo GEFS are monitored and categorized into standardized outcome labels:

| Telemetry Outcome | Criteria | Action Taken |
|:---|:---|:---|
| `SUCCESS` | Upstream returned HTTP 200 with parseable JSON | Cache populated, QC evaluated |
| `HTTP_429` | Upstream returned HTTP 429 Too Many Requests | Retry-After honored, counted in `upstream_429_total`, abstains with `DATA_UNAVAILABLE` |
| `HTTP_5XX` | Upstream returned 500, 502, 503, 504 | Bounded retries executed, abstains with `DATA_UNAVAILABLE` |
| `TIMEOUT` | Socket/Connect timeout exceeded | Abstains with `DATA_UNAVAILABLE` |
| `MALFORMED_RESPONSE` | JSON decode failure or corrupt payload | Abstains with `DATA_UNAVAILABLE` |
| `NETWORK_ERROR` | Connection reset or DNS resolution failure | Abstains with `DATA_UNAVAILABLE` |

---

## 8. Cache & SingleFlight Operational Telemetry
- **BoundedTTLCache**:
  - `cache_hits_total`: Fast-path responses served from memory without network overhead.
  - `cache_misses_total`: Cache misses requiring network execution.
  - `cache_evictions_total`: Oldest or expired keys evicted under bounded capacity (max size: 512).
- **SingleFlight Deduplication**:
  - `singleflight_calls_total`: Total invocations attempting upstream data acquisition.
  - `singleflight_coalesced_total`: Concurrent follower requests that coalesced onto an existing in-flight leader without issuing duplicate upstream network requests.

---

## 9. ML Prediction & Safe Abstention Telemetry
- **Prediction Outcomes**:
  - `COMPLETED`: Model inference succeeded, probability generated, risk level assigned (`LOW`, `MEDIUM`, `HIGH`).
  - `ABSTAINED`: Model safely refused prediction to protect user decisions.
- **Abstention Categorization**:
  - `INVALID_LOCATION`: Unresolvable or out-of-bounds geographic location.
  - `DATA_UNAVAILABLE`: Upstream provider unreachable, rate-limited, or timed out.
  - `QC_FAILED`: Meteorological quality control bounds violated.
  - `DATA_NOT_READY`: Missing ensemble members or zero records parsed.
  - `MODEL_UNAVAILABLE`: Model artifact missing or inference engine uninitialized.

---

## 10. Health Check vs Upstream Dependency Isolation Contract
- **Contract**: `GET /v1/health` is an **in-memory liveness probe**.
- **Zero External Network Calls**: Health checks do NOT call Open-Meteo, geocoding APIs, or disk inference pipelines.
- **Payload**: `{"status": "ok", "service": "forecast-bust-sentinel", "version": "0.1.0"}`
- **Execution Latency**: Typically $<1.0\text{ ms}$.

---

## 11. Process-Local Metrics Architecture & Endpoint Specification
- **Endpoint**: `GET /v1/metrics`
- **Access**: In-memory, non-blocking snapshot.
- **Sample Snapshot**:
```json
{
  "uptime_seconds": 124.5,
  "http_requests_total": {
    "GET /v1/health 200": 42,
    "POST /v1/predict 200": 18
  },
  "http_errors_total": 0,
  "http_avg_latency_ms": 3.45,
  "predictions_total": {
    "outcome=COMPLETED|risk=LOW|model=prototype-gbm-v1": 15,
    "outcome=ABSTAINED|risk=NONE|model=unknown": 3
  },
  "abstentions_total": {
    "INVALID_LOCATION": 3
  },
  "upstream_requests_total": {
    "openmeteo:SUCCESS": 1
  },
  "upstream_failures_total": 0,
  "upstream_429_total": 0,
  "cache_hits_total": 17,
  "cache_misses_total": 1,
  "cache_evictions_total": 0,
  "singleflight_calls_total": 18,
  "singleflight_coalesced_total": 17,
  "retries_attempted_total": 0
}
```

---

## 12. Alerting Strategy & Operational Thresholds

| Metric / Signal | Warning Threshold | Critical Threshold | Recommended Operational Action |
|:---|:---|:---|:---|
| **Upstream 429 Rate** | $>5\text{ events / min}$ | $>20\text{ events / min}$ | Verify cache TTL and SingleFlight deduplication; check IP reputation with Open-Meteo |
| **Upstream Timeout Rate** | $>5\%$ of requests | $>15\%$ of requests | Check upstream connectivity, network routing, or increase `WEATHER_TIMEOUT_SECONDS` |
| **Abstention Surge** | $>25\%$ of predictions | $>50\%$ of predictions | Audit upstream payload formats and QC validator thresholds |
| **App HTTP 429 Flood** | $>50\text{ events / min}$ | $>200\text{ events / min}$ | Identify abusive client IP via `client_ip` structured logs; adjust `RATE_LIMIT_REQUESTS_PER_MINUTE` |
| **High Average Latency** | $>500\text{ ms}$ | $>2000\text{ ms}$ | Check for upstream socket stalls or CPU thread starvation |

---

## 13. Runbook: Upstream Open-Meteo Degradation & Outages
- **Symptoms**: `upstream_failures_total` increasing; prediction responses returning `abstain: true` with `reason_codes: ["DATA_UNAVAILABLE"]`.
- **Diagnosis**:
  1. Inspect structured logs for `event=upstream_fetch_failed outcome=TIMEOUT` or `outcome=HTTP_5XX`.
  2. Verify network egress connectivity to `api.open-meteo.com`.
- **Mitigation**:
  1. Veyra automatically fails closed and protects users by abstaining safely.
  2. If transient, bounded retries with backoff handle brief glitches.
  3. Increase `WEATHER_CACHE_TTL_SECONDS` to extend cached forecast reuse.

---

## 14. Runbook: Upstream Rate Limiting (HTTP 429) & Provider Throttling
- **Symptoms**: `upstream_429_total` counter incrementing; logs show `outcome=HTTP_429`.
- **Diagnosis**:
  1. Check `cache_hits_total` vs `cache_misses_total` to ensure caching is enabled.
  2. Check `singleflight_coalesced_total` to verify multi-horizon requests are properly coalesced.
- **Mitigation**:
  1. Confirm `WEATHER_CACHE_ENABLED=True` and `WEATHER_DEDUP_ENABLED=True`.
  2. Ensure frontend sends concurrent timeline queries from the same `issue_time` to maximize cache hits.

---

## 15. Runbook: High Application Latency & Saturation
- **Symptoms**: `http_avg_latency_ms` exceeds 500 ms; slow dashboard responsiveness.
- **Diagnosis**:
  1. Check if latency is localized to upstream weather ingestion or ML inference.
  2. Inspect `duration_ms` in `event=upstream_fetch_complete` vs `event=prediction_completed`.
- **Mitigation**:
  1. Warm local cache with benchmark locations.
  2. Increase Uvicorn worker count in production if CPU bound.

---

## 16. Runbook: High Abstention Rates & QC Anomalies
- **Symptoms**: High volume of `QC_FAILED` or `INVALID_LOCATION` abstentions.
- **Diagnosis**:
  1. Inspect `violations` in structured prediction response metadata.
  2. Verify whether upstream Open-Meteo changed field names or physical units.
- **Mitigation**:
  1. Check `ForecastQualityControl` bounds in `backend/app/data/qc.py`.
  2. Verify geocoding resolution in `DynamicLocationService`.

---

## 17. Runbook: Application Restart, Cache Cold Starts & Recovery
- **Symptoms**: Higher initial latency on first request after restart.
- **Procedure**:
  1. Startup is non-blocking and instant (in-memory models load in $<100\text{ ms}$).
  2. Health check `/v1/health` is immediately operational.
  3. First request for a location populates LRU cache and SingleFlight leader.

---

## 18. External Production Monitoring Statement
```text
========================================================================================
EXTERNAL PRODUCTION MONITORING: NOT ACTIVE — APPLICATION NOT YET EXTERNALLY DEPLOYED
========================================================================================
Veyra currently operates in local production-hardened readiness.
No external cloud resources (AWS, GCP, Datadog, Prometheus server, New Relic)
have been connected or configured.
Zero synthetic uptime or external production metrics have been fabricated.
========================================================================================
```

---

## 19. Dedicated Automated Test Suite & Coverage Matrix (18 Tests)
The dedicated test suite `backend/tests/test_observability.py` tests all operational scenarios deterministically:

1. `test_client_supplied_request_id_preserved`: Preserves incoming valid trace headers.
2. `test_server_generated_request_id_when_missing`: Generates sanitized `req_` UUID when omitted.
3. `test_request_latency_and_http_metrics_recorded`: Records HTTP request counts, errors, and average latency.
4. `test_structured_logging_json_format_support`: Validates structured JSON line emission under `LOG_FORMAT=json`.
5. `test_validation_failure_records_422_metric_and_correlation`: Handles 422 validation errors with correlation ID preservation.
6. `test_application_rate_limiting_records_429_metric`: Verifies 429 rate limit response and `Retry-After` header.
7. `test_upstream_success_telemetry_recorded`: Validates upstream success metrics and latency recording.
8. `test_upstream_timeout_telemetry`: Classifies socket timeouts as `TIMEOUT` and records safe abstention.
9. `test_upstream_http_429_telemetry`: Classifies upstream 429s as `HTTP_429` and tracks throttling.
10. `test_upstream_http_5xx_telemetry`: Classifies upstream 500/503 errors as `HTTP_5XX`.
11. `test_upstream_malformed_response_telemetry`: Classifies malformed JSON as `MALFORMED_RESPONSE`.
12. `test_cache_hit_miss_and_eviction_metrics`: Validates BoundedTTLCache hit, miss, and LRU eviction counters.
13. `test_singleflight_coalescing_operational_visibility`: Validates concurrent request coalescing visibility.
14. `test_singleflight_exception_cleanup_and_recovery`: Verifies clean error recovery after leader failure.
15. `test_invalid_location_safe_abstention_telemetry`: Verifies safe abstention telemetry on unknown locations.
16. `test_health_endpoint_contract_and_zero_upstream_calls`: Guarantees `/v1/health` makes 0 upstream calls.
17. `test_metrics_endpoint_contract`: Validates `/v1/metrics` snapshot contract.
18. `test_telemetry_and_metrics_contain_zero_secrets`: Audits all telemetry for zero credential/secret leakage.

---

## 20. Full Automated Regression & Smoke Test Results

### 1. Dedicated Observability Suite
```text
============================= 18 passed in 0.33s ==============================
```

### 2. Full Backend Test Suite
```text
======================= 310 passed in 89.24s (0:01:29) ========================
```

### 3. Frontend Vitest Suite
```text
Test Files  2 passed (2)
     Tests  51 passed (51)
```

### 4. Frontend Production Build
```text
✓ built in 1.27s
dist/index.html                   1.04 kB │ gzip:  0.56 kB
dist/assets/index-B1hVRLRb.css   19.09 kB │ gzip:  4.49 kB
dist/assets/index-D1ObhPaN.js   230.98 kB │ gzip: 71.79 kB
```

### 5. Standalone Smoke Test Suites
- **Builder 2 Smoke Test**: 16/16 Stages Passed (100% Operational).
- **Day 7 Final Smoke Test**: 10/10 Phases Passed.
- **Historical Smoke Test**: 6/6 Phases Passed.

---

## 21. ML Safety & Schema Immutability Attestation
- **Model Artifacts**: Clean. Untouched in `models/day4/`.
- **Decision Threshold**: `0.280` strictly maintained.
- **Calibrator**: Platt Sigmoid unchanged.
- **Feature Schema**: Canonical 26 features (`builder2-canonical-26-v1.0`) unchanged.
- **Git Status**: `git status --short models/` is completely empty.

---

## 22. Manual Browser Verification Results

All 6 manual browser verification tests were executed locally against the running production-like application.

| Test Case | Configuration | Expected & Observed Result | Verdict |
|:---|:---|:---|:---:|
| **1. Health + Metrics Endpoint** | `GET /v1/health` & `GET /v1/metrics` in browser | Health returned `status: "ok"`, version `0.1.0`. Metrics returned comprehensive JSON snapshot with latency, request counters, cache, and telemetry. (Browser favicon 404 recorded in HTTP errors as expected). | **PASS** |
| **2. Successful Prediction Telemetry** | Single Target: Kolkata, `temperature_2m` | Prediction succeeded: $\approx 5.68\%$ bust probability, Risk: `LOW`, Trust: `High Confidence`, Model: `prototype-gbm-v1`. Metrics recorded `outcome=COMPLETED`, `risk=LOW`, and `openmeteo:SUCCESS`. Zero 429/failures. | **PASS** |
| **3. Safe Abstention Telemetry** | Single Target: `Atlantis`, `temperature_2m` | UI presented "Prediction Safely Abstained" with reason "Unresolvable Location / Coordinates". Metrics recorded `outcome=ABSTAINED`, `risk=NONE`, and reason `INVALID_LOCATION`. | **PASS** |
| **4. Cache Observability** | Single Target: Kolkata, `temperature_2m` (Immediate Repeat) | First attempt allowed verification across TTL. Controlled immediate repeat verified cache reuse: `openmeteo:SUCCESS` remained 2, `cache_hits_total` incremented from 1 to 2, `cache_misses_total` remained 4. Zero additional upstream requests. | **PASS** |
| **5. 7-Day Wind Timeline Monitoring** | Visual Risk Timeline: Kolkata, `wind_speed_10m` (m/s), 7-day window | All 7 horizons (24h–168h) completed successfully. Selected 24h horizon showed $\approx 5.67\%$ probability, Risk: `LOW`. 7 prediction requests generated only 1 new Open-Meteo acquisition (`openmeteo:SUCCESS` moved 2 $\rightarrow$ 3; `cache_hits_total` moved 2 $\rightarrow$ 8). Zero request amplification. | **PASS** |
| **6. Final Health + Mode Switch UI Regression** | Mode switch: Visual Timeline $\rightarrow$ Single Target | `GET /v1/health` returned `status: "ok"`. Switching back to Single Target mode correctly cleared the active timeline state with zero UI/state regression. | **PASS** |

**Manual Verification Summary**: `6 / 6 PASS` (Local production-like environment).

---

## 23. Verification Summary & Completion Status
- **Automated Tests**: 18/18 dedicated observability tests PASS; 310/310 full backend tests PASS; 51/51 frontend vitest PASS; frontend build PASS; 3/3 smoke suites PASS.
- **Manual Verification**: 6/6 browser tests PASS.
- **ML Safety**: Models untouched, threshold strictly 0.280, schema `builder2-canonical-26-v1.0`.
- **Worktree State**: Day 19 changes locally present and intentionally uncommitted pending final audit and commit.
- **External Production Monitoring**: `NOT ACTIVE — APPLICATION NOT YET EXTERNALLY DEPLOYED`.
- **Final Status**: `DAY 19 COMPLETE — AUTOMATED AND MANUAL LOCAL OBSERVABILITY VERIFIED`.
