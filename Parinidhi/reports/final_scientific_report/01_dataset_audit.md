# Chapter 1: 1,040-Cycle Historical Dataset Forensic Integrity Audit

**Scientific Status:** `VALIDATED`
**Reference Ground Truth:** `ERA5 Reanalysis (reanalysis verification/reference; not station ground truth)`

## 1. Executive Summary
This chapter documents the forensic integrity verification of the full historical benchmark extraction covering 20 years (2000–2019), 1,040 weekly forecast cycles, 25 canonical Indian synoptic stations, 3 physical variables, and 10 forecast leads (+24h to +240h).

## 2. Integrity Checklist & Verified Dimensions
- **Expected Total Rows:** 780,000 (1040 cycles × 25 stations × 3 variables × 10 leads)
- **Extracted Rows:** `780000`
- **Cycles Audited:** `1040` (730 Train / 155 Validation / 155 Test)
- **Stations Audited:** `25` canonical stations
- **Variables Audited:** `3` (`temperature_2m`, `surface_pressure`, `wind_speed_10m`)
- **Leads Audited:** `10` (+24h to +240h in 24h increments)
- **Physical Bounds Audit:**
  - `temperature_2m`: [240.0 K, 335.0 K] — PASS (0 violations)
  - `surface_pressure`: [50000.0 Pa, 110000.0 Pa] — PASS (0 violations)
  - `wind_speed_10m`: [0.0 m/s, 75.0 m/s] — PASS (0 violations)
- **Duplicate Records:** `0`
- **Missing Combinations:** `0`
- **Temporal Buffer Deadband:** `PASS`
- **Future-Lead Leakage Check:** `PASS`

## 3. Forensic Rules
1. Never silently impute or repair corrupted scientific records. Fail loudly.
2. Verified issue times and valid times match exactly: `valid_time = issue_time + lead_hours`.
3. ERA5 reference values isolated strictly as ground-truth verification target.
