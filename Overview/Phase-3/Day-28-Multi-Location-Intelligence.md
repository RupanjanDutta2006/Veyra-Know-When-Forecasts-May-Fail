# Day 28 - Multi-Location Reliability Intelligence

**Phase 3 | Veyra - Know When Forecasts May Fail**
**SIH26079 - AI-Based Forecast Bust Detection for Medium-Range Weather Forecasts**

---

## 1. Objective

Day 28 extends Veyra spatial forecast reliability intelligence into an
interactive **multi-location comparative matrix** - an operator-facing panel that
allows simultaneous inspection and comparison of calibrated bust probability,
risk tier, trust state, and abstention status across the full evaluated station set.

Day 27 answered: Where are the evaluated spatial reliability points?

Day 28 answers: How can an operator inspect and compare forecast reliability
across multiple evaluated locations through one coherent intelligence view?

---

## 2. Starting Baseline

| Item | Value |
|---|---|
| Day 27 merge commit | a2398ca467747694042c7a7b9a9e05a7f4a6638f |
| Day 27 feature commit | f29bf3921b33df194d50ff9e1f2a5a2124ee603f |
| Backend regression at baseline | 490 / 490 PASS |
| Frontend tests at baseline | 66 / 66 PASS |
| Active branch | phase3/day28-multi-location-intelligence |

---

## 3. Architecture Audit

Before implementation, existing infrastructure was audited:

**Reused (unchanged) backend:**
- POST /v1/spatial/reliability - authoritative multi-point endpoint
- backend/app/services/spatial_service.py - SingleFlight, cache, bounded parallelism
- backend/app/schemas/spatial.py - SpatialReliabilityPoint, SpatialReliabilitySummary
- backend/app/agents/forecast_bust_agent.py - V3 LightGBM + isotonic calibration
- Location registry (INDIAN_BENCHMARK_25_STATIONS)

**No new ML model. No retraining. No recalibration. No threshold changes.**

---

## 4. Design Decisions

### 4.1 Backend Contract Reuse

POST /v1/spatial/reliability already supports N-location parallel evaluation.
No new endpoint was created for Day 28.

The only backend change: SpatialReliabilitySummary extended with four
deterministic count fields: low_risk_locations, medium_risk_locations,
high_risk_locations, critical_risk_locations. Computed from existing
risk_level field - no new threshold introduced.

### 4.2 Frontend: New MultiLocationPanel Component

frontend/src/components/MultiLocationPanel.tsx - new standalone component:
- Submits batch request via existing getSpatialReliability() API client
- Renders KPI summary bar (total evaluated, highest P(BUST), mean P(BUST), elevated count)
- Renders per-location cards (grid) or dense table view with sort and filter
- Location Diagnostic Inspector drawer
- Station preset selection
- Emits onNavigateToSpatial to cross-link to Day 27 map

---

## 5. Backend Changes

### MODIFY backend/app/schemas/spatial.py

Added four deterministic breakdown fields to SpatialReliabilitySummary:
low_risk_locations, medium_risk_locations, high_risk_locations, critical_risk_locations.

### MODIFY backend/app/services/spatial_service.py

Populated the four new count fields from risk_level in evaluated point list.
No new inference pipeline. No changed risk thresholds.

### MODIFY frontend/src/api/types.ts

Added the four new breakdown fields to SpatialReliabilitySummary TypeScript interface.

### NEW frontend/src/components/MultiLocationPanel.tsx

Full-featured Day 28 multi-location comparative matrix component.

### MODIFY frontend/src/components/Navigation.tsx

Added multi-location view with Day 28 badge.

### MODIFY frontend/src/App.tsx

Imported and renders MultiLocationPanel with bidirectional navigation.

### MODIFY frontend/src/components/SpatialReliabilityPanel.tsx

Added onNavigateToMultiLocation prop and cross-navigation button.

### NEW frontend/src/test/MultiLocation.test.tsx

11-test Vitest suite for Day 28 component.

---

## 6. Multi-Location Intelligence

| Feature | Description |
|---|---|
| Station preset | 25-station benchmark set, Major Metros (5), North-South Transect (6), custom |
| Variable selector | temperature_2m, wind_speed_10m, surface_pressure |
| Lead horizon selector | 24h-384h |
| KPI summary | Total evaluated, Highest P(BUST), Mean P(BUST), Elevated risk count |
| Grid card view | Per-location cards with P(BUST), risk badge, trust/calibration |
| Dense table view | Compact tabular view |
| Risk filter | All / Elevated Risk / Low / Abstained |
| Sort | By P(BUST), Risk, Name, Input Order |
| Location Inspector | Drawer with dominant risk drivers, decision guidance, OOD, stability |
| Scientific scope | WITHIN FROZEN BENCHMARK LEAD SCOPE (<=240h) or EXTENDED OPERATIONAL HORIZON (264-384h) |
| Cross-navigation | View on Spatial Map links to Day 27 view |

