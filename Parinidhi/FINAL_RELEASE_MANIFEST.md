# VEYRA 3.0 — FINAL RELEASE MANIFEST

**Build Date:** 2026-09-05T08:56:00Z  
**Target Release:** Smart India Hackathon (SIH) Final Release  
**Production Architecture:** Builder 1 (FastAPI Orchestrator) + Builder 2 (Operational Risk & Forecast Intelligence Service)

---

## 1. System Specifications & Configuration

| Configuration Property | Value |
| :--- | :--- |
| **Active Production Model** | `veyra-v3-benchmark-lightgbm` (LightGBM on 780k Benchmark Archive) |
| **Rollback Model** | `veyra-v2-champion-lightgbm` (Explicitly activatable via `VEYRA_MODEL_VERSION=v2`) |
| **Active Data Version** | `gfs-ensemble-openmeteo-v2.0` |
| **Feature Count** | 50 Supercharged Physical Atmospheric Features |
| **Feature Leakage Safeguards** | Zero station IDs, zero lat/lon coordinates, zero historical error leakage, zero future truth |
| **Decision Threshold ($p_{\text{risk}}$)** | `0.060` (Location-stratified empirical $q_{95}$ calibrated probability cutoff) |
| **Risk Tier Boundaries** | $\text{LOW} < 0.060 \le \text{ELEVATED} < 0.600 \le \text{CRITICAL}$ |
| **Operational Trust Horizon Threshold** | $P_{\text{crit}} = 0.35$ (Design threshold, not empirical constant) |
| **Severe OOD Abstention Threshold** | $D_M \ge 40.0$ (Mahalanobis novelty distance cutoff) |
| **Hosting Port** | `localhost:8001` (Builder 2 HTTP API & Web Dashboard) |

---

## 2. Bitwise Invariant Artifact SHA-256 Hashes

| Artifact File | Complete SHA-256 Hash | Status |
| :--- | :--- | :--- |
| `data/processed/phase5b2_benchmark_raw.parquet` | `14ba86aebd3324c94d109d59490dcb9ad09be23090006d71e3effad9d356c9a3` | **VERIFIED INVARIANT** |
| `data/processed/phase5b2_benchmark_canonical.parquet` | `afebbfdb04b8ed3b37668044d88a9e09f97109ff5609d6a2d3fe93c70df7b648` | **VERIFIED INVARIANT** |
| `models/v2/lightgbm_v2_champion.joblib` | `4434f3307529642a86aeb8024536f789fb4a077b75edc85d2772a01540cbb1e3` | **VERIFIED INVARIANT** |
| `models/v3/lightgbm_v3_challenger.joblib` | `00a8410746f4a0eecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660` | **VERIFIED INVARIANT** |
| `models/v3/probability_calibrator_v3.joblib` | `9f448606ce4338ded92f238a551b3a9d8e6d2cb5902e8bc687bce5f5850af531` | **VERIFIED INVARIANT** |
| `models/v3/feature_names.json` | `265cffbbd157a2b8b8b46d3702438050980043b5ed3a6a646a7969cdb9853355` | **VERIFIED INVARIANT** |
| `models/v3/training_manifest.json` | `b90492a546e03966f8734191545375819fe7ae9aae4bff765733ef0d83d58c11` | **VERIFIED INVARIANT** |

---

## 3. Test Suite Verification Summary

| Suite | Scope | Passed | Failed | Skipped | Pass Rate |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Builder 1 Test Suite** | `backend/tests/` (Agent, API, Services, Schemas, Integration) | **103** | **0** | **0** | **100%** |
| **Builder 2 Test Suite** | `tests/` (Research, Quality Gates, ML Features, Calibration, Verification) | **108** | **0** | **0** | **100%** |
| **Total Automated Tests** | All Repository Verification Gates | **211** | **0** | **0** | **100%** |

---

## 4. Canonical Benchmark Station Network (25 Stations — 100% Operational)

1. Ahmedabad (`ahmedabad`) — Semi-Arid / Urban Heat (Active V3)
2. Bengaluru (`bengaluru`, `bangalore`, `blr`) — Tropical Savanna / Deccan Plateau (Active V3)
3. Bhopal (`bhopal`) — Humid Subtropical / Central Plains (Active V3)
4. Bhubaneswar (`bhubaneswar`) — Tropical Wet & Dry / Coastal East (Active V3)
5. Chandigarh (`chandigarh`) — Subtropical Continental / Foothills (Active V3)
6. Chennai (`chennai`, `madras`) — Tropical Wet & Dry / Coromandel Coast (Active V3)
7. Dehradun (`dehradun`) — Humid Subtropical / Himalayan Valley (Active V3)
8. Delhi (`delhi`, `new delhi`, `delhi ncr`) — Semi-Arid / Monsoonal Plains (Active V3)
9. Goa / Panaji (`goa`, `panaji`) — Tropical Monsoon / Konkan Coast (Active V3)
10. Guwahati (`guwahati`) — Humid Subtropical / Brahmaputra Valley (Active V3)
11. Hyderabad (`hyderabad`) — Semi-Arid / Deccan Plateau (Active V3)
12. Jaipur (`jaipur`) — Semi-Arid / Thar Desert Margin (Active V3)
13. Kochi (`kochi`, `cochin`) — Tropical Monsoon / Malabar Coast (Active V3)
14. Kolkata (`kolkata`, `calcutta`) — Tropical Wet & Dry / Gangetic Delta (Active V3)
15. Leh (`leh`) — Cold Desert / High Altitude Trans-Himalaya (Active V3)
16. Lucknow (`lucknow`) — Humid Subtropical / Gangetic Plains (Active V3)
17. Mumbai (`mumbai`, `bombay`) — Tropical Wet & Dry / Coastal West (Active V3)
18. Nagpur (`nagpur`) — Tropical Wet & Dry / Central Plateau (Active V3)
19. Pune (`pune`) — Semi-Arid / Rain Shadow (Active V3)
20. Raipur (`raipur`) — Tropical Wet & Dry / Mahanadi Basin (Active V3)
21. Ranchi (`ranchi`) — Humid Subtropical / Chota Nagpur Plateau (Active V3)
22. Shimla (`shimla`) — Mountain Subtropical / Western Himalaya (Active V3)
23. Srinagar (`srinagar`) — Humid Subtropical / Kashmir Valley (Active V3)
24. Thiruvananthapuram (`thiruvananthapuram`, `trivandrum`) — Tropical Monsoon / Southern Tip (Active V3)
25. Visakhapatnam (`visakhapatnam`, `vizag`) — Tropical Wet & Dry / Coastal Andhra (Active V3)

---

## 5. Known Operational Limitations & Scientific Framing

1. **High-Altitude Atmospheric Physics:**
   - Trans-Himalayan and high-elevation terrain (Leh at 3,524m, Shimla at 2,276m) exhibits ambient barometric surface pressure (~675 hPa & ~770 hPa), safely accommodated by the standard $[500.0, 1100.0]\text{ hPa}$ physical bounds.
2. **Browser Automation Tooling Availability:**
   - Host environment has no browser automation driver installed (`BROWSER_AUTOMATION_UNAVAILABLE`).
   - Comprehensive DOM, static analysis, and full-stack HTTP testing have been verified in lieu of automated browser click-through.
3. **Operational Spending:**
   - Exact expenditure across all pipelines, APIs, and cloud services: **₹0.00**.
