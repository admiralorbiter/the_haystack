# The Haystack — Epics & Task List

**Stack:** Flask / SQLite / SQLAlchemy / Jinja2 / htmx
**Mode:** Solo developer
**Honest timeline note:** The master plan's 6-week estimate assumes parallel work. Solo, expect 14–18 weeks to reach a stable IPEDS V1. The sequence below is designed to produce working software at each epic boundary — not just progress.

---

## Epic 0 — Foundation shell
**Goal:** A running Flask app with the shared UI shell, reusable templates, and mock data. Nothing real yet. You should be able to render any entity page with fake data before touching IPEDS.

**Exit criteria:** A provider detail page renders correctly from a Python dict. No database required yet.

**Effort estimate:** 1–2 weeks

### Tasks

#### App skeleton
- [x] `app.py` with Flask app factory and blueprint registration
- [x] `routes/` directory with one stub file per entity: `providers.py`, `programs.py`, `fields.py`, `map.py`, `compare.py`
- [x] Environment config (`config.py` or `.env`) with DB path, debug flag, secret key

#### Base template (`base.html`)
- [x] Top nav: Search | Explore | Map | Compare | Collections | Methods
- [x] Universal search box (stub — no logic yet)
- [x] Breadcrumb component
- [x] Page-level compare tray (stub)
- [x] Evidence/methods drawer (stub — right side or bottom sheet)
- [x] Data freshness badge component (Jinja macro)
- [x] Footer with source attribution area

#### Shared Jinja components (as macros or includes)
- [x] `stat_card(label, value, unit, caveat)` — single metric card
- [x] `stat_strip(metrics_list)` — row of 4–6 stat cards
- [x] `tab_bar(tabs, active)` — tab navigation
- [x] `filter_chips(filters)` — chip row with active state
- [x] `entity_badge(type)` — type badge (Provider, Program, etc.)
- [x] `data_freshness_badge(date, source)` — "Data as of X from Y"
- [x] `empty_state(message, suggestion)` — zero-result UI
- [x] `skeleton_row()` — loading placeholder

#### Signature feature stubs (scaffold early, build later)
These are hooks, not full implementations. Add the DOM elements and stub routes NOW so they're architectural, not bolted on later.
- [x] **Inverse Search stub** — add a `?mode=guided` query parameter stub to `/search`; add a `routes/guided_search.py` file with a comment block describing the intent
- [x] **Ecosystem/Network View stub** — on the provider directory, add a view toggle button (List | Map | Network) that currently shows an empty placeholder panel for the Network view
- [x] **Briefing Builder stub** — add a ★ "Save to Briefing" icon to the stat card macro that does nothing yet (renders but has no handler); add `routes/briefing.py` stub

#### CSS foundation
- [x] CSS custom properties: colors, spacing, type scale, border radius
- [x] Card component styles
- [x] Tab bar styles
- [x] Filter chip styles
- [x] Badge styles
- [x] Responsive grid (2-col, 1-col on mobile)
- [x] Empty state styles

#### Mock data smoke test
- [x] One `/providers/mock` route returning a hardcoded provider dict
- [x] Provider detail template renders all tabs from mock data without errors
- [x] Mobile layout readable (check at 375px)

---

## Epic 1 — Database and schema
**Goal:** SQLite schema defined, migration script written, all core tables exist. No data loaded yet.

**Exit criteria:** `python db/init_db.py` creates a valid empty database. Schema matches entity model in the PRD.

**Effort estimate:** 3–5 days

### Tasks

#### Schema
- [x] `geo_area` table — geoid, name, type (zip/tract/county/metro), state, county_fips, lat, lon
- [x] `organization` table — org_id (uuid), name, org_type, city, state, county_fips, lat, lon, website, unitid (nullable), ein (nullable)
- [x] `program` table — program_id (uuid), org_id (fk), name, credential_type, cip (6-digit), modality, completions, duration_weeks (nullable)
- [x] `occupation` table — soc (7-digit), title, soc_major, soc_minor
- [x] `program_occupation` table — program_id, soc, confidence, source
- [x] `civic_signal` table — signal_id, type, geoid, lat, lon, occurred_at, status, source
- [x] `relationship` table — rel_id, from_entity_type, from_entity_id, to_entity_type, to_entity_id, rel_type, weight, confidence, source, valid_from, valid_to  *(empty in V1, ready for Phase 6)*
- [x] `org_alias` table — org_id (fk), source, source_id, source_name  *(deduplication anchor — maps external IDs to one canonical org_id)*
- [x] `dataset_source` table — source_id, name, version, url, loaded_at, record_count, notes
- [x] `region` table — region_id, name, slug, default_lat, default_lon, default_zoom
- [x] `region_county` table — region_id, county_fips, county_name, state — seeded with KC MSA

