# The Haystack — Technical Debt Register

> Last updated: 2026-03-27 (post polish + IPEDS wiring sprint)  
> Severity: 🔴 P1 production blocker · 🟡 P2 quality · 🟢 P3 UX polish  
> Status: ✅ Done · 🔲 Parked

---

## Infrastructure

| # | Item | Severity | Status | Notes |
|---|------|----------|--------|-------|
| I-1 | SQLite → PostgreSQL migration | 🟢 P3 | 🔲 Backburner | PythonAnywhere SQLite is fine for read-heavy public use. Migrate only if write contention or concurrent session locking actually occurs in production. Not a current blocker. |
| I-2 | Flask-Caching (Redis or SimpleCache) | 🟡 P2 | ✅ Done 2026-03-27 | `SimpleCache` (in-process dict, no infra) added to `app.py`. TTL 24h — suitable since IPEDS ships annually. Upgrade path: swap `CACHE_TYPE` to `RedisCache` with `CACHE_REDIS_URL` if multiprocess hosting is needed. |

---

## Data Layer (`routes/providers.py`)

| # | Item | Severity | Status | Notes |
|---|------|----------|--------|-------|
| D-1 | Dual DB access layers (SQLAlchemy + raw sqlite3) | 🔴 P1 | ✅ Done 2026-03-27 | All three IPEDS helpers (`_get_ipeds_enrichment`, `_ipeds_outcome_measures`, `_ipeds_enrollment_demographics`) now use `db.engine.connect()` + SQLAlchemy `text()`. Removed raw `sqlite3` and `pathlib` imports. |
| D-2 | No query caching on IPEDS helpers | 🔴 P1 | ✅ Done 2026-03-27 | `@lru_cache(maxsize=256)` added to all three IPEDS helpers. 15-table JOIN only runs once per unique `unitid` per process. |
| D-3 | IPEDS dict keys inconsistently present | 🟡 P2 | ✅ Done 2026-03-27 | `_empty_ipeds()` helper seeds all ~30 keys as `None`. Templates use `is not none` safely everywhere — no more `UndefinedError` risk. |
| D-4 | `_get_ipeds_enrichment()` called twice per page load | 🟡 P2 | ✅ Done 2026-03-27 | Resolved by lru_cache (D-2). Second call from the Outcomes HTMX tab returns the memoized result at zero DB cost. |
| D-5 | UNITID input not validated before raw SQL | 🔴 P1 | ✅ Done 2026-03-27 | `_valid_unitid()` guard added — verifies value is a non-empty numeric string ≤8 digits before any SQL runs. |
| D-6 | `org_id` UUID not validated at route entry | 🔴 P1 | ✅ Done 2026-03-27 | `_UUID_RE` regex check added to `provider_detail()`. Non-UUID paths return clean 404 instead of a DB error. |
| D-7 | `completions` suppression ambiguity | 🟡 P2 | ✅ Done 2026-03-27 | `_empty_ipeds()` key names were mismatched (old stale names) causing `Undefined.__format__ TypeError` for providers with no IPEDS row. Fixed by aligning all keys to exactly what `_get_ipeds_enrichment()` writes (`instate_tuition`, `pt_undergrad`, `act_composite_75`, etc.). Real `NULL` vs suppressed distinction still deferred — but no crash now. |
| D-8 | `total_completions` with credential filter double-counts | 🟡 P2 | ✅ Done 2026-03-27 | Fixed in `providers_directory()` using `db.case()` — when `cred_filter` is active the aggregate only sums programs matching that credential type. Orgs with mixed credentials no longer show inflated totals. |
| D-9 | Scorecard `CREDLEV` mapping off-by-one error | 🔴 P1 | ✅ Done 2026-03-27 | `_credlev_for_credential_type()` in `routes/programs.py` previously mapped Bachelor's to `4` (Post-Bacc) and Associate's to `3` (Bachelor's), causing massive silently missed joins. Fixed by aligning to official Scorecard numeric taxonomy: `2` (Associate), `3` (Bachelor), `4` (Post-Bacc). |
---

## Routing & API

| # | Item | Severity | Status | Notes |
|---|------|----------|--------|-------|
| R-1 | `/providers/mock` dev route in production code | 🟡 P2 | ✅ Done 2026-03-27 | Route now guarded with `if not current_app.debug: abort(404)`. Import of `mock_data` is lazy and only attempted in debug mode. |
| R-2 | CIP filter silently accepts any string | 🟢 P3 | ✅ Done 2026-03-27 | `cip_filter` now validated as 1–2 digit numeric string before any DB query runs. Invalid, alpha, 6-digit, or SQL-injection values are silently discarded — directory renders unfiltered rather than crashing or returning phantom results. |

---

## Templates & Frontend

| # | Item | Severity | Status | Notes |
|---|------|----------|--------|-------|
| T-1 | Institution type badge used fragile in-template heuristic | 🟡 P2 | ✅ Done 2026-03-27 | `inst_type` now computed in `provider_detail()` route from `snapshot.top_credential`. Templates receive a clean pre-computed string. |
| T-2 | Sticky tab bar overlapped nav on mobile | 🟢 P3 | ✅ Done 2026-03-27 | `top: var(--nav-height, 56px)` applied. Tabs offset correctly below nav bar. |
| T-3 | Snapshot strip broke on narrow viewports | 🟢 P3 | ✅ Done 2026-03-27 | `@media (max-width: 640px)` collapses strip to 2-col, tabs get horizontal scroll. |
| T-4 | Expenditure section mislabeled as total spend | 🟢 P3 | ✅ Done 2026-03-27 | Label changed to "Selected Expenditure Categories (IPEDS Finance, FY 2022–23, in $000s — 3 of 8 categories)". |
| T-5 | No `<meta name="description">` on provider pages | 🟢 P3 | ✅ Done 2026-03-27 | `{% block meta_description %}` slot in `base.html`; `detail.html` injects org name + city + top credential. |
| T-6 | Automated test suite coverage | 🟡 P2 | 🔄 In progress | **185 tests pass** (up from ~155). Added `test_routes_providers.py` with 33 tests: provider directory (smoke, sort, pagination), CIP filter validation edge cases, cred filter accuracy, UUID validation, `_valid_unitid()` unit tests (9 cases). Coverage at ~58%; target 70% requires adding more IPEDS helper fixture tests and outcomes tab coverage. |

---

## Phase 2 Readiness

| Item | Status | Notes |
|------|--------|-------|
| College Scorecard median earnings | ✅ Done 2026-03-27 | Integration complete: 6yr/10yr and FoS tabs live |
| BLS OEWS wage data by SOC | 🔲 Not started | Links programs → wage outcomes |
| Guided Search (workforce need → provider) | 🔲 Stub only | Major Epic 9 feature |
| Compare tool (side-by-side providers) | ✅ Done | Compare tool shipped in Epic 6 |
| Program-level Scorecard linkage | ✅ Done 2026-03-27 | `_scorecard_fos_for_program` logic active |
| Regional labor market briefings | 🔲 Not started | Epic 6 feature |
| PostgreSQL migration | 🔲 Not started | See I-1 above |
| Flask-Caching setup | 🔲 Not started | See I-2 above |

---

## Resolved — Session 2026-03-27

All items marked ✅ were completed during the post-polish tech debt sprint. Key highlights:

- **Unified DB access**: Dropped all `sqlite3.connect()` raw connections. All IPEDS reads now go through `db.engine` (SQLAlchemy), sharing the same connection pool as ORM queries.
- **Full lru_cache coverage**: All three IPEDS helper functions memoized. Heavy 15-table JOIN only executes once per `unitid` per process lifetime.
- **Defensive IPEDS dict**: `_empty_ipeds()` seeds 30+ keys as `None` — safely eliminates all Jinja2 `UndefinedError` surface area.
- **Input hardening**: UUID regex for `org_id`, numeric validation for `UNITID` in all raw SQL paths.
- **Mobile responsiveness**: Two CSS breakpoints added for snapshot strip and sticky tabs.
