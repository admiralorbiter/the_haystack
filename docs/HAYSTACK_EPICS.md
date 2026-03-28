# The Haystack — Epics & Task List

**Stack:** Flask / SQLite / SQLAlchemy / Jinja2 / htmx
**Mode:** Solo developer
**Honest timeline note:** The master plan's 6-week estimate assumes parallel work. Solo, expect 14–18 weeks to reach a stable IPEDS V1. The sequence below is designed to produce working software at each epic boundary — not just progress.

---


> **Note:** Phase 1 (IPEDS Foundation, Epics 0-9) has been completed.
> V1 specifications and historical task lists are archived in `docs/archive/phase_1_ipeds/`.
> This document traces the Phase 2 expansion.

---

## Active Roadmap (Phase 2)

| Epic | Focus | Status |
|---|---|---|
| **10. Non-Title IV Training Base** | WIOA ETPL, Apprenticeships, WEAMS | 🏃 Next Up |
| **11. Workforce Connections** | BLS OEWS wage & demand integration | 🔲 Planned |
| **12. Ecosystem & Network View** | IRS 990 / Nonprofits relationships | 🔲 Planned |
| **13. Briefing Builder** | Deliverable / export generation | 🔲 Planned |

---

## Epic 10 — Non-Title IV Training Base
**Goal:** Expand Haystack beyond traditional degree-granting colleges. Ingest state and federal registries to surface short-term credentials, union trade schools, and coding bootcamps. Sequence: This must be completed fully across all three datasets before introducing wage data (Epic 11).

**Datasets to Incorporate:**
1. State WIOA ETPL (Missouri & Kansas eligible training providers)
2. DOL RAPIDS (Registered Apprenticeships)
3. VA WEAMS (GI Bill approved facilities)

**Design principle:** 
All new organizations should map seamlessly into our existing `Organization` and `Program` tables. We will apply an Identity Reconciliation pattern (fuzzy matching on name/address) to merge duplicates if a school exists in both IPEDS and ETPL. 

**Schema considerations:**
We will inspect the raw ETPL and RAPIDS data before deciding between simple boolean flags (`is_wioa_eligible`) vs a mapping table. Any approach must maintain graceful degradation (`_empty_data`) for non-IPEDS schools missing scorecard metrics.

**Exit criteria:** 
- The `/providers` directory correctly lists trade schools, union halls, and bootcamps alongside IPEDS universities.
- Provider and Program detail pages cleanly badge these entities as "WIOA Eligible", "Registered Apprenticeship", or "VA Approved" without UI crashing.

**Effort estimate:** 2 weeks

---

## Epic 11 — Workforce Connections (BLS OEWS)
**Goal:** Connect educational programs to real-world outcomes by displaying regional wage and demand data for the occupations those programs train for.

**Datasets to Incorporate:**
1. May 2023 State Occupational Employment and Wage Estimates (BLS OEWS)

**Design principle:** 
The user should never have to guess the ROI of a program. If they view a Medical Assistant program, they should immediately see the median, 25th, and 75th percentile regional wages for Medical Assistants.

**Exit criteria:** 
- The `/occupations` directory shows median salaries and annual job openings.
- Program detail pages feature a "Career Trajectory" widget showing local wages for related occupations (via the CIP->SOC crosswalk).

**Implementation notes:**
- Will load BLS data into a new `occupation_wage` table, keyed by `soc` and `county_fips` or state code.
- Relies heavily on the `program_occupation` crosswalk links established in Phase 1.

**Effort estimate:** 1 week

---

## Epic 12 — Ecosystem / Network View
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

## Epic 13 — Briefing Builder
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

### Epic 6 — Compare ✅ Shipped 2026-03-27

| Table | What it powers | Where | Status |
|---|---|---|---|
| `ipeds_ic2024` | Calendar system, admissions policy | Provider compare — Institutional Profile | ✅ Wired |
| `ipeds_cost1_2024` | In-state / out-of-state tuition | Provider compare — Admissions & Cost | ✅ Wired |
| `ipeds_adm2024` | Acceptance rate | Provider compare — Admissions & Cost | ✅ Wired |
| `ipeds_effy2024` | Total enrollment | Provider compare — Enrollment | ✅ Wired |
| `ipeds_effy2024_dist` | Distance education % | Provider compare — Enrollment | ✅ Wired |
| `ipeds_gr2024` | 150% graduation rate, Pell grad rate | Provider compare — Outcomes & Graduation | ✅ Wired |
| `ipeds_gr200_24` | 200% graduation rate | Provider compare — Outcomes & Graduation | ✅ Wired |
| `ipeds_sfa2223` | Net price (NPIST2) | Provider compare — Admissions & Cost | ✅ Wired |
| `ipeds_sfa2324` | Grant %, Pell %, loan % recipients | Provider compare — Financial Aid | ✅ Wired |
| `ipeds_ef2024d` | Student-faculty ratio | Provider compare — Outcomes & Graduation | ✅ Wired |
| `ipeds_f2324_f1a/f2/f3` | Revenue per student, instruction spending | Provider compare — Financial Health (advanced) | ⏳ Deferred Phase 2 |
| `ipeds_s2024_oc` | Full-time vs part-time faculty ratio | Provider compare — Faculty row | ⏳ Deferred Phase 2 |

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
