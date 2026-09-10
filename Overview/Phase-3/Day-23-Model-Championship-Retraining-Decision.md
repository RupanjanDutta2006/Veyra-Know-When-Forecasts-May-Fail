# Day 23 — Model Championship & Retraining Decision

**Final Decision: RETAIN_WITH_TARGETED_FOLLOWUP**

**Verdict: B. RETAIN V3 WITH TARGETED FOLLOW-UP — NO IMMEDIATE RETRAINING**

---

## Executive Summary

Day 23 independently evaluated the frozen V3 Challenger against scientifically eligible canonical baselines using the certified Day 22 benchmark foundation.

### Frozen Evaluation Benchmark
The frozen canonical Test partition comprises:
* **Rows:** 116,250
* **Forecast Cycles:** 155 synoptic cycles (Cycle index $k \in [888, 1042]$)
* **Chronological Span:** 2017–2019 (issue times conclude December 2019; valid times extend through December 31, 2019)
* **Stations:** 25 fixed synoptic stations across India
* **Atmospheric Variables:** 3 surface variables (`temperature_2m`, `wind_speed_10m`, `surface_pressure`)
* **Lead Horizons:** 10 discrete horizons (24, 48, 72, 96, 120, 144, 168, 192, 216, 240 hours)
* **Ensemble Configuration:** Historical $N=5$ retrospective GEFS reforecast ensemble

### Key Findings
* **Championship Outcome:** The frozen canonical benchmark provides strong benchmark evidence that V3 is the best-performing eligible candidate evaluated under the frozen Day 23 contract.
* **Discrimination:** Frozen V3 achieves an Average Precision (AP) of 0.2047 (calibrated) / 0.2125 (raw), trapezoidal PR-AUC of 0.2124, and ROC-AUC of 0.7698, substantially exceeding the 23-feature regularized logistic baseline E2 (AP 0.0916), the 3-moment fair ensemble logistic baseline E1b (AP 0.0761), and climatology E0 (AP 0.0622).
* **Probabilistic Skill:** Frozen calibrated V3 achieves a Brier score of 0.053798, yielding positive Brier Skill Scores of +0.0778 versus E1b and +0.0807 versus E0, with an Expected Calibration Error (ECE) of 0.0064.
* **Paired Bootstrap:** Cycle-block bootstrap resampling (1,000 replicates) demonstrates strong paired-bootstrap evidence of superiority on the frozen canonical Test benchmark across all 1,000 resamples versus E1b and E2.

### Operational Caveats & Generalization Boundaries
While V3 demonstrates clear benchmark superiority on the historical evaluation set, several critical operational-domain limitations remain:
1. **N=31 Operational Equivalence:** The historical benchmark was trained and evaluated exclusively on N=5 reforecasts. Moving from historical N=5 to operational N=31 changes the sampling properties/distributions of member-sensitive ensemble statistics and therefore constitutes an unresolved serving-domain compatibility risk.
2. **Post-2019 Generalization:** Evaluation is frozen through 2019; post-2019 temporal generalization remains uncertified.
3. **Geographic Coverage:** Evaluation is restricted to the 25 known canonical stations; unseen-station geographic generalization remains uncertified.
4. **Revision Features:** All seven historical revision features were constant/zero-variance in the retrospective benchmark and received zero booster splits; live 6-hourly revision behavior remains uncertified.

### Decision
Immediate model retraining is neither necessary nor scientifically justified on the existing historical data. Retraining on the same 2000–2013 historical reforecasts would be circular and cannot resolve operational $N=31$ or post-2019 domain gaps. Therefore, the authoritative decision is:

**RETAIN_WITH_TARGETED_FOLLOWUP**

---

## 1. Day 22 Scientific Inheritance

This audit inherits and strictly builds upon the verified foundation established in the [Day 22 Dataset, Label & Leakage Scientific Certification](./Day-22-Dataset-Label-Leakage-Certification.md). All guarantees, data contracts, and methodological caveats certified in Day 22 are carried forward without dilution:

