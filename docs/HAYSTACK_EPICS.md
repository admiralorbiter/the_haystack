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
| **16 BLS Expansion** | Employment Projections (growth) + NAICS-to-SOC Industry Matrix | ✅ Shipped 2026-03-29 |
| **16-C Regional Projections** | MERIC MO-level projections + QCEW local trend signals | ✅ Shipped 2026-03-29 |
| **19 KC Career Intelligence** | `/outlook` dashboard — Career Grades (A+→F), Now/Next/Later tiers, top jobs by tier | ✅ Shipped 2026-03-29 |
| **14 Stepping Stones** | Sequenced credential pathways + ROI break-even calculator | ✅ Shipped 2026-03-29 |
| **17 Employer-Occupation Link** | Apprenticeship SOC direct links + NAICS inferred employer matching | ✅ Shipped 2026-03-30 |
| **18 Industry (NAICS) Profiles** | Industry detail pages + LEHD J2J talent flow intelligence | ✅ Shipped 2026-03-30 |
| **13 Briefing Builder** | Collect stats/entities and generate printable one-pager | ✅ Shipped 2026-03-30 |
| **12 Ecosystem & Network View** | Force-directed graph at `/network` — CIP + SOC dual-mode edges | 🔲 Next Up |
| **15 Hidden Gems Engine** | Algorithmic surfacing of high-ROI programs + search intercept | 🔬 Research Spike |
| **Data Research Spike** | Proactive discovery of new regional/local datasets to fill data gaps | 🔬 Research Spike |
| **20 Phase 3: Org Enrichment** | IRS 990 financials + H-1B demand + USASpending federal awards | 🔲 Phase 3 |
| **21 Phase 4: Civic Signals** | 311, crime, permits, transit access — geography & map context | 🔲 Phase 4 |
| **22 Phase 7: Multi-Region** | Activate for St. Louis or national; region switcher in nav | 🔲 Phase 7 |

---

## ✅ Epic 16-C & 18 — Regional QCEW Integration & Industry Profiles (Shipped 2026-03-29)
**Goal:** Shift the platform from a national/state lens to a hyper-local KC-metro focus for economic signals.

**What Shipped:**
- **Comprehensive KC Data:** Re-engineered the `load_bls_qcew.py` pipeline to ingest all ownership types (Federal, State, Local, Private), covering ~174,000 regional records instead of just the private sector.
- **Data Quality Protections:** Implemented `qcew_utils.py` that automatically detects and rejects preliminary, incomplete quarterly reporting from the BLS, rolling back to the last confirmed complete quarter. 
- **Long-Run Trends:** Built a linear regression utility to calculate an annualized structural trend slope across 3 years of data, immune to single-quarter noise.
- **Home Page Pulse:** Built the "KC Labor Market Pulse" widget surfacing the top 4 growing and top 4 declining local industries (automatically ignoring statistical noise from tiny sub-500 job sectors).
- **Occupations Integration:** Replaced the generic "National Wage" column in the Occupations Directory with a highly actionable **"KC Momentum"** metric, derived via a crosswalk to the occupation's primary hiring industries.
- **Industry Directory & Profiles:** Deployed `/industries` and `/industries/<naics>` endpoints. Profile pages include 3-year bar charts, YoY momentum calculations, wage data, and explanatory breakdown panels detailing the structural trend vs. snapshot YoY logic.

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

## ✅ Epic 16 — BLS Expansion: Projections & Industry Matrix (Shipped 2026-03-29)
**Goal:** Fill the gap between "what jobs pay today" (OEWS) and "what jobs will grow" (EP) while establishing the NAICS-to-SOC crosswalk that unlocks the Employer-to-Occupation link in Epic 17.

### Dataset A: BLS Employment Projections 2024–2034
- **Source:** https://www.bls.gov/emp/data/occupational-data.htm (`occupation.xlsx` Table 1.2)
- **Fields:** SOC code, 2024 employment, 2034 employment, `% change`, annual job openings
- **Geographic scope:** National only (BLS does not publish metro-level 10-year projections — badged clearly as `(Nat.)`)
- **Models:** New `OccupationProjection` (`soc`, `emp_2024`, `emp_2034`, `pct_change`, `annual_openings`)
- **Loader:** `loaders/load_bls_projections.py`
- **UI surfaces:**
  - Occupation Detail snapshot strip: Surfaces a true `10-Yr Growth (Nat.)` percentage card with annual opening caveat.
  - Occupations Directory: New "10-Yr Growth (Nat.)" column and native support for `?sort=growth` URL filtering.

