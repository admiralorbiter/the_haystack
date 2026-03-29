"""
Shared utilities for all Haystack data loaders.

Import from here rather than duplicating logic across loader scripts.
All functions are pure (no Flask app context needed) so they can be
called from tests with an in-memory session.
"""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths — loaders resolve data files relative to project root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
IPEDS_DIR = RAW_DIR / "ipeds"
CROSSWALK_DIR = RAW_DIR / "crosswalks"

# ---------------------------------------------------------------------------
# IPEDS award level → human-readable credential type
# Codes sourced from IPEDS data dictionary (completions survey).
# ---------------------------------------------------------------------------
AWARD_LEVEL_NAMES: dict[str, str] = {
    "1a": "Certificate < 1 year",
    "1b": "Certificate 1–2 years",
    "2": "Certificate 2+ years",
    "3": "Associate's degree",
    "4": "Postsecondary certificate ≥ 2 years",
    "5": "Bachelor's degree",
    "6": "Post-baccalaureate certificate",
    "7": "Master's degree",
    "8": "Post-master's certificate",
    "17": "Doctoral degree – research",
    "18": "Doctoral degree – professional",
    "19": "Doctoral degree – other",
    "20": "Certificate (sub-baccalaureate, < 1 year)",
    "21": "Certificate (sub-baccalaureate, ≥ 1 year)",
}

# Older IPEDS files (pre-2012) used integer codes without the a/b split.
# Map these for backward-compatibility when loading historical years.
AWARD_LEVEL_NAMES_LEGACY: dict[str, str] = {
    "1": "Certificate < 1 year",
    **AWARD_LEVEL_NAMES,
}


# ---------------------------------------------------------------------------
# Region helpers
# ---------------------------------------------------------------------------
def get_kc_county_fips(session, region_slug: str = "kansas-city") -> set[str]:
    """
    Return the set of 5-digit county FIPS codes for a named region.
    Reads from the region_county table, which is seeded at db/seed.py.

    Raises SystemExit if the region does not exist (loader can't proceed).
    """
    from models import Region, RegionCounty

    region = session.query(Region).filter_by(slug=region_slug).first()
    if not region:
        print(
            f"[error] Region '{region_slug}' not found in database. "
            f"Run `python db/seed.py` first.",
            file=sys.stderr,
        )
        sys.exit(1)

    rows = session.query(RegionCounty).filter_by(region_id=region.region_id).all()
    fips_set = {r.county_fips for r in rows}

    if not fips_set:
        print(
            f"[error] Region '{region_slug}' has no counties. " f"Check db/seed.py.",
            file=sys.stderr,
        )
        sys.exit(1)

    return fips_set


# ---------------------------------------------------------------------------
# CIP normalization
# ---------------------------------------------------------------------------
def normalize_cip(raw_cip) -> str | None:
    """
    Normalize a CIP value to 'XX.XXXX' format.

    Handles:
    - Float: 51.3801 → '51.3801'
    - String with decimal: '51.3801' → '51.3801'
    - String without decimal (6-digit): '513801' → '51.3801'
    - String without decimal (4-digit): '5138' → '51.38'  (IPEDS older files)
    - Aggregate totals: '99', '99.0000' → None (caller should skip)

    Returns None if not parseable.
    """
    if raw_cip is None or (isinstance(raw_cip, float) and pd.isna(raw_cip)):
        return None

    s = str(raw_cip).strip()

    # Remove trailing .0 from float-cast strings
    if s.endswith(".0"):
        s = s[:-2]

    # Skip aggregate total rows
    if s == "99" or s.startswith("99."):
        return None

    # Already in XX.XXXX format
    if re.match(r"^\d{2}\.\d{2,4}$", s):
        return s

    # 6-digit without decimal: '513801' → '51.3801'
    if re.match(r"^\d{6}$", s):
        return f"{s[:2]}.{s[2:]}"

    # 4-digit without decimal: '5138' → '51.38'
    if re.match(r"^\d{4}$", s):
        return f"{s[:2]}.{s[2:]}"

    return None  # Can't parse — caller should log and skip


# ---------------------------------------------------------------------------
# Completions / suppression handling
# ---------------------------------------------------------------------------
def parse_completions(raw_value) -> int | None:
    """
    Parse a completions value from IPEDS C file.

    IPEDS suppresses small counts with blank strings or '.'.
    We store suppressed values as NULL, never as 0.

    Returns:
        int — for valid non-zero counts
        None — for suppressed/blank/unparseable values
    """
    if raw_value is None:
        return None

    s = str(raw_value).strip()

    if s in ("", ".", "N/A", "NA"):
        return None  # suppressed

    try:
        val = int(float(s))
        return val if val > 0 else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# CIP title lookup
# ---------------------------------------------------------------------------
def load_cip_titles(path=None) -> dict[str, str]:
    """
    Load CIP code → title mapping.

    Primary source: the CIP→SOC crosswalk file (sheet 'CIP-SOC') which contains
    a CIPTitle column — no separate download needed.

    If a dedicated CIP titles xlsx is provided (path arg), it takes priority.

    Returns a dict: {'51.3801': 'Registered Nursing/Registered Nurse', ...}
    Falls back to an empty dict if no file is found (warn only).
    """
    # --- Try dedicated titles file first (optional) ---
    if path is not None:
        path = Path(path)
        if not path.exists():
            print(
                f"[warn] CIP titles file not found: {path}. Program names will use CIP codes.",
                file=sys.stderr,
            )
            return {}
        return _load_cip_titles_from_file(path)

    # --- Primary: extract titles from the crosswalk file (CIP-SOC sheet) ---
    crosswalk_path = CROSSWALK_DIR / "cip2020_soc2018_crosswalk.xlsx"
    if crosswalk_path.exists():
        return _load_cip_titles_from_crosswalk(crosswalk_path)

    print(
        f"[warn] No CIP titles source found. Program names will use CIP codes.\n"
        f"       Run `python scripts/download_data.py --crosswalks-only` to fetch the crosswalk.",
        file=sys.stderr,
    )
    return {}


