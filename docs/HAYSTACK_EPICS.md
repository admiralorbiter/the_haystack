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

### Tasks

#### Understand the source files
- [ ] Download IPEDS HD (institution directory) for most recent complete year
- [ ] Download IPEDS C (completions by CIP) for same year
- [ ] Download IPEDS IC (institutional characteristics) for credential types
- [ ] Download CIP→SOC crosswalk (NCES or O*NET — pick one, document it)
- [ ] Review column names, null patterns, suppression markers

#### Loader: institutions (`loaders/load_ipeds_institutions.py`)
- [ ] Accept `--region` flag and look up county FIPS from `region_county` table
- [ ] Filter IPEDS to institutions in those counties
- [ ] Map IPEDS columns → `organization` schema
- [ ] Set `org_type = 'training'`
- [ ] Upsert on `unitid` (update if exists, insert if not)
- [ ] Write `unitid` to `org_alias` table with `source='ipeds'` — all future sources must resolve through this table before creating a new org
- [ ] Record `dataset_source` row on completion
- [ ] Log: institutions loaded, skipped, failed

#### Loader: programs (`loaders/load_ipeds_programs.py`)
- [ ] Join completions file to institution by `unitid`
- [ ] Filter to KC institutions only
- [ ] Normalize CIP to 6-digit string (pad if needed)
- [ ] Map credential level codes to human labels (e.g. `1` → "Certificate < 1 year")
- [ ] Handle suppressed completions (value = `.` or blank) → store as NULL
- [ ] Upsert on `(org_id, cip, credential_type)` composite
- [ ] Log: programs loaded, suppressed, failed

#### Deduplication rule (applies to every loader, forever)
> **Before inserting any organization, check `org_alias` for the incoming source ID.**
> If found → update existing org record, do not create a duplicate.
> If not found → create org, then write alias row.
> This ensures one canonical `org_id` per real-world entity across all data sources.

#### Loader: CIP→SOC crosswalk (`loaders/load_cip_soc.py`)
- [ ] Load crosswalk file
- [ ] Populate `occupation` table (SOC codes + titles)
- [ ] Populate `program_occupation` with confidence=1.0 for direct matches
- [ ] Log: occupation records, links created

#### QA scripts
- [ ] `qa/check_ipeds.py` — prints: institution count by county, program count, null completions rate, CIP coverage, unmatched unitids
- [ ] At least one institution per KC MSA county
- [ ] No duplicate unitids in organization table
- [ ] All programs have a valid org_id foreign key

---

## Epic 3 — Provider directory and detail
**Goal:** Real, working provider pages backed by IPEDS data. The first thing a user can actually use.

**Exit criteria:** `/providers` lists KC institutions with working filters. `/providers/<id>` renders all tabs with real data and no crashes.

**Effort estimate:** 1.5–2 weeks

### Tasks

#### Provider directory (`/providers`)
- [ ] SQLAlchemy query: list organizations where org_type='training', join program counts and total completions
- [ ] Filters: county, credential type (via program join), CIP family (2-digit prefix), completions band
- [ ] Sort: completions desc (default), program count, alphabetic
- [ ] Search: LIKE on organization name (or SQLite FTS if already set up)
- [ ] URL-synced filter state (query params)
- [ ] Result count shown ("34 providers")
- [ ] Card/list toggle (start with one, add toggle later)
- [ ] **Network view toggle:** List | Map | ~~Network~~ (Network shows a "Coming soon" panel — the toggle exists from day one so Epic 11 is a swap, not a redesign)
- [ ] Empty state if filters return zero results
- [ ] Pagination or limit (50 per page is fine for V1)

#### Provider detail (`/providers/<id>`)
- [ ] Route: fetch organization + aggregate metrics in one query
- [ ] Snapshot strip: program count, total completions, top credential type, top CIP family, linked occupation count, Scorecard coverage
- [ ] Tab: Overview — provider summary, top 5 programs by completions, CIP family breakdown
- [ ] Tab: Connections — linked occupations via CIP→SOC (ranked by program count), similar providers by CIP overlap
- [ ] Tab: Geography — static map pin (lat/lon), county label, nearby context (placeholder for Phase 4)
- [ ] Tab: Outcomes — completions table by CIP; Scorecard placeholder ("Scorecard data coming in Phase 2")
- [ ] Tab: Evidence — unitid, data source name, loaded_at date
- [ ] Tab: Methods — completions definition, CIP/SOC caveat text, suppression note
- [ ] Data freshness badge visible in header
- [ ] **Briefing Builder:** every stat card in the snapshot strip has a ★ button (wired to HTMX `POST /briefing/add` — returns 200 in V1 as a placeholder response)
- [ ] 404 if org_id not found or org_type != 'training'
- [ ] Empty states: no programs, no occupation links, no completions data

#### Performance
- [ ] No N+1 queries — all tab data fetched in batched queries, not per-row
- [ ] Provider detail renders in < 300ms on local SQLite

---

## Epic 4 — Program directory and detail
**Goal:** Programs browsable independently of providers. Users can find a specific certificate type without knowing which school offers it.

**Exit criteria:** `/programs` lists all KC programs with working filters. `/programs/<id>` renders without errors.

**Effort estimate:** 1–1.5 weeks (template and query patterns already established)

### Tasks

#### Program directory (`/programs`)
- [ ] SQLAlchemy query: list programs with org name, credential type, CIP label, completions, occupation link count
- [ ] Filters: credential type, CIP family, provider (org_id), completions band
- [ ] Sort: completions desc (default), provider alphabetic, credential type
- [ ] Search: program name + org name LIKE
- [ ] URL-synced filter state
- [ ] Empty state

#### Program detail (`/programs/<id>`)
- [ ] Snapshot strip: provider name, credential type, CIP code + label, completions, linked occupation count, Scorecard available (yes/no)
- [ ] Tab: Overview — short descriptor, provider card (name, city, link), award level, CIP family context
- [ ] Tab: Occupation links — related occupations ranked by confidence, SOC code shown, wage/demand placeholder
- [ ] Tab: Outcomes — completions value; suppression note if NULL; Scorecard placeholder
- [ ] Tab: Geography — provider map pin
- [ ] Tab: Methods — CIP/SOC mapping explanation, completions definition
- [ ] 404 handling
- [ ] Empty state: no occupation links, no completions

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
| **Inverse Search (guided query builder)** | Epic 10 |
| **Ecosystem / Network View** | Epic 11 |
| **Briefing Builder** | Epic 12 |
| User accounts / collections | TBD |
| Export / download | TBD |
| Census tract enrichment | 4 |

---

## Realistic timeline (solo)

| Epic | Effort | Cumulative |
|---|---|---|
| 0 — Foundation shell | 1–2 weeks | Week 2 |
| 1 — Schema | 3–5 days | Week 3 |
| 2 — IPEDS pipeline | 2–3 weeks | Week 6 |
| 3 — Provider pages | 1.5–2 weeks | Week 8 |
| 4 — Program pages | 1–1.5 weeks | Week 9.5 |
| 5 — Field pages | 1 week | Week 10.5 |
| 6 — Compare | 1 week | Week 11.5 |
| 7 — Map | 1–1.5 weeks | Week 13 |
| 8 — Search | 1 week | Week 14 |
| 9 — Quality pass | 3–5 days | Week 15 |

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
