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
| **2.9 Pre-Phase-3 Hardening** | org_fact table, soft-delete, API namespace, search spec, analytics | ✅ Shipped 2026-03-29 |
| **6.5 Program Compare** | Head-to-head program-level side-by-side | ✅ Shipped 2026-03-29 |
| **11 Workforce Connections** | BLS OEWS wage & O*NET demand integration | ✅ Shipped 2026-03-29 |
| **11b O*NET Depth** | Alternate Titles (search), Skills, Education Level, Work Values | ✅ Shipped 2026-03-29 |
| **16 BLS Expansion** | Employment Projections (growth) + NAICS-to-SOC Industry Matrix | 🔲 Planned |
| **17 Employer-Occupation Link** | Apprenticeship SOC direct links + NAICS inferred employer matching | 🔲 Planned |
| **12 Ecosystem & Network View** | Force-directed graph of provider relationships | 🔲 Planned |
| **13 Briefing Builder** | Collect stats/entities and generate printable one-pager | 🔲 Planned |
| **14 Stepping Stones** | Sequenced credential pathways + ROI break-even calculator | 🔬 Research Spike |
| **15 Hidden Gems Engine** | Algorithmic surfacing of high-ROI programs | 🔬 Research Spike |

---

## ✅ Epic 2.9 — Pre-Phase-3 Hardening (Shipped 2026-03-29)
**Goal:** Closed structural gaps identified in architecture review before Phase 3 (org enrichment) begins.

**What shipped:**
- **Database Robustness**: Introduced `is_active` soft-deleting and an arbitrary EAV `OrgFact` table to prevent column sprawl.
- **API Boundary**: Built `api_v1_bp` blueprint, securely isolating JSON streams from frontend templates.
- **Search Specification**: Authored `HAYSTACK_SEARCH_SPEC.md` codifying FTS5 prioritization multipliers.
- **Analytics & Telemetry**: Integrated Plausible tracking and internal `PageView` + `SearchEvent` instrumentation models.
- **Admin Tools**: Formulated an administrative dashboard (`/admin/freshness`) monitoring dataset ages via a traffic-light grid.
- **UX Polish**: Augmented program pages with a comparative "Who Else Trains For This?" widget, provider detail pages with 8-year outcome percentages, and converted raw dates into organic "timeago" strings.

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

## ✅ Epic 11 — Workforce Connections (BLS OEWS + O*NET) (Shipped 2026-03-29)
**Goal:** Connect educational programs to real-world outcomes by displaying regional wage and demand data for related occupations. This unlocks the "ROI" narrative and is a prerequisite for Epics 14 and 15.

**What shipped:**
- **O*NET Integration**: `loaders/load_onet_data.py` enriches occupations with Job Zone classifications.
- **BLS OEWS Integration**: `loaders/load_bls_oews.py` populates the new `OccupationWage` table with 25th, Median, and 75th percentile wage bands plus regional demand metrics (specifically KC MSA).
- **Career Trajectory Widget**: The `widget_career_trajectory.html` surfaces regional entry, median, and experienced wages natively on Program Detail pages.
- **Data Completeness**: "Linked Occupations" tables on Program and Field pages now render KC MSA Median Wages directly inline.
- **Intelligent Wage Fallback**: Implemented application-wide logic for high-earning occupations where the BLS caps and suppresses the median wage (e.g., >$239k). The UI gracefully falls back to the `annual_mean_wage` badged with an explanatory asterisk (`*`).
- **Cross-Geography Fallback**: Program profile "Linked Occupations" tables now fallback to National median/mean wages (badged with `(Nat.)`) when local KC MSA data is completely missing or suppressed for hyper-specialized roles.
- **Hubs Enrichment**: Quick Payoff Careers portal now aggressively surfaces O*NET Bright Outlook (`☀️`) badges, total local employment (`Local Jobs`), and IPEDS pipeline flow (`Graduates`) natively on the list view.
- **Graceful Rendering**: Created explicit Jinja scope handling across loops, and "Data Suppressed" tooltips for highly specialized federal records lacking top-percentile wage brackets. Added foundational/transfer crosswalk alerts for Liberal Arts (CIP 24) mappings.

---

## ✅ Epic 11b — O*NET Depth (Shipped 2026-03-29)
**Goal:** Surface the remaining high-value datasets from our existing O*NET `db_29_0_text` bundle to turn Occupation profiles from wage-tables into genuine career exploration profiles.

### Priority 1 — Shipped