### Dataset B: BLS NAICS-to-SOC Industry-Occupation Matrix
- **Source:** https://www.bls.gov/emp/data.htm (`matrix.xlsx`)
- **Fields:** SOC code, NAICS code, NAICS title, employment share in that industry
- **Models:** New `OccupationIndustry` (`soc`, `naics`, `industry_title`, `employment_2024`, `pct_of_occupation`)
- **Loader:** `loaders/load_bls_matrix.py`
- **UI surfaces:**
  - Embedded "Who Hires This?" widget on Occupation Detail `tab_overview.html` under Regional Earnings.
  - Directly powers inferred employer matching in Epic 17-B.

### Dataset C (Research Spike): Census LEHD Job-to-Job Flows (J2J)
- **Source:** https://lehd.ces.census.gov/data/#j2j
- **Status:** 🚫 Cancelled for Epic 16. The research spike confirmed that Census J2J data tracks worker movements via *firm/industry (NAICS)* tax records, **not** by *job title/occupation (SOC)*. Therefore, it cannot be used to calculate Occupation-to-Occupation stepping stones.
- **Pivot to Epic 18:** We will instead leverage this incredibly powerful dataset when we build out **Industry (NAICS) Profiles**. It will natively answer: "Where does this Industry bleed talent to, and where does it poach talent from?" along with the average earnings bump for making an industry jump.

---

## ✅ Epic 16-C — Regional Projections: MERIC + QCEW (Partial)
**Goal:** Replace the "national projections only" limitation with real local and state-level growth signals that are meaningful to a student in Wyandotte County who can't commute across the metro.

**Design principle:** The national `(Nat.)` badge on projections data is a transparency disclaimer, not a design goal. Locality matters enormously for students without transportation. Every projection we surface should be as close to "your backyard" as the data allows.

### Dataset C1: MERIC Missouri 10-Year Occupation Projections
- **Source:** https://meric.mo.gov/workforce-data-tools/download-center — "Long-Term Occupational Employment Projections"
- **Fields:** SOC code, 2022 base employment, 2032 projected employment, % change, annual openings — all for Missouri statewide
- **Geographic scope:** Missouri statewide (closest public source to local projections available)
- **Models:** Extend `OccupationProjection` to add `mo_emp_base`, `mo_emp_projected`, `mo_pct_change`, `mo_annual_openings` columns (optional — or create a new `OccupationProjectionMO` spoke table)
- **Loader:** `loaders/load_meric_projections.py`
- **UI surfaces:**
  - Occupation Detail snapshot strip: Add a MO-level `📍 MO Growth` stat card alongside the national card.
  - Occupations Directory: New `?sort=growth_mo` option for locally-relevant sorting.

### ✅ Dataset C2: BLS QCEW (Quarterly Census of Employment and Wages) — Local Trend Signal (Shipped 2026-03-29)
- **Source:** https://www.bls.gov/cew/downloadable-data.htm — County-level, by NAICS, quarterly
- **Fields:** NAICS code, county FIPS, quarter, establishment count, employment, average weekly wage
- **Geographic scope:** KC Metro FIPS codes. Filtered to Ownership Code 5 (Private Sector) to ensure NAICS granularity.
- **What it does:** Rather than a forecasted projection, this gives a *real, local, quarterly trend* — "KC area Manufacturing employment grew 2.1% over the last 4 quarters." Combined with our `OccupationIndustry` (matrix) crosswalk, we can infer local occupation demand signals.
- **Models:** New `IndustryQCEW` table (`naics`, `county_fips`, `year`, `quarter`, `establishments`, `employment`, `avg_weekly_wage`)
- **Loader:** `loaders/load_bls_qcew.py`
- **UI surfaces:**
  - Occupation Detail "Who Hires This?": Augment each Industry row with a local QCEW trend indicator (▲ Growing / ▼ Declining in KC area).
  - Future: Powers Epic 18 Industry Profile pages as the primary local employment time-series chart.

### Data Research Spike
**When to run:** Before starting Epic 16-C development, spend a session evaluating:
- MERIC download format (Excel vs CSV, column names, vintage year)
- Whether QCEW county files are feasibly scoped (they are large) — consider only Jackson + Johnson + Wyandotte + Clay for the KC metro
- Any additional Missouri state labor data sources (e.g., Missouri DED, KC Regional Labor Market Information)
- Kansas-side data sources (KLIC, KANSASWORKS) for the full KC bi-state metro

