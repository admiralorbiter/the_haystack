# The Haystack — Technical Debt Register

> Last updated: 2026-03-29 (Epic 2.9 additions)  
> Severity: 🔴 P1 production blocker · 🟡 P2 quality · 🟢 P3 UX polish  
> Status: ✅ Done · 🔲 Parked · 🏃 Next up

---

## Infrastructure

| # | Item | Severity | Status | Notes |
|---|------|----------|--------|-------|
| I-1 | SQLite → PostgreSQL migration | 🟢 P3 | 🔲 Backburner | PythonAnywhere SQLite is fine for read-heavy public use. Migrate only if write contention or concurrent session locking actually occurs in production. Not a current blocker. |
| I-2 | `/api/v1/` Blueprint namespace | 🟡 P2 | 🔲 Epic 2.9 | Epic 12 already specs a JSON endpoint (`GET /api/network/providers.json`). Establish the versioned namespace before that epic forces a retrofit. 3 seed endpoints: provider detail, program detail, search. |

---

## Data Layer & Performance

| # | Item | Severity | Status | Notes |
|---|------|----------|--------|-------|
| D-10 | Metric query optimization outside `ipeds_*` | 🟡 P2 | 🔲 Parked | As new datasets (ETPL, RAPIDS) merge, unified metrics queries might require materialized views rather than ON-THE-FLY joins. |
| D-11 | Soft-delete (`is_active` + `last_seen_in_source`) on Organization | 🔴 P1 | 🔲 Epic 2.9 | Without this, closed institutions (e.g. dropped IPEDS unitids) stay live in Haystack indefinitely. Must ship before the next IPEDS data reload. Loader post-sweep marks unseen records inactive; UI shows a banner on inactive pages. |
| D-12 | `org_fact` EAV evidence table | 🔴 P1 | 🔲 Epic 2.9 | Must exist before Phase 3 (IRS 990, H-1B) sources begin attaching data to Organization. Schema: `(org_id, fact_type, value_num, value_text, source, as_of_date)`. Prevents column sprawl; enables single-query Evidence tab. Fact types tracked as Python constants, not freeform strings. |
| D-13 | Pipeline DAG runner (`run_pipeline.py`) | 🟢 P3 | 🔲 Backburner | Build a topological-sort DAG runner when loader count reaches 7+. Not urgent now but plan during Phase 3 as BLS OEWS + 990 loaders land. |
| D-14 | Data diff logging on re-load | 🟢 P3 | 🔲 Backburner | When a loader re-runs with new year data, log a diff summary (N updated, M added, K unchanged, top changed fields). Invaluable for catching data quality issues and writing "What's New" content. |

---

## Analytics & Observability

| # | Item | Severity | Status | Notes |
|---|------|----------|--------|-------|
| A-1 | `page_view` table + `@app.before_request` logger | 🟡 P2 | 🔲 Epic 2.9 | Log `(path, query_params, session_id, timestamp)`. Exclude `/static/` and `/admin/`. Queryable via `/admin/sqlite`. No visibility into what users actually look at without this. |
| A-2 | `search_event` table `(query_text, result_count, timestamp)` | 🟡 P2 | 🔲 Epic 2.9 | Failed searches (result_count = 0) are the most actionable UX signal for a research tool. Required before public launch. |
| A-3 | `/admin/freshness` data freshness dashboard | 🟢 P3 | 🔲 Easy win | `record_dataset_source()` is already called in every loader. This is 1 route + 1 template = ~45 min. Traffic-light grid: green < 30 days, yellow 30–90, red 90+. |

---

## Search

| # | Item | Severity | Status | Notes |
|---|------|----------|--------|-------|
| S-1 | Formal search scoring model (`HAYSTACK_SEARCH_SPEC.md`) | 🟡 P2 | 🔲 Epic 2.9 | FTS5 is set up but there is no documented ranking spec. As entity types grow (OEWS, 311, 990), unscored results become chaotic. Spec: FTS5 rank × entity-type boost (providers > programs > occupations > employers). Freshness decay added when 311 data lands. |

---

## Testing & Quality

| # | Item | Severity | Status | Notes |
|---|------|----------|--------|-------|
| T-7 | Maintain >70% Test Coverage | 🔴 P1 | ✅ Current | Coverage successfully lifted over 70% in Phase 1 closing sprint. Must hold this line through Phase 2. |

---

## Phase 2 Readiness (Workforce Expansion)

| Item | Status | Notes |
|------|--------|-------|
| Epic 2.9: Pre-Phase-3 Hardening | 🏃 Next Up | org_fact, soft-delete, API namespace, search spec, analytics tables |
| Epic 10: Non-Title IV Training Base | ✅ Shipped 2026-03-28 | ETPL, RAPIDS, Employers, Hubs all landed |
| Epic 11: BLS OEWS Wage Integration | 🔲 Planned | Map SOCs to wage metrics — do after Epic 2.9 |
| Epic 12: Network Explorer | 🔲 Planned | Graph UI for relationships |
