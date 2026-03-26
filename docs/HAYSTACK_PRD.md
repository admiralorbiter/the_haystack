# The Haystack — Product Requirements Document (PRD)

**Version:** 0.1 — IPEDS V1 focus
**Author:** Solo / [your name]
**Last updated:** March 2026
**Status:** Draft

---

## 1. Problem statement

Residents, workforce navigators, researchers, and civic leaders lack a single place to answer:
- What training providers, employers, and organizations exist in a region and what do they offer?
- How do programs connect to occupations, supply chains, and labor demand?
- What does a given neighborhood look like in terms of opportunity, services, and conditions?
- How are organizations connected to each other — through funding, supply chains, shared leadership, or partnerships?

Existing tools are either siloed by dataset (IPEDS.nces.ed.gov, BLS, city open data portals), too national to be locally useful, or too narrow to show cross-system connections. The Haystack brings these sources together in a stable, entity-centered product that starts in Kansas City and is designed from day one to scale to any region.

**V1 focus:** Kansas City Metro (training providers + programs). The architecture is multi-region from day one.

---

## 2. Target users (V1)

**Primary:** Workforce navigator or advisor helping a client find training options in KC.
Needs: find providers by location and field, compare programs, understand outcomes, explain credentials.

**Secondary:** Researcher or policy analyst reviewing KC's training landscape.
Needs: aggregate completions data, field mix, occupation linkages, trend context.

**Out of scope for V1:** Job seekers browsing cold, employers recruiting, general public exploration.

---

## 3. Active region (V1: Kansas City MSA)

> **Architecture decision: Region is a runtime configuration, not a hardcode.**
> The `region` table stores named regions with their constituent FIPS codes. Loaders accept a `--region` flag and filter to that region's counties. The UI reads the active region from config. This means adding a second metro in Phase 7 requires seeding one new row — not rewriting queries.

### V1 Active Region: Kansas City Metro MSA

| County | State | FIPS |
|---|---|---|
| Jackson | MO | 29095 |
| Clay | MO | 29047 |
| Platte | MO | 29165 |
| Cass | MO | 29037 |
| Ray | MO | 29177 |
| Johnson | KS | 20091 |
| Wyandotte | KS | 20209 |
| Leavenworth | KS | 20103 |
| Miami | KS | 20121 |

### Region table schema
```
region — region_id, name, slug, default_lat, default_lon, default_zoom
region_county — region_id, county_fips, county_name, state
```

Every loader, every map default, and every regional aggregate derives from `region_county` for the active `region_id` — never hardcoded FIPS in query logic.

---

## 4. Tech stack (locked for V1)

| Layer | Choice |
|---|---|
| Backend | Python 3.11+ / Flask |
| Database | SQLite (single file, offline snapshots) |
| Templating | Jinja2 |
| Frontend | HTML/CSS + htmx (for interactive components) |
| Data pipeline | Python ingestion scripts, idempotent upserts |
| Hosting | Local dev → TBD (Railway / Render / Fly) |

**ORM:** We will use **SQLAlchemy**. This keeps querying robust, simplifies complex programmatic joins, and accelerates development.

---

## 5. Core entity model

These six entity types are stable. New datasets enrich them; they do not create new types.

```
geo_area           — ZIP, tract, county, city, metro
organization       — any named entity (college, employer, nonprofit, agency)
program            — an offering from an organization (course, certificate, degree)
occupation         — SOC-coded role or industry cluster
civic_signal       — time-stamped event tied to a place (311, crime, permit)
relationship       — a directional link between any two entities (supply chain, funding, partnership)
```

Key crosswalk tables:
```
program_occupation   — CIP ↔ SOC links with confidence score
org_geo              — organization ↔ geography membership
org_alias            — org_id, source, source_id, source_name (deduplication anchor)
relationship         — from_entity, to_entity, rel_type, weight, source (see Phase 6)
dataset_source       — metadata for every loaded dataset (name, loaded_at, record_count, url)
region               — named regions with constituent FIPS codes (multi-region support)
```

> [!IMPORTANT]
> **Deduplication rule:** Every loader must check `org_alias` before creating a new organization record. One canonical `org_id` per real-world entity, regardless of how many sources reference it.

---

## 6. V1 scope (IPEDS)

### In scope
- Provider (organization) directory — browse, filter, sort, search
- Provider detail page — snapshot metrics, tabs, map, occupation links
- Program directory — browse, filter, sort, search
- Program detail page — snapshot metrics, tabs, occupation links
- Field of Study (CIP) page — aggregated view by CIP family
- CIP→SOC occupation connections
- Provider compare (2 providers side by side)
- Program compare (2 programs side by side)
- Map — provider locations, clustered
- Methods and data freshness on every page
- Empty states for all zero-result scenarios

### Out of scope for V1
- Admissions, tuition, finance deep dives
- Full demographics explorer
- Custom report builder
- Scorecard outcomes (Phase 2)
- Any civic signal data (Phase 4)
- User accounts, saved searches, collections

---