---

## ✅ Epic 13 — Briefing Builder (Shipped 2026-03-30)
**Goal:** Provide researchers and grant-writers a workspace to collect multiple discrete platform entities (providers, occupations, programs) into a single unified exportable report.

**What shipped:**
- **Session Architecture:** Leveraged stateless Flask `session[]` storage, enabling instant cross-entity collection without forcing users to create accounts.
- **HTMX Ecosystem:** Engineered the `briefing_btn.html` component that uses `hx-swap-oob` to seamlessly update the global navigation counter without triggering full page reloads.
- **Entity Injection:** Retrofitted the "Save to Briefing" framework into the quick-actions headers of all four core domain entities (Providers, Programs, Occupations, Industries).
- **Review Hub (`/briefing`):** Deployed a centralized staging area allowing inline title editing, entity review, and removal with responsive UX styling.
- **Print Export (`/briefing/print`):** Created a dedicated, ink-optimized PDF rendering endpoint that hydrates the saved IDs against the backend SQLite database to fetch the latest IPEDS completions, QCEW wages, and O*NET career grades dynamically at runtime.
- **Automated Testing:** Wrote a comprehensive 10-test `pytest` harness validating border cases, session exhaustion, and database attribute rendering explicitly.

---

## ✅ Epic 17 — Employer-to-Occupation Linking (Shipped 2026-03-30)
**Goal:** Close the final gap in the workforce intelligence map. Current map: `Provider → Program → Occupation`. Target map: `Employer → Occupation ← Program ← Provider`.

**What shipped:**
- **Hybrid Data Loader:** Engineered `load_major_employers.py` utilizing the regional *Major Employers* dataset. Overcame string inconsistency ("Headquarters") by implementing a dynamic 3-digit NAICS crosswalk paired with a secondary `Description` substring scanner (detecting keywords like 'auto parts', 'hospital', 'city government').
- **Idempotent Storage:** Augmented `Organization` model with a 6-char `naics_code` schema and `OrgFact` integration for tracking total regional employees.
- **Two-Pass Inference Logic:** Wired the `occupations.py` routing engine to parse associated Industry matrices. Pass 1 strictly searches for 3-digit NAICS employer matches (highest confidence). If empty, Pass 2 degrades to a broad 2-digit Sector search (generalized regional matches).
- **Transparency UI:** Deployed the "Likely Employers in KC" widget below the Who-Hires-This table. Dynamically badges entities as `Strong Match: 3-Digit NAICS` or `Broad Match: Sector Level` to guarantee platform credibility and ensure users immediately understand the data's provenance.

### Strategy A: Apprenticeship Direct Links (Deterministic)
**Coverage:** ~50 KC apprenticeship sponsors currently in DB  
**Confidence:** High — these employers signed a federal DOL contract to train workers in a specific SOC code.
**Status:** 🛑 Partially Blocked. The `partner-finder-listings.csv` does **not** contain SOC/RAPIDS codes or any industry field. It only contains sponsor names and contact info. We need the raw DOL RAPIDS database or an alternative source to map these to occupations.

- Re-examine `data/raw/apprenticeship/partner-finder-listings.csv` for SOC/RAPIDS occupation code fields (❌ Failed: data missing)
- Update `loaders/load_apprenticeships.py` to parse occupation codes and create `ProgramOccupation` links for apprenticeship programs
- **UI surface (Occupation Detail):** New "Apprenticeship Sponsors in KC" section — employer names as clickable org links. Badged `Registered Apprenticeship`.

### Strategy C: BLS QCEW Establishment Count (Aggregate Signal)
**Coverage:** All industries in the KC metro  
**Confidence:** Aggregate — "there are 47 healthcare establishments operating in the KC metro, which is growing."

Once `IndustryQCEW` is loaded (Epic 16-C), we can surface aggregate employer presence without needing a named employer list. This is valuable for occupations in industries where named employer data is sparse.
- **UI surface (Occupation Detail):** Supplement "Who Hires This?" with a KC metro establishment count per industry row.
- **Source linkage:** `OccupationIndustry.naics` → `IndustryQCEW.naics` WHERE county IN KC metro counties.

