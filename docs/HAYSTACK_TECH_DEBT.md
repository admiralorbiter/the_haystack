# The Haystack — Technical Debt Register

> Last updated: 2026-03-28 (Phase 1 soft reset)  
> Severity: 🔴 P1 production blocker · 🟡 P2 quality · 🟢 P3 UX polish  
> Status: ✅ Done · 🔲 Parked · 🏃 Next up

---

## Infrastructure

| # | Item | Severity | Status | Notes |
|---|------|----------|--------|-------|
| I-1 | SQLite → PostgreSQL migration | 🟢 P3 | 🔲 Backburner | PythonAnywhere SQLite is fine for read-heavy public use. Migrate only if write contention or concurrent session locking actually occurs in production. Not a current blocker. |

---

## Data Layer & Performance

| # | Item | Severity | Status | Notes |
|---|------|----------|--------|-------|
| D-10 | Metric query optimization outside `ipeds_*` | 🟡 P2 | 🔲 Parked | As new datasets (ETPL, RAPIDS) merge, unified metrics queries might require materialized views rather than ON-THE-FLY joins. |

---

## Testing & Quality

| # | Item | Severity | Status | Notes |
|---|------|----------|--------|-------|
| T-7 | Maintain >70% Test Coverage | 🔴 P1 | ✅ Current | Coverage successfully lifted over 70% in Phase 1 closing sprint. Must hold this line through Phase 2. |

---

## Phase 2 Readiness (Workforce Expansion)

| Item | Status | Notes |
|------|--------|-------|
| Epic 10: Non-Title IV Training Base | 🏃 Next Up | Add ETPL, RAPIDS, WEAMS data into root schema |
| Epic 11: BLS OEWS Wage Integration | 🔲 Not started | Map SOCs to wage metrics |
| Epic 12: Network Explorer | 🔲 Not started | Graph UI for relationships |
