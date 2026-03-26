"""
IPEDS data quality assurance report.

Validates that the IPEDS pipeline loaded data correctly by running
a set of checks against the live database. No args required —
reads from the configured database directly.

Usage:
    python qa/check_ipeds.py
    python qa/check_ipeds.py --fail-fast    # exit 1 on first failure
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from models import DatasetSource, Occupation, OrgAlias, Organization, Program, ProgramOccupation, Region, RegionCounty
from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import Session

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"


def check(label: str, condition: bool, detail: str = "", fail_fast: bool = False) -> bool:
    status = PASS if condition else FAIL
    line = f"  {status}  {label}"
    if detail:
        line += f"\n         {detail}"
    print(line)
    if not condition and fail_fast:
        print("\n[error] Stopping on first failure (--fail-fast).")
        sys.exit(1)
    return condition


def run(fail_fast: bool = False) -> int:
    """Run all checks. Returns number of failures."""
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    failures = 0

    with Session(engine) as session:
        # Enable FK checks (SQLite requires this per-connection)
        session.execute(text("PRAGMA foreign_keys = ON"))

        print("=" * 60)
        print("IPEDS QA Report")
        print("=" * 60)

        # ── Dataset sources ────────────────────────────────────────────────
        print("\n[Dataset Sources]")
        sources = session.query(DatasetSource).all()
        source_ids = {s.source_id for s in sources}

        for expected_id in ["nces_cip_soc_2020"]:
            ok = expected_id in source_ids
            ds = next((s for s in sources if s.source_id == expected_id), None)
            detail = f"records={ds.record_count}, loaded={ds.loaded_at}" if ds else "NOT FOUND"
            check(f"dataset_source: {expected_id}", ok, detail, fail_fast)
            failures += 0 if ok else 1

        # IPEDS HD + C are year-specific — check for any year present
        ipeds_hd = any(s.source_id.startswith("ipeds_hd_") for s in sources)
        ipeds_c = any(s.source_id.startswith("ipeds_c_") for s in sources)
        check("dataset_source: ipeds_hd_* present", ipeds_hd, fail_fast=fail_fast)
        check("dataset_source: ipeds_c_* present", ipeds_c, fail_fast=fail_fast)
        failures += (0 if ipeds_hd else 1) + (0 if ipeds_c else 1)

        # Print all source records for reference
        print("\n  All dataset_source rows:")
        for s in sorted(sources, key=lambda x: x.source_id):
            print(f"    {s.source_id:35} records={s.record_count or '?':>6}  loaded={s.loaded_at}")

        # ── Institutions ───────────────────────────────────────────────────
        print("\n[Institutions]")
        total_orgs = session.query(Organization).filter_by(org_type="training").count()
        ok = total_orgs > 0
        check(f"At least 1 training organization", ok, f"Total: {total_orgs}", fail_fast)
        failures += 0 if ok else 1

        # Count by county
        by_county = (
            session.query(
                Organization.county_fips,
                RegionCounty.county_name,
                RegionCounty.state,
                func.count(Organization.org_id).label("cnt"),
            )
            .join(RegionCounty, Organization.county_fips == RegionCounty.county_fips, isouter=True)
            .filter(Organization.org_type == "training")
            .group_by(Organization.county_fips)
            .order_by(func.count(Organization.org_id).desc())
            .all()
        )

        print(f"\n  Institutions by county ({total_orgs} total):")
        for row in by_county:
            county_label = f"{row.county_name}, {row.state}" if row.county_name else row.county_fips or "unknown"
            print(f"    {county_label:30} {row.cnt:3}")

        # Confirm each KC MSA county has at least 1 institution
        region = session.query(Region).filter_by(slug="kansas-city").first()
        if region:
            kc_counties = session.query(RegionCounty).filter_by(region_id=region.region_id).all()
            county_fips_with_orgs = {r.county_fips for r in by_county if r.cnt > 0}
            missing = [c.county_fips for c in kc_counties if c.county_fips not in county_fips_with_orgs]
            # WARN not FAIL — rural/fringe MSA counties may legitimately have no postsecondary institutions
            status = PASS if not missing else WARN
            detail = f"No institutions in: {missing}" if missing else f"All {len(kc_counties)} counties covered"
            print(f"  {status}  KC MSA county coverage")
            if detail:
                print(f"         {detail}")

        # ── Deduplication integrity ────────────────────────────────────────
        print("\n[Deduplication Integrity]")
        org_count = session.query(Organization).filter_by(org_type="training").count()
        alias_count = session.query(OrgAlias).filter_by(source="ipeds").count()

        ok = org_count == alias_count
        check(
            "org count matches org_alias count (source=ipeds)",
            ok,
            f"organizations={org_count}, aliases={alias_count}",
            fail_fast,
        )
        failures += 0 if ok else 1

        # Check for duplicate unitids in organization table
        dup_unitids = (
            session.query(Organization.unitid, func.count(Organization.org_id).label("cnt"))
            .filter(Organization.unitid.isnot(None))
            .group_by(Organization.unitid)
            .having(func.count(Organization.org_id) > 1)
            .all()
        )
        ok = len(dup_unitids) == 0
        check(
            "No duplicate unitids in organization table",
            ok,
            f"Duplicates: {[r.unitid for r in dup_unitids]}" if dup_unitids else "",
            fail_fast,
        )
        failures += 0 if ok else 1

        # ── Programs ───────────────────────────────────────────────────────
        print("\n[Programs]")
        total_programs = session.query(Program).count()
        ok = total_programs > 0
        check(f"At least 1 program", ok, f"Total: {total_programs}", fail_fast)
        failures += 0 if ok else 1

        # Programs with NULL org_id (FK violation)
        null_org = session.query(Program).filter(Program.org_id.is_(None)).count()
        ok = null_org == 0
        check("No programs with NULL org_id", ok, f"Violations: {null_org}", fail_fast)
        failures += 0 if ok else 1

        # Suppressed completions
        suppressed = session.query(Program).filter(Program.completions.is_(None)).count()
        pct = (suppressed / total_programs * 100) if total_programs else 0
        # Warn if >50% suppressed (unusual) — don't fail
        status = WARN if pct > 50 else "  ℹ️  INFO"
        print(f"  {status}  Suppressed completions (NULL): {suppressed} ({pct:.1f}%)")

        # By credential type
        by_cred = (
            session.query(Program.credential_type, func.count(Program.program_id).label("cnt"))
            .group_by(Program.credential_type)
            .order_by(func.count(Program.program_id).desc())
            .all()
        )
        print(f"\n  Programs by credential type:")
        for row in by_cred:
            print(f"    {row.credential_type:45} {row.cnt:4}")

        # ── Occupations + Crosswalk ────────────────────────────────────────
        print("\n[Occupations & CIP→SOC Links]")
        total_occs = session.query(Occupation).count()
        ok = total_occs > 0
        check(f"Occupation table populated", ok, f"Total: {total_occs}", fail_fast)
        failures += 0 if ok else 1

        total_links = session.query(ProgramOccupation).count()
        ok = total_links > 0
        check(f"program_occupation links exist", ok, f"Total: {total_links}", fail_fast)
        failures += 0 if ok else 1

        # % of programs with at least one occupation link
        programs_with_links = (
            session.query(func.count(func.distinct(ProgramOccupation.program_id))).scalar() or 0
        )
        pct_linked = (programs_with_links / total_programs * 100) if total_programs else 0
        ok = pct_linked >= 50  # warn if less than half linked
        check(
            f"≥50% of programs have occupation links",
            ok,
            f"{programs_with_links}/{total_programs} = {pct_linked:.1f}%",
            fail_fast,
        )
        failures += 0 if ok else 1

        # FK integrity: program_occupation → program
        orphan_links = (
            session.query(ProgramOccupation)
            .filter(
                ~ProgramOccupation.program_id.in_(
                    session.query(Program.program_id)
                )
            )
            .count()
        )
        ok = orphan_links == 0
        check("No orphaned program_occupation rows", ok, f"Orphans: {orphan_links}", fail_fast)
        failures += 0 if ok else 1

        # ── Summary ────────────────────────────────────────────────────────
        print("\n" + "=" * 60)
        if failures == 0:
            print(f"✅ All checks passed.")
        else:
            print(f"❌ {failures} check(s) failed. Review output above.")
        print("=" * 60)

    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Run IPEDS data QA checks.")
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop and exit 1 on the first failed check",
    )
    args = parser.parse_args()
    failures = run(fail_fast=args.fail_fast)
    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