**Alternate Titles (Search Power-Up)**
- **File:** `Alternate Titles.txt`
- **What it does:** Maps colloquial job titles ("Welder", "Cashier") to structured SOC codes. Ingested into `OccupationAlias` table and wired into SQLite FTS5 search (`occupation_fts`). Users searching everyday terms will land on the correct occupation profile. Also powers the Epic 15 Search Intercept.
- **Models:** New `OccupationAlias` (`soc`, `alias_title`, `short_title`)
- **UI:** Powers `/search` global search Occupation section block.

**Core Skills**
- **File:** `Skills.txt` (filter: `Scale ID = 'IM'` for Importance ratings)
- **What it does:** Maps universal competencies (Active Listening, Critical Thinking, Service Orientation) to every occupation with an importance score. Surface top 5 as compact pill-tags on the Overview tab.
- **Models:** New `OccupationSkill` (`soc`, `element_name`, `importance_score`)
- **UI:** Compact pill-tag row in `tab_overview.html` under typical tasks.

**Education & Training Requirements**
- **File:** `Education, Training, and Experience.txt` (filter: `Element Name = 'Required Level of Education'`, `Scale ID = 'RL'`)
- **What it does:** Shows percentage of current workers holding each credential level (High School, Associate's, Bachelor's, etc.). Directly answers "Do I really need a degree for this?".
- **Models:** New `OccupationEducation` (`soc`, `ed_level_code`, `ed_level_label`, `pct_workers`)
- **UI:** Single-row callout in the "Profile Overview" table on `tab_overview.html`.

### Priority 2 — Deferred

**Work Values**
- **File:** `Work Values.txt` (filter: `Scale ID = 'EX'` for Extent)
- **What it does:** Maps occupation-level drivers of job satisfaction. Deferred for now to avoid UI bloat.
- **Models:** New `OccupationWorkValue` (`soc`, `element_name`, `extent_score`)
- **UI:** Small icon-paired tag row near the description block.

---

## Epic 16 — BLS Expansion: Projections & Industry Matrix (Planned)
**Goal:** Fill the gap between "what jobs pay today" (OEWS) and "what jobs will grow" (EP) while establishing the NAICS-to-SOC crosswalk that unlocks the Employer-to-Occupation link in Epic 17.

### Dataset A: BLS Employment Projections 2023–2033
- **Source:** https://www.bls.gov/emp/data/occupational-data.htm (`ep_table_1.xlsx`)
- **Fields:** SOC code, 2023 employment, 2033 employment, `% change`, annual job openings
- **Geographic scope:** National only (BLS does not publish metro-level 10-year projections — badge clearly as `(Nat.)`)
- **Models:** New `OccupationProjection` (`soc`, `emp_2023`, `emp_2033`, `pct_change`, `annual_openings`)
- **Loader:** `loaders/load_bls_projections.py`
- **UI surfaces:**
  - Occupation Detail snapshot strip: replace placeholder `☀️` Bright Outlook with real `+14% Projected Growth` card
  - Occupations Directory: new "Growth" sort option alongside Wage and Employment
  - Hubs: replace static bright outlook badge with projected growth data

### Dataset B: BLS NAICS-to-SOC Industry-Occupation Matrix
- **Source:** https://www.bls.gov/emp/tables/industry-occupation-matrix-occupation.htm
- **Fields:** SOC code, NAICS code, NAICS title, employment share in that industry
- **Models:** New `OccupationIndustry` (`soc`, `naics_code`, `naics_title`, `pct_employment`)
- **Loader:** `loaders/load_bls_naics_soc.py`
- **UI surfaces:**
  - New "Who Hires This" section on Occupation Detail (top 5 industries as a simple table or bar visual)
  - Powers inferred employer matching in Epic 17-B

### Dataset C (Research Spike): Census LEHD Job-to-Job Flows (J2J)
- **Source:** https://lehd.ces.census.gov/data/#j2j
- **Fields:** Origin SOC, destination SOC, transition rate (probability)
- **What it does:** Shows the statistical probability that a worker in Occupation A will transition to Occupation B over a 3-year window. Directly powers the Epic 14 "Stepping Stones" career pathway widget with real transition data rather than just O*NET structural similarity.
- **Status:** Research spike — evaluate schema and decide if we store transition probabilities or compute them at query time.

---

## Epic 17 — Employer-to-Occupation Linking (Planned)
**Goal:** Close the final gap in the workforce intelligence map. Current map: `Provider → Program → Occupation`. Target map: `Employer → Occupation ← Program ← Provider`.

**Design principle:** Two strategies in parallel — deterministic (high confidence, small coverage) and inferred (lower confidence, broad coverage). Both must be clearly labeled in the UI so users know the provenance of each link.

