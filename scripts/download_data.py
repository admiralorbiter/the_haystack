"""
Download all raw IPEDS data files and crosswalks.

Downloads IPEDS HD, C_A, and IC files for a range of years, plus the
CIP→SOC crosswalk and CIP title taxonomy from NCES. Files are stored in
data/raw/ipeds/{year}/ and data/raw/crosswalks/. Existing files are skipped
unless --force is passed.

Usage:
    python scripts/download_data.py                     # 2014–2024 (default, 11 years)
    python scripts/download_data.py --year 2024         # single year
    python scripts/download_data.py --years 2020 2024   # inclusive range
    python scripts/download_data.py --force             # re-download all
    python scripts/download_data.py --crosswalks-only   # only crosswalk files
"""

import argparse
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
IPEDS_DIR = RAW_DIR / "ipeds"
CROSSWALK_DIR = RAW_DIR / "crosswalks"
MANIFEST_PATH = PROJECT_ROOT / "data" / "MANIFEST.md"

# ---------------------------------------------------------------------------
# IPEDS bulk download URL base
# Files follow the NCES naming convention: {SURVEY}{year}.zip → {survey}{year}.csv
# Reference: https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx
# ---------------------------------------------------------------------------
IPEDS_BASE = "https://nces.ed.gov/ipeds/datacenter/data"

# ---------------------------------------------------------------------------
# Year encoding helpers
# NCES uses three different year encoding patterns:
#   single year  →  2024         (HD, IC, EF, GR, ADM, S, SAL, etc.)
#   fiscal pair  →  2324         (Finance: F2324_F1A, SFA2223)
#   2-digit year →  24           (GR200: GR200_23)
# ---------------------------------------------------------------------------

def _fmt(tmpl: str, year: int) -> str:
    """Format a file name template with all year variant substitutions."""
    prior = year - 1
    return (
        tmpl
        .replace("{year}", str(year))
        .replace("{yy}", str(year)[-2:])          # 2-digit  e.g. 24
        .replace("{ppyy}", f"{str(prior)[-2:]}{str(year)[-2:]}")  # fiscal pair e.g. 2324
    )


# Each entry: (zip_name_template, csv_name_template, survey_group)
# Templates may use: {year}, {yy} (2-digit), {ppyy} (prior2digit+year2digit)
IPEDS_FILES_PER_YEAR = [
    # ── Institutional Directory ──────────────────────────────────────────────
    ("HD{year}.zip",          "hd{year}.csv",          "hd"),
    # ── Institutional Characteristics ───────────────────────────────────────
    ("IC{year}.zip",          "ic{year}.csv",          "ic"),
    ("IC{year}_AY.zip",       "ic{year}_ay.csv",       "ic"),
    ("IC{year}_PY.zip",       "ic{year}_py.csv",       "ic"),
    # ── Completions ─────────────────────────────────────────────────────────
    ("C{year}_A.zip",         "c{year}_a.csv",         "completions"),
    ("C{year}_B.zip",         "c{year}_b.csv",         "completions"),
    # ── 12-month Enrollment (EFFY) ───────────────────────────────────────────
    ("EFFY{year}.zip",        "effy{year}.csv",        "enrollment"),
    ("EFFY{year}_DIST.zip",   "effy{year}_dist.csv",   "enrollment"),
    ("EFFY{year}_HS.zip",     "effy{year}_hs.csv",     "enrollment"),
    ("EFIA{year}.zip",        "efia{year}.csv",        "enrollment"),
    # ── Fall Enrollment (EF) ─────────────────────────────────────────────────
    ("EF{year}A.zip",         "ef{year}a.csv",         "enrollment"),
    ("EF{year}B.zip",         "ef{year}b.csv",         "enrollment"),
    ("EF{year}C.zip",         "ef{year}c.csv",         "enrollment"),
    ("EF{year}D.zip",         "ef{year}d.csv",         "enrollment"),
    ("EF{year}A_DIST.zip",    "ef{year}a_dist.csv",    "enrollment"),
    ("EF{year}CP.zip",        "ef{year}cp.csv",        "enrollment"),
    # ── Graduation Rates ─────────────────────────────────────────────────────
    ("GR{year}.zip",          "gr{year}.csv",          "graduation"),
    ("GR{year}_L2.zip",       "gr{year}_l2.csv",       "graduation"),
    ("GR{year}_PELL_SSL.zip", "gr{year}_pell_ssl.csv", "graduation"),
    ("GR200_{yy}.zip",        "gr200_{yy}.csv",        "graduation"),  # 2-digit year
    # ── Student Financial Aid  (fiscal year pair: SFA2223 = AY2022-23) ──────
    ("SFA{ppyy}.zip",         "sfa{ppyy}.csv",         "sfa"),
    ("SFAV{ppyy}.zip",        "sfav{ppyy}.csv",        "sfa"),
    # ── Admissions ───────────────────────────────────────────────────────────
    ("ADM{year}.zip",         "adm{year}.csv",         "admissions"),
    # ── Finance (fiscal year pair: F2324 = FY2023-24) ────────────────────────
    ("F{ppyy}_F1A.zip",       "f{ppyy}_f1a.csv",       "finance"),
    ("F{ppyy}_F2.zip",        "f{ppyy}_f2.csv",        "finance"),
    ("F{ppyy}_F3.zip",        "f{ppyy}_f3.csv",        "finance"),
    # ── Staff ────────────────────────────────────────────────────────────────
    ("S{year}_OC.zip",        "s{year}_oc.csv",        "staff"),
    ("S{year}_SIS.zip",       "s{year}_sis.csv",       "staff"),
    ("S{year}_IS.zip",        "s{year}_is.csv",        "staff"),
    ("S{year}_NH.zip",        "s{year}_nh.csv",        "staff"),
    ("EAP{year}.zip",         "eap{year}.csv",         "staff"),
    # ── Salaries ─────────────────────────────────────────────────────────────
    ("SAL{year}_IS.zip",      "sal{year}_is.csv",      "salaries"),
    ("SAL{year}_NIS.zip",     "sal{year}_nis.csv",     "salaries"),
]

