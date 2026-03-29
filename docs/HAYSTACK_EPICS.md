# The Haystack — Epics & Task List

**Stack:** Flask / SQLite / SQLAlchemy / Jinja2 / htmx
**Mode:** Solo developer

> **Note:** Phase 1 (IPEDS Foundation, Epics 0–9) has been completed.
> V1 specifications and historical task lists are archived in `docs/archive/phase_1_ipeds/`.
> This document traces the Phase 2 expansion.

---

## Phase 2 — Active Roadmap

| Epic | Focus | Status |
|---|---|---|
| **3.5 Provider Demographics** | Enrollment + Completions demographics on provider pages | ✅ Shipped 2026-03-29 |
| **4 Program Pages** | Program detail, Equity in Completions tab | ✅ Shipped 2026-03-28 |
| **6 Provider Compare** | Side-by-side provider comparison page | ✅ Shipped 2026-03-27 |
| **7 Directory UI** | Dropdown filters + sortable columns across all directories | ✅ Shipped 2026-03-27 |
| **10 Non-Title IV Training Base** | WIOA ETPL + Apprenticeships ingested, Hubs + Employers shipped | ✅ Shipped 2026-03-28 |
| **6.5 Program Compare** | Head-to-head program-level side-by-side | ✅ Shipped 2026-03-29 |
| **2.9 Pre-Phase-3 Hardening** | org_fact table, soft-delete, API namespace, search spec, analytics | 🔲 Next Up |
| **11 Workforce Connections** | BLS OEWS wage & O*NET demand integration | 🔲 Planned |
| **12 Ecosystem & Network View** | Force-directed graph of provider relationships | 🔲 Planned |
| **13 Briefing Builder** | Collect stats/entities and generate printable one-pager | 🔲 Planned |
| **14 Stepping Stones** | Sequenced credential pathways + ROI break-even calculator | 🔬 Research Spike |
| **15 Hidden Gems Engine** | Algorithmic surfacing of high-ROI programs | 🔬 Research Spike |

---

## Epic 2.9 — Pre-Phase-3 Hardening
**Goal:** Close structural gaps identified in architecture review before Phase 3 (org enrichment) begins. These are cheap now and expensive to retrofit later.

**Why do this before Epic 11?** Three of these items (soft-delete, org_fact, API namespace) become harder to add correctly once Phase 3 sources start attaching data to the Organization model.

### Task list

| # | Task | Effort | Priority | Notes |
|---|------|--------|----------|-------|
| H-1 | Add `is_active` + `last_seen_in_source` to Organization model | ~2 hrs | 🔴 P1 | When IPEDS drops a unitid next year, stale data stays live without this. Loader post-sweep marks unseen records inactive. UI shows banner on inactive pages. |
| H-2 | Add `org_fact` EAV table `(org_id, fact_type, value_num, value_text, source, as_of_date)` | ~30 min | 🔴 P1 | Prevents Phase 3 column sprawl on Organization. Enables the Evidence tab to be a single query across all sources. Fact types tracked as Python constants. |
| H-3 | Add `/api/v1/` Blueprint with 3 seed endpoints: provider detail, program detail, search | ~2 hrs | 🔴 P1 | Epic 12 already specs `GET /api/network/providers.json`. Establish the namespace now so it is not retrofitted under pressure. No auth or pagination required yet. |
| H-4 | Write `HAYSTACK_SEARCH_SPEC.md` — document scoring model: FTS5 rank × entity-type boost | ~1 hr | 🟡 P2 | Search becomes chaotic as entity types grow without a spec. Ordering: providers > programs > occupations > employers. Freshness decay added when 311 data lands. |
| H-5 | Add `page_view` table + `@app.before_request` logger | ~30 min | 🟡 P2 | Log `(path, query_params, session_id, timestamp)`. Exclude `/static/` and `/admin/`. Queryable via `/admin/sqlite`. |
| H-6 | Add `search_event` table `(query_text, result_count, timestamp)` | ~30 min | 🟡 P2 | Failed searches (result_count = 0) are the most actionable UX signal for a research tool. |
| H-7 | Build `/admin/freshness` route — traffic-light grid from `dataset_source` table | ~45 min | 🟢 P3 | `record_dataset_source()` already called in every loader. Green < 30 days, Yellow 30–90, Red 90+. |
| H-8 | Add "Who Else Trains For This?" peer programs widget on program detail pages | ~1 hr | 🟡 P2 | SQL query against programs with matching CIP in same MSA. No new data needed. Transforms program detail from a data page into a decision tool. |
| H-9 | Elevate `ipeds_om2024` 8-year outcomes on provider detail pages | ~1 hr | 🟡 P2 | Table already loaded. 8-year outcomes capture part-time/transfer students that 150% grad rates miss. Zero ingestion cost. |
| H-10 | Add relative time formatting to freshness badges | ~15 min | 🟢 P3 | "3 weeks ago" is more meaningful than "2026-03-08". |
| H-11 | Add permalink/share button on entity pages | ~30 min | 🟢 P3 | Copy-URL affordance so researchers can share a specific provider or program page. |

