# Veyra — Phase 1 / Builder 1 / Day 4

## Historical Verification Ingestion, Alignment Engine & Bust Labeling Foundation

**Project Name:** Veyra — Know When Forecasts May Fail  
**Role:** Builder 1 (Backend API, Data Ingestion, Verification Alignment, Error Engine, Bust Labeling & Training Table)  
**Date:** August 26, 2026  
**Git Branch:** `rupanjan/historical-labels` (Dedicated Historical Labeling Branch)  
**Test Status:** 70/70 Automated Tests Passing (100%)  

---

## 1. Executive Summary

On **Day 4**, Builder 1 established the **Historical Verification and Labeling Foundation** for Veyra on branch `rupanjan/historical-labels`.

- **Key Achievements:**
  1. Implemented **Reference Weather Ingestion** (`OpenMeteoArchiveReferenceService`, `BaseReferenceWeatherService`, `ReferenceWeatherRecord`) connecting to verified historical archive and ERA5 reanalysis data.
  2. Built a rigorous **Unit Conversion Policy Engine** (`UnitConverter`, `UnitMismatchError`) with explicit conversions for Temperature (K, °C, °F), Pressure (Pa, hPa, bar, atm), Wind Speed (m/s, km/h, knots, mph), and Precipitation (mm, inches), rejecting incompatible unit dimensions.
  3. Created the **Historical Alignment Engine** (`HistoricalAlignmentEngine`, `AlignedVerificationRecord`) matching forecast and ground-truth observations on location, variable, and `valid_time`, while preserving `issue_time` and `lead_hours`.
  4. Built the **Forecast Error Engine** calculating signed forecast error ($e = y_{\text{forecast}} - y_{\text{reference}}$) and absolute error ($|e|$).
  5. Implemented a **Configurable & Statistical Bust Labeling Policy** (`FixedThresholdBustPolicy`, `QuantileBustPolicy`) supporting physical meteorological thresholds and conditional extreme quantile thresholds ($q90, q95, q97.5, q99$) fitted strictly on training data.
  6. Structured the **Historical Training Table Generator** (`HistoricalDatasetBuilder`, `HistoricalTrainingRow`) deriving seasonal and temporal metadata and supporting JSON Lines/Parquet serialization.
  7. Enforced strict **Anti-Data-Leakage Safeguards**: Ground-truth reference data is tagged with `is_ground_truth_label=True` and verified to satisfy `reference_valid_time >= forecast_issue_time`, completely isolated from live prediction features.
  8. Maintained **Zero Fake Probabilities**: `/v1/predict` safely returns `abstain=True` with `bust_probability=null` and `reason_codes=["MODEL_NOT_READY"]`.
  9. Added 20 new automated unit tests, bringing the total suite to **70 tests (100% passing in 0.19s)**.

---

## 2. Historical Forecast & Reference Sources

- **Historical Forecasts:** Canonical forecast representations (`CanonicalForecastRecord`, `CanonicalForecastDataset`) from NOAA GFS / GEFS 31-member ensemble feeds.
- **Reference / Ground Truth Weather:** ERA5 Reanalysis and verified station observations ingested via `OpenMeteoArchiveReferenceService` (`https://archive-api.open-meteo.com/v1/archive`).

---

## 3. Spatial, Temporal & Variable Alignment Rules

Implemented in `backend/app/data/alignment.py`:

| Dimension | Matching Criteria | Handling on Mismatch |
|---|---|---|
| **Variable** | Exact case-insensitive match (e.g. `temperature_2m == temperature_2m`) | Alignment rejected (`None`) |
| **Spatial Coordinate** | Euclidean distance within tolerance ($\le 0.5^\circ$) or identical location name | Alignment rejected (`None`) |
| **Valid Time** | Normalized ISO 8601 UTC timestamp match (`forecast.valid_time == reference.valid_time`) | Alignment rejected (`None`) |
| **Units** | Explicit conversion via `UnitConverter.convert(ref_val, ref_unit, fc_unit)` | If incompatible dimensions -> raises `UnitMismatchError` / rejects alignment |
| **Temporal Guard** | Anti-leakage check: `reference.valid_time >= forecast.issue_time` | If violated -> alignment rejected |

