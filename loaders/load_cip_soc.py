"""
Load IPEDS CIP→SOC crosswalk into occupation + program_occupation tables.

Reads:
    data/raw/crosswalks/cip2020_soc2018_crosswalk.xlsx

Two-phase load:
    Phase 1 — Populate occupation table (SOC codes + titles)
    Phase 2 — Link crosswalk to existing program rows via matching CIP code

Run this BEFORE load_ipeds_programs.py (occupation must exist before
program_occupation FK can be satisfied). The occupation table itself
can be loaded independently of programs.

Usage:
    python loaders/load_cip_soc.py
    python loaders/load_cip_soc.py --dry-run
    python loaders/load_cip_soc.py --verbose
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from loaders.utils import CROSSWALK_DIR, normalize_cip, record_dataset_source
from models import Occupation, Program, ProgramOccupation, db
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

SOURCE_ID = "nces_cip_soc_2020"
SOURCE_NAME = "NCES CIP 2020 → SOC 2018 Crosswalk"
SOURCE_URL = "https://nces.ed.gov/ipeds/cipcode/resources.aspx"
CROSSWALK_FILE = CROSSWALK_DIR / "cip2020_soc2018_crosswalk.xlsx"

# Exclude the generic "unmatched" SOC placeholder
UNMATCHED_SOC = "99-9999"


def load_occupations(session, df: pd.DataFrame, verbose: bool) -> int:
    """
    Phase 1: Populate the occupation table from unique SOC codes in crosswalk.
    Returns count of new occupations inserted.
    """
    inserted = 0
    seen_socs = set()

    for _, row in df.iterrows():
        soc = str(row.get("soc_code", "")).strip()
        title = str(row.get("soc_title", "")).strip()

        if not soc or soc == UNMATCHED_SOC or soc in seen_socs:
            continue
        seen_socs.add(soc)

        # Derive major/minor group codes from SOC format: 'XX-XXXX.XX'
        # Major group = first 2 digits before hyphen
        # Minor group = 2-digit prefix before last 4 digits
        parts = soc.split("-")
        soc_major = parts[0] if len(parts) >= 1 else None
        soc_minor = f"{parts[0]}-{parts[1][:2]}" if len(parts) >= 2 else None

        existing = session.query(Occupation).filter_by(soc=soc).first()
        if not existing:
            session.add(
                Occupation(
                    soc=soc,
                    title=title or f"SOC {soc}",
                    soc_major=soc_major,
                    soc_minor=soc_minor,
                )
            )
            inserted += 1
            if verbose:
                print(f"  [occ] {soc} — {title}")

    session.flush()
    return inserted


def load_program_occupation_links(
    session, crosswalk: dict[str, list[str]], verbose: bool
) -> tuple[int, int]:
    """
    Phase 2: Link crosswalk SOC codes to existing program rows via CIP code.
    A single program can link to many SOC codes (many-to-many).

    Returns (links_created, programs_linked_count).
    """
    # Build map of all programs keyed by CIP code
    programs_by_cip: dict[str, list] = {}
    for prog in session.query(Program).all():
        programs_by_cip.setdefault(prog.cip, []).append(prog)

    links_created = 0
    programs_linked = set()

    for cip_code, soc_codes in crosswalk.items():
        programs = programs_by_cip.get(cip_code, [])
        if not programs:
            continue  # This CIP not in our DB — normal, not an error

        for prog in programs:
            for soc in soc_codes:
                # Check if link already exists (idempotency)
                existing = (
                    session.query(ProgramOccupation)
                    .filter_by(program_id=prog.program_id, soc=soc)
                    .first()
                )
                if not existing:
                    session.add(
                        ProgramOccupation(
                            program_id=prog.program_id,
                            soc=soc,
                            confidence=1.0,
                            source=SOURCE_ID,
                        )
                    )
                    links_created += 1
                    programs_linked.add(prog.program_id)
                    if verbose:
                        print(f"  [link] {prog.program_id[:8]}… ({cip_code}) → {soc}")

    session.flush()
    return links_created, len(programs_linked)


def run(dry_run: bool = False, verbose: bool = False) -> None:
    if not CROSSWALK_FILE.exists():
        print(
            f"[error] Crosswalk file not found: {CROSSWALK_FILE}\n"
            f"        Run `python scripts/download_data.py --crosswalks-only` first.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"  Reading {CROSSWALK_FILE.name} ...")
    # The NCES crosswalk xlsx has multiple sheets; data is on 'CIP-SOC'
    df = pd.read_excel(CROSSWALK_FILE, sheet_name="CIP-SOC", dtype=str)

    # Normalize column names — NCES uses mixed case
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Find CIP and SOC columns
    cip_col = next((c for c in df.columns if "cip" in c and "code" in c), None)
    soc_col = next((c for c in df.columns if "soc" in c and "code" in c), None)
    soc_title_col = next((c for c in df.columns if "soc" in c and "title" in c), None)

    if not cip_col or not soc_col:
        print(
            f"[error] Could not identify CIP/SOC columns. Found: {list(df.columns)}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Rename for consistent access
    df = df.rename(columns={cip_col: "cip_code", soc_col: "soc_code"})
    if soc_title_col:
        df = df.rename(columns={soc_title_col: "soc_title"})
    else:
        df["soc_title"] = ""

    # Build the crosswalk dict: normalized CIP → [SOC, ...]
    crosswalk: dict[str, list[str]] = {}
    skipped = 0
    for _, row in df.iterrows():
        cip_norm = normalize_cip(row.get("cip_code"))
        soc = str(row.get("soc_code", "")).strip()

        if not cip_norm or not soc or soc == UNMATCHED_SOC:
            skipped += 1
            continue

        crosswalk.setdefault(cip_norm, []).append(soc)

    unique_cips = len(crosswalk)
    total_links = sum(len(v) for v in crosswalk.values())
    print(f"  Crosswalk: {unique_cips} CIP codes → {total_links} SOC links ({skipped} rows skipped)")

    if dry_run:
        print("\n  [DRY RUN] Would load the above crosswalk. No writes made.")
        return

    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    with Session(engine) as session:
        # Phase 1 — Occupations
        print("\n  Phase 1: Loading occupations ...")
        occ_inserted = load_occupations(session, df, verbose)
        session.commit()
        total_occs = session.query(Occupation).count()
        print(f"  Occupations: {occ_inserted} new, {total_occs} total in DB")

        # Phase 2 — Program→Occupation links
        print("\n  Phase 2: Linking crosswalk to programs ...")
        links_created, programs_linked = load_program_occupation_links(
            session, crosswalk, verbose
        )
        session.commit()

        total_programs = session.query(Program).count()
        print(
            f"  Links created: {links_created}\n"
            f"  Programs linked: {programs_linked} of {total_programs}"
        )

        # Record dataset source
        record_dataset_source(
            session,
            source_id=SOURCE_ID,
            name=SOURCE_NAME,
            version="2020",
            url=SOURCE_URL,
            record_count=total_links,
            notes=f"{unique_cips} CIP codes, {total_links} total CIP→SOC mappings",
        )
        session.commit()

    print(f"\n✅ Done. dataset_source row written: {SOURCE_ID}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load CIP→SOC crosswalk into Haystack DB.")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without writing"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print every occupation + link"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Loading CIP→SOC Crosswalk + Occupations")
    if args.dry_run:
        print("Mode: DRY RUN (no writes)")
    print("=" * 60)

    run(dry_run=args.dry_run, verbose=args.verbose)


if __name__ == "__main__":
    main()
