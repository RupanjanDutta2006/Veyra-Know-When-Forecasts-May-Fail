# Veyra — Phase 2 Day 15: Operational Forecast-Risk Decision Engine Final Forensic Report

**Document**: Operational Forecast-Risk Decision Engine, Expected Loss Formulation, Policy Governance, Population Base-Rate Audit & Action Matrix Reconciliation
**System**: Veyra — Know When Forecasts May Fail (Forecast-Bust Sentinel)
**Role**: Builder 2 (Meteorological Risk & Machine Learning Intelligence)
**Milestone**: Day 15 Final Hardened Scientific Release Candidate
**Status**: **ACTIVE SCIENTIFIC STANDARD (DAY 15 RELEASE CANDIDATE)**

---

## 1. Executive Summary & Scientific Purpose

Day 15 elevates Veyra from an ML uncertainty/attribution estimator into a **principled Operational Forecast-Risk Decision Engine**.

In operational meteorological risk management, predicting an raw failure probability $P(\text{bust})$ is only the first step. Decision-makers must determine whether to **trust the forecast**, **monitor atmospheric stability**, **issue cautionary operational advisories**, **escalate to critical warnings**, or **abstain** when evidence is corrupted, contradictory, or out-of-distribution.

```
+----------------------------------------------------------------------------------------------------+
| SCIENTIFIC GUARANTEES & HARDENED INNOVATIONS:                                                      |
| 1. Principled Expected Loss Decision Theory: Action selection minimizes expected loss E[L(a)]      |
|    incorporating asymmetric miss penalties (C_FN = 2.5), false alarm costs (C_FP = 1.0), and       |
|    alert fatigue overhead (lambda_fatigue = 0.12).                                                 |
| 2. Explicit Parameter Governance: Every threshold is classified into:                              |
|    - EMPIRICALLY_ESTIMATED (e.g. Manifold percentiles p75=0.63, p90=0.93, p99=1.43, p99.5=1.67)   |
|    - VALIDATED_FROM_HISTORICAL_DATA (e.g. Calibrated risk tiers: 0.10, 0.22, 0.40, 0.65)           |
|    - OPERATIONAL_POLICY_PARAMETER (e.g. Cost ratio C_FN/C_FP = 2.5, Fatigue penalty = 0.12)        |
|    - DEFAULT_CONFIGURABLE_ASSUMPTION (e.g. 50% missingness ceiling; 2.80 novelty ceiling)         |
| 3. Safety-Critical Abstention ("I Don't Know"): Mandatory abstention on severe novelty,          |
|    excessive missingness (>50%), pathological inputs, or irreconcilable evidence conflict.        |
| 4. Multi-Source Evidence Fusion: Fuses calibrated probability, ensemble spread, revision          |
|    instability, OOD novelty, analogues, and regime profiles into supporting/contradicting sets.   |
| 5. Evidence Conflict Quantification: Divergence between independent sources penalizes confidence.  |
| 6. Monotonicity Guarantees: Mathematically enforced d(RiskScore)/d(P) >= 0 and                     |
|    d(Confidence)/d(Novelty) <= 0.                                                                 |
| 7. Threshold Perturbation Stability: Evaluated across +/-10% and +/-20% parameter shifts,         |
|    achieving 88.05% empirical decision stability on held-out test data.                           |
| 8. Full Precision Accounting: All monetary calculations are performed at full precision;          |
|    displayed currency totals use Decimal ROUND_HALF_UP to two decimal places.                     |
| 9. Full Adversarial Verification: 42 Day 15 tests; 238 full regression tests passing.             |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Mathematical Decision Framework: Expected Loss Formulation

Rather than applying arbitrary heuristic if-else statements, `RiskDecisionPolicy` implements formal Bayesian expected loss minimization across operational actions:

Let $y \in \{0, 1\}$ be the true forecast bust outcome and $P = P(\text{bust} \mid \text{evidence})$.
For candidate action $a \in \{\text{TRUST\_FORECAST}, \text{MONITOR}, \text{ADVISE\_CAUTION}, \text{WARN\_POTENTIAL\_BUST}, \text{ALERT\_CRITICAL\_BUST}, \text{ABSTAIN}\}$:

$$\mathbb{E}[\mathcal{L}(a \mid P)] = P \cdot \mathcal{L}(a \mid y=1) + (1 - P) \cdot \mathcal{L}(a \mid y=0) + \mathcal{C}_{\text{fatigue}}(a) + \mathcal{C}_{\text{confidence}}(a, \text{confidence})$$

### Explicit Action Loss Matrices:
1. **If Forecast Bust Occurs ($y=1$)**:
   - `TRUST_FORECAST`: Unwarned severe miss loss $= C_{\text{FN}} \cdot 1.0 = 2.50$
   - `MONITOR`: Delayed response loss $= C_{\text{FN}} \cdot 0.65 = 1.625$
   - `ADVISE_CAUTION`: Partial mitigation loss $= C_{\text{FN}} \cdot 0.35 = 0.875$
   - `WARN_POTENTIAL_BUST`: Effective warning loss $= C_{\text{FN}} \cdot 0.10 + \lambda_{\text{fatigue}} \cdot 1.0 = 0.25 + 0.12 = 0.37$
   - `ALERT_CRITICAL_BUST`: Optimal early warning $= \lambda_{\text{fatigue}} \cdot 1.5 = 0.18$
   - `ABSTAIN`: Unclassified exposure loss $= C_{\text{FN}} \cdot 0.45 = 1.125$

2. **If No Forecast Bust Occurs ($y=0$)**:
   - `TRUST_FORECAST`: Zero false alarm cost $= 0.00$
   - `MONITOR`: Minimal logging overhead $= C_{\text{FP}} \cdot 0.05 + \lambda_{\text{fatigue}} \cdot 0.25 = 0.05 + 0.03 = 0.08$
   - `ADVISE_CAUTION`: Minor operational review $= C_{\text{FP}} \cdot 0.20 + \lambda_{\text{fatigue}} \cdot 0.50 = 0.20 + 0.06 = 0.26$
   - `WARN_POTENTIAL_BUST`: Moderate false alarm disruption $= C_{\text{FP}} \cdot 0.60 + \lambda_{\text{fatigue}} \cdot 1.0 = 0.60 + 0.12 = 0.72$
   - `ALERT_CRITICAL_BUST`: High false alarm cost $= C_{\text{FP}} \cdot 1.00 + \lambda_{\text{fatigue}} \cdot 1.5 = 1.00 + 0.18 = 1.18$
   - `ABSTAIN`: Manual meteorological review overhead $= C_{\text{FP}} \cdot 0.15 = 0.15$

---

## 3. Scientific Parameter Governance Registry

Every policy parameter and threshold in Veyra is explicitly classified and traceable:

| Parameter Name | Value | Governance Classification | Scientific Origin / Justification |
|---|---|---|---|
| **`fn_cost_weight`** | `2.50` | `OPERATIONAL_POLICY_PARAMETER` | Asymmetric loss penalty for missed forecast bust relative to false alarm. |
| **`fp_cost_weight`** | `1.00` | `OPERATIONAL_POLICY_PARAMETER` | Normalized unit operational baseline cost. |
| **`alert_fatigue_penalty`** | `0.12` | `OPERATIONAL_POLICY_PARAMETER` | Operational penalty suppressing high-frequency false alerts in marginal regimes. |
| **`critical_threshold`** | `0.65` | `VALIDATED_FROM_HISTORICAL_DATA` | Composite risk score calibrated to capture top $1\%$ empirical bust severity. |
| **`high_threshold`** | `0.40` | `VALIDATED_FROM_HISTORICAL_DATA` | Calibrated to capture top $5\%$ empirical bust severity. |
| **`elevated_threshold`** | `0.22` | `VALIDATED_FROM_HISTORICAL_DATA` | Calibrated to capture top $10\%$ empirical bust severity ($>3.2\times$ climatology). |
| **`watch_threshold`** | `0.10` | `VALIDATED_FROM_HISTORICAL_DATA` | Calibrated to capture top $25\%$ empirical bust severity ($>1.5\times$ climatology). |
| **`abstention_max_novelty_distance`** | `2.80` | `DEFAULT_CONFIGURABLE_ASSUMPTION` | Conservative operational ceiling informed by empirical training-manifold scaling (well beyond measured $p_{99.9} = 1.95$). |
| **`abstention_max_missing_fraction`** | `0.50` | `DEFAULT_CONFIGURABLE_ASSUMPTION` | Conservative engineering ceiling ($50\%$ input feature completeness required). |

---

## 4. Multi-Source Evidence Fusion & Contradiction Handling

`EvidenceFusionEngine` evaluates diagnostic inputs into **Supporting Evidence** (risk-increasing) and **Contradicting Evidence** (risk-decreasing):

1. **Probability Model Evidence**: Derived from raw and calibrated bust likelihood ($P_{\text{eff}} = \max(P_{\text{raw}}, P_{\text{cal}})$).
2. **Ensemble Dispersion Evidence**: Evaluates GEFS ensemble spread against physical scale thresholds ($3.5^\circ\text{C}$ temperature, $4.0\text{ hPa}$ pressure, $8.0\text{ km/h}$ wind).
3. **Dynamic Revision Instability**: Quantifies 6h and 24h forecast trajectory shifts across synoptic initializations.
4. **Historical Analogue Support**: Non-parametric top-$k$ nearest neighbour empirical verification failure rates from $D_{\text{train}}$.
5. **Lead Time Horizon Context**: Explicit non-linear atmospheric error growth scaling across 0–72h horizons.
6. **Feature Novelty / OOD State**: Robust median/IQR manifold distance percentiles ($p_{75}=0.63, p_{90}=0.93, p_{99}=1.43, p_{99.5}=1.67$).

---

## 5. Safety-Critical Abstention ("I Don't Know") Framework

`AbstentionController` enforces explicit, safety-critical gates preventing automated overconfidence:

| Trigger Condition | Criterion | Operational Action & Reason |
|---|---|---|
| **Non-Finite Probability** | $P = \text{NaN}, \pm\infty$ or $P < 0, P > 1$ | `ABSTAIN`: *"Pathological non-finite or out-of-bounds probability value."* |
| **Data Corruption** | Verification target columns or non-finite inputs | `ABSTAIN`: *"Input feature data is corrupted (non-finite or forbidden columns)."* |
| **Excessive Missingness** | Missing feature fraction $\ge 50\%$ | `ABSTAIN`: *"Excessive missing features (>50% missing; threshold=50%)."* |
| **Extreme OOD Novelty** | Robust manifold distance $z \ge 2.80$ | `ABSTAIN`: *"Extreme feature novelty indicates conditions far outside training distribution."* |
| **Severe Evidence Conflict** | $S_{\text{conflict}} \ge 0.70$ with low analogue consensus | `ABSTAIN`: *"Severe evidentiary contradiction detected with insufficient consensus."* |
| **Novel Unmonitored Station** | Unseen location with high atmospheric novelty | `ABSTAIN`: *"Unseen geographic monitoring station exhibiting high atmospheric novelty."* |

---

## 6. Threshold Perturbation Sensitivity & Stability Analysis

`ThresholdSensitivityAnalyzer` evaluates decision stability under $\pm 10\%$ and $\pm 20\%$ parameter shifts on real held-out test data:

| Parameter Perturbation | Switched Decisions | Switch Rate | Stability Score | Status |
|---|---|---|---|---|
| **$-20\%$ Threshold Shift** | 261 / 1,500 | $17.40\%$ | $82.60\%$ | Robust |
| **$-10\%$ Threshold Shift** | 98 / 1,500 | $6.53\%$ | $93.47\%$ | Highly Stable |
| **$+10\%$ Threshold Shift** | 81 / 1,500 | $5.40\%$ | $94.60\%$ | Highly Stable |
| **$+20\%$ Threshold Shift** | 277 / 1,500 | $18.47\%$ | $81.53\%$ | Robust |
| **Mean Robustness Score** | — | — | **`88.05%`** | **`ROBUST`** |

---

## 7. Real-Data Action Matrices, Population Provenance & Cost Accounting

All monetary calculations are performed at full precision; displayed currency totals use Decimal `ROUND_HALF_UP` to two decimal places.

### A. Full Stage B Historical Archive ($N=35,040$):
* **Path**: `data/historical/multicycle_paired/paired_multicycle_stage_b_2026-08-18_2026-08-24.parquet`
* **Scope**: 35,040 rows across 20 municipal stations and 3 variables (11,680 rows each).
* **Overall Archive Bust Prevalence**: Exactly 2,389 verified busts (**`6.82%`**).

---

### B. Synoptic Onset Pressure Evaluation Slice ($N=2,000$):
* **Selection Rule**: First 100 chronological forecast records per municipal station (100 $\times$ 20).
* **Scope**: August 20 00z to August 21 12z (captures active monsoon convective onset on `surface_pressure`).
* **True Busts**: 194 ($9.70\%$) | **True Non-Busts**: 1,806 ($90.30\%$)

#### Exact Action × Outcome Matrix:
| Operational Decision | True Bust ($y=1$) | True Non-Bust ($y=0$) | Total Decisions |
|---|---|---|---|
| `TRUST_FORECAST` | 0 | 0 | 0 |
| `MONITOR` | 0 | 100 | 100 |
| `ADVISE_CAUTION` | 111 | 1,689 | 1,800 |
| `WARN_POTENTIAL_BUST` | 83 | 0 | 83 |
| `ALERT_CRITICAL_BUST` | 0 | 0 | 0 |
| `ABSTAIN` | 0 | 17 | 17 |
| **TOTAL** | **194** | **1,806** | **2,000** |

#### Exact Metric & Cost Reconciliation ($N=2,000$):
* **Total Busts**: 194 (Non-Abstained: 194, Abstained: 0).
* **Warnings Issued**: 83 ($\text{TP}=83, \text{FP}=0$).
* **Warning Precision**: $83 / 83 = \mathbf{100.00\%}$.
* **Overall Recall (over all 194 busts)**: $83 / 194 = \mathbf{42.78\%}$.
* **Conditional Recall (over 194 non-abstained busts)**: $83 / 194 = \mathbf{42.78\%}$.
* **Overall Miss Rate**: $111 / 194 = \mathbf{57.22\%}$.
* **Abstention Rate**: $17 / 2,000 = \mathbf{0.85\%}$ (all 17 were non-busts).
* **Always-Trust / Climatology Baseline Cost**: $194 \times 2.50 = \mathbf{\$485.00}$.
* **Day 15 Direct Bust Loss**: $83 \times 0.37 + 111 \times 0.875 = 30.71 + 97.125 = 127.835 \implies \mathbf{\$127.84}$ (**$73.64\%$ direct damage reduction**).
* **Day 15 Non-Bust Surveillance Overhead**: $100 \times 0.08 + 1,689 \times 0.26 = 8.00 + 439.14 = \mathbf{\$447.14}$.
* **Day 15 Abstention Cost**: $17 \times 0.15 = \mathbf{\$2.55}$.
* **Day 15 Total Accounting Cost**: $127.835 + 447.14 + 2.55 = 577.525 \implies \mathbf{\$577.53}$ (via Decimal `ROUND_HALF_UP`).

---

### C. Balanced Multi-Variable Evaluation Slice ($N=2,400$):
* **Selection Rule**: Exactly 40 records per variable per station (20 stations $\times$ 3 variables $\times$ 40 runs).
* **Scope**: 800 `surface_pressure`, 800 `temperature_2m`, 800 `wind_speed_10m`.
* **True Busts**: 162 ($6.75\%$, matching the full archive base rate of $6.82\%$) | **True Non-Busts**: 2,238 ($93.25\%$).

#### Exact Action × Outcome Matrix:
| Operational Decision | True Bust ($y=1$) | True Non-Bust ($y=0$) | Total Decisions |
|---|---|---|---|
| `TRUST_FORECAST` | 0 | 0 | 0 |
| `MONITOR` | 0 | 124 | 124 |
| `ADVISE_CAUTION` | 94 | 1,838 | 1,932 |
| `WARN_POTENTIAL_BUST` | 57 | 36 | 93 |
| `ALERT_CRITICAL_BUST` | 0 | 0 | 0 |
| `ABSTAIN` | 11 | 240 | 251 |
| **TOTAL** | **162** | **2,238** | **2,400** |

#### Exact Metric & Cost Reconciliation ($N=2,400$):
* **Total Busts**: 162 (Non-Abstained: 151, Abstained: 11).
* **Total Non-Busts**: 2,238 (Non-Abstained: 1,998, Abstained: 240).
* **Total Abstentions**: 251 ($10.46\%$ abstention rate).
* **Warnings Issued**: 93 ($\text{TP}=57, \text{FP}=36$).
* **Warning Precision**: $57 / 93 = \mathbf{61.29\%}$.
* **Overall Recall (over all 162 busts)**: $57 / 162 = \mathbf{35.19\%}$.
* **Conditional Recall (over 151 non-abstained evaluable busts)**: $57 / 151 = \mathbf{37.75\%}$.
* **Overall Miss Rate (over all 162 busts)**: $(94 + 11) / 162 = 105 / 162 = \mathbf{64.81\%}$.
* **Conditional Miss Rate (over 151 non-abstained busts)**: $94 / 151 = \mathbf{62.25\%}$.
* **Alert Rate**: $93 / 2,400 = \mathbf{3.88\%}$.
* **Always-Trust / Climatology Baseline Cost**: $162 \times 2.50 = \mathbf{\$405.00}$.
* **Day 15 Direct Bust Loss**: $57 \times 0.37 + 94 \times 0.875 = 21.09 + 82.25 = \mathbf{\$103.34}$ (**$74.48\%$ direct damage reduction**).
* **Day 15 Non-Bust Surveillance Overhead**: $124 \times 0.08 + 1,838 \times 0.26 + 36 \times 0.72 = 9.92 + 477.88 + 25.92 = \mathbf{\$513.72}$.
* **Day 15 Abstention Cost**: $11 \times 1.125 + 240 \times 0.15 = 12.375 + 36.00 = 48.375 \implies \mathbf{\$48.38}$ (via Decimal `ROUND_HALF_UP`).
* **Day 15 Total Accounting Cost**: $103.34 + 513.72 + 48.375 = 665.435 \implies \mathbf{\$665.44}$ (via Decimal `ROUND_HALF_UP`).

---

## 8. Definitive Scientific Statement on Operational Economics

> [!IMPORTANT]
> **Definitive Economic Distinctions**:
> 1. **Direct Bust Damage Mitigation ($73.64\%$ on synoptic, $74.48\%$ on multi-variable)**:
>    Day 15 dramatically reduces direct losses from catastrophic unwarned forecast failures ($\$127.84$ vs $\$485.00$ on synoptic; $\$103.34$ vs $\$405.00$ on multi-variable).
> 2. **Total Accounting Cost ($577.53 vs $485.00 on synoptic; $665.44 vs $405.00 on multi-variable)**:
>    Under a normalized loss model that assigns non-zero operational overhead ($\$0.26$ per run) to active advisory readiness on non-bust days, Day 15 incurs a higher aggregate accounting sum than a passive Always-Trust baseline that performs zero surveillance. Day 15 is **not claimed to be economically cheaper in raw accounting sum**.

---

## 9. Full Regression Suite Results

### A. Day 15 Hardened Test Suite
Execution: `python -m pytest tests/test_day15_decision_engine.py -v`
Result: **`42 passed in 3.59s`**

### B. Full Builder 2 Regression Suite
Execution: `python -m pytest tests/ -q`
Result: **`238 passed in 28.33s` across all 21 test files** ($196 + 42 = 238$).

### C. Live Smoke Tests
Execution: `python -m pytest tests/test_smoke.py tests/test_phase2_smoke.py -q`
Result: **`2 passed in 13.44s`**

---

## 10. Forensic Audit Summary & Readiness Verdict

* **Code Verification**: All Day 15 modules verified clean, typed, and mathematically sound.
* **Leakage Gate**: 0 verification-column leakages.
* **Tracked Binaries**: 0 scientific binary artifacts in Git.
* **Builder 1 Boundary**: `launch.bat`, `server.py`, `static/`, `api/routes.py` **100% untouched**.
* **Production Weights**: `models/day4/*` **100% untouched**.
* **Verdict**: **`A. SCIENTIFICALLY VERIFIED — SAFE TO COMMIT`**
