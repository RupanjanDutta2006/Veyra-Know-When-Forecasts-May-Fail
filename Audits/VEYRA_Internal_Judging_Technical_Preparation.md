# Veyra --- Internal Judging & Technical Preparation Guide

## Project in One Line

**Veyra --- Know When Forecasts May Fail** is a forecast-reliability
system. It does not generate a new weather forecast; it estimates the
calibrated probability that an existing forecast may fail unusually
badly, called a **forecast bust**.

## Core Architecture

``` text
User / Frontend
→ Location Resolution
→ Live Forecast + Ensemble Data
→ Standardization + QC
→ 50 V3 Features
→ LightGBM V3
→ Isotonic Calibration
→ Calibrated P(BUST)
→ Risk / Trust / Abstention
→ Reason Codes + Explanation
→ Dashboard Intelligence API
→ Frontend
```

# Day 21--26 Overview

## Day 21 --- V3 Integration

Builder 2's trained V3 model was integrated into Builder 1's live
backend. - 50-feature V3 contract supported. - Temperature, wind and
pressure units standardized. - Live 31-member ensemble preserved. -
Calibration integrated. - Model failure safely abstains. - Default
Single Target repaired to positive 24h lead.

**Simple:** Builder 2's ML brain was connected to Builder 1's live
application/backend.

## Day 22 --- Dataset + Label + Leakage Certification

Scientific foundation audited: - 780,000 rows - 1040 forecast cycles -
25 stations - 3 variables - 10 horizons, 24h--240h - Train: 2000--2013 -
Validation: 2014--2016 - Test: 2017--2019

Bust rule:

``` text
forecast_abs_error >= applied_threshold → BUST
```

Overall bust prevalence ≈ 5.29%. No mechanical leakage was found in the
frozen authoritative pipeline during the audit.

**Simple:** Checked whether the data, labels and training/testing
process were scientifically trustworthy.

## Day 23 --- Model Championship

V3 was compared with eligible baselines/challengers on the frozen Test
benchmark.

Key calibrated V3 results: - AP: 0.2047 - PR-AUC: 0.2124 - ROC-AUC:
0.7698 - Brier: 0.0538 - ECE: 0.0064

Decision: **RETAIN_WITH_TARGETED_FOLLOWUP** --- keep V3, no immediate
retraining.

## Day 24 --- Probabilistic Intelligence

-   Dedicated authoritative V3 evaluation: `GET /v1/model/evaluation/v3`
-   Isotonic-calibrated probability.
-   Calibration failure → safe abstention.
-   Risk semantics clarified.
-   OOD semantics clarified.
-   Explanation inconsistencies repaired.

Risk tiers:

``` text
LOW      p < 0.20
MEDIUM   0.20 ≤ p < 0.50
HIGH     0.50 ≤ p < 0.75
CRITICAL p ≥ 0.75
```

## Day 25 --- Intelligence Dashboard Contract

Centralized frontend-ready endpoint:

``` text
POST /v1/dashboard/intelligence
```

Modes: - `single` → 24h - `standard_7d` → 24--168h - `full_16d` → 24h
steps through 384h

Provides selected prediction, timeline, summary, probability, risk,
calibration status, abstention, reason codes, explanation and scientific
context.

Important: ≤240h is within frozen benchmark lead scope; \>240h is
operational-only.

Invalid location such as Atlantis safely returns ABSTAINED with null
probability/risk.

Final Day25 state: backend 428 passed, frontend 55 passed, build PASS.

## Day 26 --- Internal Release Candidate

Next stage: verify Day21--25 together as an internal Release Candidate.
It is primarily integration/release verification, not a new
ML-model-development day.

# Key Features

1.  Forecast Bust Probability
2.  V3 LightGBM Model
3.  50-feature model contract
4.  Multi-location support
5.  Temperature, wind and pressure analysis
6.  Live ensemble intelligence
7.  Isotonic probability calibration
8.  LOW/MEDIUM/HIGH/CRITICAL operational risk tiers
9.  Safe abstention
10. Reason codes and rule-based explanations
11. Horizon-wise risk timeline
12. Centralized Dashboard Intelligence API
13. Dedicated V3 evaluation API
14. Dataset/leakage auditing
15. Chronological validation
16. Model championship/baseline comparison
17. Retry, caching, error handling and rate limiting
18. SingleFlight duplicate-work reduction
19. Observability through `/v1/metrics`
20. Frozen/reproducible ML artifacts

# Algorithms / Techniques

## 1. LightGBM --- Main Prediction Algorithm

**LightGBM = Light Gradient Boosting Machine.**

It is a gradient-boosted decision-tree algorithm. Instead of relying on
one tree, multiple trees are built sequentially. Later trees help
improve patterns/errors left by earlier trees, and their contributions
are combined.

Simple example:

``` text
Tree 1 → learns ensemble-spread pattern
          ↓ remaining errors
Tree 2 → learns lead-time pattern
          ↓
Tree 3 → learns another feature interaction
          ↓
...
Combined model score
```

In Veyra:

``` text
50 meteorological/ensemble-derived features
→ LightGBM
→ raw model score
```

