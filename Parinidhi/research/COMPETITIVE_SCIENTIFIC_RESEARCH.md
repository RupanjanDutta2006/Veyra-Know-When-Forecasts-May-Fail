# Veyra — Competitive & Methodological Scientific Research

**Document:** `research/COMPETITIVE_SCIENTIFIC_RESEARCH.md`  
**System:** Veyra — Forecast-Reliability Intelligence Engine (Builder 2)  
**Date:** 2026-09-03  
**Scope:** Authoritative review of operational NWP ensemble verification, ML weather forecasting evaluation benchmarks, and multi-model comparison platforms to ground Veyra's scientific methodology.

---

## 1. NOAA GEFS / GEFSv12 Verification Framework

### Core Architecture & Literature
- **System**: NOAA Global Ensemble Forecast System version 12 (GEFSv12), operational since September 2020 (31 members, FV3 dynamical core, 0.25° horizontal grid, 64 vertical hybrid levels, 16-day forecast horizon; coupled with a 20-year retrospective reforecast archive from 2000–2019 using 5–11 members).
- **Primary References**:
  1. Hamill, T. M., et al. (2022). *The Version-12 Global Ensemble Forecast System Reforecast Dataset*. Monthly Weather Review, 150(1), 145–164.
  2. Zhou, X., et al. (2022). *The NCEP Global Ensemble Forecast System version 12 (GEFSv12)*. Weather and Forecasting, 37(6), 1045–1068.
  3. Zhu, Y., et al. (2018). *Ensemble Verification and Reliability Calibration at NCEP*. NOAA/NWS/NCEP/EMC Technical Report.

### Verification Standards & Diagnostic Metrics
1. **Spread-Error Relationship**:
   In a statistically consistent ensemble, the ensemble spread (standard deviation around the ensemble mean) should equal the root-mean-square error (RMSE) of the ensemble mean when averaged over many independent cases:
   $$\langle \sigma_{\text{ens}} \rangle = \text{RMSE}(\bar{x}_{\text{ens}}, y)$$
   NOAA verification routinely highlights that raw GEFSv12 under-spreads near the surface in convective boundary layers and complex topography (overconfidence bias).
2. **Continuous Ranked Probability Score (CRPS)**:
   $$\text{CRPS}(F, y) = \int_{-\infty}^{\infty} \left[ F(x) - \mathbb{I}(x \ge y) \right]^2 dx$$
   Where $F(x)$ is the empirical cumulative distribution function (eCDF) of the 31-member ensemble.
3. **Reliability Diagrams & Brier Score Decomposition**:
   For threshold events (e.g., $P(\text{wind} > 12\text{ km/h})$), observed frequency is plotted against forecasted probability bins. Under-dispersive ensembles manifest as slopes $< 1.0$ (forecast probabilities are too extreme).

---

## 2. ECMWF Ensemble Verification Principles

### Core Methodology & Literature
- **Primary References**:
  1. Leutbecher, M., & Palmer, T. N. (2008). *Ensemble forecasting*. Journal of Computational Physics, 227(7), 3515–3539.
  2. Buizza, R., et al. (2005). *A comparison of the ECMWF, MSC, and NCEP global ensemble prediction systems*. Monthly Weather Review, 133(5), 1076–1097.
  3. Murphy, A. H. (1973). *A new vector partition of the probability score*. Journal of Applied Meteorology, 12(4), 595–600.
  4. Ferro, C. A. (2007). *Comparing green and raw ensemble forecasts: Adjusting for finite ensemble size*. Weather and Forecasting, 22(5), 1118–1127.

### Key Insights for Veyra:
1. **Brier Score 3-Component Decomposition**:
   $$\text{BS} = \text{Reliability} - \text{Resolution} + \text{Uncertainty}$$
   - **Reliability (Calibration Error)**: $\sum_{k=1}^K w_k (\bar{p}_k - \bar{o}_k)^2 \to 0$ for perfectly calibrated forecasts.
   - **Resolution**: $\sum_{k=1}^K w_k (\bar{o}_k - \bar{o})^2 \to \text{maximum}$ (ability to discriminate distinct event probabilities).
   - **Uncertainty**: $\bar{o}(1 - \bar{o})$ (inherent climatological entropy of the test domain).
2. **Finite Ensemble Size Effects**:
   Ensemble variance estimates with $M$ members underestimate true population spread by a factor of $\sqrt{(M+1)/M}$. For GEFSv12 ($M=31$), this correction is small ($1.016$), but for 2017 reforecasts ($M=5$), the uncorrected spread is underestimated by $\approx 10\%$.
3. **Rank Histograms (Talagrand Diagrams)**:
   A flat rank histogram indicates a reliable ensemble. U-shaped histograms indicate under-dispersion (truth falls in extreme member tails too often); asymmetric histograms indicate systematic bias.

---

## 3. WeatherBench 2: Standardized Benchmark for Data-Driven & Physical Weather Models