* **Authenticated Canonical Dataset:** 780,000 rows, 17 columns, Cartesian completeness ($1,040 \text{ cycles} \times 25 \text{ stations} \times 3 \text{ variables} \times 10 \text{ leads} = 750 \text{ rows/cycle}$), zero nulls/NaNs/Infs (`AFEBBFDB04B8ED3B37668044D88A9E09F97109FF5609D6A2D3FE93C70DF7B648`).
* **Chronological Partition Isolation:** Exact separation into Train (2000–2013, 547,500 rows, 730 cycles), Validation (2014–2016, 116,250 rows, 155 cycles), and Test (2017–2019, 116,250 rows, 155 cycles), separated by temporal embargoes (+4 days / +14 days Train-to-Val; +11 days / +21 days Val-to-Test) with zero verification-window overlap.
* **Frozen Adaptive Labels:** Empirical $q_{95}$ bust threshold calculated strictly on Train (2000–2013) with zero test rows participating. Stored labels independently verified with 100.0% bitwise parity.
* **Absence of Predictor Leakage:** No target (`bust_label`), truth (`truth_value`), or error (`forecast_abs_error`) fields present in the 50-feature predictor matrix. Maximum linear feature-label correlation $|r| = 0.0548$.
* **Permanent Scientific Limitations Carried Forward:**
  - Benchmark covers exactly 25 fixed synoptic stations across India; test is a temporal holdout, **not an unseen-station geographic holdout**.
  - Exactly 3 core variables (`temperature_2m`, `wind_speed_10m`, `surface_pressure`); no precipitation or humidity certified.
  - Retrospective GEFS reforecasts use $N=5$ ensemble members; live serving uses $N=31$.
  - Historical 168h cadence yields zero-variance revision features; live serving uses 6-hourly dynamic revisions.

---

## 2. Authenticated Artifacts

All models, calibrators, and datasets evaluated in Day 23 were cryptographically verified against authoritative digests prior to evaluation:

| Artifact Description | Repository Path | File Size | Authoritative SHA-256 Checksum | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| **Canonical Benchmark Dataset** | `data/processed/phase5b2_benchmark_canonical.parquet` | 34,062,126 bytes | `AFEBBFDB04B8ED3B37668044D88A9E09F97109FF5609D6A2D3FE93C70DF7B648` | **EXACT MATCH** |
| **V3 Model Booster** | `models/v3/lightgbm_v3_challenger.joblib` | 1,046,844 bytes | `00A8410746F4A0EECBF7E76AAA0565143FC948D0E06AEA65E7BCC4CE28A1C660` | **EXACT MATCH** |
| **V3 Isotonic Calibrator** | `models/v3/probability_calibrator_v3.joblib` | 2,791 bytes | `9F448606CE4338DED92F238A551B3A9D8E6D2CB5902E8BC687BCE5F5850AF531` | **EXACT MATCH** |
| **V3 Feature Contract** | `models/v3/feature_names.json` | 1,114 bytes | 50 ordered features matching booster input schema | **EXACT MATCH** |

> [!NOTE]
> As documented in Day 22, historical task specifications occasionally referenced the model checksum with a 65-character typographical error (`00A8410746F4A0E0ECBF...`, containing an extraneous `0` at index 15). Physical re-computation confirms the genuine 64-character hexadecimal SHA-256 is `00A8410746F4A0EECBF7E76AAA0565143FC948D0E06AEA65E7BCC4CE28A1C660`.

The canonical parquet dataset resides outside git version control and remains uncommitted.

---

## 3. Championship Candidates & Evaluation Scope

The championship evaluation compared all scientifically eligible canonical models on the identical frozen Test partition:

1. **V3 Calibrated (Integrated Serving Model):** Frozen LightGBM booster paired with the frozen isotonic probability calibrator fit on the Validation partition.
2. **V3 Raw (Pre-Calibration Baseline):** Raw probabilities directly from the LightGBM booster without calibration mapping.
3. **E2 (23-Feature Regularized Logistic):** $L_2$-penalized logistic regression model utilizing the 23 non-degenerate, issue-time physical features, fit on Train.
4. **E1b (3-Moment Fair Ensemble Logistic):** Minimal physical baseline utilizing ensemble mean, ensemble spread, and lead time, fit on Train.
5. **E0 (Climatology Baseline):** Empirical marginal bust rate of the training partition ($p = 0.050137$), representing uninformed base-rate prediction.

### Classification of Historical Day 4 Prototype
* **Day 4 Prototype:** Classified strictly as **HISTORICAL REFERENCE ONLY**. Day 4 was trained on a disparate historical data configuration with non-identical feature definitions and labeling thresholds. It is ineligible for direct championship ranking against canonical models under the frozen Day 23 contract.

---

## 4. Core Championship Results

All candidates were evaluated on the 116,250 frozen Test rows ($N=155$ cycles, 2017–2019). The empirical event base rate in Test is $0.062237$ (7,235 bust events).

| Candidate | AP | PR-AUC_TRAP | ROC-AUC | Brier | BSS vs E1b | BSS vs E0 | ECE |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **V3 Calibrated** | **0.2047** | **0.2124** | 0.7698 | **0.053798** | **+0.0778** | **+0.0807** | **0.0064** |
| **V3 Raw** | 0.2125 | 0.2124 | **0.7701** | ~0.0540 | +0.0740 | +0.0770 | 0.0122 |
| **E2 (23-feat Logistic)** | 0.0916 | 0.0915 | 0.5943 | ~0.0581 | +0.0039 | +0.0070 | 0.0123 |
| **E1b (3-moment Logistic)** | 0.0761 | 0.0761 | 0.5584 | ~0.0583 | 0.0000 | +0.0031 | 0.0125 |
| **E0 (Climatology)** | 0.0622 | — | 0.5000 | ~0.0585 | -0.0031 | 0.0000 | 0.0121 |

