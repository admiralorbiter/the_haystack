# Haystack Search Specification

This document codifies the search architecture and ranking models for The Haystack platform. As the directory grows, maintaining signal-to-noise ratio in global search is critical.

## 1. Global Entity Search Engine

The global search (`/search?q=...`) searches across four distinct entity types utilizing SQLite's `FTS5` (Full Text Search) extension.

### Entities Indexed
1. **Providers** (`Organization` where `org_type = 'training'`)
2. **Programs** (`Program`)
3. **Occupations** (`Occupation`)
4. **Employers** (`Organization` where `org_type = 'employer'` or `org_type = 'hiring_partner'`)

### Scoring Model: FTS5 Rank × Priority Boost

SQLite FTS5 naturally returns a `rank` score (a negative number where more negative = better match based on TF-IDF style algorithms).
To ensure that broad searches return the most useful structures first, we multiply the FTS5 rank by an **Entity Priority Multiplier**:

| Entity | Multiplier Boost | Rationale |
|:---|:---|:---|
| **Providers** | `1.5` | If a user searches "Johnson", they are almost certainly looking for "Johnson County Community College", not a program taught by someone named Johnson. Providers are the top-level anchor of the DB. |
| **Programs** | `1.0` (Baseline) | Standard programmatic search. Matches `Program.name` and potentially `Program.cip` description. |
| **Occupations** | `0.8` | Evaluates slightly less than programs to prevent sweeping occupational titles from burying actual training. |
| **Employers** | `0.5` | Employers are secondary connections. If a user searches "Cerner", employer Cerner should show up, but if they search "Nursing", providers/programs matter more. |

### FTS5 Configuration
- Porter Stemming is **enabled** (`tokenize='porter'`) so that "Nurse", "Nurses", and "Nursing" all match correctly against variants.
- Prefix searching is enabled under the hood: a query `q=weld` is transformed into `MATCH 'weld*'` before execution.

---

## 2. Autocomplete Typeaheads via `/api/v1/`

Autocomplete endpoints are highly restricted HTMX endpoints that support inline guided search. Because they need sub-50ms latency, they utilize slightly different rules.

### `GET /api/v1/search/programs`
Used in the "I am looking for a specific training program" guided flow.
1. Checks for FTS5 match `program_fts`.
2. Selects Top 10 by pure FTS5 Rank.
3. Fallback: If `program_fts` is unpopulated (dev environments), falls back to `Program.name.ilike('%query%')`.

### `GET /api/v1/search/occupations`
Used in the "I want to start a new career" guided flow.
1. Does **not** use FTS5 as Occupation titles are strictly controlled SOC nomenclature (too short and specific for generalized stemming).
2. Uses standard SQL `ILIKE` on `Occupation.title` and `Occupation.soc`.
3. Strict limits applied (`LIMIT 10`) ordered alphabetically `Occupation.title`.

---

## 3. Freshness Decay (Future)
When granular, fast-moving datasets (like 311 or real-time Job Postings) are added in Phase 3/4, a temporal decay factor must be added to the multiplier. Events older than 45 days should suffer a `0.85x` multiplier penalty relative to fresh events.
