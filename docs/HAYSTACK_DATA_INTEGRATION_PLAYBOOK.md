# The Haystack — Data Integration Playbook

> This is the *how-to-build* companion to `HAYSTACK_DATASET_ONBOARDING_TEMPLATE.md` (which is the *what-to-plan* checklist).
> This document codifies hard-won patterns from Epics 1–10 (IPEDS, Scorecard, CIP↔SOC, WIOA ETPL).
> Update it after every new dataset integration.

---

## The Core Mental Model

Every dataset you add does exactly **one** of these three things:

| Integration Type | What it does | Example |
|---|---|---|
| **Entity source** | Creates new Organizations or Programs that don't exist yet | IPEDS, WIOA ETPL |
| **Entity enricher** | Adds data onto existing entities (no new rows) | Scorecard, IPEDS IPEDS raw tables |
| **Mapping/crosswalk** | Links entities to each other | CIP↔SOC crosswalk |

Identify which type you're building **before writing any code**. This determines everything downstream.

---

## Part 1 — The Loader Pattern

Every loader must follow this exact structure:

```python
"""
load_<dataset>.py

Source: <URL or file>
Entity type: <entity source | enricher | crosswalk>
MSA filter: <yes/no — how>
Idempotent: <yes/no — upsert key>
"""

# 1. Standard imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from models import db, <relevant models>
from loaders.utils import (
    RAW_DIR,
    get_kc_county_fips,      # always use this — never hardcode FIPSes
    record_dataset_source,   # always call this at the end
    normalize_cip,           # if touching CIP codes
    pad_county_fips,         # if reading FIPS from raw files
)

SOURCE_ID = "snake_case_unique_id"   # used in dataset_source table
SOURCE_NAME = "Human-Readable Name"

# 2. Main function — session-injectable (never creates engine itself)
def load_<dataset>(session, dry_run=False, verbose=False) -> dict:
    # Returns: {"loaded": N, "skipped": N, "failed": N}
    ...
    record_dataset_source(session, ...)
    return stats

# 3. CLI entry point — uses app context
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    from app import create_app
    app = create_app()
    with app.app_context():
        stats = load_<dataset>(db.session, ...)

if __name__ == "__main__":
    main()
```

### Rules
- **Never** create a `create_engine()` inside the loader — use the injected `session` so tests can pass in an in-memory DB.
- **Always** use `app.app_context()` in `main()` — this is what prevents FTS5 trigger errors.
- **Always** call `record_dataset_source()` at the end, even if zero records loaded.
- **Always** return a stats dict so tests can assert on it.

---

## Part 2 — The MSA Filter Pattern

All KC-scoped loaders filter by MSA. The region definition lives in the DB (seeded via `db/seed.py`). **Never hardcode FIPS codes in loaders.**

### County FIPS filter (for IPEDS-style data)
```python
kc_fips = get_kc_county_fips(session, "kansas-city")
# Then filter: df[df["FIPS"].isin(kc_fips)]
```

### ZIP code filter (for WIOA-style address data)
```python
# Use the ZCTA crosswalk to expand county FIPS to ZIPs
kc_fips = get_kc_county_fips(session, "kansas-city")
crosswalk = pd.read_csv(CROSSWALK_DIR / "zcta_county_rel_10.txt", dtype=str)
kc_zips = set(crosswalk[crosswalk["GEOID"].isin(kc_fips)]["ZCTA5"])
# Then filter: df[df["zip"].isin(kc_zips)]
```

Cache the crosswalk file to `data/raw/crosswalks/` — download once, reuse forever.

---

## Part 3 — Entity Deduplication & Identity

### The org_alias pattern (for IPEDS-sourced orgs)
```python
# Check org_alias first — never create a duplicate org_id
alias = session.query(OrgAlias).filter_by(source="ipeds", source_id=unitid).first()
if alias:
    org_id = alias.org_id  # reuse existing
else:
    org_id = str(uuid.uuid4())
    session.add(Organization(org_id=org_id, ...))
    session.add(OrgAlias(org_id=org_id, source="ipeds", source_id=unitid, ...))
```

### The fuzzy match pattern (for non-IPEDS external sources, e.g. WIOA)
Use when the external dataset has no `unitid` crosswalk to IPEDS.
```python
from thefuzz import fuzz
MATCH_THRESHOLD = 85  # tuned via test — don't change without data

best_score = 0
best_match = None
for existing_org in existing_orgs:
    if city_matches(row_city, existing_org.city):
        score = fuzz.token_sort_ratio(row_name.lower(), existing_org.name.lower())
        if score > MATCH_THRESHOLD and score > best_score:
            best_score = score
            best_match = existing_org

if best_match:
    org_id = best_match.org_id  # enrich existing
else:
    # create new org with source-prefixed ID to avoid UUID collision
    org_id = f"wioa_{uuid.uuid4().hex[:8]}"
```

