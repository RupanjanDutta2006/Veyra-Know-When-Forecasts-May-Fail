# DAY 17 — EXPLAINABLE AI (XAI) FOR FORECAST-BUST RISK REPORT

**Document**: Scientific Architecture, Schema Specification & Forensic Hardening Report (Day 17)
**System**: Veyra — Know When Forecasts May Fail (Forecast-Bust Sentinel)
**Role**: Senior Scientific ML / Explainable AI / Meteorological Risk Systems Engineer (Builder 2)
**Status**: **`A. ENGINEERINGALLY VERIFIED & EMPIRICALLY CHARACTERIZED — SAFE TO COMMIT`**

---

## 1. Executive Summary & Core Objective

Day 17 implements the canonical **Explainable AI (XAI) Intelligence Layer** for Veyra, unifying and synthesizing the entire inference reasoning chain:

```
INPUT FORECAST / ENSEMBLE (Days 9, 10, 12)
             ↓
UNCERTAINTY & NOVELTY DECOMPOSITION (Day 14)
             ↓
CALIBRATED RISK & CONFIDENCE QUANTIFICATION (Days 13, 14)
             ↓
GOVERNED OPERATIONAL DECISION & ABSTENTION (Day 15)
             ↓
MULTI-CYCLE TEMPORAL TRAJECTORY & EARLY WARNING (Day 16)
             ↓
DETERMINISTIC DECISION COUNTERFACTUALS (Day 17)
             ↓
MULTI-LEVEL EXPLANATION RENDERING & FORENSIC TRACE (Day 17)
```

### Core Design Principles:
1. **Deterministic for Identical Canonical Inputs & Configuration**: Zero external LLM API calls in the scientific reasoning path. All explanations, attributions, diagnostics, and counterfactuals are generated from verified mathematical rules and structured dataclasses.
2. **Strict Operational Isolation**: Dual execution modes (`DECISION_TIME` vs `POST_HOC_EVALUATION`) guaranteeing that future verification data cannot leak into decision-time explanations.
3. **Comprehensive Forensic Provenance**: A deterministic SHA-256 fingerprint computed across all scientific inputs, feature attributions, uncertainty states, analogue consensus, temporal states, and governing policy thresholds (strictly excluding volatile timestamps).
4. **Policy Sensitivity Counterfactuals**: Answering *"What would need to change for the operational decision to de-escalate or escalate?"*, strictly tagged as `DECISION_COUNTERFACTUAL` (policy threshold sensitivities, not physical atmospheric interventions).

---

## 2. Parameter & Governance Registry

| Parameter / Field | Governance Classification | Scientific / Operational Rationale |
| :--- | :--- | :--- |
| `schema_version` | `OPERATIONAL_POLICY_PARAMETER` | Formal schema version (`17.0.0`) ensuring serialization compatibility. |
| `baseline_risk` | `EMPIRICALLY_ESTIMATED` | Background empirical base-rate ($0.15$) used for signed additive contribution reconciliation. |
| `high_risk_driver_cutoff` | `VALIDATED_FROM_HISTORICAL_DATA` | Normalized feature contribution $\ge +0.10$ designated as primary high-risk driver. |
| `protective_driver_cutoff`| `VALIDATED_FROM_HISTORICAL_DATA` | Normalized feature contribution $\le -0.03$ designated as protective risk suppressor. |
| `novelty_abstain_cutoff` | `DEFAULT_CONFIGURABLE_ASSUMPTION` | Feature-space distance threshold ($d \ge 2.50$) triggering safety abstention. |
| `explanation_confidence` | `OPERATIONAL_POLICY_PARAMETER` | Composite metric weighting attribution completeness (0.25), novelty support (0.25), analogue support (0.25), and evidence consensus (0.25). |
| `reconciliation_tolerance`| `OPERATIONAL_POLICY_PARAMETER` | Numerical residual tolerance ($\le 0.30$) for approximate additive attribution reconciliation. |
| `counterfactual_tag` | `OPERATIONAL_POLICY_PARAMETER` | Explicit `DECISION_COUNTERFACTUAL` governance tag distinguishing policy sensitivity from physical weather causality. |

---