### Literature & Standards
- **Primary Reference**:
  Rasp, S., Hoyer, S., et al. (2024). *WeatherBench 2: A benchmark for the next generation of data-driven global weather models*. Journal of Advances in Modeling Earth Systems, 16(6), e2023MS004019. (Google DeepMind & ECMWF collaboration).
- **Core Standard Metrics**:
  - **Deterministic**: Latitude-weighted Root Mean Square Error (RMSE), Mean Absolute Error (MAE), Spatial Anomaly Correlation Coefficient (ACC).
  - **Probabilistic**: Latitude-weighted Continuous Ranked Probability Score (CRPS), Spread-Skill Ratio (SSR), Brier Score (BS), Brier Skill Score (BSS).
  - **Baseline Frameworks**: 1990–2019 Day-of-Year Climatology, 24h/48h/72h Persistence, Raw NWP Ensemble Spread.
  - **Verification Ground Truth**: ECMWF ERA5 Hourly Reanalysis ($0.25^\circ \times 0.25^\circ$) and HRES operational analyses.

---

## 4. Modern Machine Learning Weather Systems (GraphCast, GenCast, Pangu-Weather, FourCastNet)

### Literature & Evaluation Approaches
- **GraphCast** (Lam et al., 2023, *Science*): Autoregressive graph neural network on icosahedral mesh. Evaluated on 1,380 verification targets against HRES and ERA5 across 0.25° grid over 10-day leads.
- **GenCast** (Price et al., 2023, *arXiv:2312.15796*): Diffusion-based ensemble ML weather model. Explicitly evaluated against ECMWF ENS on CRPS, Extreme Forecast Index (EFI), and spread-error consistency.
- **Pangu-Weather** (Bi et al., 2023, *Nature*): 3D earth-specific vision transformers across 5 pressure levels.
- **FourCastNet** (Pathak et al., 2022, *arXiv:2202.11214*): Adaptive Fourier Neural Operators for global weather forecasting.

### Critical Takeaways for Veyra:
1. **The Role of AI in Weather**: ML models predict the *weather state* ($X(t + \Delta t)$).
2. **The "Blurriness / Over-Smoothing" Challenge**: Deterministic ML models (GraphCast, Pangu) minimize MSE, which causes predictions to become blurry at long lead times, suppressing extreme events.
3. **Veyra's Unique Identity**: Veyra is **NOT** a weather generator or ML emulator. Veyra is a **meta-intelligence reliability layer** that inspects operational NWP forecasts, assesses their structural stability and ensemble geometry, and predicts **when and why the forecasts will bust**.

---

## 5. Multi-Model Forecast Comparison Platforms (Meteologix, ECMWF Open Data, NOAA Ensemble Matrix)

| System | Primary Functionality | What They Do Well | What They Do NOT Do (Veyra's Value Add) |
| :--- | :--- | :--- | :--- |
| **Meteologix / Kachelmann** | Visual comparison of deterministic runs (ECMWF, GFS, ICON, GEM, UKMO) & ensemble plumes. | High-resolution interactive plume charts, spaghetti maps, and member overlays. | No automated bust prediction; no calibrated failure probability; no failure fingerprint discovery; relies entirely on human interpretation of raw charts. |
| **NOAA EMC Verification** | Operational scorecard tables comparing monthly/seasonal model scores against radiosondes/buoys. | Extensive spatial statistical scorecards, anomaly correlation plots. | Retrospective only (reports how models scored last month); does not provide real-time issue-time bust risk on tomorrow's forecast. |
| **ECMWF Open Data** | Global probabilistic gridded ensemble feeds (51 members). | Authoritative global probabilistic fields (EFI, SOT, ensemble quantiles). | Raw gridded fields; does not provide station-level explainable failure root-cause analysis or issue-time dynamic overconfidence detection. |
| **Veyra Sentinel** | **Forecast-Reliability Intelligence Engine** above NWP. | **1. Calibrated Failure Probability $P(\text{bust})$**<br>**2. Confident-But-Wrong Detection**<br>**3. Automated Failure Fingerprint Classification**<br>**4. Actionable Natural-Language Decision Intelligence** | Focuses strictly on reliability risk rather than replacing numerical models. |

---

## 6. Synthesis: Principles Incorporated into Veyra V2 Supercharge

1. **Strict Stratified Quantile Labeling**: Every monitoring station's bust threshold is derived from its own historical high-quantile error distribution ($\tau_{\text{loc, var}}$), neutralizing static elevation biases.
2. **Zero Historical Error Leakage**: Feature engineering relies exclusively on issue-time physical observables (ensemble geometry, distribution shape, inter-cycle revisions, stability indices, diurnal angles).
3. **Probabilistic Integrity**: All probability outputs are calibrated strictly on validation data and verified using Brier Score, Brier Skill Score, and Expected Calibration Error (ECE).
4. **Grouped Temporal Independence**: Cross-validation and bootstrap confidence intervals are grouped by synoptic issue date/cycle to eliminate weather pseudoreplication.
