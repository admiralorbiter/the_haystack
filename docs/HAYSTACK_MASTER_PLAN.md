# The Haystack — Master Plan

## Purpose
Build **The Haystack** as a modular, place-based intelligence platform that maps the interconnected systems of any region — starting with Kansas City.

The Haystack answers: *Who is here, what do they offer, how are they connected, and what conditions surround them?*

This plan is built on:
- a region-configurable geographic scope (start with KC MSA, expand to any metro)
- an offline-first snapshot pipeline
- explicit, stable identifiers and crosswalks (NAICS, SOC, CIP, GEOID, EIN)
- a unified organization spine with a relationship/network layer
- and a strong evidence model separating data from interpretation

## Core recommendation
Do **not** design Haystack around datasets.

Design it around:
1. **Core entities**
2. **Stable UI shells**
3. **Repeatable dataset intake rules**
4. **Progressive disclosure**

A new dataset should feel like “new evidence inside a familiar product,” not “a whole new feature area.”

---

## 1. Product architecture

### 1.1 Haystack should have 6 durable entity types
These entities should remain stable even as data sources change.

#### A. Geography
Examples:
- metro
- county
- city
- ZIP
- tract
- council district
- neighborhood

Questions answered:
- What is happening here?
- How does this place compare to nearby places?
- What organizations, programs, incidents, and trends are tied to this area?

#### B. Organization
Examples:
- college
- employer
- nonprofit
- public agency
- hospital
- union
- chamber

Questions answered:
- Who is this?
- Where are they?
- What do they do?
- What data do we know about them?

#### C. Program / Offering
Examples:
- college program
- certificate
- apprenticeship
- bootcamp
- grant-funded initiative

Questions answered:
- What is offered?
- What skills/occupations does it connect to?
- What outcomes exist?

#### D. Work / Opportunity
Examples:
- industry
- occupation
- employer cluster
- pathway

Questions answered:
- What jobs exist?
- What is growing?
- What credentials and providers connect to it?

#### E. Civic Signal
Examples:
- 311 request
- crime incident
- traffic event
- permit
- code violation
- economic event

Questions answered:
- What happened?
- Where is it happening?
- Is it isolated or patterned?

#### F. Relationship / Network
Examples:
- supplier → buyer (supply chain)
- funder → grantee
- employer → training partner
- org → person (board member, alumni)
- org → org (shared leadership, acquisition)
- program → occupation (CIP↔SOC is a relationship)

Questions answered:
- How are these entities connected?
- Who flows resources to whom?
- What pathways exist between a person and an opportunity?
- What organizations sit at the center of a local network?

Schema concept:
```
relationship — rel_id, from_entity_type, from_entity_id, to_entity_type, to_entity_id,
               rel_type, weight, confidence, source, valid_from, valid_to
```

This is the layer that turns a directory into a network intelligence tool.

---

## 2. Stable top-level navigation

Top-level navigation should stay fixed even as datasets grow.

### Recommended nav
- **Search**
- **Explore**
- **Map**
- **Compare**
- **Collections**
- **Methods**

### Why this works
- It keeps the app organized around user tasks, not source systems.
- It avoids the trap of adding a new nav item for every new dataset.
- It lets IPEDS, crime, 311, workforce, and IRS 990 all plug into the same frame.

### What each area does
#### Search
Global grouped search across all entities.

#### Explore
A detail-first browser for organizations, programs, places, occupations, industries, and signals.

#### Map
A spatial workspace with a small number of controlled modes.

#### Compare
Entity comparison: provider vs provider, tract vs tract, occupation vs occupation.

#### Collections
Curated saved views or “topic bundles” such as:
- Higher education
- Neighborhood conditions
- Safety and service demand
- Workforce pathways
- Civic infrastructure

#### Methods
Data freshness, sources, caveats, refresh dates, field definitions.

---

## 3. UI grammar: every page should use the same pattern

Every detail page should follow this order:

1. **Header**
   - name
   - type badge
   - location / scope
   - freshness
   - quick actions

2. **Snapshot strip**
   - 4 to 6 metrics max
   - one-line labels
   - no tiny text walls

