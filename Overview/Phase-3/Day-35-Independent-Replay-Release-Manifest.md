# Day 35: Independent Replay & Release Manifest (Gate C5)

## Executive Summary

Day 35 formalizes **Independent Replay & Production Release Manifest Validation** (Gate C5) for Veyra Phase 3. It establishes a machine-readable release manifest (`release_manifest.json`), an independent offline replay harness (`ReplayHarness`), a 10-scenario golden replay matrix (`GOLDEN_REPLAY_MATRIX`), non-circular base-commit Git provenance validation, and live provider smoke status handling.

---

## 1. Release Manifest Architecture

The production release manifest is located at `backend/app/core/release_manifest.json`.

```json
{
  "release_id": "veyra-v3.0.0-release-candidate",
  "manifest_schema_version": "v1.0.0",
  "generation_timestamp": "2026-09-20T21:00:00Z",
  "git_provenance": {
    "base_commit_sha": "968e3e58f1f3f7e93fa0c25682a8644c108935ac",
    "target_branch": "main",
    "strategy": "base_commit_provenance"
  },
  "model_artifact": {
    "path": "models/v3/lightgbm_v3_challenger.joblib",
    "sha256": "00a8410746f4a0eecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660",
    "version": "veyra-v3-benchmark-lightgbm",
    "decision_threshold": 0.060
  },
  "calibrator_artifact": {
    "path": "models/v3/probability_calibrator_v3.joblib",
    "sha256": "9f448606ce4338ded92f238a551b3a9d8e6d2cb5902e8bc687bce5f5850af531",
    "type": "IsotonicRegression",
    "method": "isotonic"
  },
  "feature_contract": {
    "feature_count": 50,
    "feature_schema_version": "veyra-50-features-v3.0",
    "feature_names_reference": "models/v3/feature_names.json"
  },
  "scientific_policies": {
    "certification_policy_version": "v3.0.0-frozen-benchmark",
    "certified_station_count": 25,
    "certified_variables": [
      "temperature_2m",
      "wind_speed_10m",
      "surface_pressure"
    ],
    "max_certified_lead_hours": 240,
    "ood_policy_version": "v3.0.0-physical-support",
    "time_contract_version": "v3.0.0-utc-temporal-invariants",
    "revision_store_schema_version": "v1.0.0-sqlite-wal"
  }
}
```

### Git Provenance Strategy
To prevent self-referential hash loops where a committed manifest file cannot contain its own commit SHA, Day 35 uses a **base commit provenance strategy** (`base_commit_provenance`), locking `base_commit_sha` to `968e3e58f1f3f7e93fa0c25682a8644c108935ac`.

---

## 2. Independent Replay Harness

The `ReplayHarness` (`backend/app/core/replay_harness.py`) independently verifies low-level scientific pipeline contracts rather than calling a single high-level endpoint:

1. **Location Resolution**: Verifies dynamic location geocoding & alias mapping (`Panaji` $\rightarrow$ `Goa`).
2. **Time Contract**: Derives lead hours and validates ISO 8601 UTC timestamp formatting.
3. **Artifact Integrity**: Recomputes SHA-256 for model and calibrator.
4. **Feature Engineering**: Constructs exact 50-feature vector using `V3FeaturePipeline`.
5. **Inference & Calibration**: Evaluates LightGBM decision function and Isotonic calibration.
6. **Risk Band Classification**: Maps calibrated $P(\text{BUST})$ into `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
7. **Scientific Certification**: Evaluates Gate C1 evidence boundary ($25$ stations, $\le 240\text{h}$).
8. **Out-of-Distribution Policy**: Evaluates Gate C2 physical domain bounds.

---

## 3. Golden Replay Matrix (10 Scenarios)

The golden matrix (`GOLDEN_REPLAY_MATRIX` in `backend/app/core/golden_replay_matrix.py`) covers:

| Scenario ID | Location | Variable | Lead | Certified | OOD | Objective |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GOLDEN-01` | Delhi | temperature_2m | 24h | Yes | No | Benchmark station 24h certified baseline |
| `GOLDEN-02` | Bengaluru | wind_speed_10m | 240h | Yes | No | Maximum certified lead horizon boundary |
| `GOLDEN-03` | Mumbai | surface_pressure | 264h | No | No | Extended operational scope (uncertified) |
| `GOLDEN-04` | Patna | temperature_2m | 48h | No | No | Uncertified station verification |
| `GOLDEN-05` | Panaji | wind_speed_10m | 48h | Yes | No | Deterministic location alias (`Panaji` $\rightarrow$ `Goa`) |
| `GOLDEN-06` | Blank | temperature_2m | 24h | No | No | Invalid location / automated abstention |
| `GOLDEN-07` | Delhi | temperature_2m | 24h | Yes | No | Uncalibrated fallback safety simulation |
| `GOLDEN-08` | Delhi | temperature_2m | 24h | Yes | Yes | Extreme temperature (380.0 K $\rightarrow$ OOD) |
| `GOLDEN-09` | Leh | temperature_2m | 12h | Yes | No | Timezone normalization & Leh inclusion |
| `GOLDEN-10` | Shimla | surface_pressure | 24h | Yes | No | Revision no-history initial state |

---

## 4. Live Provider Smoke Status

Live provider connectivity is checked independently via `perform_live_provider_smoke_check()` in `backend/app/core/live_smoke.py`.
- If live Open-Meteo queries succeed: reports `LIVE_PROVIDER_VERIFIED`.
- If network/rate-limiting occurs: reports `LIVE_PROVIDER_UNVERIFIED`.
- **Crucially**: Live provider status does NOT fail the offline deterministic replay gate.

---

## 5. Verification Results

- **Day 35 Focused Suite**: `21 / 21` passed (`backend/tests/test_day35_independent_replay_release_manifest.py`).
- **Targeted Cross-Day Suite**: `123 / 123` passed (Days 30, 32, 33, 34, 35, V3 Integrity).
- **Full Backend Suite**: `624 / 624` passed.
- **Frontend Test Suite**: `100 / 100` passed.
- **Production Build**: `PASS` (`tsc && vite build` built cleanly).
- **Artifact Hashes**:
  - Model SHA256: `00a8410746f4a0eecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660`
  - Calibrator SHA256: `9f448606ce4338ded92f238a551b3a9d8e6d2cb5902e8bc687bce5f5850af531`

---

## 6. Scientific Limitations

1. **Frozen Evidence Boundary**: Certification remains strictly limited to 25 synoptic stations, 3 variables, $\le 240\text{h}$ lead hours, and 2017–2019 NOAA GEFSv12 benchmark test holdout.
2. **Extended Horizons**: Leads from 264h to 384h operate as extended operational forecasts outside frozen certification.
3. **Replay Scope**: Deterministic replay guarantees bitwise pipeline reproducibility for frozen inputs; live provider feeds may vary due to upstream model cycle updates.
