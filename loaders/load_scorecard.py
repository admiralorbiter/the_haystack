"""
load_scorecard.py — Load College Scorecard data into SQLite for KC MSA providers.

Creates two tables:
  scorecard_institution    — one row per UNITID (all KC providers, all non-sparse columns)
  scorecard_field_of_study — one row per (UNITID, CIPCODE, CREDLEV)

Data source:
  data/raw/scorecard/College_Scorecard_Raw_Data_03232026.zip

Only KC MSA institutions are loaded (matched by UNITID from the organization table).
Columns with ≥50% non-suppressed data across KC institutions are included.
PrivacySuppressed / "PS" values are stored as empty string (NULL equivalent in SQLite TEXT).

Usage:
    python loaders/load_scorecard.py
    python loaders/load_scorecard.py --zip path/to/other.zip

Exit codes:
    0 — success
    1 — zip not found or no KC unitids
"""

import argparse
import sqlite3
import sys
import zipfile
from datetime import datetime
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("[error] pandas is required: pip install pandas")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "haystack.db"
DEFAULT_ZIP = PROJECT_ROOT / "data" / "raw" / "scorecard" / "College_Scorecard_Raw_Data_03232026.zip"

INSTITUTION_FILE = "Most-Recent-Cohorts-Institution.csv"
FOS_FILE = "Most-Recent-Cohorts-Field-of-Study.csv"

# Suppression markers used by Scorecard
_SUPPRESSED = {"PrivacySuppressed", "PS", "NULL", ""}

# Minimum availability ratio to include a column from the institution table
_MIN_AVAILABILITY = 0.5

# FoS columns to always include (all of them — it's only 178)
_FOS_COLS_KEEP = None  # None = keep all


def _get_kc_unitids(conn: sqlite3.Connection) -> set[str]:
    """Return all unitids for KC MSA training providers."""
    rows = conn.execute(
        "SELECT unitid FROM organization WHERE unitid IS NOT NULL AND org_type = 'training'"
    ).fetchall()
    return {str(r[0]).strip() for r in rows}


def _availability_ratio(series: "pd.Series") -> float:
    """Fraction of values that are not suppressed/null."""
    total = len(series)
    if total == 0:
        return 0.0
    bad = series.isin(_SUPPRESSED) | series.isna()
    return (total - bad.sum()) / total


def _clean_value(v) -> str:
    """Convert suppressed / NaN values to empty string for SQLite."""
    if pd.isna(v):
        return ""
    sv = str(v).strip()
    return "" if sv in _SUPPRESSED else sv


def load_institution(
    conn: sqlite3.Connection,
    z: zipfile.ZipFile,
    kc_unitids: set[str],
) -> int:
    """
    Load scorecard_institution table: all KC rows, columns filtered by ≥50% availability.
    Returns row count loaded.
    """
    print(f"  Reading {INSTITUTION_FILE} ...", flush=True)
    with z.open(INSTITUTION_FILE) as f:
        df = pd.read_csv(f, dtype=str, low_memory=False)

    kc_df = df[df["UNITID"].isin(kc_unitids)].copy()
    print(f"  KC subset: {len(kc_df)} rows of {len(df)} total")

    if kc_df.empty:
        print("  [error] No KC unitids matched in institution file")
        return 0

    # Filter columns by availability in KC subset
    kept_cols = [
        col for col in kc_df.columns
        if _availability_ratio(kc_df[col]) >= _MIN_AVAILABILITY
    ]
    print(f"  Columns: {len(kept_cols)} of {len(kc_df.columns)} kept (≥50% available in KC)")

    kc_df = kc_df[kept_cols]

    # Build CREATE TABLE statement dynamically
    col_defs = ", ".join(f'"{c}" TEXT' for c in kept_cols)
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS "scorecard_institution"')
    cursor.execute(f'CREATE TABLE "scorecard_institution" ({col_defs})')

    # Insert rows (clean suppression markers to empty string)
    placeholders = ", ".join("?" for _ in kept_cols)
    rows_to_insert = [
        [_clean_value(row[col]) for col in kept_cols]
        for _, row in kc_df.iterrows()
    ]
    cursor.executemany(
        f'INSERT INTO "scorecard_institution" VALUES ({placeholders})',
        rows_to_insert,
    )
    cursor.execute('CREATE INDEX "ix_scorecard_institution_unitid" ON "scorecard_institution" ("UNITID")')
    conn.commit()
    print(f"  ✓ scorecard_institution: {len(kc_df)} rows, {len(kept_cols)} columns")
    return len(kc_df)