**Log all merges.** If verbose=True, print `[Merge] ExternalName -> ExistingName`.
Always cache the current run's new orgs in a `{(name_lower, city_lower): org_id}` dict to avoid creating duplicate orgs for the same provider offering multiple programs.

### The satellite linking pattern (for parent-child relationships)
When an external source (like WIOA) contains divisions or branches of institutions that already exist in the database (like IPEDS parent colleges), link them using the `Relationship` table rather than merging them.

```python
# loaders/link_org_parents.py
from thefuzz import fuzz

# Manual override hatch to safely fix edge case linkages without writing code
MANUAL_OVERRIDES = {
    'wioa_dd3': 'beedcde0',   # Force link: fixes false negative (abbreviations)
    'wioa_1d3': None,         # Force skip: suppresses false positive auto-link
}

def find_parent(satellite, colleges):
    best_score = 0.0
    best_match = None
    
    for college in colleges:
        # Use partial_ratio to check if college name is contained in the satellite name
        # (e.g., 'Park University' contained in 'Park University-Parkville')
        partial = fuzz.partial_ratio(satellite.name.lower(), college.name.lower())
        
        if partial >= 92 and partial > best_score:
            best_score = partial
            best_match = college
            
    return best_match
    
# Create generic relationship row
session.add(Relationship(
    from_entity_id=satellite.org_id,
    to_entity_id=parent.org_id,
    rel_type="parent_org",
    source="auto_fuzzy" # distinct from 'manual' 
))
```
**Important:** Keep identity reconciliation/linking as separate, idempotent maintenance scripts (e.g., `link_org_parents.py`) so they can be run, tuned, and overridden independently from the raw data ingestion pipeline.

---

## Part 4 — Schema Changes (Migrations)

When a new dataset needs new columns:

### DO
```python
# In Alembic migration — keep it surgical
def upgrade() -> None:
    with op.batch_alter_table('program', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_wioa_eligible', sa.Boolean(), 
                            nullable=False, server_default='0'))
```

### DON'T
- Don't let `alembic revision --autogenerate` touch FTS5 virtual tables — it will try to drop and recreate them, breaking triggers.
- Before running autogenerate, check the generated migration for any `DROP TABLE` on `*_fts` tables and remove those lines manually.
- Always backup `db/haystack.db` before applying migrations: `copy "db/haystack.db" "db/haystack.db.bak"`

### FTS5 rule
The FTS5 virtual tables (`organization_fts`, `program_fts`) are maintained by DB triggers. Never drop them in migrations. If the DB gets corrupted, the fix is always: delete `haystack.db`, run `init_db.py`, re-run all loaders.

---

## Part 5 — The UI Integration Pattern

Every new dataset that surfaces in the UI needs ALL of the following. Do not ship without completing this list.

### Tier A — Inline badges in all program/org tables
Every template that loops over `Program` objects (there are currently 7) needs to show the new flag if it's a boolean attribute on the model. Use `.badge-sm` in tables, full `.badge-*` on detail headers.

**All current template surfaces for programs:**
1. `programs/directory.html` — main table
2. `programs/partials/tab_overview.html` — "Similar Programs" table
3. `providers/partials/tab_overview.html` — "Top Programs" table
4. `fields/partials/tab_overview.html` — "Top Programs" table
5. `fields/partials/tab_programs.html` — "All Programs" table
6. `compare/programs.html` — comparison profile section
7. `search/results.html` — program result cards

When you add a new boolean Program flag in a future dataset, **touch all 7**.

### Tier B — Directory filter
If the flag is boolean (on/off), add a dropdown filter option to `programs/directory.html` using the existing `pathway` filter pattern.

If it's a structured value (e.g. sector, funding_type), add a new `<select>` filter following the `cred_filter` pattern in `routes/programs.py`.

### Tier C — Detail page
1. Header badge (detail.html `title-row`)
2. Definition list row in `tab_overview.html`
3. Caveats block in `tab_methods.html`

### Tier D — Methods footers
Update the methods footer on **every page that uses this data** to credit the source and explain suppression rules. Never let a footer go stale after a new dataset ships.

