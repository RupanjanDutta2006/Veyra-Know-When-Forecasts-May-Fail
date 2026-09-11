# Day 7 Scientific Expansion Report: Empirical Stage B Full Geographic Expansion

**Execution Timestamp (UTC)**: 2026-08-26T15:40:18.369731+00:00  
**System**: Forecast-Bust Sentinel (SIH26079)  
**Status**: STAGE B EMPIRICAL EXECUTION COMPLETE (20/20 Locations Historically Paired)

---

## 1. Actual Collected Data & Location Promotion Status
Stage B executed multi-cycle collection and ERA5 truth pairing for all 20 candidate monitoring locations:
- **Total Registered Locations**: 20
- **Historically Paired Locations**: **20 / 20**
- **Source Verified Locations**: **20**
- **Candidate Locations**: **0**
- **Total Stage B Paired Dataset**: **35040 rows** across 3 variables and 4 cycles (`00Z`, `06Z`, `12Z`, `18Z`)

| Location ID | City | State / Region | Status | Requested Coords | Source Grid Coords | Spatial Distance | Paired Rows | Match Rate |
|---|---|---|---|---|---|---|---|---|
| `ahmedabad` | **Ahmedabad** | Gujarat | `HISTORICALLY_PAIRED` | 23.0225°N, 72.5714°E | 23.0000°N, 72.5000°E | 7.72 km | 1752 | 100.0% |
| `bengaluru` | **Bengaluru** | Karnataka | `HISTORICALLY_PAIRED` | 12.9716°N, 77.5946°E | 13.0000°N, 77.5000°E | 10.73 km | 1752 | 100.0% |
| `bhopal` | **Bhopal** | Madhya Pradesh | `HISTORICALLY_PAIRED` | 23.2599°N, 77.4126°E | 23.2500°N, 77.5000°E | 9.00 km | 1752 | 100.0% |
| `bhubaneswar` | **Bhubaneswar** | Odisha | `HISTORICALLY_PAIRED` | 20.2961°N, 85.8245°E | 20.2500°N, 85.7500°E | 9.31 km | 1752 | 100.0% |
| `chandigarh` | **Chandigarh** | Chandigarh | `HISTORICALLY_PAIRED` | 30.7333°N, 76.7794°E | 30.7500°N, 76.7500°E | 3.37 km | 1752 | 100.0% |
| `chennai` | **Chennai** | Tamil Nadu | `HISTORICALLY_PAIRED` | 13.0827°N, 80.2707°E | 13.2500°N, 80.2500°E | 18.74 km | 1752 | 100.0% |
| `delhi` | **Delhi** | National Capital Region | `HISTORICALLY_PAIRED` | 28.6139°N, 77.209°E | 28.5000°N, 77.2500°E | 13.28 km | 1752 | 100.0% |
| `goa` | **Panaji** | Goa | `HISTORICALLY_PAIRED` | 15.2993°N, 73.8278°E | 15.2500°N, 74.0000°E | 19.27 km | 1752 | 100.0% |
| `guwahati` | **Guwahati** | Assam | `HISTORICALLY_PAIRED` | 26.1445°N, 91.7362°E | 26.2500°N, 91.7500°E | 11.81 km | 1752 | 100.0% |
| `hyderabad` | **Hyderabad** | Telangana | `HISTORICALLY_PAIRED` | 17.385°N, 78.4867°E | 17.5000°N, 78.5000°E | 12.87 km | 1752 | 100.0% |
| `jaipur` | **Jaipur** | Rajasthan | `HISTORICALLY_PAIRED` | 26.9124°N, 75.7873°E | 27.0000°N, 75.7500°E | 10.42 km | 1752 | 100.0% |
| `kochi` | **Kochi** | Kerala | `HISTORICALLY_PAIRED` | 9.9312°N, 76.2673°E | 10.0000°N, 76.2500°E | 7.88 km | 1752 | 100.0% |
| `kolkata` | **Kolkata** | West Bengal | `HISTORICALLY_PAIRED` | 22.5726°N, 88.3639°E | 22.5000°N, 88.2500°E | 14.21 km | 1752 | 100.0% |
| `lucknow` | **Lucknow** | Uttar Pradesh | `HISTORICALLY_PAIRED` | 26.8467°N, 80.9462°E | 26.7500°N, 81.0000°E | 12.01 km | 1752 | 100.0% |
| `mumbai` | **Mumbai** | Maharashtra | `HISTORICALLY_PAIRED` | 19.076°N, 72.8777°E | 19.0000°N, 73.0000°E | 15.38 km | 1752 | 100.0% |
| `nagpur` | **Nagpur** | Maharashtra | `HISTORICALLY_PAIRED` | 21.1458°N, 79.0882°E | 21.2500°N, 79.0000°E | 14.76 km | 1752 | 100.0% |
| `pune` | **Pune** | Maharashtra | `HISTORICALLY_PAIRED` | 18.5204°N, 73.8567°E | 18.5000°N, 73.7500°E | 11.48 km | 1752 | 100.0% |
| `raipur` | **Raipur** | Chhattisgarh | `HISTORICALLY_PAIRED` | 21.2514°N, 81.6296°E | 21.2500°N, 81.7500°E | 12.48 km | 1752 | 100.0% |
| `ranchi` | **Ranchi** | Jharkhand | `HISTORICALLY_PAIRED` | 23.3441°N, 85.3096°E | 23.2500°N, 85.2500°E | 12.11 km | 1752 | 100.0% |
| `srinagar` | **Srinagar** | Jammu and Kashmir | `HISTORICALLY_PAIRED` | 34.0837°N, 74.7973°E | 34.0000°N, 74.7500°E | 10.28 km | 1752 | 100.0% |