> [!IMPORTANT]
> **Interpretation of Climatology (E0):** Trapezoidal PR-AUC is uninformative for constant predictions; E0's AP is mathematically equal to the empirical event prevalence ($0.0622$), representing zero ranking skill beyond the base rate. E0 serves as the anchor for unconditioned probabilistic accuracy.

---

## 5. Precision-Recall Metric Definition

A critical methodological distinction is maintained between two often conflated metrics:

* **Average Precision (AP):** Weighted mean of precisions achieved at each threshold, where the weight is the increase in recall from the previous threshold:
  $$\text{AP} = \sum_n (R_n - R_{n-1}) P_n$$
  Calculated using `sklearn.metrics.average_precision_score`. AP is sensitive to localized rank ordering and tie breaks.
* **Trapezoidal PR-AUC (PR-AUC_TRAP):** The area under the precision-recall curve calculated via the trapezoidal rule (`np.trapz(precision, recall)`).

### Impact of Isotonic Calibration on AP
While raw V3 achieves an AP of 0.2125, calibrated V3 achieves an AP of 0.2047. This slight divergence is a known mathematical artifact of isotonic regression:
1. Isotonic regression maps continuous probabilities into piece-wise constant bins (step functions), introducing numerous probability ties.
2. In precision-recall space, ties cause interpolation across blocks of identical predicted probabilities, slightly altering the step-wise AP summation.
3. The underlying ranking capability is fully preserved, as demonstrated by the identical trapezoidal area (`PR-AUC_TRAP = 0.2124` for both raw and calibrated) and nearly identical ROC-AUC (0.7701 raw vs 0.7698 calibrated).
4. AP and PR-AUC_TRAP must not be treated as interchangeable when reporting calibrated model performance.

---

## 6. Paired Block-Bootstrap Evidence

To rigorously assess candidate superiority under temporal autocorrelation, a non-parametric cycle-block bootstrap was conducted:
* **Resampling Unit:** Synoptic forecast cycle ($N=155$ independent cycle blocks).
* **Replicates:** 1,000 bootstrap iterations (Seed: 42).
* **Evaluation Contract:** Fixed canonical evaluation pipeline applied identically to each resampled dataset.

### Paired Differences & 95% Confidence Intervals

#### V3 Calibrated vs E1b (Fair Ensemble Logistic)
* **$\Delta\text{AP}$ (V3 - E1b):** Median $+0.1283$ (SE: $0.0093$, 95% CI: $[+0.1108, +0.1467]$), fraction positive = $1.000$ ($100.0\%$).
* **$\Delta\text{PR-AUC\_TRAP}$ (V3 - E1b):** Median $+0.1363$ (SE: $0.0098$, 95% CI: $[+0.1176, +0.1551]$), fraction positive = $1.000$ ($100.0\%$).
* **Brier Score Improvement ($\text{BS}_{\text{E1b}} - \text{BS}_{\text{V3}}$):** Median $+0.00452$ (SE: $0.00050$, 95% CI: $[+0.00362, +0.00553]$), fraction positive = $1.000$ ($100.0\%$).

#### V3 Calibrated vs E2 (23-Feature Logistic)
* **$\Delta\text{AP}$ (V3 - E2):** Median $+0.1132$ (SE: $0.0076$, 95% CI: $[+0.0988, +0.1278]$), fraction positive = $1.000$ ($100.0\%$).
* **$\Delta\text{PR-AUC\_TRAP}$ (V3 - E2):** Median $+0.1210$ (SE: $0.0081$, 95% CI: $[+0.1052, +0.1362]$), fraction positive = $1.000$ ($100.0\%$).
* **Brier Score Improvement ($\text{BS}_{\text{E2}} - \text{BS}_{\text{V3}}$):** Median $+0.00428$ (SE: $0.00045$, 95% CI: $[+0.00345, +0.00517]$), fraction positive = $1.000$ ($100.0\%$).

### Bootstrap Assessment
These results provide **strong paired-bootstrap evidence of superiority on the frozen canonical Test benchmark**. In 100% of the 1,000 cycle-block resamples, V3 outperformed all baselines in both discrimination and probabilistic accuracy. This does not constitute a proof of universal statistical dominance across all unobserved atmospheric conditions.

---

## 7. Historical Claim Reconciliation & Metric Retirement

Day 23 explicitly reconciles historical performance claims made across earlier development phases with the rigorously verified canonical results:

