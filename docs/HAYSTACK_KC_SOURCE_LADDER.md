# The Haystack — Dataset Source Ladder

## Goal
A practical, universal sequence for adding datasets to any Haystack region without overwhelming the product.

This ladder describes **what to add and why**, in a sequence that maximizes value while keeping the platform coherent. KC-specific sources are called out explicitly.

---

## Recommended order

### Tier 1 — Prove the shell
1. **IPEDS**
   - Why first: structured, high value, stable, entity-friendly
   - Primary entities: Provider, Program, Field of Study
   - First UI surfaces: provider directory, program pages, compare, provider map

2. **College Scorecard**
   - Why second: outcome layer for IPEDS
   - Primary entities: Provider, Program/Field
   - First UI surfaces: earnings cards, outcome compare, methods notes

3. **Occupation / workforce linkage**
   - Why third: turns education inventory into pathways intelligence
   - Primary entities: Occupation, Program, Provider
   - First UI surfaces: occupation links, sector links, compare context

---

## Tier 2 — Strengthen the organization spine
4. **IRS 990 / BMF**
   - Why: adds nonprofit finance and identity depth to organizations
   - Primary entities: Organization
   - UI surfaces: organization evidence blocks, filters, compare metrics

5. **SEC EDGAR / FDIC / NCUA / USASpending / H-1B**
   - Why: enrich organizations with credible, structured facts
   - Primary entities: Organization
   - UI surfaces: detail cards, filters, collections, compare

---

## Tier 3 — Add civic signal layers
6. **311 service requests**
   - Why: strong neighborhood condition signal, map-friendly, operationally meaningful
   - Primary entities: Civic Signal, Geography
   - UI surfaces: map mode, neighborhood conditions, trend summaries

7. **Crime**
   - Why: major local context layer, high user interest, place-based relevance
   - Primary entities: Civic Signal, Geography
   - UI surfaces: map mode, neighborhood conditions, compare by place/time window

---

## Tier 3 — Add civic signal layers
6. **311 service requests**
   - Why: strong neighborhood condition signal, map-friendly, operationally meaningful
   - Primary entities: Civic Signal, Geography
   - UI surfaces: map mode, neighborhood conditions, trend summaries
   - *KC-specific: KC Open Data 311 portal*

7. **Crime**
   - Why: major local context layer, high user interest, place-based relevance
   - Primary entities: Civic Signal, Geography
   - UI surfaces: map mode, neighborhood conditions, compare by place/time window
   - *KC-specific: KCPD open data, JoCo Sheriff data*

8. **Traffic / mobility**
   - Why: makes place-based exploration more useful and concrete
   - Primary entities: Geography, Civic Signal
   - UI surfaces: map mode, commute overlays, nearby/travel friction context

---

## Tier 4 — Network and relationship layer
9. **USASpending / federal contracts and grants**
   - Why: maps funding flows between the federal government and local organizations
   - Primary entities: Organization, Relationship
   - UI surfaces: org evidence block ("receives X in federal awards"), funding network panel

10. **BEA Input-Output tables**
    - Why: supply chain relationships between industries at the regional level
    - Primary entities: Occupation/Industry, Relationship
    - UI surfaces: supply chain context panel, "this sector buys from / sells to" view

11. **IRS 990 grants-out data**
    - Why: maps philanthropic funding flows between nonprofits
    - Primary entities: Organization, Relationship
    - UI surfaces: "Who funds this?" and "Who does this fund?" on org detail pages

---

## Source categories to keep distinct in the product
Do not mix these into one giant view by default.

### Structured inventory data
- IPEDS
- Scorecard
- IRS 990
- SEC
- FDIC
- NCUA

### Labor and pathway data
- occupations
- industry
- wage and outlook datasets
- CIP↔SOC mappings

### Civic signals
- 311
- crime
- traffic
- permits
- code enforcement

### Place context
- Census
- CDC
- HUD
- USDA

These categories should connect behind the scenes, but stay visually separated unless the user explicitly wants an integrated view.

---

## UI rule for each new source
Every new source must have a primary home.

Examples:
- IPEDS → Provider / Program pages
- 311 → Geography pages and Map
- Crime → Geography pages and Map
- IRS 990 → Organization pages
- Traffic → Mobility map mode and place summaries

If a source has no clear “home surface,” it is not ready to ship.

---

## Best next additions after IPEDS

### Highest-confidence sequence
1. IPEDS
2. College Scorecard
3. Occupation / workforce crosswalk views
4. Organization enrichment (IRS 990 first)
5. 311
6. Crime
7. Traffic

### Why this sequence works
- it keeps the first few releases structured and explainable,
- it strengthens the organization and program model before noisy event data,
- and it prevents civic signals from dominating the product too early.