def load_field_of_study(
    conn: sqlite3.Connection,
    z: zipfile.ZipFile,
    kc_unitids: set[str],
) -> int:
    """
    Load scorecard_field_of_study table: all KC rows, all 178 columns.
    Returns row count loaded.
    """
    print(f"  Reading {FOS_FILE} ...", flush=True)
    with z.open(FOS_FILE) as f:
        df = pd.read_csv(f, dtype=str, low_memory=False)

    kc_df = df[df["UNITID"].isin(kc_unitids)].copy()
    print(f"  KC subset: {len(kc_df)} rows of {len(df)} total")

    if kc_df.empty:
        print("  [error] No KC unitids matched in FoS file")
        return 0

    # Normalize CIPCODE: Scorecard uses integer like 5101
    # Store as-is (TEXT) — queries will do CAST or prefix matching
    # Add a normalized_cip column: zero-pad to 4 digits and add prefix dot
    # e.g. 5101 → "51.01" matching our program.cip prefix
    def _normalize_cip(v: str) -> str:
        """Convert Scorecard 4-digit CIP to XX.XX format."""
        v = str(v).strip().replace(".", "")
        if len(v) <= 2:
            return v.zfill(2)  # family only
        # Pad to 4 digits
        v = v.zfill(4)
        return f"{v[:2]}.{v[2:]}"

    kc_df = kc_df.copy()
    kc_df["CIPCODE_NORM"] = kc_df["CIPCODE"].apply(_normalize_cip)

    cols = list(kc_df.columns)
    col_defs = ", ".join(f'"{c}" TEXT' for c in cols)

    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS "scorecard_field_of_study"')
    cursor.execute(f'CREATE TABLE "scorecard_field_of_study" ({col_defs})')

    placeholders = ", ".join("?" for _ in cols)
    rows_to_insert = [
        [_clean_value(row[col]) for col in cols]
        for _, row in kc_df.iterrows()
    ]
    cursor.executemany(
        f'INSERT INTO "scorecard_field_of_study" VALUES ({placeholders})',
        rows_to_insert,
    )
    # Composite index for join: (UNITID, CIPCODE_NORM, CREDLEV)
    cursor.execute(
        'CREATE INDEX "ix_scorecard_fos_join" ON "scorecard_field_of_study" ("UNITID", "CIPCODE_NORM", "CREDLEV")'
    )
    conn.commit()
    print(f"  ✓ scorecard_field_of_study: {len(kc_df)} rows, {len(cols)} columns")
    return len(kc_df)


def record_dataset_source(conn: sqlite3.Connection, inst_count: int, fos_count: int) -> None:
    """Write a dataset_source record for audit trail."""
    now = datetime.now().isoformat()
    conn.execute(
        """
        INSERT OR REPLACE INTO dataset_source (source_id, name, version, url, loaded_at, record_count, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "college_scorecard_2425",
            "College Scorecard",
            "2024-25",
            "https://collegescorecard.ed.gov/data/",
            now,
            inst_count + fos_count,
            f"Institution rows: {inst_count}, Field-of-Study rows: {fos_count}. KC MSA only.",
        ),
    )
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--zip",
        default=str(DEFAULT_ZIP),
        help=f"Path to the Scorecard zip file (default: {DEFAULT_ZIP})",
    )
    args = parser.parse_args()

    zip_path = Path(args.zip)
    if not zip_path.exists():
        print(f"[error] Zip not found: {zip_path}")
        sys.exit(1)

    if not DB_PATH.exists():
        print(f"[error] Database not found: {DB_PATH}")
        sys.exit(1)

    print("=" * 60)
    print("Haystack — Load College Scorecard")
    print(f"Zip   : {zip_path}")
    print(f"DB    : {DB_PATH}")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)

    kc_unitids = _get_kc_unitids(conn)
    print(f"KC providers: {len(kc_unitids)} unitids from organization table")
    if not kc_unitids:
        print("[error] No KC unitids found — run IPEDS loader first")
        conn.close()
        sys.exit(1)

    with zipfile.ZipFile(zip_path) as z:
        available = z.namelist()
        print(f"Zip contains: {[n for n in available if n.endswith('.csv')]}")
        print()

        inst_count = 0
        fos_count = 0

        if INSTITUTION_FILE in available:
            inst_count = load_institution(conn, z, kc_unitids)
        else:
            print(f"  [skip] {INSTITUTION_FILE} not found in zip")

        print()

        if FOS_FILE in available:
            fos_count = load_field_of_study(conn, z, kc_unitids)
        else:
            print(f"  [skip] {FOS_FILE} not found in zip")

    if inst_count > 0 or fos_count > 0:
        record_dataset_source(conn, inst_count, fos_count)
        print()
        print(f"  ✓ dataset_source recorded")

    conn.close()

    print()
    print("=" * 60)
    print(f"✅ Done: {inst_count} institution rows, {fos_count} FoS rows loaded")
    print(f"   Tables: scorecard_institution, scorecard_field_of_study")
    print(f"   Browse at: http://127.0.0.1:5000/admin/sqlite")
    print("=" * 60)


if __name__ == "__main__":
    main()