## 3. Dual Provenance Architecture & Specification

Day 17 implements an explicit two-tiered provenance architecture to distinguish between pure scientific decision invariance and full execution auditability:

```
┌────────────────────────────────────────────────────────────────────────┐
│  1. DECISION PROVENANCE HASH (`decision_provenance_hash`)              │
│  - Evaluates: scientific features, moments, calibrated risk, drivers,  │
│    uncertainty, novelty, analogues, temporal kinematics,               │
│    counterfactuals, and governing decision policy thresholds.          │
│  - INVARIANTS:                                                         │
│    * Strictly invariant across execution modes (DECISION_TIME vs       │
│      POST_HOC_EVALUATION on same features -> IDENTICAL hash).          │
│    * Strictly invariant to retrospective truth values (truth_value,    │
│      forecast_error, bust_label).                                      │
│    * Strictly invariant to issue_time_utc and volatile timestamps.     │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│  2. EXECUTION PROVENANCE HASH (`provenance_hash`)                      │
│  - Combines: `decision_provenance_hash` + `mode` + `post_hoc_digest`   │
│  - INVARIANTS:                                                         │
│    * Distinguishes DECISION_TIME from POST_HOC_EVALUATION executions.  │
│    * Evaluates canonical sorted digest of post_hoc_verification.       │
│    * Updates deterministically when retrospective truth payload changes│
│      while preserving decision_provenance_hash.                        │
└────────────────────────────────────────────────────────────────────────┘
```

### Verification Proof & Observed Hashes:
- **Clean `DECISION_TIME`**:
  - `decision_provenance_hash`: `1f7e4acb551e7b0296f5e390`
  - `provenance_hash`: `9b5657c9bc45d6fbdd43acfe`
- **`POST_HOC_EVALUATION` (`truth_value = 1010.0`)**:
  - `decision_provenance_hash`: `1f7e4acb551e7b0296f5e390` *(Identical!)*
  - `provenance_hash`: `0d12fc1d9079b9502851a524` *(Distinct execution hash)*
- **`POST_HOC_EVALUATION` (`truth_value = 990.0`, `bust_label = 0`)**:
  - `decision_provenance_hash`: `1f7e4acb551e7b0296f5e390` *(Identical!)*
  - `provenance_hash`: `e2b52067e14b2f6e2941328c` *(Distinct execution hash)*
- **Scientific Feature Change (`ensemble_std = 5.5`)**:
  - `decision_provenance_hash`: `be0fa1cdcad897ce1280ef1d` *(Changes!)*
  - `provenance_hash`: `714f01cf82f7107dc5d9f868` *(Changes!)*

---

## 4. Feature Attribution & Additive Reconciliation Audit

`XAIAttributionEngine` produces ranked feature attributions mapped to domain-grounded meteorological interpretation templates:
* **Attribution Method**: `MODEL_IMPORTANCE_MOMENT_SCALING` (when tree/linear model is fitted) or `METEOROLOGICAL_MOMENT_HEURISTIC` (moment-scaled heuristic fallback).
* **Reconciliation Status**: Formally classified as `APPROXIMATE_ADDITIVE`.
* **Mathematical Representation**:
  $$\text{Target Risk} \approx \text{Baseline Risk} (0.15) + \sum c_i^+ + \sum c_i^-$$
* **Reconciliation Residual**:
  $$\text{Residual} = \left| P_{\text{target}} - \left( P_{\text{base}} + \sum c_i \right) \right| \le 0.30$$
* **Domain Disclaimer**: Feature contributions represent signed feature moment influences on the statistical risk estimate, not physical causal interventions in atmospheric dynamics.

---

## 5. Multi-Variable Stage B Empirical Validation

Validated against the active production dataset (`data/historical/multicycle_paired/paired_multicycle_stage_b_2026-08-18_2026-08-24.parquet`):

| Target Meteorological Variable | Test Scope | Verification Outcome |
| :--- | :--- | :--- |
| **`surface_pressure`** | Multi-cycle trajectories (lead 0–72h, 20 locations) | Clean attribution, temporal kinematics, zero leakage, valid Level 1/2/3 rendering. |
| **`temperature_2m`** | Multi-cycle trajectories (lead 0–72h, 20 locations) | Diurnal hour tracking, spread expansion diagnostics, stable provenance hash. |
| **`wind_speed_10m`** | Multi-cycle trajectories (lead 0–72h, 20 locations) | Gust dispersion attribution, directional revision analysis, policy counterfactuals. |

