# The Haystack — Technical Debt Register

> Last updated: 2026-03-29 (Epic 2.9 additions)  
> Severity: 🔴 P1 production blocker · 🟡 P2 quality · 🟢 P3 UX polish  
> Status: ✅ Done · 🔲 Parked · 🏃 Next up

---

## Infrastructure

| # | Item | Severity | Status | Notes |
|---|------|----------|--------|-------|
| I-1 | SQLite → PostgreSQL migration | 🟢 P3 | 🔲 Backburner | PythonAnywhere SQLite is fine for read-heavy public use. Migrate only if write contention or concurrent session locking actually occurs in production. Not a current blocker. |
| I-2 | `/api/v1/` Blueprint namespace | 🟡 P2 | ✅ Shipped | Epic 12 already specs a JSON endpoint (`GET /api/network/providers.json`). Establish the versioned namespace before that epic forces a retrofit. 3 seed endpoints: provider detail, program detail, search. |

---

## Data Layer & Performance

| # | Item | Severity | Status | Notes |
|---|------|----------|--------|-------|
| D-10 | Metric query optimization outside `ipeds_*` | 🟡 P2 | 🔲 Parked | As new datasets (ETPL, RAPIDS) merge, unified metrics queries might require materialized views rather than ON-THE-FLY joins. |
| D-11 | Soft-delete (`is_active` + `last_seen_in_source`) on Organization | 🔴 P1 | ✅ Shipped | Without this, closed institutions (e.g. dropped IPEDS unitids) stay live in Haystack indefinitely. Must ship before the next IPEDS data reload. Loader post-sweep marks unseen records inactive; UI shows a banner on inactive pages. |
| D-12 | `org_fact` EAV evidence table | 🔴 P1 | ✅ Shipped | Must exist before Phase 3 (IRS 990, H-1B) sources begin attaching data to Organization. Schema: `(org_id, fact_type, value_num, value_text, source, as_of_date)`. Prevents column sprawl; enables single-query Evidence tab. Fact types tracked as Python constants, not freeform strings. |
| D-13 | Pipeline DAG runner (`run_pipeline.py`) | 🟢 P3 | 🔲 Backburner | Build a topological-sort DAG runner when loader count reaches 7+. Not urgent now but plan during Phase 3 as BLS OEWS + 990 loaders land. |
| D-14 | Data diff logging on re-load | 🟢 P3 | 🔲 Backburner | When a loader re-runs with new year data, log a diff summary (N updated, M added, K unchanged, top changed fields). Invaluable for catching data quality issues and writing "What's New" content. |

---

## Analytics & Observability

| # | Item | Severity | Status | Notes |
|---|------|----------|--------|-------|
| A-1 | `page_view` table + `@app.before_request` logger | 🟡 P2 | ✅ Shipped | Log `(path, query_params, session_id, timestamp)`. Exclude `/static/` and `/admin/`. Queryable via `/admin/sqlite`. No visibility into what users actually look at without this. |
| A-2 | `search_event` table `(query_text, result_count, timestamp)` | 🟡 P2 | ✅ Shipped | Failed searches (result_count = 0) are the most actionable UX signal for a research tool. Required before public launch. |
| A-3 | `/admin/freshness` data freshness dashboard | 🟢 P3 | ✅ Shipped | `record_dataset_source()` is already called in every loader. This is 1 route + 1 template = ~45 min. Traffic-light grid: green < 30 days, yellow 30–90, red 90+. |

---

## Search

| # | Item | Severity | Status | Notes |
|---|------|----------|--------|-------|
| S-1 | Formal search scoring model (`HAYSTACK_SEARCH_SPEC.md`) | 🟡 P2 | ✅ Shipped | FTS5 is set up but there is no documented ranking spec. As entity types grow (OEWS, 311, 990), unscored results become chaotic. Spec: FTS5 rank × entity-type boost (providers > programs > occupations > employers). Freshness decay added when 311 data lands. |

---

## Testing & Quality

| # | Item | Severity | Status | Notes |
|---|------|----------|--------|-------|
| T-7 | Maintain >70% Test Coverage | 🔴 P1 | ✅ Current | Coverage successfully lifted over 70% in Phase 1 closing sprint. Must hold this line through Phase 2. |

---

## Phase 2 Readiness (Workforce Expansion)

| Item | Status | Notes |
|------|--------|-------|
| Epic 2.9: Pre-Phase-3 Hardening | ✅ Shipped | org_fact, soft-delete, API namespace, search spec, analytics tables |
| Epic 10: Non-Title IV Training Base | ✅ Shipped | ETPL, RAPIDS, Employers, Hubs all landed |
| Epic 11/11b: Workforce & O*NET | ✅ Shipped | Wage integration, skills, alternate titles, education levels |
| Epic 16: BLS Expansion | ✅ Shipped | 10-Yr Projections, NAICS Industry Matrix, QCEW Local Momentum |
| Epic 13: Briefing Builder | ✅ Shipped | Session-based collection tray, print export, HTMX nav counter |
| Epic 14: Stepping Stones | ✅ Shipped | Job Zone pathway segmentation, skill gap matrix, ROI break-even calculator |
| Epic 17: Employer-Occupation Link | ✅ Shipped | NAICS major employer data, 2-pass inferred occupation matching |
| Epic 19: Career Intelligence | ✅ Shipped | Career Grades, Remote/Automation Risk, `/outlook` dashboard |
| Epic 12: Network Explorer | 🔲 Next Up | `/network` page, Cytoscape.js, dual-mode CIP+SOC edges |
| Epic 15: Hidden Gems Engine | 🔬 Research Spike | Weighted SQL scoring + search intercept |
| Epic 20: Phase 3 Org Enrichment | 🔲 Planned | IRS 990, H-1B petition data, USASpending |
| Epic 21: Phase 4 Civic Signals | 🔲 Planned | 311, crime, permits, transit feeds |
| Epic 22: Phase 7 Multi-Region | 🔲 Future | Region switcher, `--region` flag on all loaders |

---

## Network Layer

| # | Item | Severity | Status | Notes |
|---|------|----------|--------|-------|
| N-1 | Pre-stored network edges in `Relationship` table | 🟢 P3 | 🔲 Backburner | V1 edges computed on-the-fly in `/api/v1/network/providers`. Fine for 75 nodes. When graph exceeds 100 nodes (Phase 6, with 990 + board member edges), build `loaders/load_network_edges.py` maintenance script to materialize `Relationship` rows with `rel_type` values from `RelationshipType` constants. |
| N-2 | `RelationshipType` constants class in `models.py` | 🟡 P2 | 🔲 Next Up | Only `"parent_org"` is in use. Ship a formal `RelationshipType` class before Epic 12 to prevent string drift across future loaders and APIs. |