---

## 7. Abstention and Null Safety

Abstained locations display P(BUST)=N/A (never 0.0%), Risk=N/A (never LOW),
ABSTAINED badge, and reason codes (e.g., INVALID_LOCATION).

Manual API verification confirmed: Atlantis (invalid location) returned
bust_probability=null, abstain=True, reason_codes=[INVALID_LOCATION].
Null coercion to 0% or LOW: NEVER occurred.

---

## 8. Variable and Horizon Behavior

| Variable | Verified |
|---|---|
| temperature_2m | 24h, 240h, 264h, 384h |
| wind_speed_10m | 24h |
| surface_pressure | 24h |

| Lead Hours | Scientific Scope |
|---|---|
| <= 240h | FROZEN_BENCHMARK_LEAD_SCOPE |
| 264-384h | EXTENDED_OPERATIONAL_HORIZON |

Changing variable or horizon triggers real backend call - no frontend-only mutation.

---

## 9. Manual API Verification Results

Live backend at http://127.0.0.1:8000 (verified 2026-09-19):

wind_speed_10m @ 24h:
- Kolkata: P(BUST)=2.1% risk=LOW calib=CALIBRATED
- Delhi: P(BUST)=0.5% risk=LOW calib=CALIBRATED
- Mumbai: P(BUST)=0.3% risk=LOW calib=CALIBRATED
- Chennai: P(BUST)=11.7% risk=LOW calib=CALIBRATED

temperature_2m @ 240h: scope=FROZEN_BENCHMARK_LEAD_SCOPE
temperature_2m @ 264h: scope=EXTENDED_OPERATIONAL_HORIZON (correct boundary)
temperature_2m @ 384h: scope=EXTENDED_OPERATIONAL_HORIZON

Mixed (Kolkata + Atlantis + Delhi):
- Kolkata: P(BUST)=0.5% abstain=False
- Atlantis: P(BUST)=N/A abstain=True reason=INVALID_LOCATION
- Delhi: P(BUST)=0.5% abstain=False
- SUMMARY: total=3 avail=2 abstained=1

---

## 10. Regression Verification

| Suite | Before Day 28 | After Day 28 | Result |
|---|---|---|---|
| Backend (pytest) | 490 / 490 | 490 / 490 | PASS |
| Frontend (vitest) | 66 / 66 | 77 / 77 | PASS (+11 new) |
| Frontend production build | PASS | PASS | PASS |

All existing endpoints verified functional after Day 28.

---

## 11. Artifact Integrity

| Artifact | SHA256 | Status |
|---|---|---|
| models/v3/lightgbm_v3_challenger.joblib | 00A8410746F4A0E0ECBF7E76AAA0565143FC948D0E06AEA65E7BCC4CE28A1C660 | UNCHANGED |
| models/v3/probability_calibrator_v3.joblib | 9F448606CE4338DED92F238A551B3A9D8E6D2CB5902E8BC687BCE5F5850AF531 | UNCHANGED |
| Feature count | 50 | UNCHANGED |
| models/day4/ | N/A | UNTOUCHED |
| batch_verification_25.csv | N/A | LOCAL / UNTRACKED |

---

## 12. Scientific Limitations

1. Within Frozen Benchmark Lead Scope (<=240h) does NOT imply every live station is independently benchmark-certified.
2. Extended Operational Horizon (264-384h) not included in Day 22 certification.
3. No spatial interpolation: View shows only discrete evaluated stations.
4. Comparison is within current evaluated set only - not a general city quality ranking.
5. OOD diagnostics: Rule-based / heuristic. Not SHAP-based.

---

## 13. PPT / Demo Readiness

Feature Label: Multi-Location Reliability Monitoring

Safe Description:
Veyra compares forecast-reliability intelligence across multiple evaluated locations
using the same calibrated V3 serving pipeline.

Demo scenario:
- Select 25-station preset, click Refresh
- Show locations with calibrated P(BUST) and risk tiers
- Click a location to open diagnostic inspector
- Switch to 384h, show EXTENDED OPERATIONAL HORIZON label
- Navigate to Day 27 spatial map via cross-navigation button

---

## 14. Known Follow-Ups

1. A cold-start temperature_2m@24h request timed out during manual verification; subsequent requests succeeded. This is retained as a non-blocking operational observation.
2. Production build chunk size warning (642 KB JS) - optimization deferred.

---

## 15. Final Verdict

**DAY28_COMPLETE_AND_FROZEN**

| Gate | Result |
|---|---|
| Implementation | PASS |
| Backend regression 490/490 | PASS |
| Frontend tests 77/77 | PASS |
| Production build | PASS |
| Manual API verification | PASS |
| Scientific audit | PASS |
| Artifact integrity | PASS |
| Documentation | PASS |