---

## 6. Public API Exports & Execution Governance Architecture

### A. Public API Exports Verification
Programmatically audited `evaluation/__all__` against `evaluation` package exports:
1. `CanonicalXAIExplanation`
2. `ExplanationMode`
3. `ExplanationLevel`
4. `DriverCategory`
5. `DriverDirection`
6. `UncertaintySource`
7. `HistoricalEvidenceAlignment`
8. `FeatureRiskDriver`
9. `UncertaintyExplanation`
10. `NoveltyExplanation`
11. `HistoricalEvidenceExplanation`
12. `EvidenceConflictItem`
13. `TemporalDynamicsExplanation`
14. `DecisionRationale`
15. `DecisionCounterfactual`
16. `XAIAttributionEngine`
17. `DecisionCounterfactualGenerator`
18. `XAIRenderer`
19. `ExplainableForecastEngine`

### B. Dual Mode Verification Payload Governance Architecture
- **`DECISION_TIME` Mode**: Strictly rejects all verification/target columns (`truth_value`, `forecast_error`, `forecast_abs_error`, `ensemble_mean_error`, `ensemble_mean_abs_error`, `bust_label`, `is_bust`, `bust_label_q95`).
- **`POST_HOC_EVALUATION` Mode**: Structurally isolates verification columns from input payloads at the engine boundary. Sanitized features are passed to model inference, attribution, uncertainty decomposition, and decision logic. Retrospective verification columns are routed strictly to `post_hoc_verification`.
- **Attribution Isolation Invariant**: `XAIAttributionEngine.compute_risk_drivers()` retains its own strict contract check (`validate_feature_contract`), ensuring that verification columns can never be attributed as model risk drivers under any circumstances.
- **Provenance Invariance Invariant**: Changes to retrospective truth values preserve identical scientific `decision_provenance_hash` values while updating `provenance_hash`.

---

## 7. Comprehensive Test Suite Results

```
================================================================================
FINAL DAY 17 HARDENED VALIDATION SUITE:
================================================================================
1. Day 17 XAI Test Suite:
   - Command: python -m pytest tests/test_day17_xai_explainability.py -v
   - Result:  48 passed in 1.42s

2. Days 14–16 Hardened Subsuite:
   - Command: python -m pytest tests/test_day16_temporal_early_warning.py tests/test_day15_decision_engine.py tests/test_day14_uncertainty_attribution.py -q
   - Result:  107 passed in 2.55s

3. Full Builder 2 Regression Suite:
   - Command: python -m pytest tests/ -q
   - Result:  328 passed in 21.30s across all 23 test files

4. Live Server & Phase 2 Smoke Tests:
   - Command: python -m pytest tests/test_smoke.py tests/test_phase2_smoke.py -q
   - Result:  2 passed in 10.28s

5. Git Boundary & Hygiene Checks:
   - git diff --check: CLEAN (0 errors)
   - Tracked binary artifacts (.parquet, .joblib, .pkl, .grib, .nc): 0
   - Builder 1 boundary (launch.bat, server.py, static/, api/routes.py): 100% UNTOUCHED
   - Production model weights (models/day4/*): 100% UNTOUCHED
================================================================================
```

---

## 8. Final Scientific Release Verdict

# **`A. ENGINEERINGALLY VERIFIED & EMPIRICALLY CHARACTERIZED — SAFE TO COMMIT`**

*(All XAI modules execute deterministically for identical canonical inputs and configuration without external LLM dependencies, feature attributions and counterfactuals are strictly governed and non-causal, decision-time verification leakage is rigorously blocked, post-hoc verification payloads are structurally isolated from attribution, dual provenance hashing cleanly separates scientific decision invariance from execution auditability, multi-level renderers produce structured Level 1/2/3 explanations, all 328 regression tests pass with zero regressions, Builder 1 boundary is untouched, and zero binary artifacts are tracked.)*