3. **Primary tabs**
   - Overview
   - Connections
   - Geography
   - Trends
   - Evidence
   - Methods

4. **Expandable sections**
   - show only 1–2 sections open by default
   - everything else available via “show more” or accordion

5. **Evidence / methodology footer**
   - sources
   - as-of date
   - caveats

### Rule of thumb
If a page needs more than 6 things visible at once, it probably needs:
- tabs,
- secondary drawers,
- or a comparison view,
not more cards on the canvas.

---

## 4. The key UI idea: lenses, not menus

Instead of asking the user to navigate source systems, let them change **lenses**.

### Recommended lens system
For any entity, expose the same lens choices when relevant:
- **Summary** — the shortest useful answer
- **Outcomes** — completions, earnings, demand, trends
- **Place** — geography, map, nearby context
- **Connections** — linked orgs, programs, occupations, sectors
- **Signals** — events, news, incidents, service requests
- **Methods** — provenance and caveats

This keeps the UI consistent even when the underlying data changes.

---

## 5. The shell you should build first

Before adding many datasets, freeze the shell.

### 5.1 Global shell
- fixed top nav
- universal search box
- breadcrumb
- right-side evidence drawer
- page-level compare tray
- consistent filter chip row

### 5.2 Universal components
Build these once and reuse them everywhere:
- StatCard
- TrendCard
- MapCard
- EntityTable
- ConnectionList
- EvidenceDrawer
- CompareTray
- FilterChips
- SectionAccordion
- DataFreshnessBadge
- EmptyState
- LoadingSkeleton

### 5.3 Page templates
Create 4 reusable page templates:
1. **Directory page**
2. **Entity detail page**
3. **Map workspace**
4. **Compare page**

New datasets should populate templates, not create unique page types.

---

## 6. Data onboarding contract

Each new dataset must answer the same intake questions.

### 6.1 Dataset contract
For every dataset, define:
- dataset name
- owner/source
- license/usage notes
- update cadence
- grain
- primary entity
- geography support
- join keys
- freshness field
- quality caveats
- default UI surfaces
- compare support
- map support
- export support

### 6.2 UI contract
For every dataset, define:
- default list columns
- default metric cards
- default filters
- detail tabs used
- map layer type
- compare metrics
- methods copy

### 6.3 Ship criteria
A dataset is not “added” until it has:
- loader
- QA checks
- freshness metadata
- at least one directory/detail surface
- methods text
- empty/loading states
- one compare or map surface when relevant

---

## 7. Recommended phased roadmap

## Phase 0 — Haystack foundation
**Goal:** freeze the shell before data growth.

Build now:
- top nav
- universal search
- entity detail template
- compare tray
- evidence drawer
- methods pattern
- shared filter chips
- data freshness badge

### Exit criteria
- You can render a detail page for any entity with the same layout.
- You can plug in mock data without inventing new UI patterns.

---

## Phase 1 — IPEDS first slice
**Goal:** make higher-ed and training data the first complete vertical.

Deliver:
- Provider directory
- Provider detail
- Program directory
- Program detail
- CIP/field page
- occupation connection section
- map of providers
- compare providers/programs
- College Scorecard earnings & debt outcomes
- methods page for IPEDS + Scorecard

### Why IPEDS first
IPEDS is structured, high-value, and naturally tied to organizations, programs, geography, completions, and outcomes.
It is ideal for proving the Haystack pattern.

---

## Phase 2 — Scorecard and workforce connection
**Goal:** turn IPEDS into pathways intelligence.

Add:
- OEWS wage data by SOC
- SOC/CIP crosswalk surfaces
- occupation detail links to programs
- provider-to-sector and provider-to-occupation views
- compare program outcomes vs occupation wages

This is where Haystack becomes more than a directory.

---

## Phase 3 — Organization enrichment
**Goal:** strengthen the organization spine.

Add:
- IRS 990
- FDIC / NCUA
- SEC EDGAR
- USASpending
- H-1B

Expose them as reusable “organization evidence blocks,” not one-off pages.

---