## 7. Functional requirements

### 7.1 Data pipeline
- IPEDS institutions filtered to the **active region** (by county FIPS from `region_county` table)
- Programs loaded and linked to institutions via `unitid`
- CIP codes normalized to 6-digit format
- CIP→SOC crosswalk loaded and available for queries
- `dataset_source` record created on every load with timestamp and row count
- Loader is idempotent: re-running does not duplicate records

### 7.2 Provider directory (`/providers`)
- Lists all IPEDS institutions in the active region
- Default sort: completions descending
- Filters: county, credential type, CIP family, completions band
- Search: institution name (SQLite FTS or LIKE)
- Card shows: name, city, program count, total completions, top field

### 7.3 Provider detail (`/providers/<id>`)
- Snapshot strip: program count, completions, top credential, top CIP, linked occupations, Scorecard coverage (yes/no)
- Tabs: Overview, Connections, Geography, Outcomes, Evidence, Methods
- Map: provider location pin
- Connections tab: linked occupations via CIP→SOC, similar providers
- Evidence tab: source dataset, loaded date, IPEDS unitid
- Methods tab: completions definition, CIP/SOC caveat, suppression note

### 7.4 Program directory (`/programs`)
- Lists all programs across providers in the active region
- Filters: credential type, provider, CIP family, completions band
- Search: program name
- Card shows: name, provider, credential type, CIP, completions, linked occupations count

### 7.5 Program detail (`/programs/<id>`)
- Snapshot strip: provider, credential type, CIP, completions, linked occupations, Scorecard data available
- Tabs: Overview, Occupation links, Outcomes, Geography, Methods

### 7.6 Field of Study page (`/fields/<cip>`)
- Shows all providers and programs in a CIP family or specific CIP
- Snapshot: provider count, total completions, credential mix, linked occupations
- Sections: provider list, top programs, linked occupations

### 7.7 Compare (`/compare/providers`, `/compare/programs`)
- Accept 2 entity IDs via query params
- Same metric order for both entities
- Differences visually indicated (higher/lower badges)

### 7.8 Map (`/map`)
- Provider mode only in V1
- Clustered provider pins
- Filter by credential type or CIP family
- Click opens provider summary → link to detail page

---

## 8. Non-functional requirements

| Requirement | Target |
|---|---|
| Directory page load | < 500ms for default view (SQLite, no N+1) |
| Detail page load | < 300ms |
| Map payload | Clustered GeoJSON, not raw points |
| Mobile readability | Detail pages readable at 375px width |
| Empty states | Every zero-result path has a message |
| Freshness | Data-as-of date visible on every page |

---

## 9. Acceptance criteria (IPEDS V1 done when)

**Data**
- [ ] IPEDS institutions loaded for all KC MSA counties
- [ ] Programs linked to institutions
- [ ] CIP codes usable for filtering
- [ ] CIP→SOC occupation links available
- [ ] `dataset_source` table populated with load metadata

**UI — directories**
- [ ] Provider directory renders with filters and sort working
- [ ] Program directory renders with filters and sort working
- [ ] Search returns grouped, relevant results

**UI — detail pages**
- [ ] Provider detail: all 6 tabs render without error
- [ ] Program detail: all tabs render without error
- [ ] Data freshness badge visible on every detail page
- [ ] Methods tab present on provider and program pages

**UI — compare and map**
- [ ] Compare works for 2 providers
- [ ] Compare works for 2 programs
- [ ] Map shows clustered provider pins, filterable

**Quality**
- [ ] No page requires a custom layout outside the shared shell
- [ ] Empty states present for: no programs, no completions data, no occupation links
- [ ] Mobile layout readable on detail pages (375px)
- [ ] No N+1 queries on directory pages

---

## 10. Out-of-scope decisions (log these, don't resolve in V1)

| Decision | Notes |
|---|---|
| Authentication / user accounts | Not needed until collections feature |
| Full-text search engine | SQLite FTS sufficient for V1 |
| ORM vs raw SQL | SQLAlchemy (decided) |
| JS framework | htmx (decided) |
| Hosting target | Local dev first; Railway / Render / Fly all viable |
| Census tract enrichment | Phase 4 |
| Scorecard integration | Phase 2 — after IPEDS is stable |

---

## 11. Open questions (need answers before or during V1)

1. **KC region FIPS list** — use the 9-county MSA above or a tighter core?
2. **IPEDS data year** — which survey year to load first (most recent complete = 2022-23)?
3. **Completions suppression** — IPEDS suppresses values < 3; display as "<3" or hide?
4. **CIP→SOC crosswalk source** — NCES official crosswalk or O*NET?
5. **JS library** — Alpine.js (simpler, inline) or htmx (server-driven, less JS)?

---

## 12. Success metrics for V1

- A user can find a KC training provider, view its programs, and understand what occupations they connect to — in under 3 clicks
- A user can compare 2 providers on completions and occupation links without confusion
- Every page has visible data freshness and a methods explanation
- No page invents a layout pattern not in the shared shell