### Tier E — Compare tools
- **Program compare** (`compare/programs.html`): Add a static label-only row in the "Program Profile" section.
- **Provider compare** (`routes/compare.py -> _build_provider_rows()`): Add count rows as program-level aggregates.

### Tier F — Scorecard tab / outcomes tab empty states
If the new dataset does NOT have outcomes data (no IPEDS unitid, no Scorecard enrollment), add a **targeted** empty state message explaining *why*, not a generic "no data" fallback.

---

## Part 6 — Data Quality Rules (Non-Negotiable)

These rules apply across every dataset. Check them in every loader.

| Rule | Implementation |
|---|---|
| Suppression = NULL, never 0 | `parse_completions()` in utils.py |
| FIPS always 5-digit padded | `pad_county_fips()` in utils.py |
| CIP always `XX.XXXX` format | `normalize_cip()` in utils.py |
| Datetimes always UTC-aware | `datetime.now(timezone.utc)` |
| Bad rows skip, don't crash | `try/except`, log to `stderr`, continue loop |
| Freshness always recorded | `record_dataset_source()` at end of every load |

---

## Part 7 — Testing Requirements

Every loader needs:

```python
class TestLoad<Dataset>:
    def test_normal_load(self, db_session):
        """Records inserted, count matches."""

    def test_idempotent(self, db_session):
        """Run twice, no duplicates."""

    def test_empty_file(self, db_session, tmp_path):
        """Zero rows loaded, no crash."""

    def test_out_of_region(self, db_session):
        """Rows outside KC ZIP/FIPS are excluded."""

    def test_missing_fields(self, db_session):
        """Rows with missing required fields are skipped, not crashed."""

    def test_dataset_source_recorded(self, db_session):
        """dataset_source table has a row for SOURCE_ID after load."""
```

Use fixture CSVs in `tests/fixtures/<dataset>/` with exactly 5–10 rows.

---

## Part 8 — Known Technical Debt & Future Improvements

These are patterns we've accepted as "good enough for V1" that will need to be addressed as data volume grows:

| Item | Current state | Future fix |
|---|---|---|
| Fuzzy org matching | O(n) loop over all orgs per row — fine at <50 WIOA records, slow at 5,000 | Build a normalized name index or use a blocking strategy (same city first) |
| WIOA orgs have no lat/lon | Point drops off map | Geocode by ZIP centroid from Census ZCTA data during load |
| New dataset flags in 7 templates | Manual touch required for each new boolean flag | Extract to a Jinja macro `{% from 'partials/program_badges.html' import program_badges %}` called in all 7 places |
| compare.py hardcodes row slices | `rows[:3]`, `rows[3:5]` etc — fragile as row count grows | Use a `group` key in each row dict, render groupings in template |
| FTS5 tables excluded from migrations | Risk of autogenerate messing them up | Add a migration ignore list or custom `include_object` hook to `env.py` |

---

## Part 9 — Checklist for Every New Dataset

Copy-paste this into the Epic ticket when starting a new data integration.

```
## Integration Checklist

### Backend
- [ ] Onboarding template filled out (HAYSTACK_DATASET_ONBOARDING_TEMPLATE.md)
- [ ] Loader follows utils.py patterns (utils.py functions used, no hardcoded FIPS/ZIPs)
- [ ] MSA filter implemented via get_kc_county_fips()
- [ ] Entity dedup pattern chosen (org_alias vs fuzzy match) and documented
- [ ] Alembic migration surgical — no FTS5 tables touched
- [ ] DB backed up before migration
- [ ] record_dataset_source() called
- [ ] dry-run and verbose modes implemented

### Tests
- [ ] Fixture CSV in tests/fixtures/<dataset>/
- [ ] test_normal_load passes
- [ ] test_idempotent passes
- [ ] test_empty_file passes
- [ ] test_out_of_region passes
- [ ] pytest --cov still passes 70% gate

### UI
- [ ] Badge styles added to components.css
- [ ] All 7 program table templates updated with inline badges
- [ ] Directory filter added if applicable
- [ ] Detail page header badge, dl row, methods caveats added
- [ ] Compare tools updated (programs + providers)
- [ ] Targeted empty states for Scorecard/outcomes tabs if no outcomes data
- [ ] Methods footers on all affected pages updated
- [ ] Admin dashboard shows new dataset_source record

### Sign-off
- [ ] Manual walkthrough of detail page, directory filter, search, and compare
- [ ] HAYSTACK_AI_COLLAB_GUIDE.md updated with any process lessons
- [ ] This playbook updated with new patterns discovered
```