### KC Employer Data Research Spike
Before building Strategy B/C, evaluate these named employer data sources for the KC region:
- **Missouri Secretary of State** — registered business database with NAICS codes (free, bulk download)
- **KANSASWORKS / KLIC** — Kansas labor market employer registry for the bi-state metro
- **DataAxle / ReferenceUSA** — licensed business directory (check if PREP-KC has an institutional subscription)
- **KCMO Open Data Portal** — business license data with industry codes

### Strategy D: Employer Recruitment Pipelines (J2J Intelligence)
**Coverage:** 20 Primary 2-Digit NAICS Sectors
**Confidence:** High — Tracks state-level tax records of job-to-job worker movements across the trailing 12 months.

Once `IndustryFlowJ2J` is populated (Epic 18), we can synthesize a "Recruitment Origin Matrix" on an Employer's profile page. When a user views an Employer in the "Manufacturing" sector, the platform can dynamically display:
*Employers in this sector most commonly recruit active talent from the following industries:*
1. Administrative and Support Services
2. Retail Trade
3. Construction

- **Backend Logic:** Query `IndustryFlowJ2J` where `destination_naics` equals the Employer's primary `naics_code` prefix. Calculate the highest outbound `transitions` from a distinct `origin_naics`.
- **UI Surface:** A flex-grid visualization injected onto the `templates/employers/detail.html` layout to guide institutional partnership targeting.

---

## ✅ Epic 19 — KC Career Intelligence Dashboard (Shipped 2026-03-29)
**Goal:** Build a `/outlook` page and occupation-level "Career Grades" using a proprietary weighted algorithm to assess demand, wage, trajectory, automation risk, and job zone ROI.

**What shipped:**
- **External Data Ingestion:** Automated loaders for O*NET Bright Outlook (`load_onet_bright_outlook.py`), Frey & Osborne Automation Risk (`load_automation_risk.py`), and Dingel & Neiman Remote Work Potential (`load_remote_potential.py`).
- **KC Career Grade Algorithm:** Custom 100-point percent-rank weighted index scoring local occupations based on openings, growth, median wage, QCEW local momentum, automation risk, and ROI.
- **Career Intelligence Dashboard:** New `/outlook` interactive UI surfacing top SOC groups and tier-based career leaderboards.
- **UI Integration:** Wired new indicators (Bright Outlook, Remote-Capable, Auto-Risk) across the entire platform, including global Search Results and all Occupations directory tables.

---

## ✅ Epic 18 — Industry (NAICS) Profiles (Shipped 2026-03-30)
**Goal:** Build dedicated Industry profile pages that let users explore KC-area employment by sector, see talent pipeline flows between industries, and understand which industries are growing vs contracting.

**Design principle:** Just as Occupation profiles answer "is this job good?", Industry profiles answer "is this sector healthy in KC?" These pages will be the future home of all NAICS-level data, including the J2J talent flow intelligence that was too broad for the Occupation layer.

**Prerequisites:** Epic 16-C QCEW loaded, Epic 17 NAICS tagging on employers.

### ✅ Phase A: Industry Directory (Shipped 2026-03-30)
- Basic NAICS directory page at `/industries`
- Sources employment totals from `IndustryQCEW` (QCEW county data)
- Shows list of broad sectors (Agriculture, Manufacturing, Healthcare, etc.) with KC-area employment counts
- **UI UX:** Includes a zero-latency JavaScript fallback filter to toggle between `All Industries`, `2-Digit Super Sectors`, and `Granular Sub-Industries`.

### ✅ Phase B: Industry Detail Pages (Foundation Shipped 2026-03-29)
- Started early during Epic 16-C to surface QCEW data.
- `/industries/<naics>` — a profile page for a specific industry
- **Snapshot strip:** Total KC establishments, total KC employment, avg weekly wage. Includes an interactive 12-quarter bar chart.
- **Top Occupations:** (Pending) Pulls from `OccupationIndustry` to show which job titles dominate this sector
- **Training Pathways:** (Pending) Pulls from `ProgramOccupation` to surface KC training programs that feed into this industry