#### Infra
- [x] `models.py` — SQLAlchemy declarative models for all tables
- [x] Alembic setup (`alembic init migrations`) to manage schema changes
- [x] `db/seed.py` — Seeds `geo_scope` and runs print success
- [x] `db/connection.py` — SQLAlchemy session maker and Flask app teardown hook
- [x] Basic indexes: `organization(county_fips)`, `program(org_id)`, `program(cip)`, `program_occupation(program_id)`

#### QA
- [x] Running init_db twice does not error (idempotent)
- [x] All foreign keys defined
- [x] `PRAGMA foreign_keys = ON` set on every connection

---

## Epic 2 — IPEDS data pipeline
**Goal:** IPEDS institutions and programs loaded into the database for all KC MSA counties. CIP→SOC crosswalk loaded.

**Exit criteria:** SQL queries return real KC provider and program records. Row count logged.

**Effort estimate:** 2–3 weeks (IPEDS is messier than it looks)

**Status: ✅ COMPLETE** — Shipped 2026-03-26

**What shipped:**
- 38 KC MSA training institutions loaded (IPEDS HD 2024)
- 1,132 programs with human-readable names ("CIP Title — Credential Level", Option B)
- 867 occupations + 5,119 program→occupation links (CIP→SOC crosswalk 2020)
- Idempotent, additive pipeline covering 2014–2024 (11 years downloadable)
- 35 tests, all passing
- QA script with automated checks on FK integrity, deduplication, and coverage
- Retro complete, doc drift fixed, process lessons logged in collab guide

### Tasks

#### Understand the source files
- [x] Download IPEDS HD (institution directory) for most recent complete year
- [x] Download IPEDS C (completions by CIP) for same year
- [x] Download IPEDS IC (institutional characteristics) for credential types
- [x] Download CIP→SOC crosswalk (NCES — CIP 2020 / SOC 2018)
- [x] Review column names, null patterns, suppression markers

#### Loader: institutions (`loaders/load_ipeds_institutions.py`)
- [x] Accept `--region` flag and look up county FIPS from `region_county` table
- [x] Filter IPEDS to institutions in those counties
- [x] Map IPEDS columns → `organization` schema
- [x] Set `org_type = 'training'`
- [x] Upsert on `unitid` (update if exists, insert if not)
- [x] Write `unitid` to `org_alias` table with `source='ipeds'` — all future sources must resolve through this table before creating a new org
- [x] Record `dataset_source` row on completion
- [x] Log: institutions loaded, skipped, failed

#### Loader: programs (`loaders/load_ipeds_programs.py`)
- [x] Join completions file to institution by `unitid`
- [x] Filter to KC institutions only
- [x] Normalize CIP to 6-digit string (pad if needed)
- [x] Map credential level codes to human labels (e.g. `5` → "Bachelor's degree", `20` → "Certificate (sub-baccalaureate, < 1 year)")
- [x] Handle suppressed completions (value = `.` or blank) → store as NULL
- [x] Upsert on `(org_id, cip, credential_type)` composite
- [x] Log: programs loaded, suppressed, failed

#### Deduplication rule (applies to every loader, forever)
> **Before inserting any organization, check `org_alias` for the incoming source ID.**
> If found → update existing org record, do not create a duplicate.
> If not found → create org, then write alias row.
> This ensures one canonical `org_id` per real-world entity across all data sources.

#### Loader: CIP→SOC crosswalk (`loaders/load_cip_soc.py`)
- [x] Load crosswalk file (sheet `"CIP-SOC"` — must specify explicitly)
- [x] Populate `occupation` table (SOC codes + titles)
- [x] Populate `program_occupation` with confidence=1.0 for direct matches
- [x] Log: occupation records, links created
- [x] Pipeline runs CIP→SOC twice: Phase 1 before programs (occupation table), Phase 2 after programs (links)

