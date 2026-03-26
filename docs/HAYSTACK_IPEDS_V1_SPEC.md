# The Haystack — IPEDS V1 Spec

## Goal
Use IPEDS as the first full vertical slice for Haystack.

This slice should prove that Haystack can:
- ingest one major dataset,
- connect it to existing keys,
- render multiple entity pages,
- and keep the UI manageable.

---

## 1. Product objective

Answer these 5 questions well:
1. What training providers exist in the KC region?
2. What programs do they offer?
3. How many awards/completions are they producing?
4. What occupations or sectors do those programs connect to?
5. What outcomes exist when Scorecard data is available?

If IPEDS V1 answers those 5 questions clearly, it is a success.

---

## 2. V1 scope

### In scope
- provider directory
- provider detail page
- program directory
- program detail page
- CIP/field of study filtering
- provider map layer
- provider compare
- completions metrics
- CIP→SOC linked occupations
- optional Scorecard earnings where available

### Out of scope for V1
- admissions and tuition deep dives
- institution finance deep dives
- full student demographics explorer
- long trend history unless easy to support
- custom report builder
- complex persona branching

---

## 3. Core entities in the IPEDS slice

### Provider
Backed by Organization where `org_type = training`

Minimum fields:
- org_id
- name
- city/state
- website
- scorecard_unitid
- latitude/longitude
- total programs
- total completions
- primary CIP family

### Program
Backed by Program table

Minimum fields:
- program_id
- org_id
- name
- credential_type
- cip
- duration_weeks if available
- modality
- completions
- linked SOC count

### Field of Study
Derived from CIP hierarchy

Minimum fields:
- CIP code
- CIP label
- family/group label
- providers offering it
- total completions in region
- linked occupations

### Occupation connection
Backed by ProgramOccupation + SOC/CIP logic

Minimum fields:
- soc
- title
- confidence
- related programs count
- related providers count

---

## 4. Recommended V1 routes

### Directory routes
- `/providers`
- `/programs`
- `/fields` or `/cip`

### Detail routes
- `/providers/<id>`
- `/programs/<id>`
- `/fields/<cip>`

### Comparison
- `/compare/providers?...`
- `/compare/programs?...`

### Map
- `/map?mode=providers`

---

## 5. Screen-by-screen design

## 5.1 Provider directory

### Primary jobs
- browse local training institutions
- filter by credential type, geography, field, size
- compare providers quickly

### Default columns/cards
- provider name
- city
- program count
- total completions
- top field
- linked occupations count

### Filters
- county / city
- credential type
- CIP family
- completions band
- public/private if available later

### Sorts
- completions
- program count
- alphabetic
- linked occupations

### UX note
Default to **card/list hybrid**, not giant tables.

---

## 5.2 Provider detail

### Snapshot strip
- programs count
- award completions
- top credential type
- top CIP family
- linked occupations
- earnings coverage available? yes/no

### Tabs
#### Overview
- provider summary
- top programs
- field mix

#### Connections
- linked occupations
- sectors served
- similar providers

#### Geography
- map
- nearby neighborhoods / counties
- nearby employers later

#### Outcomes
- completions by field
- Scorecard earnings where available

#### Evidence
- source notes
- data dates

#### Methods
- IPEDS coverage explanation
- CIP/SOC crosswalk caveat

---

## 5.3 Program directory

### Primary jobs
- browse offerings, not just schools
- compare certificates vs degrees
- find which providers offer the same field

### Default fields
- program name
- provider
- credential type
- CIP
- completions
- linked occupations count

### Filters
- credential type
- provider
- CIP family
- completions band
- modality

### Sorts
- completions
- provider
- credential type
- linked occupations

---

## 5.4 Program detail

### Snapshot strip
- provider
- credential type
- CIP code
- completions
- linked occupations
- available earnings data

### Tabs
#### Overview
- short description
- provider card
- award level

#### Occupation links
- related occupations ranked by confidence
- wages / demand later

#### Outcomes
- completions
- scorecard outcomes where available

#### Geography
- provider location
- nearby peer programs later

#### Methods
- CIP/SOC mapping notes

---

## 5.5 Field/CIP page

### Why this page matters
This becomes the bridge between program inventory and workforce relevance.