### ✅ Phase C: LEHD J2J Talent Flow Intelligence (Shipped 2026-03-30)
- **Source:** https://lehd.ces.census.gov/data/#j2j  
- **What it does:** Tracks where workers *come from* when they join an industry, and where they *go* when they leave — by prior/next industry (NAICS).
- **Architecture:** Bypasses 130M+ rows of granular demographic partitions by strictly querying `ind_level == 'S'` (Sector) and parsing structural summary demographic codes (`A00`, `E0`). Required summing the `EE` (Continuous Employment) and `AQHire` (Adjacent-Quarter Hires) fields to reconstruct total inter-sector transitions.
- **UI widget:** "Talent Pipelines" — a fast, flex-block dual-list showing the trailing 4-quarters of top 5 inbound origins and outbound destinations.
- **Loader:** `loaders/load_lehd_j2j.py`
- **Models:** `IndustryFlowJ2J`

---

## Epic 12 — Ecosystem / Network View
**Goal:** Render a living, force-directed graph of KC's training ecosystem — making relationships between providers, programs, employers, and occupations visually navigable at `/network`.

**Design principle:** The List view shows *what exists*. The Network view shows *how things connect*. This is the layer that turns a directory into a network intelligence tool.

**Exit criteria:** `/network` renders a Cytoscape.js canvas with provider nodes sized by completions, colored by dominant CIP family, and connected by dual-mode edges (CIP-overlap + SOC-overlap). Clicking a node opens a side-panel detail drawer.

**Effort estimate:** ~1.5 days

### Architecture Decisions
- **Page location:** Own page at `/network` (not a sub-page of providers)
- **Edge mode:** Dual-mode — CIP-overlap edges (same training field) + SOC-overlap edges (same job market). Edges merged when both exist (`edge_type = "both"`)
- **Edge storage:** On-the-fly for V1 (computed in API endpoint). Phase 6 will pre-materialize via `load_network_edges.py`
- **Node scope:** Top 75 providers by IPEDS completions
- **Graph library:** Cytoscape.js (CDN, no npm build step)

### V1 Implementation

**Models (`models.py`):**
- Add `RelationshipType` constants class (mirrors `OrgFactType`) locking canonical `rel_type` strings:
  - `PARENT_ORG`, `SHARED_CIP`, `SHARED_SOC`, `LIKELY_HIRES`, `FUNDS`, `SHARED_BOARD`, `TALENT_ORIGIN`

**API (`routes/api/network.py`):**
- `GET /api/v1/network/providers` — returns `{nodes: [], edges: []}` JSON
- `?edge=both|cip|soc` and `?limit=75` query params
- Algorithm: top-N providers → CIP pairwise overlap → SOC pairwise overlap → merge → prune edges weight < 2

**Route (`routes/network.py`):**
- `GET /network` — renders canvas page; passes CIP family list + county list for filters

**Template (`templates/network/index.html`):**
- Control bar: edge mode selector, CIP family filter, county filter, node count badge
- Full-height `#cy` Cytoscape canvas
- Click-to-open side panel drawer (name, city, completions, CIP, link to provider detail)
- Color legend: CIP families + edge type colors (CIP=teal, SOC=amber, Both=purple)
- Methods footer with data-as-of date

### Phase 6 Network Edges (Future Data Sources)

| Relationship | `rel_type` | Source | Status |
|---|---|---|---|
| Parent ↔ Satellite | `parent_org` | `link_org_parents.py` | ✅ Live |
| Employer → Occupation | `likely_hires` | `OccupationIndustry` NAICS xwalk | ✅ Logic exists, not yet stored |
| Funder → Grantee | `funds` | IRS 990 / ProPublica | 🔲 Phase 3 |
| Board Member Crossover | `shared_board_member` | ProPublica / Candid | 🔲 Phase 6 |
| Supply Chain | `supplies_to` | BEA Input-Output tables | 🔲 Phase 6 |
| Industry Talent Flow | `talent_pipeline_origin` | LEHD `IndustryFlowJ2J` (loaded) | ✅ Data ready, needs graph surface |
| Apprenticeship → SOC | `apprenticeship_trains_for` | DOL RAPIDS | 🛑 Blocked (data missing SOC fields) |

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

## ✅ Epic 14 — Stepping Stones & ROI Break-Even Pathways (Shipped 2026-03-29)
**Goal:** Shift from static occupation endpoints to sequenced, connected career pathways — helping users trace the journey from entry-level to their ultimate goal, with every step costing real money and paying real wages.