---

## 2. Empirical Multi-Cycle Revision & Acceleration Verification
In the collected genuine multi-location dataset (35040 total rows), non-null inter-cycle revisions were computed for identical valid times:

| Feature | Feature Description | Non-Null Count | Coverage Pct |
|---|---|---|---|
| `forecast_delta_6h` | 6h Inter-cycle signed forecast shift | **32160** / 35040 | **91.8%** |
| `forecast_delta_12h` | 12h Inter-cycle signed forecast shift | **29280** / 35040 | **83.6%** |
| `forecast_delta_24h` | 24h Inter-cycle signed forecast shift | **23520** / 35040 | **67.1%** |
| `ensemble_spread_delta_6h` | 6h Ensemble spread evolution | **32160** / 35040 | **91.8%** |
| `spread_delta_12h` | 12h Ensemble spread evolution | **29280** / 35040 | **83.6%** |
| `ensemble_spread_delta_24h` | 24h Ensemble spread evolution | **23520** / 35040 | **67.1%** |
| `revision_accel_6h` | 6h Second-order revision acceleration | **29280** / 35040 | **83.6%** |
| `revision_accel_12h` | 12h Second-order revision acceleration | **23520** / 35040 | **67.1%** |
| `spread_accel_6h` | 6h Second-order spread acceleration | **29280** / 35040 | **83.6%** |

---

## 3. Forecast Trajectory Regimes Observed in Real Data
Distribution of deterministic trajectory classifications across 35040 real forecast records:

| Trajectory Regime | Count | Percentage | Meteorological Meaning |
|---|---|---|---|
| `STABLE` | **29280** | 83.6% | Precedence-governed classification |
| `INSUFFICIENT_CYCLES` | **5760** | 16.4% | Precedence-governed classification |

---

## 4. Persisted Physical Artifacts
- **Processed Multi-Cycle GEFS**: `data/processed/gefs_multicycle/{location_id}/` (20 stations)
- **Consolidated Historical Paired**: `data/historical/multicycle_paired/paired_multicycle_stage_b_2026-08-18_2026-08-24.parquet`
- **Experimental Instability Feature Dataset**: `data/features/experimental_instability/features_instability_stage_b_2026-08-18_2026-08-24.parquet`
- **Audit & Diagnostics**: `reports/day7/`

---

## 5. Frozen State Preservation & Zero Regression
- `data/features/training_dataset.parquet` and `models/day4/*` remain **100% frozen**.
- `ForecastBustModelService` maintains exact 26-feature canonical compatibility.