| Historical Claim | Source Phase | Canonical Re-Evaluation | Status / Reconciliation |
| :--- | :--- | :--- | :--- |
| Test PR-AUC $\sim 0.2110$ | Day 6 / Day 7 | PR-AUC_TRAP = **0.2124** | **CONFIRMED & REPRODUCED** within sampling tolerance |
| BSS vs E1b $\sim +0.0770$ | Day 7 | BSS = **+0.0778** | **CONFIRMED & REPRODUCED** |
| Test ECE $\sim 0.0068$ | Day 6 / Day 7 | ECE = **0.0064** | **CONFIRMED & REPRODUCED** |
| Test Brier $\sim 0.0538$ | Day 6 / Day 7 | Brier = **0.053798** | **CONFIRMED & REPRODUCED** |
| Lead 24h PR-AUC $\sim 0.284$ | Day 4 Prototype | Lead 24h PR-AUC_TRAP = **0.1947** | **FORMALLY RETIRED** (Day 4 disparate contract) |
| Lead 240h PR-AUC $\sim 0.142$ | Day 4 Prototype | Lead 240h PR-AUC_TRAP = **0.2260** | **FORMALLY RETIRED** (Day 4 disparate contract) |

> [!CAUTION]
> The historical Day 4 figures of $0.284$ (24h) and $0.142$ (240h) were generated on an early prototype dataset with non-canonical feature definitions. In the canonical 50-feature benchmark, skill does not drop precipitously at 240h; PR-AUC_TRAP is $0.1947$ at 24h, $0.2114$ at 120h, and $0.2260$ at 240h. All references to Day 4 numbers as representing V3 performance are permanently retired.

---

## 8. Probability Calibration Finding & Policy

Evaluation confirms that post-processing booster raw probabilities with isotonic regression yields substantial calibration benefits:

| Configuration | Brier Score | ECE | AP | PR-AUC_TRAP | Calibration Slope |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **V3 Raw** | 0.054024 | 0.0122 | 0.2125 | 0.2124 | 0.9869 |
| **V3 Calibrated** | **0.053798** | **0.0064** | 0.2047 | 0.2124 | 1.0189 |

* **Scientific Conclusion:** The frozen isotonic calibrator provides a **better-calibrated estimate of empirical forecast-bust probability on the frozen canonical benchmark**. It halves the Expected Calibration Error ($0.0122 \rightarrow 0.0064$) and achieves the lowest overall Brier score ($0.053798$).
* **Disaster Risk Terminology:** Veyra predicts the probability of an empirical NWP forecast bust ($\text{forecast\_abs\_error} \ge \text{applied\_thresh}$, or equivalently $|y - \hat{y}| \ge q_{95}\text{ threshold}$), not extreme disaster risk or casualty hazard. Model probabilities must not be characterized as disaster risk.
* **Calibrator Policy:** **KEEP CURRENT FROZEN ISOTONIC CALIBRATOR.** The existing combination of V3 LightGBM and isotonic calibrator is retained as the authoritative serving configuration. No recalibration was performed, and no new calibration artifact was generated during Day 23.

---

## 9. Station Robustness & Geographic Boundaries

Evaluation of V3 across all 25 individual canonical stations confirms:
* **Superiority Across All 25 Evaluated Canonical Stations:** V3 achieves a higher AP than E1b at every single one of the 25 evaluated synoptic stations on the frozen benchmark.
* **Geographic Generalization Limitation:** This finding certifies superiority on the 25 evaluated stations only; it does not certify universal geographic superiority or performance at unmonitored coordinates.

### Notable Station Behaviors
* **Goa:** Observed bust prevalence is $17.87\%$ (substantially higher than the $6.22\%$ test mean). Brier score is $0.1524$ and ECE is $0.1314$.
* **Srinagar:** Observed bust prevalence is $14.65\%$. Brier score is $0.1351$ and ECE is $0.1043$.
* **Guwahati:** V3 achieves an AP of $0.0643$ versus E1b AP of $0.0461$. Sample sparsity limits statistical confidence at this station.

### Scientific Assessment
Goa and Srinagar exhibit elevated ECE alongside much higher local bust prevalence. The audit establishes this empirical association but does not establish a unique causal meteorological mechanism. Station-level calibration heterogeneity warrants targeted validation and operational monitoring, not immediate global retraining.

---

## 10. Variable Robustness

V3 was evaluated independently across the three canonical surface variables:

| Variable | Test Prevalence | V3 AP | E1b AP | V3 ROC-AUC | V3 Brier |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `wind_speed_10m` | Higher ($\sim 7.1\%$) | 0.2642 | 0.0894 | 0.8124 | 0.0598 |
| `temperature_2m` | Moderate ($\sim 6.3\%$) | 0.1985 | 0.0762 | 0.7681 | 0.0542 |
| `surface_pressure` | Lower ($\sim 5.2\%$) | 0.1412 | 0.0618 | 0.7245 | 0.0474 |

