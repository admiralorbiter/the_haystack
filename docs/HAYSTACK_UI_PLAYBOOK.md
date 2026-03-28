# The Haystack — UI Playbook

## Goal
Create a UI system that can absorb new datasets without turning into a dashboard maze.

---

## 1. Design philosophy

### The product should feel like:
- a research tool,
- a city atlas,
- and an intelligence workspace,
not a menu tree of databases.

### Your biggest UI risk
The risk is not “too little information.”
The risk is that every source system arrives with its own mental model:
- IPEDS wants institutions and completions
- 311 wants incidents and status
- crime wants case types and time windows
- workforce wants sectors and occupations
- IRS 990 wants organizations and filings

If you let each source bring its own navigation, the product becomes incoherent.

---

## 2. The page model

Every page should answer 3 questions quickly:
1. What is this?
2. Why does it matter?
3. What can I do next?

### Standard page layout

```text
[Top nav] [Search] [Compare tray icon] [Methods]

[Breadcrumb]
[Title] [Type badge] [Location/scope] [Freshness badge]
[Quick actions: Compare | Save | Open in Map]

[Snapshot strip: 4-6 cards]

[Primary tabs]
Overview | Connections | Geography | Trends | Evidence | Methods

[Main content area]
Reusable cards / tables / lists / mini-maps

[Right drawer]
Evidence / notes / source detail / cross-links
```

---

## 3. Top-level information architecture

### Recommended nav labels
- Search
- Explore
- Map
- Compare
- Collections
- Methods

### Avoid
- IPEDS
- 311
- Crime
- IRS 990
- Census
- Workforce
as top-level nav items

Those are sources, not tasks.

---

## 4. Page types you actually need

### A. Directory page
Used for:
- providers
- programs
- organizations
- occupations
- industries
- neighborhoods
- signals

#### Structure
- filter chips at top
- compact list/table toggle
- sort control
- saved filter URL state
- summary count + active filters

#### Default list columns
Keep to 5–7 columns max.
Extra fields go in row expansion or detail page.

### B. Entity detail page
Used for:
- one provider
- one program
- one occupation
- one organization
- one tract/neighborhood

#### Structure
- summary first
- relationship graph/list second
- long tables third
- methods last

### C. Compare page
Used for:
- provider vs provider
- program vs program
- tract vs tract
- occupation vs occupation

#### Structure
- same metric order for all compared entities
- differences highlighted inline
- “best for” row at the top

### D. Map workspace
Used for:
- spatial discovery
- density and clustering
- nearby search
- geographic filtering

#### Rule
Map mode should never try to show everything at once.
One mode at a time.

---

## 5. Map modes

Recommended modes:
1. **Places** — providers, orgs, employers
2. **Conditions** — crime, 311, health, census
3. **Mobility** — traffic, transit, commute, travel time
4. **Pathways** — providers + occupations + sector overlays

Each mode should change the controls, legend, and summary bar.

---

## 6. The best pattern for dense data: progressive disclosure

### Layer 1 — visible immediately
- title
- 4–6 snapshot metrics
- one sentence takeaway
- one primary chart/table

### Layer 2 — opened by user action
- section accordions
- compare tray
- map overlay options
- row expansion

### Layer 3 — expert detail
- raw fields
- methodology
- export
- source links

### Key rule
Most users should get value without ever entering Layer 3.

---

## 7. Component library to build first

### Must-have components
- StatCard
- StatStrip
- SectionCard
- TrendLineCard
- RankedListCard
- MapCard
- CompareRow
- EntityPill
- FilterChip
- Badge
- DataFreshnessBadge
- SourceList
- EvidenceDrawer
- EmptyState
- SkeletonLoader

### Why this matters
If you build these first, every new dataset gets cheaper.

---

## 8. A practical rule for cards and charts

### Card budget per page
- snapshot strip: 4–6 cards
- core page sections: 3–5 cards visible before scrolling too much
- charts: usually 1–3 per page before secondary sections

