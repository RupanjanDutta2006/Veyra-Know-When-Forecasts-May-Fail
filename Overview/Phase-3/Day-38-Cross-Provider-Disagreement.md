# Day 38 — Cross-Provider Disagreement Intelligence (Gate C8)

## 1. Executive Summary

Day 38 implements Cross-Provider Disagreement Intelligence (`CrossProviderDisagreementService`, `CrossProviderDisagreementRequest`, `CrossProviderDisagreementResponse`), offering a typed, multi-provider forecast divergence diagnostic interface while preserving strict separation from Day 29 GEFS ensemble member spread and calibrated P(BUST) risk estimation.

### Key Accomplishments:
- **Scientific Definition**: Measures divergence (`signed_difference`, `absolute_difference`, `relative_difference_pct`) between normalized provider forecast values for identical targets (same canonical location, variable, valid time, and unit).
- **Architecture & Deterministic Validation**: Because Day 37's second provider adapter is fixture-only, Day 38 serves as an architectural and deterministic diagnostic milestone. It explicitly marks secondary provider inputs with `has_fixture_provider = True` and a clear provenance notice.
- **Comparability Contract**: Enforces strict unit normalization (°C, m/s, hPa) and valid-time alignment before executing comparisons. Mismatched units or missing provider data yield explicit `NOT_COMPARABLE` or `PROVIDER_UNAVAILABLE` status without fake zero differences.
- **Strict GEFS & P(BUST) Separation**: Keeps cross-provider disagreement strictly separate from Day 29 GEFS ensemble member spread (`ensemble_spread`, `ensemble_range`). Does NOT mutate frozen 50-feature V3 LightGBM inputs, P(BUST), risk thresholds, scientific certification, or OOD policies.
- **Dedicated API Endpoint**: Exposes `POST /v1/provider-disagreement/diagnostics`.
- **Frontend Panel**: Introduces `CrossProviderDisagreementPanel` displaying primary live provider vs secondary fixture provider comparisons with explicit fixture notice banners and clear diagnostic scope disclaimers.

---

## 2. API Data Contract

```json
{
  "status": "AVAILABLE",
  "reason_code": "COMPARISON_SUCCESSFUL",
  "canonical_location": "Delhi",
  "variable": "temperature_2m",
  "valid_time": "2026-09-21T00:00:00Z",
  "unit": "°C",
  "primary_provider": {
    "provider_id": "openmeteo_gefs",
    "provider_name": "Open-Meteo GEFS Ensemble",
    "provider_source_mode": "LIVE",
    "forecast_value": 32.0,
    "unit": "°C"
  },
  "secondary_provider": {
    "provider_id": "fixture_second_provider",
    "provider_name": "Fixture Secondary Provider (Deterministic Test-Only)",
    "provider_source_mode": "FIXTURE",
    "forecast_value": 33.2,
    "unit": "°C"
  },
  "signed_difference": -1.2,
  "absolute_difference": 1.2,
  "relative_difference_pct": 3.68,
  "is_comparable": true,
  "has_fixture_provider": true,
  "provenance_notice": "Comparison includes secondary provider using deterministic fixture data for architectural validation.",
  "scope_note": "Cross-provider divergence measures difference between normalized provider forecasts for the same target. It is separate from GEFS ensemble member spread and does not alter calibrated P(BUST) estimation."
}
```

---

## 3. Verification & Test Results

- **Day 38 Focused Tests**: 20 / 20 PASS (`backend/tests/test_day38_cross_provider_disagreement.py`)
- **Cross-Day Targeted Tests**: 153 / 153 PASS (Days 32–38)
- **Frozen V3 Hash Integrity**:
  - Model SHA256: `00a8410746f4a0eecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660` (EXACT)
  - Calibrator SHA256: `9f448606ce4338ded92f238a551b3a9d8e6d2cb5902e8bc687bce5f5850af531` (EXACT)
- **Operational Status**: `PRIMARY_LIVE_PLUS_SECONDARY_FIXTURE`

---

## 4. Evidence Boundaries & Limitations

- **Fixture Provenance**: The secondary provider is deterministic fixture data. This milestone validates the multi-provider comparison pipeline and diagnostic interface, not real-world multi-provider operational consensus.
- **Diagnostic Separation**: Cross-provider disagreement is purely diagnostic. It must not be interpreted as probability of forecast failure, atmospheric chaos, or model certainty.