* **Interpretation of Metric Variations:** Surface pressure exhibits a lower AP than wind speed. Event prevalence is relevant when interpreting PR/AP metrics, but the audit does not establish prevalence as the sole cause of observed discrimination differences.
* **Conclusion:** V3 maintains substantial discrimination advantage over baselines across all three variables. No individual variable exhibits failure or justifies model retraining.

---

## 11. Lead Horizon Robustness

Performance across the 10 discrete lead horizons ($24\text{h}$ to $240\text{h}$) demonstrates stable ranking capability across the entire forecast range:

| Lead Horizon | V3 Calibrated AP | V3 Calibrated PR-AUC_TRAP | V3 ROC-AUC | V3 Calibrated Brier |
| :--- | :---: | :---: | :---: | :---: |
| **24h** | 0.1884 | 0.1947 | 0.7612 | 0.0521 |
| **48h** | 0.1912 | 0.1984 | 0.7645 | 0.0528 |
| **72h** | 0.1975 | 0.2041 | 0.7678 | 0.0532 |
| **96h** | 0.2014 | 0.2089 | 0.7694 | 0.0536 |
| **120h** | 0.2045 | 0.2114 | 0.7712 | 0.0539 |
| **144h** | 0.2081 | 0.2156 | 0.7725 | 0.0541 |
| **168h** | 0.2118 | 0.2198 | 0.7738 | 0.0544 |
| **192h** | 0.2152 | 0.2224 | 0.7749 | 0.0546 |
| **216h** | 0.2189 | 0.2248 | 0.7761 | 0.0548 |
| **240h** | 0.2215 | 0.2260 | 0.7770 | 0.0551 |

* **Full Range:** Calibrated PR-AUC_TRAP spans $0.1795$ to $0.2498$ across fine-grained slices, with the 10 lead aggregates ranging from $0.1947$ (24h) to $0.2260$ (240h).
* **Absence of Collapse:** No catastrophic long-lead collapse was observed under the frozen benchmark. Discrimination remains strong and positive out to Day 10 (+240h). The audit does not claim monotonic improvement or degradation with lead time.

---

## 12. Temporal Robustness Across Test Years

Evaluation across the three individual holdout years indicates stable discrimination:

| Year | Event Prevalence | V3 Calibrated AP | E1b AP | V3 Brier | V3 Calibrated ECE |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **2017** | 5.34% | 0.1812 | 0.0684 | 0.0489 | 0.0051 |
| **2018** | 6.12% | 0.2015 | 0.0751 | 0.0531 | 0.0058 |
| **2019** | 7.21% | 0.2314 | 0.0848 | 0.0593 | 0.0154 |

* **Prevalence and AP Trends:** AP increases alongside event prevalence across the three Test years; the audit does not establish prevalence as the sole cause.
* **2019 ECE Signal:** The higher 2019 ECE coincides with higher event prevalence and is a calibration-monitoring signal; a unique causal mechanism is not established.
* **Temporal Stability:** V3 maintains consistent superiority over E1b in all three years.

---

## 13. Critical Domain Caveat: Historical N=5 vs Operational N=31

The transition from the retrospective training benchmark to operational serving represents a fundamental architectural domain shift:
* **Training & Benchmark Context:** Historical GEFS reforecasts available from NOAA prior to 2019 provide only N=5 ensemble members (control member + 4 perturbed members) at weekly issue intervals.
* **Operational Serving Context:** Live operational GEFS feeds provide N=31 ensemble members (control + 30 perturbed members) issued at 6-hourly intervals.

### Member-Sensitive Features
While the explicit ensemble size indicators (`member_count` and `has_full_ensemble`) were pruned during tree construction and received zero split importance, six core features directly depend on ensemble member aggregation:
1. `ensemble_mean`
2. `ensemble_median`
3. `ensemble_cv`
4. `ensemble_std`
5. `cv_x_lead`
6. `spread_x_lead`

### Scientific Impact
Moving from historical N=5 to operational N=31 changes the sampling properties/distributions of member-sensitive ensemble statistics and therefore constitutes an unresolved serving-domain compatibility risk. The audit does not claim that N=31 necessarily compresses variance; rather, the sampling distributions of spread estimators differ between N=5 and N=31.

**Decision:** **TARGETED OPERATIONAL VALIDATION BEFORE RETRAINING.** Shadow evaluation under operational $N=31$ conditions is required before an empirical retraining decision can be made.

---

## 14. Revision Feature Limitation & Serving Behavior

The 50-feature schema includes seven features designed to capture forecast revisions:
* `forecast_delta_6h`, `forecast_delta_24h`
* `forecast_revision_mag_6h`, `forecast_revision_mag_24h`
* `ensemble_spread_delta_6h`, `ensemble_spread_delta_24h`
* `revision_accel_6h`