#### QA scripts
- [x] `qa/check_ipeds.py` — prints: institution count by county, program count, null completions rate, CIP coverage, dedup integrity
- [x] At least one institution per core KC MSA county (rural fringe counties are WARN not FAIL)
- [x] No duplicate unitids in organization table
- [x] All programs have a valid org_id foreign key

#### Epic 2.5 — Thin admin UI + Raw Data Explorer

**Status: ✅ COMPLETE** — Shipped 2026-03-26

**What shipped:**
- Admin dashboard (`/admin`) with live row counts (38 orgs, 1,132 programs, 867 occupations, 5,119 links), dataset source audit log, and HTMX loader runner buttons streaming stdout into a `<pre>` block.
- Raw data explorer (`/admin/data/<table_slug>`) for all 4 core tables — paginated (50 rows/page), sortable via column header clicks (query-param driven, no JS), empty state on zero rows.
- Whitelist security pattern on both table slugs and loader names — unknown slugs → 404.
- Lightweight `base_admin.html` shell (no main nav, amber "Admin Mode" banner, back-to-site link).
- 15 new route tests covering happy path, edge cases (empty DB, out-of-range page, invalid sort col), and error paths (invalid slug, SQL injection slug).
- Fixed pre-existing `pyproject.toml` coverage scope bug (`--cov=.` → scoped to `routes/models/db/loaders`).

##### Admin dashboard (`/admin`)
- [x] `routes/admin.py` blueprint — `/admin` route, no auth (local dev only)
- [x] Table showing all `dataset_source` rows (name, loaded_at, record_count)
- [x] Live row counts per core table (`organization`, `program`, `occupation`, `program_occupation`)
- [x] HTMX action to re-run a named loader via `POST /admin/run/<loader_name>` — streams stdout to a `<pre>` block

##### Raw data explorer (`/admin/data/<table>`)
- [x] Route accepts a `<table>` slug: `organizations`, `programs`, `occupations`, `program-occupations`
- [x] Paginated table view (50 rows/page) showing all columns for the selected table
- [x] Basic sort by clicking column header (query param driven — no JS required)
- [x] Row count + pagination controls (Prev / Next)
- [x] Shared admin layout — no main nav, clear "Admin only" label
- [x] Link back to `/admin` dashboard from every data table page


---

## Epic 3 — Provider directory and detail
**Goal:** Real, working provider pages backed by IPEDS data. The first thing a user can actually use.

**Exit criteria:** `/providers` lists KC institutions with working filters. `/providers/<id>` renders all tabs with real data and no crashes.

**Effort estimate:** 1.5–2 weeks

**Status: ✅ COMPLETE** — Shipped 2026-03-26

**What shipped:**
- Provider directory (`/providers`) with county and credential type filters, text search, and sorts.
- Provider detail page (`/providers/<id>`) with HTMX-powered deferred tab loading for performance.
- Snapshot strip featuring real data metrics (Programs, Award Completions, Top Credential, Top CIP Family, Linked Occupations) and a stub for Scorecard metrics.
- Connections Tab: Advanced SQL self-joins to find similar providers by CIP overlap, and Occupation Links resolving CIP to SOC codes in real-time.
- CSS foundation for the "Premium Civic-Tech" aesthetic: glassmorphism, responsive tables, pill-shaped filters, and clean tab navigation.
- Data Provenance tracking via `dataset_source`.

### Tasks

#### Provider directory (`/providers`)
- [x] SQLAlchemy query: list organizations where org_type='training', join program counts and total completions
- [x] Filters: county, credential type (via program join), CIP family (2-digit prefix), completions band
- [x] Sort: completions desc (default), program count, alphabetic
- [x] Search: LIKE on organization name (or SQLite FTS if already set up)
- [x] URL-synced filter state (query params)
- [x] Result count shown ("34 providers")
- [x] Card/list toggle (start with one, add toggle later)
- [x] **Network view toggle:** List | Map | ~~Network~~ (Network shows a "Coming soon" panel — the toggle exists from day one so Epic 11 is a swap, not a redesign)
- [x] Empty state if filters return zero results
- [x] Pagination or limit (50 per page is fine for V1)

