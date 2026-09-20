# Day 34 — Time Contract + Durable Revision Store Foundation (Gate C4 Part 1)

**Phase**: 3 — Scientific Integration & Quality Gates
**Gates Addressed**: Gate C4 Part 1 (Formal Time Contract & Durable Revision Store Foundation)
**Status**: COMPLETE, VERIFIED & FROZEN
**Starting Main SHA**: `780369f3b9a69875ac07fef5ab3fd0b61b7c5d4c`

---

## 1. Overview & Objectives

Day 34 formalizes and locks two critical temporal and persistence foundations:
1. **Formal Time Contract**: Establishes strict UTC normalization, ISO 8601 formatting, and explicit derivation of forecast lead times via the primary invariant $\text{lead\_hours} = \text{valid\_time} - \text{issue\_time}$. Enforces whole-hour validation, non-negative/strictly positive lead times ($\ge 1\text{h}$), and safe horizon bounds ($1\text{h} \le \text{lead} \le 384\text{h}$).
2. **Durable Revision Store Foundation**: Introduces an SQLite-backed persistent, idempotent, and chronologically ordered storage engine for real weather forecast issue-cycle runs, strictly preventing request-manufactured history while enabling true multi-run revision analysis.

---

## 2. Scientific Governance Principles

### Separation of Core Concepts
1. **Calibrated P(BUST)**: Isotonic probability calibration assessing the likelihood of forecast failure ($e > q_{95}$).
2. **Scientific Certification (Gate C1)**: Frozen benchmark boundary restricted to 25 synoptic stations, 3 core variables, and $\le 240\text{h}$ lead time.
3. **Extended Operational Horizon**: Forecast leads from $264\text{h}$ to $384\text{h}$ supported for operational inference, but strictly excluded from frozen scientific certification.
4. **Day 30 Historical Honesty Rule**: Repeated process requests or client-supplied timestamps **never manufacture** revision history. When no prior comparable durable run exists, responses honestly return `INSUFFICIENT_HISTORY` (`REVISION_HISTORY_UNAVAILABLE`).
5. **Durable Identity**: Revision records are keyed by `(canonical_location, variable, valid_time, issue_time, provider_source)`. Duplicate ingestions of the same run are strictly idempotent.
6. **Previous Selection Chronology**: Previous comparable revisions are selected strictly by issue-cycle chronology ($\text{issue\_time} < \text{current\_issue\_time}$ ordered by $\text{issue\_time}\ \text{DESC}\ \text{LIMIT}\ 1$), not by insertion order or request count.
7. **Delta Convention**: Signed changes are defined as $\text{CURRENT} - \text{PREVIOUS}$.

---

## 3. Implementation Details

### Time Contract
- **Module**: `backend/app/core/time_contract.py`
- **Normalization**: ISO 8601 UTC strings (`%Y-%m-%dT%H:%M:%SZ`).
- **Validation**:
  - `valid_time > issue_time` (strictly positive lead time).
  - Derived lead must be a whole integer hour.
  - $1 \le \text{lead\_hours} \le 384$.
  - $\text{lead\_hours} \le 240$ designated as certified benchmark horizon; $264\text{h} \le \text{lead\_hours} \le 384\text{h}$ as extended operational horizon.

### Durable Revision Store
- **Module**: `backend/app/core/revision_store.py`
- **Storage Engine**: SQLite with WAL journaling and isolated database support.
- **Unique Constraint**: `UNIQUE (canonical_location, variable, valid_time, issue_time, provider_source)`.
- **Failure Resilience**: Connection errors or database corruptions fail gracefully to `False`/`None`/`[]` without crashing prediction workflows or fabricating fake history.
- **Test Isolation**: Supports `:memory:` and dedicated isolated temporary databases.

### Revision Service Integration
- **Module**: `backend/app/services/revision_service.py`
- **Workflow**:
  1. Resolves canonical location (unifying aliases like `Goa` $\rightarrow$ `Panaji`).
  2. Validates temporal targets and derives exact lead horizon.
  3. Queries `RevisionStore` for preceding comparable issue cycles.
  4. Runs V3 inference pipeline.
  5. On success with prior history: returns `RevisionStatus.AVAILABLE` with `TrajectoryDiagnostics` ($\text{CURRENT} - \text{PREVIOUS}$), ensemble drift, and chronological trajectory points.
  6. On success without prior history: returns `RevisionStatus.INSUFFICIENT_HISTORY` with null historical deltas and `history_is_durable = False`.
  7. On abstention: returns `RevisionStatus.ABSTAINED` without persisting invalid records.

---

## 4. Verification Results

- **Focused Day 34 Tests**: 26 passed (`backend/tests/test_day34_time_contract_revision_store.py`)
- **Targeted Cross-Day Suite**: 102 passed across Days 30, 32, 33, and 34
- **Full Backend Suite**: 581 passed (0 failed, 0 errors)
- **Frontend Unit Suite**: 100 passed across 9 test files
- **Frontend Production Build**: Built cleanly with zero errors in 18.29s.
- **Artifact Integrity**:
  - Model SHA-256: `00a8410746f4a0eecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660`
  - Calibrator SHA-256: `9f448606ce4338ded92f238a551b3a9d8e6d2cb5902e8bc687bce5f5850af531`
  - Feature Count: 50 ordered features
  - Certified Stations: Exactly 25 frozen synoptic stations