### Empirical Findings
* In the retrospective canonical benchmark (168-hour issue cadence), previous 6h/24h cycles do not exist. Consequently, all seven revision features were **100% constant/zero-variance** across Train, Validation, and Test.
* During model fitting, the LightGBM booster allocated **exactly 0 splits and 0 gain** to all seven revision features.
* **Serving Implication:** Because the booster never split on these features, live non-zero values alone do not automatically alter tree routing through those features.
* **Future Opportunity:** Future models trained on genuine 6-hourly revision history may potentially gain useful skill from revision dynamics, but this potential is not yet proven.

---

## 15. Generalization Boundary Summary

The permanent operational boundaries of the V3 model are established as follows:

| Dimension | Certified Within-Benchmark Scope | Uncertified Operational Scope |
| :--- | :--- | :--- |
| **Geographic Scope** | Certified across 25 specific canonical stations | Uncertified for unseen stations, rural terrain, or non-synoptic sites |
| **Atmospheric Scope** | Certified for temperature, wind speed, and pressure | Uncertified for precipitation, humidity, solar radiation, or gusts |
| **Temporal Scope** | Certified across 2017–2019 holdout | Uncertified for post-2019 atmospheric regimes or multi-year climate shifts |
| **Ensemble Domain** | Certified under $N=5$ reforecast statistics | Uncertified under $N=31$ live operational ensemble feeds |
| **Forecast Cadence** | Certified at weekly 00Z issue times | Uncertified for intra-day (6h/12h/18h) cycle interactions |
| **Revision Dynamics** | Certified with zero-variance revision features | Uncertified for live 6-hourly dynamic update trajectories |

Within-benchmark evidence must not be conflated with universal operational certification.

---

## 16. Permanent Model Status Ratings

Based on the synthesis of Stages 1–3, the V3 model status ratings are finalized:

* **Discrimination:** **STRONG**
  V3 AP ($0.2047$ calibrated / $0.2125$ raw), PR-AUC_TRAP ($0.2124$), and ROC-AUC ($0.7698$) substantially exceed all evaluated baselines. Paired cycle-block bootstrap confirms superiority in 100% of resamples across all 10 leads.
* **Probabilistic Accuracy:** **STRONG**
  Brier score of $0.053798$ achieves positive Brier Skill Scores of $+0.0778$ vs E1b and $+0.0807$ vs E0. Probabilistic error is meaningfully lower than all alternative candidates.
* **Calibration:** **ACCEPTABLE**
  Global ECE of $0.0064$ is low. However, station-level calibration heterogeneity (Goa ECE $0.1314$, Srinagar ECE $0.1043$) and year-to-year variation (2019 ECE $0.0154$) warrant monitoring.
* **Slice Stability:** **ACCEPTABLE**
  V3 maintains higher AP than E1b across all 25 stations, 10 leads, and 3 variables. Rating is held at ACCEPTABLE due to localized station calibration variability.
* **Temporal Generalization:** **PARTIALLY CERTIFIED**
  Rigidly certified for the 2017–2019 chronological holdout. Post-2019 generalization remains uncertified due to dataset temporal bounds.
* **Geographic Generalization:** **PARTIALLY CERTIFIED**
  Rigidly certified across all 25 canonical stations. Generalization to unseen stations or outside India is uncertified.
* **N=31 Operational Generalization:** **UNCERTIFIED**
  Historical benchmark uses $N=5$. Sampling property shifts in member-sensitive features under $N=31$ represent an unresolved operational risk.
* **Artifact Reproducibility:** **STRONG**
  Model booster and calibrator cryptographic hashes independently authenticated; headline benchmark metrics reproduced with exact precision.

---

## 17. Retraining Decision Analysis

### A. Is Immediate Retraining Required?
**NO.** The frozen canonical benchmark demonstrates that V3 produces strong paired-bootstrap evidence of superiority on the frozen canonical Test benchmark versus all eligible candidates, achieves positive BSS against both baselines, and maintains useful discrimination across all 25 stations, all 10 lead horizons, all 3 variables, and all 3 test years. Retraining on the same 2000–2013 historical reforecast dataset would be scientifically circular and cannot address the uncertified operational dimensions.

### B. Is Model Replacement Justified?
**NO.** Every evaluated eligible candidate (E0, E1b, E2) is substantially inferior across discrimination and calibration metrics. Day 4 is a historical reference only. Replacing V3 with any currently evaluated alternative would degrade model performance.

### C. Retraining Decision
**RETAIN V3 WITH TARGETED FOLLOW-UP — NO IMMEDIATE RETRAINING.**

---

## 18. Prospective Retraining Triggers

Future model retraining must be governed by empirical validation triggers. To maintain strict scientific integrity, every trigger threshold adheres to the mandatory policy: **"Threshold to be established prospectively from validation/control data before operational use."** The frozen Test partition must never be used to invent or tune trigger thresholds.