---

## 4. Forecast Error & Bust Labeling Policy

### Error Definition:
$$\text{forecast\_error} = \text{forecast\_value} - \text{reference\_value}$$
$$\text{absolute\_error} = |\text{forecast\_error}|$$

### Bust Label Definition:
$$\text{bust\_label} = \begin{cases} 1 & \text{if } \text{absolute\_error} \ge \text{threshold} \\ 0 & \text{otherwise} \end{cases}$$

### Configurable Policies:
1. **`FixedThresholdBustPolicy` (Default Baseline):**
   - `temperature_2m`: $3.0^\circ\text{C}$
   - `surface_pressure`: $4.0\text{ hPa}$
   - `wind_speed_10m`: $4.0\text{ m/s}$
   - `relative_humidity_2m`: $20.0\%$
   - `precipitation`: $10.0\text{ mm}$
   - `geopotential_height_500hPa`: $60.0\text{ gpm}$
2. **`QuantileBustPolicy` (Statistical Extreme Error):**
   - Fits conditional extreme quantile thresholds $Q_p(|e|)$ (e.g. $p = 0.95$ for $q95$) on the historical training set grouped by `(variable, lead_time_bin)`.
   - Lead time partitions: `day1` (0–24h), `day2-3` (25–72h), `day4-7` (73–168h), `day8+` (169h+).

---

## 5. Historical Dataset Schema

Implemented in `backend/app/data/training_dataset.py`:

```python
class HistoricalTrainingRow:
    location: str
    latitude: float
    longitude: float
    region: str
    variable: str
    issue_time: str
    valid_time: str
    lead_hours: int
    forecast_value: float
    reference_value: float
    unit: str
    error: float
    absolute_error: float
    season: str               # "winter", "spring", "summer", "autumn"
    month: int                # 1 - 12
    bust_label: int           # 1 (Bust) or 0 (No-Bust)
    bust_threshold: float
    forecast_source: str      # "NOAA_GEFS_OPENMETEO"
    reference_source: str     # "ERA5_REANALYSIS"
    alignment_status: str     # "SUCCESS" or "UNIT_CONVERTED"
    is_ground_truth_label: bool = True
```

---

## 6. Strict Anti-Data-Leakage Safeguards

1. **Isolation of Truth:** `ReferenceWeatherRecord` and `AlignedVerificationRecord` are strictly tagged with `is_ground_truth_label=True` and cannot be imported or called in live inference endpoints (`/v1/predict`).
2. **Chronological Validity:** For any live feature $F(t)$, $\text{availability\_time}(F) \le \text{issue\_time}$ is strictly enforced.
3. **Training Boundary:** Empirical bust quantile thresholds are fitted strictly on past training partitions without peeking into evaluation or test partitions.

---

## 7. Automated Test Results (70 Tests Passing)

```text
Results:
  - backend/tests/test_agent.py                 8 PASSED
  - backend/tests/test_bust_labeling.py         5 PASSED (Day 4 Bust Labeling suite)
  - backend/tests/test_health.py                2 PASSED
  - backend/tests/test_historical_alignment.py  6 PASSED (Day 4 Alignment & Error suite)
  - backend/tests/test_historical_dataset.py    4 PASSED (Day 4 Dataset & Reference suite)
  - backend/tests/test_predict.py              11 PASSED
  - backend/tests/test_qc.py                    7 PASSED
  - backend/tests/test_schemas.py               6 PASSED
  - backend/tests/test_services.py              8 PASSED
  - backend/tests/test_unit_conversion.py       5 PASSED (Day 4 Unit Conversion suite)
  - backend/tests/test_weather_ingestion.py     8 PASSED
  ============================= 70 passed in 0.19s =============================
```

---

## 8. Day Status

**STATUS: COMPLETE**

---

**Previous:** [Day 3](./Day-3.md) | **Next:** [Day 5](./Day-5.md)