### Chart rules
Every chart must answer one clear question:
- trend over time?
- composition?
- rank/order?
- comparison?
- distribution?

If a chart has no decision purpose, demote it below the fold or drop it.

---

## 9. Search behavior

Search should return **grouped entities**, not raw records.

### Good grouped result buckets
- Organizations
- Providers
- Programs
- Occupations
- Industries
- Places
- Signals

### Result card anatomy
- title
- entity type badge
- short descriptor
- 1–2 metrics
- why it matched
- jump actions

### Do not do
- giant undifferentiated mixed result table

---

## 10. Filters

### Recommended filter hierarchy
- quick chips first
- one “More filters” drawer second
- URL-synced state always

### Good quick filters
- geography
- entity type
- credential type
- sector
- date range
- outcome band

### Avoid
- long always-open sidebars
- source-specific jargon in primary filters
- deep dropdown trees

---

## 11. Compare tray

This should be a core product behavior.

### UX pattern
- every entity has “Add to compare”
- sticky tray at bottom/right
- compare opens in consistent layout
- max 2–4 items depending on entity type

### Why it matters
It turns a data catalog into a decision tool.

---

## 12. Evidence and methods

### Evidence drawer contents
- source list
- last refreshed date
- coverage notes
- caveats
- related notes
- download/export link

### Methods tab contents
- what this metric means
- how it is calculated
- time coverage
- join/crosswalk notes
- known limitations

This is especially important for:
- CIP↔SOC mappings
- score-based rankings
- crime/311 aggregations
- tract summaries

---

## 13. Suggested visual rhythm for Haystack

### Use strong hierarchy
- large title
- one quiet subtitle
- restrained badges
- cards with consistent density
- muted methods text

### Core Color Palette
- **Primary / Dark Raspberry:** `#870058` (use for major structural elements like top nav or primary accents)
- **Secondary / Cherry Rose:** `#A4303F` (use for buttons, active states, or highlighting key metrics)
- **Background / Papaya Whip:** `#FFECCC` (use for the main app background to give a warm, approachable feel)
- **Surface / Apricot Cream:** `#F2D0A4` (use for cards, trays, and drawers resting on the background)
- **Accent / Tea Green:** `#C8D6AF` (use for positive semantic values, success badges, or map clusters)

### Use dataset identity subtly
Dataset identity should appear in:
- source badges
- methods tab
- evidence drawer
not in the whole page layout.

---

## 14. Wireframe sketches

## 14.1 Provider detail page

```text
[Providers / Metropolitan Community College]
[Training Provider] [Kansas City, MO] [Data as of Mar 2026]
[Compare] [Open in Map]

[Programs: 34] [Award completions: 1,280] [Top field: Health] [Linked occupations: 61]

Overview | Connections | Geography | Outcomes | Scorecard | Evidence | Methods

Overview
- About this provider
- Top programs
- Largest CIP families
- Nearby neighborhoods served

Connections
- Occupations linked via CIP->SOC
- Sectors served
- Similar providers

Geography
- map + nearby tracts + travel rings

Outcomes
- completions trend by program
- grad rates and financial aid metrics

Scorecard
- 6-year median earnings
- median student loan debt
- repayment rates
- earnings by field of study
```

## 14.2 Neighborhood page

```text
[Explore / 64111]
[ZIP / Neighborhood context] [Data as of Mar 2026]

[Population] [Median income] [311 request rate] [Crime rate] [Programs nearby] [Major employers nearby]

Overview | Conditions | Opportunity | Organizations | Signals | Methods
```

---

## 15. UI anti-patterns to avoid

- adding new top-level nav for every source
- giant dashboards with 12+ visible cards
- maps with 8 toggles on by default
- filters that reset unexpectedly
- multiple competing badge/color systems
- unlabeled abbreviations in primary UI
- custom layout per entity type

---

## 16. First UI milestone

Before real scale, ship these 4 screens in production quality:
1. Program directory
2. Provider detail
3. Program detail
4. Provider compare

If those 4 feel calm and coherent, the rest of Haystack gets much easier.