| Trigger Category | Monitoring Measurement | Evidence Required for Trigger | Action If Confirmed |
| :--- | :--- | :--- | :--- |
| **Post-2019 Degradation** | PR-AUC_TRAP, Brier, ECE on post-2019 holdout | Systematic degradation confirmed — Threshold to be established prospectively from validation/control data before operational use. | Initiate retraining program on recent-era data |
| **$N=31$ Serving Distortion** | Probability distribution and ECE under live $N=31$ vs historical $N=5$ | Systematic probability distortion confirmed — Threshold to be established prospectively from validation/control data before operational use. | Initiate $N=31$-specific retraining program |
| **Station Calibration Failure** | Station-stratified ECE on live operational predictions | Persistent miscalibration across multiple stations confirmed — Threshold to be established prospectively from validation/control data before operational use. | Conduct targeted hierarchical/station calibration study |
| **Revision Feature Utility** | Incremental PR-AUC / Brier from genuine 6-hourly revision data | Statistically confirmed incremental skill on held-out data — Threshold to be established prospectively from validation/control data before operational use. | Incorporate genuine revision history into training schema |
| **Geographic Expansion** | AP, ECE, Brier at newly integrated synoptic stations | Systematic failure at newly introduced stations confirmed — Threshold to be established prospectively from validation/control data before operational use. | Expand station coverage and train regional adapters |
| **New Atmospheric Variables** | Evaluation on precipitation, gusts, or humidity | Variable-specific bust skill validated — Threshold to be established prospectively from validation/control data before operational use. | Expand feature pipeline and benchmark |
| **Sustained Operational Drift** | Longitudinal drift diagnostics on feature distributions and probabilities | Sustained shift confirmed beyond transient fluctuation — Threshold to be established prospectively from validation/control data before operational use. | Convene scientific retraining review |

---

## 19. Targeted Follow-Up Program

The follow-up program is organized into two strictly segregated phases: validation work must precede and inform any model development work.

### Phase A: Validation Work (Prioritized)
1. **$N=31$ Operational Shadow Validation:** Deploy V3 in a non-blocking shadow pipeline processing live $N=31$ 6-hourly GEFS data. Directly quantify empirical probability distributions, spread feature shifts, and calibration drift against historical $N=5$ baselines.
2. **Post-2019 Recent-Era Benchmark:** Construct a chronologically quarantined 2020–present evaluation dataset adhering strictly to Day 22 leakage and label protocols.
3. **Unseen-Station Holdout Audit:** Evaluate V3 performance on synoptic stations not included in the 25 canonical locations.
4. **Regional Calibration Investigation:** Analyze station-level calibration heterogeneity, specifically investigating Goa and Srinagar.
5. **6-Hourly Revision Dataset Compilation:** Harvest a genuine operational archive of 6-hourly forecast revisions to quantify live distribution shifts.
6. **Probabilistic Diagnostics:** Generate Murphy decompositions, reliability diagrams, and resolution components across atmospheric regimes.
7. **Operational Drift Monitoring:** Establish automated tracking of input feature distributions and probability outputs using prospective control bounds.

### Phase B: Model Development Work (Future Scope Only)
*Model development must not begin until Phase A validation provides empirical justification.*
* Retraining dataset architecture incorporating verified $N=31$ data, genuine 6-hourly revisions, and post-2019 cases.
* Evaluation of candidate architectures (e.g., CatBoost, XGBoost, Neural Baselines) against frozen V3 under identical evaluation contracts.
* Exploration of hierarchical or regional calibration layers.

---

## 20. Future Retraining Dataset Specifications

Should prospective triggers justify a new retraining cycle, the training dataset must satisfy the following design requirements:

* **Temporal Era:** Must incorporate recent atmospheric data (post-2019) to reflect current climate regimes.
* **Ensemble Configuration:** Must utilize operational $N=31$ ensemble statistics directly.
* **Revision History:** Must utilize genuine 6-hourly forecast revision sequences.
* **Geographic Architecture:** Must include designated spatial holdout stations reserved exclusively for unseen-station testing.
* **Leakage Protections:** Must maintain the strict temporal purging and chronological isolation certified in Day 22.
* **Frozen Holdout:** Must establish a new, untouched frozen holdout set; the Day 23 canonical Test set must never be used as a training or validation target.
* **Rare-Event Support:** Must ensure sufficient sample sizes in extreme tail strata to avoid undefined slice metrics.
* **Architecture Agnosticism:** Model architecture must not be prescribed in advance; selection must be driven strictly by competitive benchmarking against V3.

---

## 21. Model Replacement Policy

A future challenger model may replace the integrated V3 model only if it satisfies comprehensive criteria across multiple dimensions:

