# Day 36: Dashboard Parity & Explanation Coherence

## Executive Summary

Day 36 establishes full **Dashboard Parity & Explanation Coherence** across Veyra's user-facing frontend dashboard and backend scientific contracts. It verifies that all visual representations, metrics, labels, tooltips, risk bands, certification badges, distribution diagnostics, explanation summaries, and revision trajectory views accurately reflect underlying backend Pydantic contracts without introducing uncertified claims or misleading terminology.

---

## 1. Scientific Parity Matrix

| Component / Metric | Backend Contract | Frontend Type & Value | Display Label | Governance & Wording Contract |
| :--- | :--- | :--- | :--- | :--- |
| **P(BUST)** | Calibrated probability $P(\text{BUST})$ from Isotonic Regression | `bust_probability: number \| null` | `Calibrated Bust Probability` | Calibrated probability that an already-issued forecast fails under stratum-specific $q_{95}$ threshold. **Never** labeled as rain/weather probability. |
| **Risk Band** | `LOW` ($< 0.20$), `MEDIUM` ($0.20\text{--}0.50$), `HIGH` ($0.50\text{--}0.75$), `CRITICAL` ($\ge 0.75$) | `risk_level: RiskLevel \| null` | `Risk: LOW / MEDIUM / HIGH / CRITICAL` | Operational risk band indicating probability threshold. **Never** labeled as weather severity. |
| **Certification (Gate C1)** | `evaluate_scientific_certification()` | `certification: ScientificCertificationResult` | `CERTIFIED EVIDENCE SCOPE` / `OUTSIDE CERTIFIED EVIDENCE SCOPE` | Evidence boundary derived from 25 synoptic stations, 3 surface variables, $\le 240\text{h}$ lead. **Never** implies forecast correctness or safety. |
| **OOD Diagnostic (Gate C2)** | `evaluate_ood_policy()` | `ood_diagnostics: OODDiagnosticResult` | `IN DISTRIBUTION` / `OUT OF DISTRIBUTION` | Parameter support diagnostic derived from 20-year NOAA GEFS. `causes_abstention = false`. **Never** forces pipeline abstention. |
| **Certainty Index** | $2 \cdot \|P(\text{BUST}) - 0.5\|$ | `confidence_index: number \| null` | `Certainty: XX.X%` | Distance from decision boundary ambiguity ($0.5$). Tooltip explicitly clarifies this is a heuristic score, **not** a Bayesian confidence interval. |
| **Decision Ambiguity** | $(1.0 - 2 \cdot \|P(\text{BUST}) - 0.5\|) \cdot 100$ | `uncertainty_pct: number \| null` | `Ambiguity: XX.X%` | Decision boundary ambiguity. Tooltip explicitly clarifies this is **not** a predictive error interval. |
| **GEFS Disagreement** | Ensemble member dispersion | `ForecastDisagreementResponse` | `Ensemble Member Dispersion` | Measures spread across 31 GEFS ensemble members (°C, m/s, hPa). Labeled as **ensemble-member dispersion**, not multi-model disagreement or weather chaos. |
| **Revision Trajectory** | `RevisionStore` SQLite WAL database | `ForecastRevisionResponse` | `Forecast Revision Trajectory` | When no prior issue cycle exists, displays `History Unavailable` / `INSUFFICIENT_HISTORY`. **Never** renders synthetic line segments or fake zero deltas. |
| **Lead Horizon Scope** | `derive_and_validate_lead_hours()` | `lead_hours: number` | `24h` to `240h` (Certified) vs `264h` to `384h` (Extended) | Distinguishes $\le 240\text{h}$ frozen certified horizon from $264\text{h}\text{--}384\text{h}$ extended operational horizon. |
| **Model Provenance** | `get_authoritative_v3_provenance()` | `model_provenance: ModelProvenanceInfo` | `LightGBM V3 Challenger` | Displays Model SHA-256 (`00a84107...`), Calibrator SHA-256 (`9f448606...`), 50 features, `IsotonicRegression`. |

---

## 2. Key Wording & Coherence Rules

1. **P(BUST) Semantics**: P(BUST) measures forecast bust/failure probability. It is never described as "probability of precipitation", "storm probability", or "weather forecast confidence".
2. **Operational Risk Bands**: Operational risk bands (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) represent bust risk thresholds ($0.20$, $0.50$, $0.75$). They do not indicate weather event severity.
3. **Scientific Certification Scope**: Gate C1 certification indicates that the query falls inside the frozen 25-station, 3-variable, $\le 240\text{h}$ benchmark evidence boundary. It is never conflated with low bust probability or guaranteed forecast accuracy.
4. **Out-of-Distribution Policy**: Gate C2 OOD status assesses parameter support against 20-year NOAA GEFS historical bounds. OOD detection is diagnostic-only and does not force pipeline abstention.
5. **Physical Explainability**: Explanations highlight feature signals derived from LightGBM prediction contributions (`pred_contrib=True`) and physical domain heuristics without claiming unverified TreeSHAP coverage.
6. **Revision Trajectory Honesty**: If no durable prior issue cycle exists in the SQLite revision store, the UI honestly renders `History Unavailable` without drawing synthetic line segments.

---

## 3. Verification Results

- **Day 36 Focused Test Suite**: `20 / 20` passed (`backend/tests/test_day36_dashboard_parity_explanation_coherence.py`).
- **Targeted Cross-Day Suite**: `143 / 143` passed (Days 30, 32, 33, 34, 35, 36, V3 Integrity).
- **Full Backend Suite**: `644 / 644` passed.
- **Frontend Test Suite**: `100 / 100` passed (`vitest`).
- **Production Build**: `PASS` (`tsc && vite build` completed cleanly).
- **Artifact Hashes**:
  - Model SHA256: `00a8410746f4a0eecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660`
  - Calibrator SHA256: `9f448606ce4338ded92f238a551b3a9d8e6d2cb5902e8bc687bce5f5850af531`

---

## 4. Scientific Limitations

1. **Station Boundaries**: Frozen certification is limited to 25 synoptic stations. Locations such as Patna, Dispur, Gangtok, Shillong, Varanasi, and Vijayawada remain outside frozen certification.
2. **Horizon Boundaries**: Lead horizons beyond 240h (264h–384h) operate as extended operational forecasts outside frozen certification.
3. **Revision History**: Durable revision trajectories require multiple real issue cycles in the SQLite revision store. Initial queries honestly show `History Unavailable`.
