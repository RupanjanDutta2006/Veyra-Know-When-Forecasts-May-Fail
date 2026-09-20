# Day 32 — Certification Scope Human-Verification Repair Report

**Veyra — Know When Forecasts May Fail**  
*SIH26079 — AI-Based Forecast Bust Detection for Medium-Range Weather Forecasts*  
*Phase 3: Operational Reliability & Meteorological Intelligence*  
*Authoritative Record: Targeted Scientific Certification Station-Scope Repair*

---

## 1. Executive Summary & Human Discovery

Following the initial merge of the Day 32 Scientific Certification Gate (`feat(day32)`), a human smoke test and forensic verification audit discovered a station-scope boundary inflation:

- **Human Smoke Test Finding:** A request to `POST /v1/certification/evaluate` correctly certified `Kolkata` at `24h` and rejected `264h`. However, the API returned `certified_station_count: 30` and a list of 30 stations in `certified_benchmark_stations`.
- **Scientific Evidence Conflict:** The authoritative Day 22 / Day 23 frozen benchmark dataset (`data/processed/phase5b2_benchmark_canonical.parquet`) comprises exactly **25 synoptic stations** across 1,040 cycles, 3 variables, 10 lead horizons, and 780,000 rows.
- **Defect Impact:** Six extended/operational stations (`Dispur`, `Gangtok`, `Patna`, `Shillong`, `Varanasi`, `Vijayawada`) were receiving false-positive `CERTIFIED` status, while the genuine Himalayan benchmark station (`Leh`) was incorrectly omitted and receiving `OUTSIDE_CERTIFIED_SCOPE`.

This document records the forensic audit, root cause, code repair, and regression proof locking the certification gate to the exact frozen 25 benchmark stations.

---

## 2. Scientific Benchmark Ground Truth

The authoritative evidence boundary is established by the canonical dataset and associated training manifests:

| Metric / Parameter | Value in Canonical Parquet |
| :--- | :--- |
| **Dataset Path** | `data/processed/phase5b2_benchmark_canonical.parquet` |
| **Total Rows** | 780,000 rows |
| **Total Forecast Cycles** | 1,040 cycles (2000–2019) |
| **Surface Atmospheric Variables** | 3 (`temperature_2m`, `wind_speed_10m`, `surface_pressure`) |
| **Forecast Lead Horizons** | 10 (`24h, 48h, 72h, 96h, 120h, 144h, 168h, 192h, 216h, 240h`) |
| **Unique Synoptic Stations** | **Exactly 25 stations** |

### Authoritative Frozen 25 Station Location IDs:
```
1.  ahmedabad
2.  bengaluru
3.  bhopal
4.  bhubaneswar
5.  chandigarh
6.  chennai
7.  dehradun
8.  delhi
9.  goa (Panaji)
10. guwahati
11. hyderabad
12. jaipur
13. kochi
14. kolkata
15. leh
16. lucknow
17. mumbai
18. nagpur
19. pune
20. raipur
21. ranchi
22. shimla
23. srinagar
24. thiruvananthapuram
25. visakhapatnam
```

This list matches:
- `CANONICAL_STATIONS` in `Parinidhi/research/contract/dataset_contract.py`
- `FROZEN_25_IDS` in `Parinidhi/scripts/extract_phase5b2_benchmark.py`
- `is_benchmark: true` in `Parinidhi/configs/canonical_locations.json`
- `KNOWN_BENCHMARK_LOCATIONS` in `backend/app/services/location_service.py`

---

## 3. Root Cause Analysis

In `backend/app/core/certification_policy.py`:
1. The comment and docstring correctly stated `# Canonical 25 synoptic stations evaluated in Day 22/27/28 benchmark dataset`.
2. However, the hardcoded list `CERTIFIED_BENCHMARK_STATIONS` contained 30 entries because candidate/extended regional points (`Dispur`, `Gangtok`, `Patna`, `Shillong`, `Varanasi`, `Vijayawada`) were accidentally included from early development prototypes, while `Leh` was omitted.
3. Because `evaluate_scientific_certification()` checked membership in `_CERTIFIED_STATION_LOWER_SET` derived from `CERTIFIED_BENCHMARK_STATIONS`, all 6 extra stations satisfied the location boundary check, producing false-positive `CERTIFIED` results.
4. Conversely, `Leh` was not in `_CERTIFIED_STATION_LOWER_SET` and was erroneously rejected as `UNCERTIFIED_LOCATION`.

---

## 4. Set Comparison & Scope Alignment

```
FROZEN_BENCHMARK_STATIONS (25):
  Ahmedabad, Bengaluru, Bhopal, Bhubaneswar, Chandigarh, Chennai,
  Dehradun, Delhi, Goa, Guwahati, Hyderabad, Jaipur, Kochi, Kolkata,
  Leh, Lucknow, Mumbai, Nagpur, Pune, Raipur, Ranchi, Shimla,
  Srinagar, Thiruvananthapuram, Visakhapatnam

PREVIOUS_CERTIFICATION_STATIONS (30):
  Ahmedabad, Bengaluru, Bhopal, Bhubaneswar, Chandigarh, Chennai,
  Dehradun, Delhi, [Dispur], [Gangtok], Goa, Guwahati, Hyderabad,
  Jaipur, Kochi, Kolkata, Lucknow, Mumbai, Nagpur, [Patna], Pune,
  Raipur, Ranchi, [Shillong], Shimla, Srinagar, Thiruvananthapuram,
  [Varanasi], [Vijayawada], Visakhapatnam

REMOVED FALSE-POSITIVE STATIONS (6):
  1. Dispur
  2. Gangtok
  3. Patna
  4. Shillong
  5. Varanasi
  6. Vijayawada

RESTORED FALSE-NEGATIVE STATION (1):
  1. Leh
```