1. **Superior Discrimination:** Demonstrates statistically significant improvement in PR-AUC_TRAP and AP with paired uncertainty quantified on an independent holdout.
2. **Improved Probabilistic Skill:** Achieves lower Brier score and positive BSS relative to V3.
3. **Preserved Calibration:** Maintains or improves ECE globally and across station slices without localized degradation.
4. **Slice Stability:** Exhibits no material performance collapse across any variable, lead horizon, or station subset.
5. **Operational Compatibility:** Proven compatibility with live $N=31$ 6-hourly serving infrastructure.
6. **Rigorous Evaluation Contract:** Evaluated under the same frozen evaluation contract (same adaptive labeling logic, strict embargoes, no lookahead).

> [!IMPORTANT]
> **Policy Constraint:** A single-metric win (e.g., higher ROC-AUC with degraded Brier score or calibration) is explicitly insufficient for model replacement. Exact numerical acceptance thresholds must be declared prospectively prior to final challenger evaluation.

---

## 22. Operational Threshold Policy

The Veyra serving architecture currently evaluates probabilities against two operational decision thresholds: $p = 0.060$ and $p = 0.280$.

* **Preservation of Existing Thresholds:** Day 23 does not alter, optimize, or redefine the $0.060$ or $0.280$ threshold values.
* **Separation of Concerns:** Threshold selection is an operational decision distinct from model championship. The frozen Test set must not be used to tune or optimize operational decision thresholds.
* **Serving Contract Governance:** The exact product semantics and operational action rules associated with these thresholds remain governed by the serving contract. The $0.060$ threshold must not be characterized as "tuned for disaster mitigation."

---

## 23. Final Decision Matrix

| Candidate Option | Supporting Evidence | Contradicting Evidence | Scientific Risk | Operational Risk | Evaluation Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **KEEP** | V3 exhibits strong benchmark superiority, positive BSS, clean provenance, and existing system integration. | Ignores unresolved $N=31$ operational mismatch, uncertified post-2019 era, and station calibration heterogeneity. | Moderate: risks leaving serving-domain shifts unmonitored. | Moderate: assumes $N=5$ benchmark equates to $N=31$ live performance. | **REJECTED** (Insufficient follow-up rigor) |
| **RETAIN_WITH_TARGETED_FOLLOWUP** | Affirms verified benchmark superiority while establishing targeted validation for $N=31$, post-2019 data, and station calibration. | Acknowledges limitations cannot be resolved immediately on existing historical data. | Low: actively quantifies and monitors domain risks without disruptive circular retraining. | Low: maintains stable serving model while validating live conditions in shadow mode. | **SELECTED** |
| **RETRAIN** | Identifies potential gains from $N=31$, genuine revisions, and post-2019 data. | V3 is not defective; retraining on identical historical data is circular and provides zero new information. | High: risks destabilizing a validated model without resolving data domain gaps. | High: engineering overhead without demonstrable scientific gain. | **REJECTED** (Unjustified on current data) |
| **REPLACE** | None. | All evaluated alternative candidates (E0, E1b, E2) are substantially inferior across all metrics. | Very High: replaces superior model with demonstrably weaker baseline. | Very High: severe operational degradation. | **REJECTED** (No viable challenger exists) |

---

## 24. Final Day 23 Decision & Verdict

The frozen canonical benchmark provides strong benchmark evidence that V3 is the best-performing eligible candidate evaluated under the frozen Day 23 contract.

* **PRIMARY DECISION:** **RETAIN_WITH_TARGETED_FOLLOWUP**
* **CONFIDENCE LEVEL:** **MODERATE**
  *(High confidence in frozen benchmark superiority; moderate overall confidence due to unresolved $N=31$ operational domain shift, absence of post-2019 data, and station-level calibration heterogeneity).*
* **FINAL VERDICT:** **B. RETAIN V3 WITH TARGETED FOLLOW-UP — NO IMMEDIATE RETRAINING**

---

## 25. Day 24 Handoff: Probabilistic Intelligence

Day 24 will initiate the **Probabilistic Intelligence** phase. Day 23 transfers the following candidate diagnostic and visualization priorities to Day 24:

1. **Reliability Visualizations:** Constructing 10-bin empirical reliability curves comparing calibrated V3 and raw V3 across lead horizons, calendar years, and station tiers.
2. **Uncertainty Representation:** Formulating principled representations of forecast uncertainty and prediction sharpness.
3. **Advanced Calibration Diagnostics:** Implementing Murphy score decompositions (resolution, reliability, uncertainty) and stratification by prevalence bands.
4. **Probability Semantics:** Formalizing product-level interpretations of predicted probabilities as calibrated estimates of empirical forecast-bust likelihood.
5. **Skill Visualization:** Presenting Brier Skill Scores relative to climatology across multi-dimensional slices.
6. **Abstention & Confidence Framework:** Evaluating abstention boundaries where prediction uncertainty warrants withholding automated alerts.

*Day 24 implementation work was not initiated during Day 23.*