### Snapshot strip
- providers offering this field
- total completions
- credential mix
- linked occupations
- top counties / cities

### Sections
- provider list
- top programs
- linked occupations
- possible sectors served

---

## 6. Query priorities

Build these reusable queries first:

1. provider summary query
2. provider program mix query
3. program-to-occupation query
4. CIP summary query
5. provider comparison query
6. program comparison query

These queries should power both UI and exports where possible.

---

## 7. V1 map behavior

### Provider mode only
Keep it simple:
- cluster providers
- filter by credential type or CIP family
- click for quick summary
- jump to provider page

### Avoid in V1
- too many overlays
- choropleth plus dense providers plus signals
- travel-time isochrones unless already easy

---

## 8. Methods and caveats to display

Users must see these clearly:
- IPEDS completions are awards conferred, not enrollments
- CIP→SOC links are crosswalk-based, not guaranteed outcomes
- Scorecard availability varies by institution/field/credential
- some programs may have suppressed or missing values

---

## 9. Acceptance criteria

### Data
- IPEDS institutions loaded for KC region
- programs loaded and linked to organizations
- CIP data usable for filtering
- program-to-occupation mappings available

### UX
- providers searchable
- programs searchable
- compare works for 2 providers and 2 programs
- methods tab present on provider/program pages
- data freshness visible
- map layer works without overwhelming the screen

### Quality
- clear empty states for missing completions or outcomes
- no page needs a custom layout outside the shared shell
- mobile detail pages remain readable

---

## 10. Best next extension after V1

After IPEDS V1, add **College Scorecard** as the first enrichment.

Why:
- it upgrades inventory into outcomes,
- stays within the same entity model,
- and makes compare pages much more useful.

That is the cleanest possible next step before introducing noisier civic datasets like 311 or crime.

---

## 11. Pipeline implementation notes (Epic 2 lessons)

Gotchas discovered during Epic 2 that must be carried forward to future loaders:

### CIP→SOC crosswalk file
- The NCES crosswalk xlsx (`CIP2020_SOC2018_Crosswalk.xlsx`) has **multiple sheets**.
- The first sheet is a metadata/readme sheet with columns `file_name, description`.
- **Always read with `sheet_name="CIP-SOC"`** or the data will be unreadable.
- The `CIP-SOC` sheet contains both `CIPCode` and `CIPTitle` columns — **no separate CIP taxonomy file is needed**. Extract titles from the crosswalk itself.

### Award level codes
IPEDS uses both older letter-suffix codes and newer numeric codes. All known codes:
```
1a  Certificate < 1 year
1b  Certificate 1–2 years
2   Certificate 2+ years
3   Associate's degree
4   Postsecondary certificate ≥ 2 years
5   Bachelor's degree
6   Post-baccalaureate certificate
7   Master's degree
8   Post-master's certificate
17  Doctoral degree – research
18  Doctoral degree – professional
19  Doctoral degree – other
20  Certificate (sub-baccalaureate, < 1 year)   ← added 2024 data
21  Certificate (sub-baccalaureate, ≥ 1 year)   ← added 2024 data
```
If a new code appears as `Level XX`, add it to `AWARD_LEVEL_NAMES` in `loaders/utils.py` and re-run the programs loader (the upsert will update existing rows by credential_type).

**Important:** Because the upsert key includes `credential_type`, renaming an award level code after rows are already loaded creates orphan records with the old name. To correct: delete rows with the old credential_type string and re-run the loader.

### Pipeline step ordering
`load_cip_soc.py` has two phases:
1. **Phase 1 (occupation table):** Run before programs — creates occupation rows that programs can link to.
2. **Phase 2 (program_occupation links):** Must run *after* programs exist — otherwise zero links are created.

The pipeline runner (`scripts/run_pipeline.py`) handles this by calling `load_cip_soc.py` twice. This is idempotent — Phase 1 skips existing rows, Phase 2 skips existing links.

### NCES URL stability
Not all NCES file URLs are stable. The CIP taxonomy xlsx (`CIPCode2020_v1.0.xlsx`) returned 404. Always verify URLs before adding them as automated downloads. Prefer files that are linked from a known stable index page (`/ipeds/datacenter/data/`).
