# Veyra — Model Artifact & Calibrator Audit

**Audit Date:** September 5, 2026  
**Artifact Directory:** `models/`  
**Evaluation Target:** V2 Frozen Production Champion vs V3 Benchmark-Trained Challenger

---

## 1. Model Artifact Verification & Cryptographic Hashes

| Artifact Path | Description | File Size | SHA-256 Checksum | Verification Status |
|:---|:---|:---:|:---|:---:|
| `models/v2/lightgbm_v2_champion.joblib` | **Frozen V2 Champion Booster** (3 trees, pilot dataset) | 11,188 B | `4434f3307529642a86aeb8024536f789fb4a077b75edc85d2772a01540cbb1e3` | **VERIFIED / UNTOUCHED** |
| `models/v2/probability_calibrator_v2.joblib` | **V2 Platt Sigmoid Calibrator** | 403 B | `1aab956a3cda6765a40c48c79f6ad7716284d5b57b66943fd2eb913685b71631` | **VERIFIED / UNTOUCHED** |
| `models/v2/feature_names.json` | **V2 50 Feature List (JSON)** | 1,114 B | `265cffbbd157a2b8b8b46d3702438050980043b5ed3a6a646a7969cdb9853355` | **VERIFIED / UNTOUCHED** |
| `models/v2/frozen_thresholds.json` | **V2 Stratified Bust Thresholds** | 11,539 B | `1c22a51528bb1ffe378d289ee4168ed2b35c91619ae5f3104c3ba2008166cd95` | **VERIFIED / UNTOUCHED** |
| `models/v3/lightgbm_v3_challenger.joblib` | **V3 Benchmark Challenger Booster** (295 trees, 547.5k rows) | 1,046,844 B | `00a8410746f4a0eecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660` | **VERIFIED / VALID** |
| `models/v3/probability_calibrator_v3.joblib` | **V3 Validation Isotonic Calibrator** | 2,791 B | `9f448606ce4338ded92f238a551b3a9d8e6d2cb5902e8bc687bce5f5850af531` | **VERIFIED / VALID** |
| `models/v3/feature_names.json` | **V3 50 Feature List (JSON)** | 1,114 B | `265cffbbd157a2b8b8b46d3702438050980043b5ed3a6a646a7969cdb9853355` | **VERIFIED / EQUIVALENT** |
| `models/v3/training_manifest.json` | **V3 Training Provenance Manifest** | 2,434 B | `b90492a546e03966f8734191545375819fe7ae9aae4bff765733ef0d83d58c11` | **VERIFIED / VALID** |

---

## 2. Exact 50-Feature Equivalence Check

Both `models/v2/feature_names.json` and `models/v3/feature_names.json` share the identical SHA-256 hash (`265cffbb...55`). The exact 50 feature names and ordering are:

```json
[
  "ensemble_mean", "ensemble_median", "ensemble_std", "ensemble_min", "ensemble_max",
  "ensemble_range", "ensemble_p10", "ensemble_p25", "ensemble_p75", "ensemble_p90",
  "ensemble_iqr", "ensemble_skew_proxy", "ensemble_kurtosis_proxy", "ensemble_cv",
  "ensemble_spread_to_iqr_ratio", "quantile_spacing_ratio", "tail_asymmetry", "robust_mad",
  "member_count", "has_full_ensemble", "forecast_value", "forecast_delta_6h", "forecast_delta_24h",
  "forecast_revision_mag_6h", "forecast_revision_mag_24h", "ensemble_spread_delta_6h",
  "ensemble_spread_delta_24h", "revision_accel_6h", "stability_index", "structural_overconfidence_risk",
  "rapid_change_proxy", "diurnal_phase_alignment", "lead_hours", "lead_days", "lead_decay_factor",
  "spread_x_lead", "cv_x_lead", "revision_x_spread", "valid_hour", "valid_month",
  "valid_dayofweek", "sin_hour", "cos_hour", "sin_month", "cos_month", "is_weekend",
  "is_surface_pressure", "is_temperature_2m", "is_wind_speed_10m", "ood_score"
]
```

### Excluded Non-Physical / Leaking Columns Check:
- Station ID / Station Name dummy variables: **0 present (REJECTED)**
- Latitude / Longitude coordinates: **0 present (REJECTED)**
- Station Elevation (m): **0 present (REJECTED)**
- Ground-truth (`truth_value`, `era5`): **0 present (REJECTED)**
- Error & Target labels (`forecast_abs_error`, `bust_label`): **0 present (REJECTED)**
- Future leads / future cycles: **0 present (REJECTED)**

---

## 3. Calibrator Isolation & Verification

- **V2 Calibrator:** Platt Sigmoid calibrated on pilot validation dataset.
- **V3 Calibrator:** Fitted exclusively on `split_partition == 'val'` (116,250 rows, 2014–2016). Zero test-set observations were exposed during calibration.
- **Validation Calibrated ECE:** `5.29e-18` on validation; `0.0068` on held-out test split.

---

## 4. Promotion & Production Deployment Status

- **Frozen V2 Champion:** Remains 100% untouched and preserved in `models/v2/`.
- **V3 Benchmark Challenger:** Successfully trained, calibrated, and passed all 5 scientific promotion gates.
- **Production Integration Status:** **NOT YET PROMOTED TO PRODUCTION**. `models/forecast_intelligence_service.py` supports loading both models dynamically via `version="v2"` / `version="v3"`.
