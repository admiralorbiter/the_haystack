"""
load_ipeds_tables.py — Load institution-level IPEDS CSVs directly into SQLite.

Each CSV is loaded as a raw table named  ipeds_{stem}  (e.g. ipeds_ic2024).
Tables are dropped and recreated on each run so re-running is always safe.

These tables are NOT SQLAlchemy models — they are loaded with sqlite3 directly
and are browseable via /admin/sqlite in the admin UI.

Usage:
    python loaders/load_ipeds_tables.py                  # load all configured files
    python loaders/load_ipeds_tables.py --year 2024      # only 2024 files
    python loaders/load_ipeds_tables.py --file ic2024    # single file stem

Institution-level files (one row per UNITID, ~7k rows):
    ic2024         Institutional Characteristics
    cost1_2024     Cost (tuition, fees, room & board)
    cost2_2024     Cost (in-state by living arrangement)
    adm2024        Admissions and Test Scores
    gr2024         Graduation Rates 150%
    gr2024_l2      Graduation Rates 150% (2yr)
    gr200_24       Graduation Rates 200%
    gr2024_pell_ssl  Graduation Rates (Pell/SSL)
    sfa2324        Student Financial Aid & Net Price
    sfav2324       Military/Veterans Benefits
    efia2024       12-month Instructional Activity
    al2024         Academic Libraries
    om2024         Outcome Measures
    effy2024       12-month Enrollment (headcount)
    effy2024_dist  12-month Enrollment (distance ed)
"""

import argparse
import csv
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IPEDS_DIR = PROJECT_ROOT / "data" / "raw" / "ipeds"
DB_PATH = PROJECT_ROOT / "db" / "haystack.db"

# ---------------------------------------------------------------------------
# Files to load — stem (no extension) → friendly label
# These are institution-level: one row per UNITID, manageable for SQLite.
# Large per-program/per-person files (c2024_a, ef2024a, s2024_oc, etc.)
# are kept as raw CSV only (browse via /admin/raw).
# ---------------------------------------------------------------------------
IPEDS_TABLES: list[tuple[str, str, str]] = [
    # (year, stem, label)
    # ── 2024 ─────────────────────────────────────────────────────────────────
    ("2024", "ic2024",            "Institutional Characteristics 2024"),
    ("2024", "cost1_2024",        "Cost - Tuition & Room/Board 2024"),
    ("2024", "cost2_2024",        "Cost - In-State by Living Arrangement 2024"),
    ("2024", "adm2024",           "Admissions & Test Scores 2024"),
    ("2024", "gr2024",            "Graduation Rates 150% 2024"),
    ("2024", "gr2024_l2",         "Graduation Rates 150% 2yr 2024"),
    ("2024", "gr200_24",          "Graduation Rates 200% 2024"),
    ("2024", "gr2024_pell_ssl",   "Graduation Rates Pell/SSL 2024"),
    ("2024", "sfa2324",           "Student Financial Aid 2023-24"),
    ("2024", "sfav2324",          "Veterans Financial Benefits 2023-24"),
    ("2024", "efia2024",          "12-Month Instructional Activity 2024"),
    ("2024", "effy2024",          "12-Month Enrollment Headcount 2024"),
    ("2024", "effy2024_dist",     "12-Month Enrollment Distance Ed 2024"),
    ("2024", "al2024",            "Academic Libraries 2024"),
    ("2024", "om2024",            "Outcome Measures 2024"),
    # Fall Enrollment 2024
    ("2024", "ef2024a",           "Fall Enrollment Race/Ethnicity/Gender 2024"),
    ("2024", "ef2024b",           "Fall Enrollment Age/Attendance 2024"),
    ("2024", "ef2024c",           "Fall Enrollment Residence/Migration 2024"),
    ("2024", "ef2024d",           "Fall Enrollment Retention/Faculty Ratio 2024"),
    ("2024", "ef2024cp",          "Fall Enrollment Major Field of Study 2024"),
    ("2024", "ef2024a_dist",      "Fall Enrollment Distance Education 2024"),
    # Completions 2024
    ("2024", "c2024_b",           "Completions by Race/Ethnicity/Gender 2024"),
    # Finance 2024 (fiscal year 2023-24)
    ("2024", "f2324_f1a",         "Finance GASB Public Institutions FY2024"),
    ("2024", "f2324_f2",          "Finance FASB Private/Public Institutions FY2024"),
    ("2024", "f2324_f3",          "Finance Private For-Profit FY2024"),
    # Staff 2024
    ("2024", "s2024_oc",          "Fall Staff Occupational Category 2024"),
    ("2024", "s2024_sis",         "Fall Staff Full-Time Instructional by Tenure 2024"),
    ("2024", "s2024_is",          "Fall Staff Full-Time Instructional by Race/Gender 2024"),
    ("2024", "s2024_nh",          "Fall Staff New Hires 2024"),
    ("2024", "eap2024",           "Employees by Assigned Position 2024"),
    # Salaries 2024
    ("2024", "sal2024_is",        "Salaries Full-Time Instructional Staff 2024"),
    ("2024", "sal2024_nis",       "Salaries Full-Time Non-Instructional Staff 2024"),
    # ── 2023 ─────────────────────────────────────────────────────────────────
    ("2023", "adm2023",           "Admissions & Test Scores 2023"),
    ("2023", "gr2023",            "Graduation Rates 150% 2023"),
    ("2023", "gr2023_l2",         "Graduation Rates 150% 2yr 2023"),
    ("2023", "gr200_23",          "Graduation Rates 200% 2023"),
    ("2023", "gr2023_pell_ssl",   "Graduation Rates Pell/SSL 2023"),
    ("2023", "sfa2223",           "Student Financial Aid 2022-23"),
    ("2023", "sfav2223",          "Veterans Financial Benefits 2022-23"),
    ("2023", "efia2023",          "12-Month Instructional Activity 2023"),
    ("2023", "effy2023",          "12-Month Enrollment Headcount 2023"),
    ("2023", "effy2023_dist",     "12-Month Enrollment Distance Ed 2023"),
    # Fall Enrollment 2023
    ("2023", "ef2023a",           "Fall Enrollment Race/Ethnicity/Gender 2023"),
    ("2023", "ef2023b",           "Fall Enrollment Age/Attendance 2023"),
    ("2023", "ef2023c",           "Fall Enrollment Residence/Migration 2023"),
    ("2023", "ef2023d",           "Fall Enrollment Retention/Faculty Ratio 2023"),
    ("2023", "ef2023a_dist",      "Fall Enrollment Distance Education 2023"),
    # Finance 2023 (fiscal year 2022-23)
    ("2023", "f2223_f1a",         "Finance GASB Public Institutions FY2023"),
    ("2023", "f2223_f2",          "Finance FASB Private/Public Institutions FY2023"),
    ("2023", "f2223_f3",          "Finance Private For-Profit FY2023"),
    # Staff 2023
    ("2023", "s2023_oc",          "Fall Staff Occupational Category 2023"),
    ("2023", "s2023_sis",         "Fall Staff Full-Time Instructional by Tenure 2023"),
    ("2023", "s2023_is",          "Fall Staff Full-Time Instructional by Race/Gender 2023"),
    ("2023", "s2023_nh",          "Fall Staff New Hires 2023"),
    ("2023", "eap2023",           "Employees by Assigned Position 2023"),
    # Salaries 2023
    ("2023", "sal2023_is",        "Salaries Full-Time Instructional Staff 2023"),
    ("2023", "sal2023_nis",       "Salaries Full-Time Non-Instructional Staff 2023"),
]