# Named subsets for --surveys filter
SURVEY_GROUPS: dict[str, list[str]] = {
    "core":        ["hd", "ic", "completions"],
    "enrollment":  ["enrollment"],
    "graduation":  ["graduation"],
    "sfa":         ["sfa"],
    "admissions":  ["admissions"],
    "finance":     ["finance"],
    "staff":       ["staff", "salaries"],
    "all":         ["hd", "ic", "completions", "enrollment", "graduation",
                    "sfa", "admissions", "finance", "staff", "salaries"],
}

# Crosswalk files — downloaded once, not per-year.
# CIP titles are extracted from the crosswalk CIPTitle column directly,
# so no separate taxonomy file is needed.
CROSSWALK_FILES = [
    {
        "filename": "cip2020_soc2018_crosswalk.xlsx",
        "url": "https://nces.ed.gov/ipeds/cipcode/Files/CIP2020_SOC2018_Crosswalk.xlsx",
        "description": "CIP 2020 → SOC 2018 crosswalk + CIP titles (NCES)",
    },
]

DEFAULT_START_YEAR = 2014
DEFAULT_END_YEAR = 2024


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def download_file(url: str, dest: Path, force: bool = False, label: str = "") -> bool:
    """
    Download url to dest. Skips if dest exists and not force.
    Returns True if downloaded, False if skipped.
    """
    if dest.exists() and not force:
        print(f"  [skip] {dest.name} already exists")
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    display = label or dest.name

    try:
        print(f"  [fetch] {display} ...", end="", flush=True)
        resp = requests.get(url, timeout=60, stream=True)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)

        size_mb = downloaded / 1_048_576
        print(f" {size_mb:.1f} MB ✓")
        return True

    except requests.HTTPError as e:
        print(f" ERROR: {e}")
        if dest.exists():
            dest.unlink()  # remove partial file
        return False
    except requests.RequestException as e:
        print(f" ERROR: {e}")
        return False


def extract_zip(zip_path: Path, target_csv_name: str, dest_dir: Path) -> bool:
    """
    Extract a single CSV from a zip file. Returns True on success.
    IPEDS files use utf-8-sig encoding (BOM), which pandas handles automatically.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / target_csv_name

    try:
        with zipfile.ZipFile(zip_path) as z:
            # IPEDS zips contain the CSV with uppercase names internally
            names = z.namelist()
            # Match case-insensitively
            match = next(
                (n for n in names if n.lower() == target_csv_name.lower()),
                None,
            )
            if not match:
                print(f"    [warn] {target_csv_name} not found in {zip_path.name}")
                print(f"    Available: {names}")
                return False

            with z.open(match) as src, open(dest_file, "wb") as dst:
                dst.write(src.read())

        return True

    except zipfile.BadZipFile:
        print(f"    [error] {zip_path.name} is not a valid zip file")
        return False


def write_manifest(entries: list[dict]) -> None:
    """Append download events to MANIFEST.md."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Read existing content
    existing = MANIFEST_PATH.read_text() if MANIFEST_PATH.exists() else ""

    # Append new entries
    with open(MANIFEST_PATH, "w") as f:
        if not existing:
            f.write("# Data Download Manifest\n\n")
            f.write(
                "Auto-generated by `scripts/download_data.py`. "
                "Tracks what was downloaded and when.\n\n"
            )
            f.write("| File | Source | Downloaded At |\n")
            f.write("|---|---|---|\n")
        else:
            f.write(existing)

        for entry in entries:
            f.write(f"| `{entry['file']}` | {entry['url']} | {entry['at']} |\n")