## Phase 4 — Civic signal layer
**Goal:** add city-condition context.

Add next:
- 311
- crime
- permits
- code enforcement
- transit / traffic

Important:
These should enter Haystack primarily through:
- Geography pages
- Map mode
- Signal collections
- Organization/place context panels

Do **not** let them overwhelm program/provider pages.

---

## Phase 5 — Integrated neighborhood intelligence
**Goal:** connect training opportunity to neighborhood conditions.

Examples:
- provider access vs crime exposure
- training supply vs 311 burden
- program density vs transit access
- pathways by neighborhood

This is where Haystack becomes distinctly local and hard to replicate.

---

## Phase 6 — Network and relationship layer
**Goal:** map the connections between entities, not just the entities themselves.

Add:
- `relationship` table to track directional entity links with type, weight, source
- Supply chain mapping (USAS spending, USASpending contracts, BEA input-output tables)
- Funding flows (IRS 990 grants-out, USASpending awards)
- Board and leadership networks (ProPublica Nonprofit Explorer, OpenCorporates)
- Employer-to-training partnerships (apprenticeship registrations, MOU datasets)
- Alumni pathways (aggregate, anonymized Scorecard fields-of-study data)

UI surfaces:
- Network graph view for an organization's connections
- "Who funds this?" and "Who does this fund?" panels on org detail pages
- Supply chain context panel on employer pages
- Pathway tracer: from program → occupation → employer cluster

This is where Haystack becomes irreplaceable.

---

## Phase 7 — Multi-region expansion
**Goal:** activate Haystack for a second metro region.

By this point the architecture should allow:
- Adding a new `geo_scope` region record with a name and bounding FIPS set
- Running existing loaders with a `--region` flag to ingest data for the new area
- UI region switcher in the top nav (e.g., "Kansas City" | "St. Louis" | "National")
- Cross-region comparison via the Compare surface

This is not a rewrite — it is the payoff for building the region-configurable architecture in Phase 0.

---

## 8. What to keep from your existing docs

Keep these ideas intact because they are strong:
- persona-aware framing
- organization as a central spine
- explicit identifiers: NAICS, SOC, CIP, GEOID
- offline-first snapshot publishing
- evidence separated from interpretation
- research notes and qualitative signals

But shift the product framing from “many routes” to “few durable shells.”

---

## 9. Design rules to prevent UI sprawl

### Non-negotiable rules
1. **No new top-level nav item per dataset.**
2. **No page launches without methods/freshness.**
3. **No detail page with more than 6 snapshot metrics.**
4. **No nested filter sidebars deeper than one level.**
5. **No dataset-specific color systems.**
6. **No chart without a one-sentence takeaway.**
7. **No metric added without a display label, unit, and caveat.**

### Good defaults
- chip filters before dropdown forests
- grouped search results before giant tables
- drilldowns in drawers before full page jumps
- summary first, dense tables second
- reusable tabs before bespoke layouts

---

## 10. Definition of done for Haystack increments

A slice is “done” when all are true:
- the data loads cleanly
- the entity is searchable
- the detail page uses the shared shell
- freshness and methods are visible
- one comparison path exists
- one spatial path exists when relevant
- no new nav category was needed
- empty states are clear
- mobile layout still works

---

## 11. Suggested first 6-week build order

### Week 1
- freeze top-level IA
- define entity types
- define shared components
- create dataset intake template

### Week 2
- implement provider directory + detail shell with mock data
- implement program directory + detail shell with mock data

### Week 3
- connect IPEDS institutions and programs
- add CIP filters and basic map layer

### Week 4
- add CIP→SOC links and provider compare
- methods/freshness + evidence drawer

### Week 5
- add Scorecard outcomes
- tune empty states, sorting, search grouping

### Week 6
- QA
- performance pass
- write the next dataset spec (likely 311 or organization enrichment)

---

## 12. Final recommendation

Think of Haystack as a **kernel plus modules**:
- the **kernel** is the entity model + UI shell + methods system,
- the **modules** are datasets,
- the **value** comes from cross-connections.

If you lock the shell first, you can keep adding data for a long time without redesigning the product every month.