def _load_cip_titles_from_crosswalk(crosswalk_path: Path) -> dict[str, str]:
    """Extract CIP titles from the CIP-SOC crosswalk (CIP-SOC sheet)."""
    try:
        df = pd.read_excel(crosswalk_path, sheet_name="CIP-SOC", dtype=str)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        code_col = next(
            (
                c
                for c in df.columns
                if "cipcode" in c or "cip_code" in c or c.startswith("cip")
            ),
            None,
        )
        title_col = next(
            (
                c
                for c in df.columns
                if "ciptitle" in c
                or "cip_title" in c
                or (c.startswith("cip") and "title" in c)
            ),
            None,
        )

        if not code_col or not title_col:
            print(
                f"[warn] CIP title columns not found in crosswalk. "
                f"Columns: {list(df.columns)}",
                file=sys.stderr,
            )
            return {}

        titles = {}
        for _, row in df.iterrows():
            normalized = normalize_cip(row.get(code_col))
            title = row.get(title_col)
            if normalized and isinstance(title, str) and title.strip():
                titles[normalized] = title.strip().title()

        print(
            f"  Loaded {len(titles)} CIP titles from crosswalk ({crosswalk_path.name})"
        )
        return titles

    except Exception as e:
        print(
            f"[warn] Could not extract CIP titles from crosswalk: {e}", file=sys.stderr
        )
        return {}


def _load_cip_titles_from_file(path: Path) -> dict[str, str]:
    """Load CIP titles from a dedicated xlsx file (optional)."""
    try:
        df = pd.read_excel(path, dtype=str)
        df.columns = [c.strip().lower() for c in df.columns]

        code_col = next(
            (c for c in df.columns if "cipcode" in c or "cip code" in c), None
        )
        title_col = next(
            (c for c in df.columns if "ciptitle" in c or "cip title" in c), None
        )

        if not code_col or not title_col:
            print(
                f"[warn] Could not identify CIPCode/CIPTitle columns in {path.name}. "
                f"Columns found: {list(df.columns)}",
                file=sys.stderr,
            )
            return {}

        titles = {}
        for _, row in df.iterrows():
            raw_code = row.get(code_col)
            title = row.get(title_col)
            normalized = normalize_cip(raw_code)
            if normalized and isinstance(title, str) and title.strip():
                titles[normalized] = title.strip().title()

        print(f"  Loaded {len(titles)} CIP titles from {path.name}")
        return titles

    except Exception as e:
        print(f"[warn] Could not read CIP titles file: {e}", file=sys.stderr)
        return {}


def get_cip_title(cip_code: str, cip_titles: dict[str, str]) -> str:
    """
    Return human-readable title for a CIP code.
    Falls back to 'CIP {code}' if not in the lookup dict.
    """
    return cip_titles.get(cip_code, f"CIP {cip_code}")


def make_program_name(
    cip_code: str, award_level_code: str, cip_titles: dict[str, str]
) -> str:
    """
    Compose a human-readable program name from CIP code and award level.

    Example: '51.3801', '3' → 'Registered Nursing — Associate's Degree'
    Fallback: '51.3801', '99' → 'CIP 51.3801 — Level 99'
    """
    title = get_cip_title(cip_code, cip_titles)
    level = AWARD_LEVEL_NAMES.get(
        str(award_level_code),
        AWARD_LEVEL_NAMES_LEGACY.get(
            str(award_level_code), f"Level {award_level_code}"
        ),
    )
    return f"{title} — {level}"


# ---------------------------------------------------------------------------
# Dataset source metadata
# ---------------------------------------------------------------------------
def record_dataset_source(
    session,
    source_id: str,
    name: str,
    version: str,
    url: str,
    record_count: int,
    notes: str = None,
) -> None:
    """
    Upsert a row in the dataset_source table.
    Always updates loaded_at and record_count (so re-runs show fresh timestamps).
    """
    from models import DatasetSource

    existing = session.query(DatasetSource).filter_by(source_id=source_id).first()
    if existing:
        existing.loaded_at = datetime.now(timezone.utc)
        existing.record_count = record_count
        existing.notes = notes
    else:
        session.add(
            DatasetSource(
                source_id=source_id,
                name=name,
                version=version,
                url=url,
                loaded_at=datetime.now(timezone.utc),
                record_count=record_count,
                notes=notes,
            )
        )


# ---------------------------------------------------------------------------
# FIPS helpers
# ---------------------------------------------------------------------------
def pad_county_fips(raw_fips) -> str | None:
    """
    Normalize a county FIPS value to a zero-padded 5-character string.

    Handles:
    - int: 29095 → '29095'
    - float: 29095.0 → '29095'
    - str: '29095' → '29095'
    - short str: '291' → None (too short, probably bad data)
    """
    if raw_fips is None or (isinstance(raw_fips, float) and pd.isna(raw_fips)):
        return None

    s = str(raw_fips).strip()

    # Remove trailing .0 from float cast
    if s.endswith(".0"):
        s = s[:-2]

    # Must be all digits at this point
    if not s.isdigit():
        return None

    # Reject codes that are too short to be a valid FIPS even after padding
    # Valid county FIPS is always 5 digits; anything under 3 digits is garbage
    if len(s) < 4:
        return None

    # Zero-pad to 5 chars
    s = s.zfill(5)

    if len(s) != 5:
        return None

    return s