#### Provider detail (`/providers/<id>`)
- [x] Route: fetch organization + aggregate metrics in one query
- [x] Snapshot strip: program count, total completions, top credential type, top CIP family, linked occupation count, Scorecard coverage
- [x] Tab: Overview — provider summary, top 5 programs by completions, CIP family breakdown
- [x] Tab: Connections — linked occupations via CIP→SOC (ranked by program count), similar providers by CIP overlap
- [x] Tab: Geography — static map pin (lat/lon), county label, nearby context (placeholder for Phase 4)
- [x] Tab: Outcomes — completions table by CIP; Scorecard placeholder ("Scorecard data coming in Phase 2")
- [x] Tab: Evidence — unitid, data source name, loaded_at date
- [x] Tab: Methods — completions definition, CIP/SOC caveat text, suppression note
- [x] Data freshness badge visible in header
- [x] **Briefing Builder:** every stat card in the snapshot strip has a ★ button (wired to HTMX `POST /briefing/add` — returns 200 in V1 as a placeholder response)
- [x] 404 if org_id not found or org_type != 'training'
- [x] Empty states: no programs, no occupation links, no completions data

#### Performance
- [x] No N+1 queries — all tab data fetched in batched queries, not per-row
- [x] Provider detail renders in < 300ms on local SQLite

---

## Epic 4 — Program directory and detail
**Goal:** Programs browsable independently of providers. Users can find a specific certificate type without knowing which school offers it.

**Exit criteria:** `/programs` lists all KC programs with working filters and FTS5 search. `/programs/<id>` renders without errors.

**Effort estimate:** 1–1.5 weeks (template and query patterns already established)

**Status: ✅ COMPLETE** — Shipped 2026-03-26

**What shipped:**
- Program directory (`/programs`) with FTS5 search (porter tokenizer + org_name denormalization), credential type / CIP family / completions band / provider filters, sortable results table, compare checkbox stub, pagination (50/page).
- Program detail page (`/programs/<id>`) with HTMX-powered deferred tab loading identical to Provider pattern.
- Snapshot strip: Field, CIP Code (monospace), Annual Completions, Credential, Linked Occupations.
- Tab: Overview — program details, provider card with Visit Institution link, top 5 occupation links preview, "Similar Programs in KC" table (same CIP family, different providers, sorted by completions).
- Tab: Occupation Links — all linked SOC occupations with confidence pills (green/amber/red) and wage placeholder for Phase 2.
- Tab: Outcomes — completions value or suppression notice block; Scorecard Phase 2 placeholder.
- Tab: Geography — provider location + map pin placeholder (Epic 7).
- Tab: Methods — CIP taxonomy, CIP↔SOC crosswalk explanation, suppression definition, data currency.
- FTS5 Alembic migration (`a3f7e8b2c1d5`) with INSERT/UPDATE/DELETE sync triggers and org_name denormalization.
- Compare checkbox stub on every program row (disabled, ready for Epic 6).
- Programs nav link wired in base.html.
- data-href row navigation pattern (no onclick Jinja/JS conflicts).
- 30+ new tests (directory: happy path, empty DB, 5 filters, 3 sorts, pagination; detail: happy path, 404s, suppressed, SQL injection; 8 HTMX tab fragment tests).
- Fixed pre-existing `load_cip_titles()` bug: explicit path miss no longer falls back to crosswalk silently.
- 98 tests, all passing.

#### Program FTS5 Architecture
- [ ] Create Alembic migration for `program_fts` virtual table using SQLite FTS5.
- [ ] Configure `program_fts` to use the `porter` stemming tokenizer (matches "nursing" to "nurse") to avoid `trigram` compatibility issues.
- [ ] Add `INSERT`, `UPDATE`, `DELETE` triggers to `program` and `organization` tables to keep the FTS index automatically synchonized without pipeline logic changes.
- [ ] Map `program_fts` in `models.py` for SQLAlchemy `MATCH` queries.

#### Program directory (`/programs`)
- [ ] SQLAlchemy query: list programs with org name, credential type, CIP label, completions, occupation link count
- [ ] Filters: credential type, CIP family, provider (org_id), completions band
- [ ] Sort: completions desc (default), provider alphabetic, credential type
- [ ] Search: FTS5 query matching program title, institution name, and CIP code.
- [ ] URL-synced filter state
- [ ] Standardized `empty_state` UI usage

