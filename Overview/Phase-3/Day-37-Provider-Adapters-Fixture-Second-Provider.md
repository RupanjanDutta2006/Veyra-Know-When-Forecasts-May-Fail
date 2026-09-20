# Day 37 — Provider Adapter Architecture & Fixture Second Provider (Gate C7)

## 1. Executive Summary

Day 37 introduces a clean, multi-provider forecast adapter architecture (`BaseProviderAdapter`, `NormalizedProviderForecast`, `ProviderRegistry`) that wraps existing production weather ingestion while adding a deterministic fixture-backed second provider (`fixture_second_provider`).

### Key Accomplishments:
- **Provider Adapter Contract**: Standardizes multi-provider forecast retrieval, provider identity, execution modes (`LIVE` vs `FIXTURE`), and response statuses (`SUCCESS`, `UNAVAILABLE`, `INVALID_REQUEST`, `UNSUPPORTED_VARIABLE`, `TIME_MISMATCH`, `ERROR`).
- **Unit Normalization Engine**: Automatically normalizes raw provider inputs into Veyra canonical units:
  - Temperature: °C (converts K, °F)
  - Wind Speed: m/s (converts km/h, knots)
  - Surface Pressure: hPa (converts Pa, bar, atm)
- **Primary Open-Meteo Adapter**: `OpenMeteoProviderAdapter` wraps `OpenMeteoGEFSWeatherService` behind the standardized adapter interface, preserving 100% backward compatibility, 31-member GEFS ensemble ingestion, quality control, and in-memory caching.
- **Fixture Second Provider**: `FixtureSecondProviderAdapter` provides deterministic test/demo-only forecast data for contract testing. Explicitly marked as `provider_source_mode = FIXTURE` and never presented as a live operational source.
- **Provider Registry**: `ProviderRegistry` manages adapter registration and lookup. Unrecognized provider IDs raise an explicit `UnknownProviderError` instead of silently falling back.
- **Scientific Contract Preservation**: Retains frozen V3 LightGBM model hash (`00a84107...`), IsotonicCalibrator hash (`9f44860...`), 50-feature ordering, 25 certified stations, and P(BUST) logic without drift.

---

## 2. Architecture & Components

```
                    ┌─────────────────────────────┐
                    │      ProviderRegistry       │
                    └──────────────┬──────────────┘
                                   │
                   ┌───────────────┴───────────────┐
                   ▼                               ▼
       ┌───────────────────────┐       ┌────────────────────────┐
       │OpenMeteoProviderAdapter│       │FixtureSecondProviderAdapter│
       │ (provider_id: openmeteo)│       │ (provider_id: fixture)  │
       │  Mode: LIVE           │       │  Mode: FIXTURE         │
       └───────────┬───────────┘       └───────────┬────────────┘
                   │                               │
                   ▼                               ▼
       NormalizedProviderForecast      NormalizedProviderForecast
       - Canonical Unit (°C, m/s, hPa)  - Canonical Unit (°C, m/s, hPa)
       - UTC Timestamp                 - UTC Timestamp
       - Explicit Status               - Explicit Status
```

---

## 3. Verification & Test Results

- **Day 37 Focused Tests**: 20 / 20 PASS (`backend/tests/test_day37_provider_adapters.py`)
- **Frozen V3 Hash Integrity**:
  - Model SHA256: `00a8410746f4a0eecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660` (EXACT)
  - Calibrator SHA256: `9f448606ce4338ded92f238a551b3a9d8e6d2cb5902e8bc687bce5f5850af531` (EXACT)
- **Live Primary Provider Status**: `LIVE_PRIMARY_PROVIDER_VERIFIED`
- **Secondary Provider Mode**: `SECOND_PROVIDER_MODE=FIXTURE_ONLY`

---

## 4. Evidence Boundaries & Limitations

- **Fixture Second Provider**: Is explicitly a deterministic test fixture. It does NOT represent a second live operational weather provider.
- **Certification Scope**: Remains strictly locked to the 25 benchmark stations, 3 certified variables, <=240h lead, and 2017–2019 holdout set.
- **P(BUST) Unchanged**: Provider abstraction does not alter P(BUST) estimation, operational risk bands, or OOD diagnostics.