**Exit criteria:** All P1 items (H-1, H-2, H-3) complete before Phase 3 data sources begin ingestion. P2 items complete before public launch.

---

## ✅ Epic 3.5 — Provider Demographics (Shipped 2026-03-29)
**What shipped:**
- New `OrganizationDemographics` model (1:1 with Organization) for Fall 2024 enrollment data.
- New `OrganizationCompletionsDemographics` model (1:1 with Organization) for 2023–24 completions data (IPEDS Grand Total rows, `CIPCODE = 99.0000`).
- `loaders/load_ipeds_demographics.py` ingests both tables in a single pass.
- Provider detail page: new **"Student Demographics"** HTMX tab showing enrollment demographics stacked above completions demographics for direct equity comparison.

---

## ✅ Epic 4 — Program Pages (Shipped 2026-03-28)
**What shipped:**
- New `ProgramDemographics` model (1:1 with Program) storing CIP-level completions by race/ethnicity/gender.
- `loaders/load_ipeds_demographics.py` also ingests `c2024_a.csv` by CIP code.
- Program detail page: new **"Equity in Completions"** HTMX tab.

---

## ✅ Epic 6 — Provider Compare (Shipped 2026-03-27)
**What shipped:**
- `/compare` route with side-by-side comparison of up to 3 providers.
- Sections: Institutional Profile, Admissions & Cost, Enrollment, Financial Aid, Outcomes & Graduation.
- Data sources: IPEDS `ic2024`, `cost1_2024`, `adm2024`, `effy2024`, `gr2024`, `gr200_24`, `sfa2324`, `ef2024d`.

---

## ✅ Epic 7 — Directory UI Modernization (Shipped 2026-03-27)
**What shipped:**
- Replaced chip filter rows with compact `<select>` dropdowns on all three directory pages (Providers, Programs, Fields).
- Clickable column-header sorting on all directory tables.

---

## ✅ Epic 10 — Non-Title IV Training Base (Shipped 2026-03-28)
**What shipped:**

### WIOA ETPL
- `loaders/load_etpl.py` ingests Missouri & Kansas eligible training providers.
- Identity Reconciliation (fuzzy matching) merges ETPL entries with existing IPEDS orgs.
- `is_wioa_eligible` flag propagated to Program records.
- Providers and Programs directories badge WIOA-eligible entities.

### Apprenticeships
- `loaders/load_apprenticeships.py` ingests DOL Partner Finder listings (`data/raw/apprenticeship/partner-finder-listings.csv`).
- `OrgContact` pattern applied for apprenticeship sponsor contacts.
- `load_apprenticeships.py` follows the fuzzy-match + `link_org_parents.py` reconciliation pattern.

### Employers Directory
- New `/employers` directory route and `employers/directory.html` template.
- Employers shown with apprenticeship sponsor contacts and ZIP-based KC MSA geofencing.

### Hubs Engine
- `routes/hubs.py` and `HUBS_CONFIG` define curatable thematic portals.
- Apprenticeship Hub and Tech/Training Hub live at `/hubs/<slug>`.

### Parent–Satellite Linking
- `loaders/link_org_parents.py` runs as a separate idempotent maintenance script to auto-link satellite campuses to parent orgs using fuzzy matching + manual overrides.

---

## ✅ Epic 6.5 — Program-to-Program Head-to-Head Compare (Shipped 2026-03-29)
**What shipped:**
- Added "Add to Compare" affordances on program cards and program detail pages.
- New `/compare/programs` route mirroring the existing provider compare pattern.
- Aggregated Outomes, Student Demographics, and College Scorecard metrics with dynamic grouping.
- Built explicit graceful degradation logic to render `N/A` for WIOA/Apprenticeship non-Title IV records.

**Effort estimate:** 1 week

---

## Epic 11 — Workforce Connections (BLS OEWS + O*NET)
**Goal:** Connect educational programs to real-world outcomes by displaying regional wage and demand data for related occupations. This unlocks the "ROI" narrative and is a prerequisite for Epics 14 and 15.

**Datasets to Incorporate:**
1. **BLS OEWS** — May 2024 State Occupational Employment and Wage Estimates (median, 25th, 75th pct wages by SOC)
2. **O*NET** — Occupational taxonomy, job zone levels, bright outlook flags

**Design principle:**
The user should never have to guess the ROI of a program. Viewing a Medical Assistant program should immediately surface the median, 25th, and 75th percentile regional wages for Medical Assistants in the KC MSA.

