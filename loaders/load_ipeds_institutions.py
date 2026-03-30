"""
Load IPEDS institutions into the organization + org_alias tables.

Reads:
    data/raw/ipeds/{year}/hd{year}.csv   IPEDS HD (institution directory)

The deduplication rule (enforced here, forever):
    Before inserting any organization, check org_alias for the incoming
    source_id. If found → update existing org. If not found → insert new org,
    then write the alias row.

Usage:
    python loaders/load_ipeds_institutions.py --region kansas-city
    python loaders/load_ipeds_institutions.py --region kansas-city --year 2023
    python loaders/load_ipeds_institutions.py --region kansas-city --dry-run
    python loaders/load_ipeds_institutions.py --region kansas-city --verbose
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Make project root importable from this script location
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from config import Config
from loaders.utils import (IPEDS_DIR, get_kc_county_fips, pad_county_fips,
                           record_dataset_source)
from models import OrgAlias, Organization, db

SOURCE_ID = "ipeds_hd"
SOURCE_NAME = "IPEDS HD — Institution Directory"
SOURCE_URL = "https://nces.ed.gov/ipeds/datacenter/data/HD{year}.zip"

# IPEDS SECTOR code → Haystack org_type
# All training providers are 'training' in V1; we preserve sector detail
# in org_alias notes for potential future use.
SECTOR_MAP = {
    "1": "training",  # Public, 4-year or above
    "2": "training",  # Private not-for-profit, 4-year or above
    "3": "training",  # Private for-profit, 4-year or above
    "4": "training",  # Public, 2-year
    "5": "training",  # Private not-for-profit, 2-year
    "6": "training",  # Private for-profit, 2-year
    "7": "training",  # Public, less-than 2-year
    "8": "training",  # Private not-for-profit, less-than 2-year
    "9": "training",  # Private for-profit, less-than 2-year
}


def load_institutions(
    session,
    year: int,
    region_slug: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Load KC MSA institutions from IPEDS HD file.

    Returns a summary dict with counts: loaded, updated, skipped, failed.
    """
    csv_path = IPEDS_DIR / str(year) / f"hd{year}.csv"
    if not csv_path.exists():
        print(
            f"[skip] File not found: {csv_path}\n"
            f"        Run `python scripts/download_data.py --year {year}` first.",
            file=sys.stderr,
        )
        sys.exit(0)

    # Load the KC MSA county FIPS set
    kc_fips = get_kc_county_fips(session, region_slug)
    print(f"  Region '{region_slug}': {len(kc_fips)} counties")

    # Read HD file — IPEDS uses utf-8-sig (BOM) encoding
    print(f"  Reading {csv_path.name} ...")
    df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str, low_memory=False)
    print(f"  Total rows in HD file: {len(df):,}")

    # Normalize county FIPS column
    # HD files use 'COUNTYCD' for county FIPS (5-digit). Some years may pad,
    # some may not — pad_county_fips() handles both.
    if "COUNTYCD" not in df.columns:
        print(
            "[error] COUNTYCD column not found in HD file. "
            "Check the data dictionary for this year.",
            file=sys.stderr,
        )
        sys.exit(0)

    df["_county_fips_norm"] = df["COUNTYCD"].apply(pad_county_fips)

    # Filter to KC MSA counties only
    kc_df = df[df["_county_fips_norm"].isin(kc_fips)].copy()
    print(f"  KC MSA institutions: {len(kc_df)}")

    if len(kc_df) == 0:
        print(
            "[warn] No institutions found for the KC MSA counties. "
            "Check that county FIPS codes match the HD file.",
            file=sys.stderr,
        )
        return {"loaded": 0, "updated": 0, "skipped": 0, "failed": 0}

    if dry_run:
        print("\n  [DRY RUN] Would insert/update the following institutions:")
        for _, row in kc_df.iterrows():
            print(f"    UNITID={row.get('UNITID','?')}  {row.get('INSTNM','?')}")
        return {"loaded": 0, "updated": 0, "skipped": 0, "failed": 0}

    # --- Load into database ---
    loaded = updated = skipped = failed = 0

    for _, row in kc_df.iterrows():
        unitid = str(row.get("UNITID", "")).strip()
        if not unitid:
            print("  [warn] Row with empty UNITID — skipping", file=sys.stderr)
            failed += 1
            continue

        name = str(row.get("INSTNM", "")).strip() or f"Institution {unitid}"
        city = str(row.get("CITY", "")).strip() or None
        state = str(row.get("STABBR", "")).strip() or None
        county_fips = pad_county_fips(row.get("COUNTYCD"))
        website = str(row.get("WEBADDR", "")).strip() or None

        # Website cleanup — IPEDS sometimes omits the scheme
        if website and not website.startswith("http"):
            website = "https://" + website

        try:
            lat = float(row["LATITUDE"]) if row.get("LATITUDE", "").strip() else None
        except (ValueError, AttributeError):
            lat = None

        try:
            lon = float(row["LONGITUD"]) if row.get("LONGITUD", "").strip() else None
        except (ValueError, AttributeError):
            lon = None

        # --- Deduplication rule ---
        alias = (
            session.query(OrgAlias).filter_by(source="ipeds", source_id=unitid).first()
        )

        if alias:
            # Org exists — update in-place
            org = session.query(Organization).filter_by(org_id=alias.org_id).first()
            if org:
                org.name = name
                org.city = city
                org.state = state
                org.county_fips = county_fips
                org.lat = lat
                org.lon = lon
                org.website = website
                org.unitid = unitid
                org.last_seen_in_source = datetime.now(timezone.utc)
                org.is_active = True
                updated += 1
                if verbose:
                    print(f"  [update] {unitid} — {name}")
            else:
                # Alias exists but org is missing — log and skip
                print(
                    f"  [warn] org_alias exists for UNITID={unitid} but org_id={alias.org_id} "
                    f"not found in organization table. Skipping.",
                    file=sys.stderr,
                )
                failed += 1
        else:
            # New org — insert organization + alias
            org = Organization(
                name=name,
                org_type=SECTOR_MAP.get(
                    str(row.get("SECTOR", "0")).strip(), "training"
                ),
                city=city,
                state=state,
                county_fips=county_fips,
                lat=lat,
                lon=lon,
                website=website,
                unitid=unitid,
                last_seen_in_source=datetime.now(timezone.utc),
                is_active=True,
            )
            session.add(org)
            session.flush()  # Get the generated org_id

            session.add(
                OrgAlias(
                    org_id=org.org_id,
                    source="ipeds",
                    source_id=unitid,
                    source_name=name,
                )
            )
            loaded += 1
            if verbose:
                print(f"  [insert] {unitid} — {name}")

    session.commit()

    # Record dataset source metadata
    record_dataset_source(
        session,
        source_id=f"{SOURCE_ID}_{year}",
        name=f"{SOURCE_NAME} ({year})",
        version=str(year),
        url=SOURCE_URL.format(year=year),
        record_count=loaded + updated,
        notes=f"KC MSA filter: {len(kc_fips)} counties, {len(kc_df)} raw rows matched",
    )
    session.commit()

    return {"loaded": loaded, "updated": updated, "skipped": skipped, "failed": failed}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load IPEDS institutions for a region."
    )
    parser.add_argument(
        "--region", default="kansas-city", help="Region slug (default: kansas-city)"
    )
    parser.add_argument(
        "--year", type=int, default=2024, help="IPEDS data year (default: 2024)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be loaded without writing",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print every insert/update"
    )
    args = parser.parse_args()

    print("=" * 60)
    print(f"Loading IPEDS Institutions — {args.year}")
    print(f"Region: {args.region}")
    if args.dry_run:
        print("Mode: DRY RUN (no writes)")
    print("=" * 60)

    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    with Session(engine) as session:
        counts = load_institutions(
            session,
            year=args.year,
            region_slug=args.region,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

    print(f"\nResults:")
    print(f"  Inserted (new):  {counts['loaded']}")
    print(f"  Updated (exist): {counts['updated']}")
    print(f"  Failed:          {counts['failed']}")
    print(f"\n✅ Done. dataset_source row written: {SOURCE_ID}_{args.year}")


if __name__ == "__main__":
    main()
