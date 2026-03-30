"""
Load IPEDS completions into the program table.

Reads:
    data/raw/ipeds/{year}/c{year}_a.csv   IPEDS C completions (Part A)
    data/raw/crosswalks/cip2020_titles.xlsx  CIP code → title (for program names)

Filters:
    - Only institutions already in the organization table (via org_alias)
    - Only MAJORNUM == 1 rows (avoids double-counting second majors)
    - Skips CIPCode 99.0000 (aggregate total rows)
    - Suppressed completions (blank/'.') stored as NULL, never as 0

Upsert key: (org_id, cip, credential_type) composite

Usage:
    python loaders/load_ipeds_programs.py --region kansas-city
    python loaders/load_ipeds_programs.py --region kansas-city --year 2023
    python loaders/load_ipeds_programs.py --region kansas-city --dry-run
    python loaders/load_ipeds_programs.py --region kansas-city --verbose
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from config import Config
from loaders.utils import (AWARD_LEVEL_NAMES, AWARD_LEVEL_NAMES_LEGACY,
                           IPEDS_DIR, load_cip_titles, make_program_name,
                           normalize_cip, parse_completions,
                           record_dataset_source)
from models import OrgAlias, Program, db

SOURCE_ID = "ipeds_c"
SOURCE_NAME = "IPEDS Completions (Part A)"
SOURCE_URL = "https://nces.ed.gov/ipeds/datacenter/data/C{year}_A.zip"


def load_programs(
    session,
    year: int,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """Load programs from IPEDS completions file into the program table."""
    csv_path = IPEDS_DIR / str(year) / f"c{year}_a.csv"
    if not csv_path.exists():
        print(
            f"[skip] File not found: {csv_path}\n"
            f"        Run `python scripts/download_data.py --year {year}` first.",
            file=sys.stderr,
        )
        sys.exit(0)

    # Build lookup: UNITID (str) → org_id for KC institutions already in DB
    aliases = session.query(OrgAlias).filter_by(source="ipeds").all()
    unitid_to_org: dict[str, str] = {a.source_id: a.org_id for a in aliases}

    if not unitid_to_org:
        print(
            "[error] No IPEDS institutions found in the database.\n"
            "        Run load_ipeds_institutions.py first.",
            file=sys.stderr,
        )
        sys.exit(0)

    print(f"  KC institutions in DB: {len(unitid_to_org)}")

    # Load CIP titles for program name composition
    cip_titles = load_cip_titles()

    # Read completions file
    print(f"  Reading {csv_path.name} ...")
    df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str, low_memory=False)
    print(f"  Total rows in completions file: {len(df):,}")

    # Filter 1: Only rows for KC institutions
    df = df[df["UNITID"].isin(unitid_to_org.keys())].copy()
    print(f"  Rows for KC institutions: {len(df):,}")

    # Filter 2: Only MAJORNUM == 1 (first major only)
    if "MAJORNUM" in df.columns:
        df = df[df["MAJORNUM"].str.strip() == "1"].copy()
        print(f"  After MAJORNUM=1 filter: {len(df):,}")

    # Filter 3: Skip CIPCode 99 (aggregate totals)
    df["_cip_norm"] = df["CIPCODE"].apply(normalize_cip)
    df_skipped_totals = df[df["_cip_norm"].isna()].shape[0]
    df = df[df["_cip_norm"].notna()].copy()
    print(
        f"  After CIP-99/invalid filter: {len(df):,} rows ({df_skipped_totals} aggregate/invalid skipped)"
    )

    # Parse completions — blank/suppressed → None
    df["_completions"] = df["CTOTALT"].apply(parse_completions)
    suppressed_count = df["_completions"].isna().sum()

    # Normalize award level codes
    df["_awlevel"] = df["AWLEVEL"].str.strip()

    if dry_run:
        print(f"\n  [DRY RUN] Would process {len(df)} program rows:")
        print(f"    Suppressed completions: {suppressed_count}")
        print(f"    Award levels found: {sorted(df['_awlevel'].unique())}")
        return {
            "loaded": 0,
            "updated": 0,
            "suppressed": suppressed_count,
            "skipped": df_skipped_totals,
            "failed": 0,
        }

    # --- Group by (unitid, cip, awlevel) and sum completions ---
    # Multiple rows can exist per CIP + award level (gender/race disaggregation).
    # We want the CTOTALT column which is already the total across demographics.
    # Just take the first row per group since CTOTALT = total.
    group_cols = ["UNITID", "_cip_norm", "_awlevel"]
    grouped = df.groupby(group_cols, as_index=False).agg(
        completions=("_completions", "first"),
        awlevel_display=("_awlevel", "first"),
    )

    loaded = updated = failed = 0

    for _, row in grouped.iterrows():
        unitid = str(row["UNITID"]).strip()
        cip = row["_cip_norm"]
        awlevel = row["awlevel_display"]
        completions = row["completions"]  # May be None (suppressed)

        org_id = unitid_to_org.get(unitid)
        if not org_id:
            failed += 1
            continue

        # Resolve credential type label
        credential_type = AWARD_LEVEL_NAMES.get(
            awlevel,
            AWARD_LEVEL_NAMES_LEGACY.get(awlevel, f"Level {awlevel}"),
        )

        # Compose human-readable program name (Option B)
        name = make_program_name(cip, awlevel, cip_titles)

        # Upsert on (org_id, cip, credential_type)
        existing = (
            session.query(Program)
            .filter_by(org_id=org_id, cip=cip, credential_type=credential_type)
            .first()
        )

        if existing:
            existing.completions = completions
            existing.name = name
            updated += 1
            if verbose:
                print(f"  [update] {org_id[:8]}… {cip} {credential_type}")
        else:
            session.add(
                Program(
                    org_id=org_id,
                    name=name,
                    credential_type=credential_type,
                    cip=cip,
                    completions=completions,
                    modality=None,  # IPEDS C does not carry modality
                    duration_weeks=None,  # IPEDS C does not carry duration
                )
            )
            loaded += 1
            if verbose:
                comp_display = (
                    str(completions) if completions is not None else "suppressed"
                )
                print(f"  [insert] {cip} — {credential_type} ({comp_display})")

    session.commit()

    # Record dataset source
    record_dataset_source(
        session,
        source_id=f"{SOURCE_ID}_{year}",
        name=f"{SOURCE_NAME} ({year})",
        version=str(year),
        url=SOURCE_URL.format(year=year),
        record_count=loaded + updated,
        notes=(
            f"KC filter: {len(unitid_to_org)} institutions. "
            f"Suppressed: {suppressed_count}."
        ),
    )
    session.commit()

    return {
        "loaded": loaded,
        "updated": updated,
        "suppressed": suppressed_count,
        "skipped": df_skipped_totals,
        "failed": failed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load IPEDS completions into program table."
    )
    parser.add_argument(
        "--region", default="kansas-city", help="Region slug (used for messaging only)"
    )
    parser.add_argument(
        "--year", type=int, default=2024, help="IPEDS data year (default: 2024)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without writing"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print every insert/update"
    )
    args = parser.parse_args()

    print("=" * 60)
    print(f"Loading IPEDS Programs — {args.year}")
    if args.dry_run:
        print("Mode: DRY RUN (no writes)")
    print("=" * 60)

    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    with Session(engine) as session:
        counts = load_programs(
            session,
            year=args.year,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

    print(f"\nResults:")
    print(f"  Inserted (new):            {counts['loaded']}")
    print(f"  Updated (exist):           {counts['updated']}")
    print(f"  Suppressed (NULL compl.):  {counts['suppressed']}")
    print(f"  Skipped (CIP-99/invalid):  {counts['skipped']}")
    print(f"  Failed:                    {counts['failed']}")
    print(f"\n✅ Done. dataset_source row written: {SOURCE_ID}_{args.year}")


if __name__ == "__main__":
    main()