def _table_name(stem: str) -> str:
    """Convert file stem to SQLite table name: ic2024 → ipeds_ic2024."""
    return f"ipeds_{stem.replace('-', '_')}"


def load_csv_to_sqlite(conn: sqlite3.Connection, csv_path: Path, table: str) -> int:
    """
    Load a CSV file into a SQLite table. All columns stored as TEXT.
    Returns number of rows inserted.
    """
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print(f"  [warn] {csv_path.name} — empty file, skipped")
        return 0

    columns = list(rows[0].keys())
    col_defs = ", ".join(f'"{c}" TEXT' for c in columns)

    cursor = conn.cursor()
    cursor.execute(f'DROP TABLE IF EXISTS "{table}"')
    cursor.execute(f'CREATE TABLE "{table}" ({col_defs})')

    placeholders = ", ".join("?" for _ in columns)
    cursor.executemany(
        f'INSERT INTO "{table}" VALUES ({placeholders})',
        [[row.get(c, "") for c in columns] for row in rows],
    )

    # Index on UNITID if present for fast joins with organization table
    if "UNITID" in columns:
        cursor.execute(f'CREATE INDEX "ix_{table}_unitid" ON "{table}" ("UNITID")')

    conn.commit()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", help="Only load files for this year (e.g. 2024)")
    parser.add_argument("--file", help="Only load this file stem (e.g. ic2024)")
    parser.add_argument(
        "--list", action="store_true", help="List configured files and exit"
    )
    args = parser.parse_args()

    if args.list:
        print(f"{'Year':<6} {'Stem':<25} {'Label'}")
        print("-" * 65)
        for year, stem, label in IPEDS_TABLES:
            print(f"{year:<6} {stem:<25} {label}")
        return

    # Filter
    targets = [
        (year, stem, label)
        for year, stem, label in IPEDS_TABLES
        if (not args.year or year == args.year)
        and (not args.file or stem == args.file)
    ]

    if not targets:
        print("No matching files found. Use --list to see all configured files.")
        sys.exit(1)

    print("=" * 60)
    print("Haystack — Load IPEDS Tables into SQLite")
    print(f"Database: {DB_PATH}")
    print(f"Files to process: {len(targets)}")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    total_rows = 0
    loaded = 0
    skipped = 0

    for year, stem, label in targets:
        csv_path = IPEDS_DIR / year / f"{stem}.csv"
        table = _table_name(stem)

        if not csv_path.exists():
            print(f"  [skip] {csv_path.name} — file not found")
            skipped += 1
            continue

        print(f"  [load] {csv_path.name} → {table} ... ", end="", flush=True)
        n = load_csv_to_sqlite(conn, csv_path, table)
        print(f"{n:,} rows ✓")
        total_rows += n
        loaded += 1

    conn.close()

    print()
    print("=" * 60)
    print(f"✅ Done: {loaded} tables loaded, {skipped} skipped")
    print(f"   Total rows: {total_rows:,}")
    print(f"   Browse at: http://127.0.0.1:5000/admin/sqlite")
    print("=" * 60)


if __name__ == "__main__":
    main()