### Strategy A: Apprenticeship Direct Links (Deterministic)
**Coverage:** ~50 KC apprenticeship sponsors currently in DB  
**Confidence:** High — these employers signed a federal DOL contract to train workers in a specific SOC code.

- Re-examine `data/raw/apprenticeship/partner-finder-listings.csv` for SOC/RAPIDS occupation code fields
- Update `loaders/load_apprenticeships.py` to parse occupation codes and create `ProgramOccupation` links for apprenticeship programs
- **UI surface (Occupation Detail):** New "Apprenticeship Sponsors in KC" section — employer names as clickable org links. Badged `Registered Apprenticeship`.

### Strategy B: NAICS Inferred Employer Matching (Probabilistic)
**Coverage:** All KC employers in DB once tagged with NAICS code  
**Confidence:** Inferred — "employers in this industry *likely* hire this occupation."

**Schema prerequisite:** Add `naics_code: Mapped[str]` to `Organization` (nullable). NAICS code sourcing options (ranked by preference):
1. Parse from apprenticeship listing CSV if industry field exists (free, immediate)
2. Manual tag for top ~50 active KC employers in the DB (quick, high accuracy)
3. Defer to Phase 3 IRS 990 ingestion which maps NTEE → NAICS automatically

**Matching logic:**
1. For a given SOC, query `OccupationIndustry` → get top industries that employ this role
2. Query `Organization` WHERE `naics_code IN (...)` AND `org_type = 'employer'` AND KC-scoped
3. Return as "Likely Employers in KC" with clear `(Inferred via industry)` badge and tooltip

**UI surface (Occupation Detail):** New collapsible "Employers in KC" section showing both Strategy A results (labeled `Registered Apprenticeship`) and Strategy B results (labeled `Inferred — employer in related industry`) in the same panel with clear visual differentiation.

**Critical rule:** Never display inferred employer links without the `(Inferred)` disclaimer. The Haystack's credibility depends on users understanding how data was derived.

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

**Design principle:** Education is not a single leap. A CNA cert leads to LPN leads to RN. Haystack should make that ladder visible, cost it out, and show the payoff at every rung. We will build UI views that natively stack related careers (e.g. Nursing Assistant [Job Zone 2] -> LPN [Job Zone 3] -> RN [Job Zone 5]), graphing wage jumps visually with a "Find Training for Next Step" affordance.

**Status:** 🔬 Research Spike — requires Labor-First primitives (Occupations directory) first.

**Research Spike:**
- **Census LEHD Job-to-Job (J2J) Flows** (see Epic 16 Dataset C) are the primary data engine for probabilistic "next step" transition probabilities. Evaluate whether we store J2J origin→destination pairs or compute at query time.
- Evaluate O*NET `RelatedOccupation` data (already ingested in Epic 11) as a structural fallback when J2J data is unavailable for a specific SOC.
- Investigate Credential Engine Registry (CTDL) for structured credential stacking schemas showing how certs roll up into degrees.
- Prototype the "Interactive ROI Slider" math: cost of credential ÷ (BLS median wage − current wage) = break-even years.

**Data dependencies:**
- Epic 11 (BLS OEWS wages) — ✅ Shipped
- Epic 16 (BLS Employment Projections + J2J Flows) — prerequisite for accurate trajectory step sizing
- Credential Engine Registry (future external ingestion).

---

## Epic 15 — The "Hidden Gems" Discovery Engine & Search Intercept
**Goal:** Intercept users who don't know what to search for by algorithmically surfacing high-ROI, low-cost programs, and redirecting labor-centric searches (e.g. "Welding") directly to occupation profiles.

**Design principle:** Change the platform from a pure search engine into an active discovery engine. Highlight community colleges, technical schools, and union apprenticeships with exceptional outcomes. Intercept semantic queries: if a user searches for a job, show them an "Occupation Card" summarizing local median wages and program counts alongside standard directory hits.

**Status:** 🔬 Research Spike — benefits significantly from BLS OEWS wage data.

**Research Spike:**
- Construct a weighted SQL scoring heuristic using: `grad_rate_150 > 60%` + `avg_cost < 10000` + `median_earnings_6yr > 45000`.
- Evaluate algorithm fragility: Does it surface statistically anomalous programs with tiny N-counts? Design a minimum completions threshold (e.g., N ≥ 25) to suppress noise.
- Prototype Search Interception: parse `SearchEvent` queries against FTS5 `occupation_fts` to inject a high-priority "Career Match" card above the fold.

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