**Judge answer:** "Our primary ML algorithm is LightGBM, a
gradient-boosted decision-tree model that learns nonlinear relationships
between meteorological and ensemble-derived features and forecast
busts."

## 2. Isotonic Calibration

Not the main prediction model. It calibrates the LightGBM output:

``` text
LightGBM raw score
→ Isotonic Calibrator
→ Calibrated P(BUST)
```

A strong classifier does not automatically have well-calibrated
probabilities, so calibration improves probability interpretation.

**Judge answer:** "LightGBM performs the main classification; isotonic
calibration is applied afterward to produce a better-calibrated bust
probability."

## 3. Rule-Based Risk Classification

``` text
p < .20 → LOW
.20 ≤ p < .50 → MEDIUM
.50 ≤ p < .75 → HIGH
p ≥ .75 → CRITICAL
```

This is deterministic backend logic, not another trained ML model.

## 4. Safe Abstention Logic

If trustworthy inference cannot be produced---e.g. invalid location,
model unavailable, calibration failure---the system can abstain instead
of inventing a normal probability.

# Likely Judge Questions & Ready Answers

## Q1. What is Veyra?

Veyra is a forecast-reliability system. It estimates the calibrated
probability that an existing forecast may fail unusually badly.

## Q2. Does Veyra predict weather?

No. It predicts forecast reliability/bust risk rather than generating a
new weather forecast.

## Q3. What is a forecast bust?

A forecast is labelled as a bust when its absolute forecast error meets
or exceeds the applicable certified bust threshold.

## Q4. Which main algorithm do you use?

LightGBM for main classification, followed by isotonic probability
calibration.

## Q5. Why LightGBM?

The project uses structured/tabular meteorological and ensemble-derived
features. LightGBM is suitable for efficiently learning nonlinear
relationships and feature interactions in such data.

## Q6. How many features does V3 use?

The frozen V3 contract uses 50 features.

## Q7. What dataset was used?

The canonical benchmark contains 780,000 rows, 1040 cycles, 25 stations,
3 variables and 10 historical horizons.

## Q8. Why chronological splitting?

Weather data is temporal. Chronological splitting reduces future-like
leakage risk and gives a more realistic historical evaluation.

## Q9. How did you check leakage?

We audited whether future observations, forecast error or bust-label
information mechanically entered the predictor path. No mechanical
leakage was found in the frozen authoritative pipeline.

## Q10. Is the dataset balanced?

No. Busts are rare; overall prevalence is about 5.29% and Test
prevalence about 6.22%.

## Q11. Why isn't accuracy enough?

Because rare-event classification can show high accuracy simply by
predicting mostly non-busts. We therefore use AP, PR-AUC, ROC-AUC, Brier
Score and ECE.

## Q12. What are V3's main benchmark results?

AP 0.2047, PR-AUC 0.2124, ROC-AUC 0.7698, Brier 0.0538 and ECE 0.0064 on
the frozen Day23 benchmark.

## Q13. PR-AUC 0.21 sounds low. Why is it useful?

It must be interpreted relative to the rare-event prevalence and
eligible baselines. Test bust prevalence is about 6.22%, and V3 showed
stronger benchmark performance than the eligible evaluated baselines.
Generalization limitations remain documented.

## Q14. Why didn't you retrain V3?

V3 remained the strongest eligible evaluated candidate, so immediate
retraining was not justified. We retained it with targeted follow-up
validation.

## Q15. What is calibration?

Calibration improves the relationship between model output and observed
event frequency so probability values are more meaningful.

## Q16. Which calibration method?

Isotonic calibration.

## Q17. What if calibration fails?

Veyra safely abstains instead of presenting an uncalibrated raw score as
a calibrated probability.

## Q18. What does abstention mean?

The system refuses to provide a normal risk prediction when trustworthy
inference conditions are not satisfied.

## Q19. What happens for an invalid location?

Probability and risk remain null and the result is ABSTAINED/UNAVAILABLE
rather than fake zero risk.

## Q20. What are the risk levels?

LOW \<20%, MEDIUM 20--\<50%, HIGH 50--\<75%, CRITICAL ≥75%. These are
operational product tiers.

## Q21. What is OOD?

Out-of-distribution. It indicates an input may differ from known model
data. In the current contract it is diagnostic-only, not an automatic
abstention trigger.

## Q22. How many ensemble members?

Historical benchmark N=5; live serving preserves N=31. This remains an
explicit operational-validation limitation.

## Q23. Why not reduce N=31 to N=5?

Arbitrary downsampling could discard information and create an
uncertified transformation. We preserve live data and document the
difference.

## Q24. Explain the inference flow.

Location → live forecast/ensemble → standardization/QC → 50 V3 features
→ LightGBM → isotonic calibration → P(BUST) → risk/safety/explanation →
API/frontend.

## Q25. Why create the dashboard intelligence endpoint?

It keeps prediction semantics, timeline, summary, abstention and
scientific context backend-owned instead of making the frontend
independently recompute them.

## Q26. Why show 384h if benchmark only covers 240h?