#### Program detail (`/programs/<id>`)
- [ ] Snapshot strip: provider name, credential type, CIP code + label, completions, linked occupation count, Scorecard available (yes/no)
- [ ] Base shell route + HTMX lazy-loading architecture identical to Providers.
- [ ] Tab: Overview — short descriptor, provider card (name, city, link), award level, CIP family context
- [ ] Tab: Occupation links — related occupations ranked by confidence, SOC code shown, wage/demand placeholder
- [ ] Tab: Outcomes — completions value; suppression note if NULL; Scorecard placeholder
- [ ] Tab: Geography — provider map pin
- [ ] Tab: Methods — CIP/SOC mapping explanation, completions definition
- [ ] 404 handling

---

## Epic 5 — Field of Study (CIP) pages
**Goal:** A bridge between program inventory and workforce relevance. Users can browse by field, not just by school or program name.

**Exit criteria:** `/fields` lists CIP families. `/fields/<cip>` shows all providers and programs in that field with occupation links.

**Effort estimate:** 1 week

### Tasks

#### Field directory (`/fields`)
- [ ] Group programs by 2-digit CIP family
- [ ] Show: CIP family label, provider count, total completions, top credential type
- [ ] Sort: completions desc

#### Field detail (`/fields/<cip>`)
- [ ] Works for both 2-digit (family) and 6-digit (specific CIP)
- [ ] Snapshot strip: providers offering, total completions, credential mix, linked occupations, top counties
- [ ] Sections: provider list, top programs, linked occupations
- [ ] Empty state: no programs in this CIP in KC region

---

## Epic 6 — Compare
**Goal:** Side-by-side comparison is what turns a directory into a decision tool.

**Exit criteria:** `/compare/providers?ids=A,B` renders a working 2-column comparison. Same for programs.

**Effort estimate:** 1 week

### Tasks

#### Provider compare
- [ ] Route accepts comma-separated org_ids (max 2 for V1)
- [ ] Fetch both providers' full metrics in one query
- [ ] Same row order for both: programs, completions, top CIP, linked occupations, credential mix
- [ ] Visual indicator for higher/lower value (badge or arrow icon)
- [ ] "Add to compare" button on provider cards and detail pages
- [ ] Compare tray (sticky, shows up to 2 queued providers)
- [ ] Methods row at bottom of comparison

#### Program compare
- [ ] Route accepts program_ids
- [ ] Same pattern as provider compare
- [ ] Rows: provider, credential type, CIP, completions, occupation links

---

## Epic 7 — Map
**Goal:** Spatial discovery of providers. Simple, clustered, filterable. Not overwhelming.

**Exit criteria:** `/map` shows provider pins clustered, filterable by credential type or CIP family. Clicking a pin shows a summary card with a link to the detail page.

**Effort estimate:** 1–1.5 weeks

### Tasks

#### Map route
- [ ] `/map` renders map page with provider GeoJSON endpoint
- [ ] `/api/map/providers.geojson` — returns filtered provider points (lat, lon, name, org_id, top credential, completions)
- [ ] GeoJSON clustered server-side or client-side (Leaflet.markercluster is the simplest option)

#### Map frontend
- [ ] Leaflet.js (CDN) — lightweight, no build step
- [ ] Cluster providers by zoom level
- [ ] Filter controls: credential type, CIP family (same chips as directory)
- [ ] Click opens popup: name, city, completions, "View provider →" link
- [ ] Default map center: KC (39.0997° N, -94.5786° W), zoom 10
- [ ] Empty state if filters return no providers

#### Avoid in V1
- [ ] No choropleth overlays
- [ ] No travel time rings
- [ ] No civic signal overlays

---

## Epic 8 — Search
**Goal:** Global grouped search across providers, programs, and fields. Returns entity-typed results, not raw rows.

**Exit criteria:** Typing a query in the nav search box returns grouped results (Providers, Programs, Fields) with type badges.

**Effort estimate:** 1 week

### Tasks
- [ ] `/search?q=<query>` route
- [ ] SQLite FTS5 virtual tables for organization.name and program.name (or fallback LIKE)
- [ ] Results grouped by entity type
- [ ] Each result card: title, type badge, 1–2 metrics, link to detail page
- [ ] Max 5 results per group in quick search; "Show all" links to filtered directory
- [ ] Empty state: "No results for X — try browsing providers or programs"