# ---------------------------------------------------------------------------
# Main download logic
# ---------------------------------------------------------------------------
def download_ipeds_year(year: int, force: bool, surveys: list[str] | None = None) -> list[dict]:
    """Download IPEDS survey files for one year. Returns manifest entries.

    Args:
        year: IPEDS data year.
        force: Re-download even if file already exists.
        surveys: Survey group names to include (e.g. ['core', 'enrollment']).
                 None or empty = use 'core' (hd + ic + completions).
    """
    # Resolve which groups to download
    active_groups: set[str]
    if not surveys:
        active_groups = set(SURVEY_GROUPS["core"])
    else:
        active_groups = set()
        for s in surveys:
            active_groups.update(SURVEY_GROUPS.get(s, [s]))

    print(f"\n── Year {year} (surveys: {', '.join(sorted(active_groups))}) ──")
    year_dir = IPEDS_DIR / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries = []
    tmp_dir = IPEDS_DIR / "_zips"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    for zip_name_tmpl, csv_name_tmpl, group in IPEDS_FILES_PER_YEAR:
        if group not in active_groups:
            continue

        zip_name = _fmt(zip_name_tmpl, year)
        csv_name = _fmt(csv_name_tmpl, year)
        csv_dest = year_dir / csv_name

        if csv_dest.exists() and not force:
            print(f"  [skip] {csv_name} already extracted")
            continue

        # Download zip to temp location
        zip_dest = tmp_dir / zip_name
        url = f"{IPEDS_BASE}/{zip_name}"
        download_file(url, zip_dest, force=force, label=zip_name)

        if not zip_dest.exists():
            print(f"  [warn] Skipping extraction — {zip_name} not available")
            continue

        # Extract the CSV
        print(f"  [extract] {zip_name} → {csv_name}")
        success = extract_zip(zip_dest, csv_name, year_dir)

        if success:
            manifest_entries.append(
                {
                    "file": f"data/raw/ipeds/{year}/{csv_name}",
                    "url": url,
                    "at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
            )
            # Remove zip after extraction to save disk space
            zip_dest.unlink(missing_ok=True)

    return manifest_entries


def download_crosswalks(force: bool) -> list[dict]:
    """Download CIP→SOC crosswalk and CIP taxonomy files."""
    print(f"\n── Crosswalk files ──")
    CROSSWALK_DIR.mkdir(parents=True, exist_ok=True)

    manifest_entries = []
    for cf in CROSSWALK_FILES:
        dest = CROSSWALK_DIR / cf["filename"]
        downloaded = download_file(
            cf["url"], dest, force=force, label=f"{cf['filename']} ({cf['description']})"
        )
        if downloaded:
            manifest_entries.append(
                {
                    "file": f"data/raw/crosswalks/{cf['filename']}",
                    "url": cf["url"],
                    "at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
            )

    return manifest_entries


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download IPEDS data files and crosswalks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Download a single year (e.g. 2023)",
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs=2,
        metavar=("START", "END"),
        help="Download an inclusive year range (e.g. --years 2020 2023)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download files even if they already exist",
    )
    parser.add_argument(
        "--crosswalks-only",
        action="store_true",
        help="Only download crosswalk files (skip IPEDS year files)",
    )
    parser.add_argument(
        "--surveys",
        nargs="+",
        metavar="SURVEY",
        help=(
            "Survey groups to download. Options: core (default), enrollment, "
            "graduation, sfa, admissions, finance, staff, all. "
            "Example: --surveys core enrollment graduation"
        ),
    )

    args = parser.parse_args()

    # Determine year range
    if args.year:
        years = [args.year]
    elif args.years:
        start, end = args.years
        years = list(range(start, end + 1))
    else:
        years = list(range(DEFAULT_START_YEAR, DEFAULT_END_YEAR + 1))

    print("=" * 60)
    print("Haystack — IPEDS Data Download")
    print(f"Mode: {'FORCE re-download' if args.force else 'Additive (skip existing)'}")
    if not args.crosswalks_only:
        print(f"Years: {years[0]}–{years[-1]} ({len(years)} years)")
    print("=" * 60)

    all_manifest_entries = []

    # Download crosswalks first (loaders depend on them)
    crosswalk_entries = download_crosswalks(force=args.force)
    all_manifest_entries.extend(crosswalk_entries)

    # Download IPEDS year files
    if not args.crosswalks_only:
        surveys = args.surveys or None
        if surveys:
            # Expand named groups and show what will be downloaded
            active: set[str] = set()
            for s in surveys:
                active.update(SURVEY_GROUPS.get(s, [s]))
            print(f"Survey filter: {', '.join(sorted(active))}")
        else:
            print("Survey filter: core (hd, ic, completions) — use --surveys all for everything")
        for year in years:
            year_entries = download_ipeds_year(year, force=args.force, surveys=surveys)
            all_manifest_entries.extend(year_entries)

    # Write manifest
    if all_manifest_entries:
        write_manifest(all_manifest_entries)
        print(f"\n✓ Manifest updated: data/MANIFEST.md")

    print("\n" + "=" * 60)
    print(f"✅ Download complete.")
    print(f"   IPEDS data: data/raw/ipeds/")
    print(f"   Crosswalks: data/raw/crosswalks/")
    print(f"   Next step:  python scripts/run_pipeline.py --region kansas-city")
    print("=" * 60)


if __name__ == "__main__":
    main()