**Exit criteria:**
- Program detail pages show a "Career Trajectory" widget with local wages for linked occupations (via CIP→SOC crosswalk).
- The `/occupations` or `/fields` pages show BLS wage bands alongside program completions.

**Implementation notes:**
- Load BLS data into a new `occupation_wage` table keyed by `soc` and state/MSA code.
- Relies on the `program_occupation` crosswalk (CIP↔SOC) established in Phase 1.
- O*NET job zone data enriches the `Occupation` model with entry-level vs. experienced requirements.

**Effort estimate:** 1–1.5 weeks

---

## Epic 12 — Ecosystem / Network View
**Goal:** Render a living, force-directed graph of KC's training ecosystem — making relationships between providers, programs, employers, and occupations visually navigable.

**Design principle:** The List view shows *what exists*. The Network view shows *how things connect*. Both should be toggleable on any directory page where relationship data exists.

**Exit criteria:** Provider directory has a Network view toggle rendering a force-directed graph of providers connected by shared CIP families (V1) or funded relationships (Phase 6).

**Effort estimate:** 2 weeks

### Design
**V1 network edges (data we already have):**
- Providers connected by shared CIP families (if A and B both offer Health programs, they are peers)
- Providers connected by overlapping linked occupations
- Visual clustering by CIP family to reveal training hubs and deserts

**Phase 6 network edges (future — when relationship table has data):**
- Funding flows (funder → grantee via IRS 990)
- Board member cross-pollination (ProPublica Nonprofit Explorer)
- Employer-training partnerships

### Implementation notes
- Use **Cytoscape.js** for graph rendering — good layout algorithms, compatible with HTMX data injection
- Route `GET /api/network/providers.json` returns nodes + edges JSON
- Pre-filter to top 50 providers by completions to keep initial render fast

---

## Epic 13 — Briefing Builder
**Goal:** Let users collect stats and entities while browsing, then generate a shareable, printable one-pager. Turns Haystack from a research tool into a deliverable generator.

**Design principle:** Workforce navigators, policy analysts, and grant writers need to communicate findings to others. The Briefing Builder means Haystack generates the artifact, not just informs it.

**Exit criteria:** A user can ★ any stat card or entity, view their collection at `/briefing`, and export it as a print-optimized HTML page.

**Effort estimate:** 1.5 weeks

**Note:** `routes/briefing.py` already exists as a stub — no new route file needed, just implementation.

### Design
- ★ button on every stat card, entity card, and comparison row
- HTMX `POST /briefing/add` wires the add action
- Briefing stored in Flask session (V1) — no auth needed
- Sticky collection tray in top nav shows count
- Export renders print-optimized HTML (no nav, logo, data-as-of date, sources listed)

**Future:** PDF export via browser print, email delivery, saved collections across sessions.

---

## Epic 14 — Stepping Stones & ROI Break-Even Pathways
**Goal:** Shift from static occupation endpoints to sequenced, connected career pathways — helping users trace the journey from entry-level to their ultimate goal, with every step costing real money and paying real wages.

**Design principle:** Education is not a single leap. A CNA cert leads to LPN leads to RN. Haystack should make that ladder visible, cost it out, and show the payoff at every rung.

**Status:** 🔬 Research Spike — requires Epic 11 (BLS OEWS) first.

**Research Spike:**
- Evaluate O*NET job zone links vs Census LEHD Job-to-Job transition grids for "likely next occupation" data.
- Investigate Credential Engine Registry (CTDL) for structured credential stacking schemas showing how certs roll up into degrees.
- Prototype the "Interactive ROI Slider" math: cost of credential ÷ (BLS median wage − current wage) = break-even years.

**Data dependencies:**
- Epic 11 (BLS OEWS wages) must ship first.
- Credential Engine Registry (future external ingestion).
- Census LEHD Job-to-Job Flows (for probabilistic "next step" career transitions).

---

## Epic 15 — The "Hidden Gems" Discovery Engine
**Goal:** Intercept users who don't know what to search for by algorithmically surfacing high-ROI, low-cost programs that are structurally buried by dominant institutions in standard search directories.

**Design principle:** Change the platform from a pure search engine into an active discovery engine. Highlight community colleges, technical schools, and union apprenticeships with exceptional outcomes.

**Status:** 🔬 Research Spike — benefits significantly from Epic 11 (BLS OEWS) wage data.

**Research Spike:**
- Construct a weighted SQL scoring heuristic using: `grad_rate_150 > 60%` + `avg_cost < 10000` + `median_earnings_6yr > 45000`.
- Evaluate algorithm fragility: Does it surface statistically anomalous programs with tiny N-counts? Design a minimum completions threshold (e.g., N ≥ 25) to suppress noise.
- Consider a "Surprise Me" entry point on the homepage vs an embedded "Staff Picks" carousel.