The application can operationally produce horizons beyond 240h, but they
are explicitly marked operational-only rather than benchmark-certified
performance.

## Q27. Are explanations SHAP?

No. The current explanation layer is rule-based.

## Q28. What if the upstream weather provider fails?

The backend uses retry, caching and safe error handling. If required
data cannot be obtained reliably, the system should return
unavailable/abstention behavior rather than invent values.

## Q29. Why caching?

Multiple horizons can depend on the same upstream payload, so caching
reduces redundant calls and latency.

## Q30. What is SingleFlight?

It coalesces equivalent concurrent upstream work to avoid unnecessary
duplicate fetches.

## Q31. How do you monitor the backend?

Using `/v1/metrics`, including HTTP, prediction, abstention, upstream,
cache, SingleFlight and dashboard metrics.

## Q32. What technologies are used?

FastAPI/Python backend, LightGBM ML, isotonic calibration,
React/TypeScript/Vite reference frontend, Pytest/Vitest testing and
Git/GitHub version control.

## Q33. How much testing has been done?

The frozen Day25 state passed 428 backend tests, 55 frontend tests and
the production build, plus manual browser/Swagger verification.

## Q34. Is Veyra 100% accurate?

No. It is a probabilistic reliability system and explicitly communicates
limitations and abstention conditions.

## Q35. Can Veyra replace meteorological agencies?

No. It is an additional forecast-reliability layer, not a replacement
for official forecasts or warnings.

## Q36. Biggest limitations?

N=5 historical vs N=31 live ensemble difference, benchmark ending in
2019, limited geographic certification, and no frozen benchmark
certification beyond 240h.

## Q37. Why should users trust it?

We do not ask for blind trust: we use chronological evaluation, leakage
auditing, baseline comparisons, calibration metrics, artifact
verification, safe abstention and explicit limitations.

## Q38. How do you ensure reproducibility?

Frozen V3 model/calibrator artifacts have verified SHA256 hashes and
documented feature/scientific contracts.

## Q39. What makes Veyra different from a normal weather app?

A normal weather app presents the forecast. Veyra estimates the
reliability/bust risk of that forecast.

## Q40. What is innovative?

The project integrates calibrated forecast-bust probability, ensemble
intelligence, abstention, explanations and horizon-wise risk into a
user-facing reliability layer.

## Q41. What would you improve next?

N=31 operational validation, post-2019 benchmarking, unseen-location
validation, stronger probabilistic diagnostics, drift monitoring and
later multi-model disagreement analysis.

## Q42. Does LOW risk guarantee a correct forecast?

No. It only means the estimated probability of meeting the defined bust
condition is relatively low.

## Q43. Does 70% bust probability mean 70% chance of rain?

No. It means an estimated 70% probability that forecast error meets or
exceeds the defined bust threshold; it is not a weather-event
probability.

# Important API Questions

-   Health: `GET /v1/health`
-   Prediction: `POST /v1/predict`
-   Dashboard: `POST /v1/dashboard/intelligence`
-   V3 Evaluation: `GET /v1/model/evaluation/v3`
-   Metrics: `GET /v1/metrics`

Important request-contract detail: `PredictionRequest` does **not**
contain a `lead_hours` field. Lead is derived from `issue_time` and
`valid_time`.

# Trap Questions --- Never Overclaim

-   Do not say **100% accurate**.
-   Do not say **zero leakage guaranteed everywhere**; say no mechanical
    leakage was found in the frozen audited pipeline.
-   Do not say **384h scientifically benchmark-certified**; frozen
    benchmark scope is through 240h.
-   Do not call current explanations **SHAP**; they are rule-based.
-   Do not interpret bust probability as chance of rain or another
    weather event.

# 30-Second Pitch

> "Veyra is an AI-based forecast-reliability system. Instead of
> generating another weather forecast, it analyzes an existing forecast
> and estimates the calibrated probability that the forecast may fail
> unusually badly. Our V3 LightGBM model uses a 50-feature
> meteorological and ensemble-derived contract. We audited the dataset
> and leakage, benchmarked V3 against eligible baselines, calibrated its
> probabilities, added safe abstention and rule-based explanations, and
> exposed the intelligence through a centralized dashboard API for
> frontend integration."

# 10-Second Pitch

> "Veyra does not predict the weather again; it predicts how likely an
> existing weather forecast is to fail unusually badly."

# Day 21--26 Memory Trick

``` text
DAY 21 → Integrate V3
DAY 22 → Certify Data
DAY 23 → Compare & Retain Model
DAY 24 → Trust the Probability
DAY 25 → Deliver Intelligence to Frontend
DAY 26 → Internal Release Candidate
```

# Five Things Every Team Member Must Know

1.  Veyra does not generate weather forecasts.
2.  LightGBM is the main prediction algorithm; isotonic calibration
    calibrates its probability.
3.  Bust means forecast absolute error meeting or exceeding the
    applicable certified threshold.
4.  Frozen benchmark lead scope ends at 240h; 264--384h is
    operational-only.
5.  Never claim 100% accuracy, universal zero leakage, SHAP
    explanations, or universal geographic/generalization certification.