---

## 5. Architectural Principle: Operational Scope vs. Scientific Certification

Veyra explicitly maintains a two-tier location design:

1. **Operational Support (`LocationRegistry` & `DynamicLocationService`):**
   - Resolves locations worldwide via Open-Meteo Geocoding.
   - Computes spatial mismatch distance ($\text{km}$) to forecast grid points.
   - Generates live inference predictions and operational risk flags.
2. **Scientific Benchmark Certification (`CertificationPolicy` / Gate C1):**
   - Strictly asserts whether a request falls inside the empirical training and evaluation evidence boundary (2000–2019 offline benchmark).
   - Only requests for the 25 canonical benchmark stations, 3 core surface variables, and lead horizons $\le 240\text{h}$ receive `CERTIFIED` / `CERTIFIED_FROZEN_BENCHMARK_SCOPE`.
   - All other operational requests receive `OUTSIDE_CERTIFIED_SCOPE` with explicit reason codes (`UNCERTIFIED_LOCATION`, `UNCERTIFIED_LEAD_HORIZON`, `UNCERTIFIED_VARIABLE`).

**Operational support does NOT imply scientific benchmark certification.**

---

## 6. Targeted Code Repairs

### A. Certification Policy (`backend/app/core/certification_policy.py`)
- Updated `CERTIFIED_BENCHMARK_STATIONS` to contain exactly the 25 canonical stations in Title Case.
- Updated `_CERTIFIED_STATION_LOWER_SET` to include `ladakh` (standard alias for `leh`) along with `panaji`, `ncr`, `new delhi`.

### B. Regression Suite (`backend/tests/test_scientific_certification.py`)
Added deterministic tests:
1. `test_station_count_exactly_25`: Asserts `len(CERTIFIED_BENCHMARK_STATIONS) == 25`.
2. `test_station_set_matches_frozen_benchmark`: Asserts exact mathematical set equivalence with the frozen 25 station IDs.
3. `test_leh_restored_to_certified_scope`: Verifies `Leh` returns `CERTIFIED`.
4. `test_removed_extra_stations_return_outside_certified_scope`: Parameterized test verifying all 6 extra stations return `OUTSIDE_CERTIFIED_SCOPE` / `UNCERTIFIED_LOCATION`.
5. `test_kolkata_certified_scope`: Verifies `Kolkata` at `24h` returns `CERTIFIED`.
6. `test_kolkata_extended_lead_horizon`: Verifies `Kolkata` at `264h` returns `OUTSIDE_CERTIFIED_SCOPE` / `UNCERTIFIED_LEAD_HORIZON`.
7. `test_http_certification_policy_endpoint`: Verifies `GET /v1/certification/policy` returns `certified_station_count == 25` and exact station list.

---

## 7. Artifact Integrity Confirmation

All core V3 model artifacts and calibrators were recomputed and verified byte-for-byte:

| Artifact | Path | SHA-256 Checksum | Status |
| :--- | :--- | :--- | :--- |
| **V3 Model Booster** | `models/v3/lightgbm_v3_challenger.joblib` | `00A8410746F4A0EECBF7E76AAA0565143FC948D0E06AEA65E7BCC4CE28A1C660` | **MATCH** |
| **V3 Probability Calibrator** | `models/v3/probability_calibrator_v3.joblib` | `9F448606CE4338DED92F238A551B3A9D8E6D2CB5902E8BC687BCE5F5850AF531` | **MATCH** |
| **Feature Contract** | `models/v3/feature_names.json` | 50 ordered features | **MATCH** |

---

## 8. Post-Repair Verification Matrix

| Location | Variable | Lead | Expected Status | Reason Code | Verified Result |
| :--- | :--- | :---: | :--- | :--- | :---: |
| **Kolkata** | `temperature_2m` | 24h | `CERTIFIED` | `CERTIFIED_FROZEN_BENCHMARK_SCOPE` | **PASS** |
| **Leh** | `temperature_2m` | 24h | `CERTIFIED` | `CERTIFIED_FROZEN_BENCHMARK_SCOPE` | **PASS** |
| **Dispur** | `temperature_2m` | 24h | `OUTSIDE_CERTIFIED_SCOPE` | `UNCERTIFIED_LOCATION` | **PASS** |
| **Gangtok** | `temperature_2m` | 24h | `OUTSIDE_CERTIFIED_SCOPE` | `UNCERTIFIED_LOCATION` | **PASS** |
| **Patna** | `temperature_2m` | 24h | `OUTSIDE_CERTIFIED_SCOPE` | `UNCERTIFIED_LOCATION` | **PASS** |
| **Shillong** | `temperature_2m` | 24h | `OUTSIDE_CERTIFIED_SCOPE` | `UNCERTIFIED_LOCATION` | **PASS** |
| **Varanasi** | `temperature_2m` | 24h | `OUTSIDE_CERTIFIED_SCOPE` | `UNCERTIFIED_LOCATION` | **PASS** |
| **Vijayawada** | `temperature_2m` | 24h | `OUTSIDE_CERTIFIED_SCOPE` | `UNCERTIFIED_LOCATION` | **PASS** |
| **Kolkata** | `temperature_2m` | 264h | `OUTSIDE_CERTIFIED_SCOPE` | `UNCERTIFIED_LEAD_HORIZON` | **PASS** |
| **London** | `temperature_2m` | 24h | `OUTSIDE_CERTIFIED_SCOPE` | `UNCERTIFIED_LOCATION` | **PASS** |
| **Kolkata** | `precipitation` | 24h | `OUTSIDE_CERTIFIED_SCOPE` | `UNCERTIFIED_VARIABLE` | **PASS** |