---

## IPEDS Data Wiring — Full Table Map

> All 57 IPEDS tables are loaded into SQLite (`ipeds_*` prefix).
> Browseable at `/admin/sqlite`. This section maps each table to its shipped or planned UI surface.

### ✅ Wired — Shipped with Epic 3 expansion (2026-03-26)

| Table | What it powers | Where |
|---|---|---|
| `ipeds_ic2024` | Calendar type, admissions policy (open/selective) | Provider Overview tab |
| `ipeds_cost1_2024` | In-state tuition, out-of-state tuition, room & board | Provider Overview tab |
| `ipeds_cost2_2024` | Available for cost detail expansion | Provider Overview tab (spare) |
| `ipeds_adm2024` | Acceptance rate, ACT/SAT 75th percentile | Provider Overview tab |
| `ipeds_gr2024` | 150% graduation rate | Provider Outcomes tab |
| `ipeds_gr200_24` | 200% graduation rate | Provider Outcomes tab |
| `ipeds_effy2024` | Total 12-month enrollment headcount | Provider Overview snapshot strip |
| `ipeds_effy2024_dist` | % enrollment via distance education | Provider Overview |
| `ipeds_ef2024d` | Student-to-faculty ratio, retention rate | Provider Overview tab |
| `ipeds_sfa2324` | Net price by income bracket (5 bands) | Provider Overview — Financial Aid |
| `ipeds_sfav2324` | Military/veterans benefit recipients | Provider Overview tab |
| `ipeds_om2024` | 8-year outcome measures | Provider Outcomes tab |

### ✅ Wired — Epic 4: Program Pages (2026-03-28)

| Table | What it powers | Where |
|---|---|---|
| `ipeds_c2024_b` | Program-level completions by demographic | Program detail — "Equity in Completions" tab |
| `ipeds_ef2024cp` | Enrollment by CIP field | Program detail — enrollment context |

### ✅ Wired — Epic 3.5: Provider Demographics (2026-03-29)

| Table | What it powers | Where |
|---|---|---|
| `ipeds_ef2024a` | Fall 2024 enrollment by race/ethnicity/gender | Provider detail — "Student Demographics" tab |
| `ipeds_c2024_a` (CIPCODE=99.0000) | Institution-wide completions by demographic | Provider detail — "Student Demographics" tab |

### ✅ Wired — Epic 6: Provider Compare (2026-03-27)

| Table | What it powers | Where |
|---|---|---|
| `ipeds_ic2024` | Calendar system, admissions policy | Provider compare — Institutional Profile |
| `ipeds_cost1_2024` | In-state / out-of-state tuition | Provider compare — Admissions & Cost |
| `ipeds_adm2024` | Acceptance rate | Provider compare — Admissions & Cost |
| `ipeds_effy2024` | Total enrollment | Provider compare — Enrollment |
| `ipeds_effy2024_dist` | Distance education % | Provider compare — Enrollment |
| `ipeds_gr2024` | 150% graduation rate, Pell grad rate | Provider compare — Outcomes |
| `ipeds_gr200_24` | 200% graduation rate | Provider compare — Outcomes |
| `ipeds_sfa2324` | Grant %, Pell %, loan % recipients | Provider compare — Financial Aid |
| `ipeds_ef2024d` | Student-faculty ratio | Provider compare — Outcomes |

### Planned — Epic 5: Field (CIP) Pages

| Table | What it powers | Where |
|---|---|---|
| `ipeds_ef2024cp` | Enrollment by CIP family — demand signal | Field detail — enrollment trends |
| `ipeds_c2024_b` | Completions by CIP — equity data | Field detail — outcomes equity |
| `ipeds_gr2024` | Graduation rates by provider in this CIP | Field detail — provider comparison |

### Planned — Epic 7: Map

| Table | What it powers | Where |
|---|---|---|
| `ipeds_effy2024` | Enrollment size → pin size / cluster weight | Map — provider pins |
| `ipeds_cost1_2024` | Tuition → tooltip on pin | Map — popup card |
| `ipeds_ic2024` | Admissions type → filter chip on map | Map — filter layer |

### Deferred / Phase 3+

| Table | Potential future use |
|---|---|
| `ipeds_f2324_f1a/f2/f3` | Financial health dashboard, revenue per student |
| `ipeds_s2024_oc/sis/is/nh` | Staff equity analysis, tenure-track ratios |
| `ipeds_sal2024_is/nis` | Faculty salary benchmarking |
| `ipeds_eap2024` | Employee headcount by functional category |
| `ipeds_ef2024b` | Age distribution of student body |
| `ipeds_ef2024c` | Student migration / state-of-origin data |

> **Note:** All deferred tables are already in SQLite and explorable via `/admin/sqlite`. No re-loading needed — just write the query.