**What shipped:**
- **Pathway Segmentation:** O*NET Job Zones group related careers into "Next Steps" (Upskilling), "Lateral Moves", and "Previous Steps".
- **Strict Economic Filter:** Algorithmic gating logic prevents "False Promotions" by requiring Next Steps to offer a >10% median wage jump.
- **Skill Gaps Engine:** Matrix diffs the user's current `OccupationSkill` vs the target's, isolating top numerical capability jumps (e.g., "Critical Thinking +15").
- **Local ROI Break-Even Math:** A reactive client-side Break-Even calculator integrated into "Next Step" cards. It proactively pulls the targeted `scorecard_field_of_study.debt_stgp_mdn` to pre-fill the cost of KC training programs, outputting years-to-pay-off instantly.

**Data dependencies:**
- Epic 11 (BLS OEWS wages) — ✅ Shipped
- Epic 16 (BLS Projections + Industry Matrix) — ✅ Shipped
- Epic 16-C (MERIC regional projections) — provides step-sizing by local growth signal
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

## Epic 20 — Phase 3 Organization Enrichment (IRS 990 + H-1B)
**Goal:** Strengthen the organization spine with financial health signals from IRS 990 filings and immigration/skills demand signals from H-1B petition data.

**Status:** 🔲 Planned (Phase 3)

**Prerequisites:** `org_fact` EAV table (✅ shipped in Epic 2.9), `is_active` soft-delete (✅ shipped), `ein` field on Organization (✅ present)

### Dataset A: IRS Form 990 Filings
- **Source:** AWS Public Data (`s3://irs-form-990/`) or ProPublica Nonprofit Explorer API
- **Fields:** EIN, revenue, expenses, net income, top executive salaries, program service expenses
- **Models:** `OrgFact` rows with `fact_type IN ('revenue', 'expenses', 'net_income')` (schema already supports this)
- **UI surfaces:**
  - Organization detail page: New "Financial Health" tab (revenue trend, program vs admin spend ratio)
  - Provider detail: Endowment context for tuition justification

### Dataset B: DOL H-1B Petition Data  
- **Source:** DOL Office of Foreign Labor Certification public disclosure data
- **Fields:** Employer name, SOC code, wage offered, petition count, decision year
- **Models:** `OrgFact` rows with `fact_type = 'h1b_petitions'`
- **UI surfaces:**
  - Employer detail pages: "High-Skills Demand" signal badge
  - Occupation detail: "Who sponsors H-1B visas for this role?" widget

### Dataset C: USASpending Federal Contracts & Grants
- **Source:** https://usaspending.gov/download_center/award_data_archive
- **Fields:** Recipient name/EIN, award amount, agency, award type, NAICS
- **Models:** `OrgFact` rows with `fact_type = 'federal_award'`; future `Relationship` rows with `rel_type = 'funds'`
- **UI surfaces:**
  - Organization detail: Federal funding timeline
  - Phase 6: Funder → Grantee network edges

---

## Epic 21 — Phase 4 Civic Signal Layer (311 + Crime + Permits)
**Goal:** Add city-condition context to neighborhoods, making it possible to understand the environment surrounding training providers and employers.

**Status:** 🔲 Planned (Phase 4)

**Design principle:** Civic signals should surface primarily through Geography pages and Map mode — NOT on provider/program pages where they would distract from workforce data.

### Planned Sources
- **KCMO 311 Service Requests** — KCMO Open Data Portal (public CSV)
- **Crime/Incident Reports** — KCMO Open Data Portal
- **Building Permits** — KCMO development activity signal
- **Transit Access** — GTFS feeds for KCATA and KC Streetcar

### Primary UI Surfaces
- `GeoArea` detail pages (ZIP, tract, county) — signal density maps
- Map mode: choropleth layer for 311 density or crime concentration
- Provider detail — small "Neighborhood Context" strip (transit access + service density only)

---

## Epic 22 — Phase 7 Multi-Region Expansion
**Goal:** Activate Haystack for a second metro region (St. Louis or national).

**Status:** 🔲 Future (Phase 7)

**Design principle:** This is not a rewrite — it is the payoff for building the region-configurable architecture in Phase 0. The `Region` and `RegionCounty` models already exist; loaders already use `get_kc_county_fips()` which queries from the DB.

**What's needed:**
- New `geo_scope` region record with a name and bounding FIPS set (seed data only)
- Region switcher in top nav (`"Kansas City" | "St. Louis" | "National"`)
- Cross-region comparison via Compare surface
- All IPEDS/BLS loaders tested with `--region stl` flag

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