---

## Epic 9 — Methods, freshness, and quality pass
**Goal:** Every page has data freshness, methods text, and clear caveats. This is the difference between a prototype and something you can show people.

**Exit criteria:** Every entity page passes the ship checklist from `HAYSTACK_DATASET_ONBOARDING_TEMPLATE.md`.

**Effort estimate:** 3–5 days

### Tasks
- [ ] Methods text written for: IPEDS completions, CIP definition, CIP→SOC crosswalk, suppression handling
- [ ] Data freshness badge populates from `dataset_source` table on every page
- [ ] Empty states reviewed for: zero programs, zero completions, zero occupation links, zero compare items
- [ ] Mobile layout pass on all 4 primary screens (directory, detail, compare, map)
- [ ] Performance check: no query over 500ms on local SQLite
- [ ] No page with more than 6 snapshot metrics
- [ ] No page with a custom layout not in the shared shell

---

## Deferred to Phase 2+

| Feature | Phase |
|---|---|
| College Scorecard outcomes | 2 |
| Occupation detail pages | 2 |
| Provider→sector connections | 2 |
| IRS 990 / org enrichment | 3 |
| 311 service requests | 4 |
| Crime data | 4 |
| Neighborhood / tract pages | 4 |
| **Admin UI + Raw Data Explorer** (dataset status, loader runner, `/admin/data/<table>`) | Epic 2.5 — **next up** |
| **Inverse Search (guided query builder)** | Epic 10 |
| **Ecosystem / Network View** | Epic 11 |
| **Briefing Builder** | Epic 12 |
| User accounts / collections | TBD |
| Export / download | TBD |
| Census tract enrichment | 4 |

---

## Realistic timeline (solo)

| Epic | Effort | Cumulative | Status |
|---|---|---|---|
| 0 — Foundation shell | 1–2 weeks | Week 2 | ✅ Done |
| 1 — Schema | 3–5 days | Week 3 | ✅ Done |
| 2 — IPEDS pipeline | 2–3 weeks | Week 6 | ✅ Done |
| 3 — Provider pages | 1.5–2 weeks | Week 8 | ✅ Done |
| **2.5 — Admin UI + Data Explorer** | **1.5–2.5 days** | **Week 8.5** | **✅ Done** |
| 4 — Program pages | 1–1.5 weeks | Week 10 | ✅ Done |
| 5 — Field pages | 1 week | Week 11 | 🔲 Planned |
| 6 — Compare | 1 week | Week 12 | 🔲 Planned |
| 7 — Map | 1–1.5 weeks | Week 13.5 | 🔲 Planned |
| 8 — Search | 1 week | Week 14.5 | 🔲 Planned |
| 9 — Quality pass | 3–5 days | Week 15 | 🔲 Planned |

**Honest V1 target: 14–16 weeks solo.** This is a real product, not a hackathon demo. The IPEDS pipeline alone will take longer than you expect the first time. Build in buffer at Epics 2 and 3.

### Milestones worth celebrating
- **End of Epic 0:** The shell exists. You can see what Haystack will feel like.
- **End of Epic 2:** Real KC data in the database. The pipeline works.
- **End of Epic 3:** The first thing you can show anyone.
- **End of Epic 6:** A decision tool, not just a directory.
- **End of Epic 9:** V1 ships.
- **End of Epic 10:** A workflow tool, not just a research tool.
- **End of Epic 11:** The network layer is visible.
- **End of Epic 12:** Haystack generates deliverables, not just answers.

---

## Epic 10 — Inverse Search (Guided Query Builder)
**Goal:** Let users start from a need and have Haystack trace backward to providers and programs. The inverse of browsing.

**Design principle:** Most tools assume you know what you're looking for. Inverse Search assumes you know the *outcome* you need ("train 20 welders", "find a cert program near ZIP 64111") and helps you find the path.

**Exit criteria:** `/search/guided` renders a 3-step form that produces a filtered provider/program list.

**Effort estimate:** 1.5–2 weeks

### Design
**Step 1 — What outcome do you need?**
- I need to find training programs for someone
- I need to find providers that offer a field of study
- I need to understand what jobs a program connects to
- I need to compare providers by outcome

