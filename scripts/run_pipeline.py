"""
Orchestrate the full Haystack data pipeline in dependency order.

Runs all steps from schema init through QA verification. Stops on the
first failure and prints a clear error message.

Usage:
    python scripts/run_pipeline.py                       # full pipeline, kansas-city
    python scripts/run_pipeline.py --region kansas-city  # explicit region
    python scripts/run_pipeline.py --year 2023           # explicit year
    python scripts/run_pipeline.py --skip-download       # skip download step
    python scripts/run_pipeline.py --dry-run             # pass --dry-run to all loaders
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DB_DIR = PROJECT_ROOT / "db"
LOADERS_DIR = PROJECT_ROOT / "loaders"
QA_DIR = PROJECT_ROOT / "qa"


def run_step(label: str, cmd: list, cwd: Path = None) -> None:
    """Run a subprocess step. Exits the whole pipeline on failure."""
    print(f"\n{'─' * 60}")
    print(f"▶  {label}")
    print(f"   {' '.join(str(c) for c in cmd)}")
    print(f"{'─' * 60}")

    start = time.time()
    result = subprocess.run(cmd, cwd=cwd or PROJECT_ROOT)
    elapsed = time.time() - start

    if result.returncode != 0:
        print(f"\n❌ FAILED: {label} (exit code {result.returncode})")
        print("   Fix the error above, then re-run the pipeline.")
        sys.exit(1)

    print(f"✅ Done ({elapsed:.1f}s)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full Haystack data pipeline.")
    parser.add_argument("--region", default="kansas-city", help="Region slug")
    parser.add_argument("--year", type=int, default=2024, help="IPEDS data year")
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip the download step (use existing files)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pass --dry-run to all loaders (no DB writes)",
    )
    args = parser.parse_args()

    py = sys.executable
    dry = ["--dry-run"] if args.dry_run else []

    print("=" * 60)
    print("Haystack — Full Data Pipeline")
    print(f"Region: {args.region}  |  Year: {args.year}")
    if args.dry_run:
        print("Mode: DRY RUN")
    if args.skip_download:
        print("Download: SKIPPED")
    print("=" * 60)

    steps = []

    # Step 0 — Download (optional)
    if not args.skip_download:
        steps.append((
            f"Download IPEDS {args.year} + crosswalks",
            [py, str(SCRIPTS_DIR / "download_data.py"), "--year", str(args.year)],
        ))

    # Step 1 — Schema
    steps.append((
        "Initialize database schema (Alembic upgrade to head)",
        [py, str(DB_DIR / "init_db.py")],
    ))

    # Step 2 — Seed
    steps.append((
        "Seed region + county FIPS data",
        [py, str(DB_DIR / "seed.py")],
    ))

    # Step 3 — CIP→SOC crosswalk Phase 1 (must run before programs — populates occupation table)
    steps.append((
        "Load CIP→SOC crosswalk + occupations (Phase 1: occupation table)",
        [py, str(LOADERS_DIR / "load_cip_soc.py")] + dry,
    ))

    # Step 4 — Institutions
    steps.append((
        f"Load IPEDS institutions ({args.year})",
        [
            py,
            str(LOADERS_DIR / "load_ipeds_institutions.py"),
            "--region", args.region,
            "--year", str(args.year),
        ] + dry,
    ))

    # Step 5 — Programs
    steps.append((
        f"Load IPEDS programs ({args.year})",
        [
            py,
            str(LOADERS_DIR / "load_ipeds_programs.py"),
            "--region", args.region,
            "--year", str(args.year),
        ] + dry,
    ))

    # Step 6 — CIP→SOC Phase 2 (link programs to occupations — programs must exist first)
    steps.append((
        "Link programs to occupations via CIP→SOC crosswalk (Phase 2: program_occupation)",
        [py, str(LOADERS_DIR / "load_cip_soc.py")] + dry,
    ))

    # Step 6 — QA (only if not dry-run — QA reads from DB)
    if not args.dry_run:
        steps.append((
            "Run IPEDS QA checks",
            [py, str(QA_DIR / "check_ipeds.py")],
        ))

    # Execute
    for label, cmd in steps:
        run_step(label, cmd)

    print(f"\n{'=' * 60}")
    print("✅ Pipeline complete!")
    print(f"   {len(steps)} steps ran successfully.")
    print(f"\n   Next: python qa/check_ipeds.py   (re-run anytime)")
    print(f"         flask run                  (start the app)")
    print("=" * 60)


if __name__ == "__main__":
    main()