**Step 2 — Refine (changes by outcome type):**
- For training: select occupation family (SOC group) → system resolves to CIP codes → returns providers
- For field of study: select CIP family → returns programs and providers
- For job connections: select a program or CIP → returns linked occupations

**Step 3 — Filter the results:**
- Renders the standard directory with pre-populated filters from the guided path
- User can then adjust freely

### Implementation notes
- The route `GET /search/guided` is already stubbed from Epic 0
- Relies on the CIP↔SOC `program_occupation` table built in Epic 2
- Uses HTMX for step-by-step form progression (each step swap returns the next step's HTML fragment)
- Results are standard directory pages — no new templates needed

---

## Epic 11 — Ecosystem / Network View
**Goal:** Show the connections between organizations as a visual network, not just a list. A new view mode on the Organizations/Providers directory that makes relationships visible.

**Design principle:** The List view shows *what exists*. The Network view shows *how things connect*. Both should be toggleable on any directory page where relationship data exists.

**Exit criteria:** The provider directory has a working Network view toggle that renders a force-directed graph of providers connected by shared CIP fields (V1) or relationship data (Phase 6).

**Effort estimate:** 2 weeks

### Design
**V1 network edges (no Phase 6 data needed):**
- Providers connected by shared CIP families (if A and B both offer Health programs, they are peers)
- Providers connected by overlapping linked occupations
- Visual clustering: filter by CIP family to see a tighter ecosystem view

**Phase 6 network edges (when relationship table has data):**
- Funding flows (funder → grantee)
- Supply chain connections (buyer → supplier)
- Employer-training partnerships

### Implementation notes
- The List | Map | Network toggle is already stubbed from Epic 0 (Network shows placeholder)
- Use **Cytoscape.js** for the graph renderer: good layout algorithms, works well with HTMX data injection
- Route `GET /api/network/providers.json` returns nodes + edges JSON from SQLAlchemy queries
- For large graphs, pre-filter to the top 50 providers by completions before rendering

---

## Epic 12 — Briefing Builder
**Goal:** Let users collect stats and entities as they browse and generate a shareable, printable one-pager. Turn Haystack from a research tool into a deliverable generator.

**Design principle:** Workforce navigators, policy analysts, and grant writers need to communicate findings to others. A briefing builder means Haystack generates the artifact, not just informs it.

**Exit criteria:** A user can ★ any stat card on any page, view their collection in a `/briefing` page, and export it as a printable HTML page.

**Effort estimate:** 1.5 weeks

### Design
**Collection behavior:**
- ★ button on every stat card, entity card, and comparison row
- HTMX `POST /briefing/add` wires the add action (already stubbed from Epic 3)
- Briefing stored in Flask session (V1) or LocalStorage (no auth needed)
- Sticky briefing tray in top nav shows count of collected items

**Briefing page (`/briefing`):**
- Shows all collected items grouped by entity type
- User can remove items, reorder, add a title and note
- "Export" renders a print-optimized HTML page (no nav, clean layout, logo, data-as-of date, sources)

**Future:** connect to Collections (save briefings across sessions), PDF export via browser print, email delivery.

---

## IPEDS Data Wiring — Full Table Map

> All 57 IPEDS tables are loaded into SQLite (`ipeds_*` prefix).
> Browseable now at `/admin/sqlite`. This section maps each table to the Epic where it gets wired into a user-facing UI component.

### Already Wired (shipped with Epic 3 expansion — 2026-03-26)

| Table | What it powers | Where |
|---|---|---|
| `ipeds_ic2024` | Calendar type, admissions policy (open/selective) | Provider Overview tab |
| `ipeds_cost1_2024` | In-state tuition, out-of-state tuition, room & board | Provider Overview tab |
| `ipeds_cost2_2024` | Available for cost detail expansion | Provider Overview tab (spare) |
| `ipeds_adm2024` | Acceptance rate, ACT/SAT 75th percentile | Provider Overview tab |

### Epic 3 Expansion (Provider detail — next sprint)

| Table | What it powers | Where |
|---|---|---|
| `ipeds_gr2024` | 150% graduation rate (cohort) | Provider Outcomes tab |
| `ipeds_gr2024_l2` | 2-year graduation rate | Provider Outcomes tab |
| `ipeds_gr2024_pell_ssl` | Pell/SSL recipient graduation rate | Provider Outcomes tab |
| `ipeds_gr200_24` | 200% graduation rate | Provider Outcomes tab |
| `ipeds_effy2024` | Total unduplicated 12-month headcount | Provider Overview snapshot strip |
| `ipeds_effy2024_dist` | % enrollment via distance education | Provider Overview (online delivery signal) |
| `ipeds_ef2024d` | Student-to-faculty ratio, retention rate | Provider Overview tab |
| `ipeds_sfa2324` | Net price by income bracket (5 bands) | Provider Overview tab (Financial Aid section) |
| `ipeds_sfav2324` | Military/veterans benefit recipients | Provider Overview tab |
| `ipeds_efia2024` | FTE enrollment (instructional activity) | Provider Outcomes tab |
| `ipeds_om2024` | Outcome measures (8-year completion) | Provider Outcomes tab |
| `ipeds_al2024` | Library volumes, digital resources | Provider Outcomes tab (optional) |

### Epic 4 — Program pages

| Table | What it powers | Where |
|---|---|---|
| `ipeds_c2024_b` | Program-level completion counts by race/ethnicity/gender | Program detail — Outcomes tab equity breakdown |
| `ipeds_ef2024cp` | Enrollment by major field (CIP) — demand signal | Program detail — enrollment context |
| `ipeds_ef2024a` | Total fall enrollment by level (UG, GR, PB) | Program detail — institutional context |

### Epic 5 — Field (CIP) pages

| Table | What it powers | Where |
|---|---|---|
| `ipeds_ef2024cp` | Enrollment by CIP family — demand signal across schools | Field detail page — enrollment trends |
| `ipeds_c2024_b` | Completions by CIP — equity data | Field detail page — outcomes equity |
| `ipeds_gr2024` | Graduation rates by provider in this CIP | Field detail — provider performance comparison |

### Epic 6 — Compare

| Table | What it powers | Where |
|---|---|---|
| `ipeds_cost1_2024` | Side-by-side tuition comparison | Provider compare — Cost row |
| `ipeds_adm2024` | Acceptance rate comparison | Provider compare — Selectivity row |
| `ipeds_gr2024` | Graduation rate comparison | Provider compare — Outcomes row |
| `ipeds_sfa2324` | Net price comparison by income band | Provider compare — Aid row |
| `ipeds_f2324_f1a/f2/f3` | Revenue per student, instruction spending % | Provider compare — Financial Health row (advanced) |
| `ipeds_s2024_oc` | Full-time vs part-time faculty ratio | Provider compare — Faculty row |

### Epic 7 — Map

| Table | What it powers | Where |
|---|---|---|
| `ipeds_effy2024` | Enrollment size = map pin size / cluster weight | Map — provider pins |
| `ipeds_cost1_2024` | Tuition = tooltip on pin | Map — popup card |
| `ipeds_ic2024` | Calendar / admissions = filter chip on map | Map — filter layer |

### Epic 8 — Search

| Table | What it powers | Where |
|---|---|---|
| `ipeds_ic2024` | Institutional type filter in search results | Search — filter chips |
| `ipeds_adm2024` | Admission selectivity signal in result cards | Search — result card metadata |

### Epic 9 — Quality pass

| Table | What it powers | Where |
|---|---|---|
| `ipeds_gr2024` + `ipeds_gr2023` | Year-over-year graduation rate delta | Methods tab — data provenance |
| All `*2023` tables | Prior-year comparison baseline | Methods tab — freshness badges |

### Deferred / Phase 2+

| Table | Potential future use |
|---|---|
| `ipeds_f2324_f1a/f2/f3` | Financial health dashboard, revenue per student |
| `ipeds_s2024_oc/sis/is/nh` | Staff equity analysis, tenure-track ratios |
| `ipeds_sal2024_is/nis` | Faculty salary benchmarking |
| `ipeds_eap2024` | Employee headcount by functional category |
| `ipeds_ef2024a` | Enrollment demographics (race/gender) — equity lens |
| `ipeds_ef2024b` | Age distribution of student body |
| `ipeds_ef2024c` | Student migration / state-of-origin data |
| `ipeds_al2024` | Library resources indicator |

> **Note:** All deferred tables are already in SQLite and explorable via `/admin/sqlite`. No re-loading needed when these features are built — just write the query.
