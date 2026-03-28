"""
Link WIOA training provider satellites to their parent IPEDS colleges.

Uses fuzzy name matching (thefuzz) to find high-confidence parent-child
relationships between WIOA-only providers and IPEDS institutions.

Written rows: Relationship(from=wioa_org, to=ipeds_org, rel_type='parent_org')

This is a SEPARATE maintenance script -- not part of the ETPL loader.
Safe to re-run (idempotent: deletes existing auto_fuzzy parent_org rows first,
but preserves source='manual' rows).

Handling false positives / negatives
-------------------------------------
  BLOCKLIST        -- name-fragment pairs that fuzzy matching should never link
  MANUAL_OVERRIDES -- per-org overrides that take full precedence over fuzzy:
                      str value  -> force this parent org_id  (fixes false negatives)
                      None value -> suppress auto-link entirely (fixes false positives)
  --threshold      -- lower = more links; higher = fewer but more precise (default 92)
  --dry-run        -- preview all matches before writing; safe to run anytime

Usage:
    python loaders/link_org_parents.py
    python loaders/link_org_parents.py --verbose
    python loaders/link_org_parents.py --dry-run
    python loaders/link_org_parents.py --threshold 85
"""

import argparse
import sys
from pathlib import Path

from thefuzz import fuzz

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from models import db, Organization, Relationship

# ---------------------------------------------------------------------------
# Threshold for partial_ratio (containment): the IPEDS college name
# must be at least this percentage contained within the WIOA provider name.
# ---------------------------------------------------------------------------
DEFAULT_THRESHOLD = 92

# ---------------------------------------------------------------------------
# BLOCKLIST: (wioa_name_fragment, college_name_fragment) pairs that would
# produce known false positives if fuzzy-matched.
# ---------------------------------------------------------------------------
BLOCKLIST = [
    ("columbia college", "metropolitan community"),
    ("kansas city kansas", "johnson county"),
]

# ---------------------------------------------------------------------------
# MANUAL_OVERRIDES: { wioa_org_id: parent_org_id | None }
#
#   str value  -> force link to this specific IPEDS org (fixes false negatives,
#                 abbreviations, etc.)  Tagged source='manual' in the DB.
#   None value -> suppress auto-linking (fixes false positives).
#
# These take FULL precedence over fuzzy matching.
# To find org_ids run: python -c "from app import create_app; ..."
# ---------------------------------------------------------------------------
MANUAL_OVERRIDES: dict[str, "str | None"] = {
    # Example entries -- fill in real org_ids as needed:
    # 'wioa_dd3': 'beedcde0',   # KCKCC Tech Ed Center -> Kansas City Kansas Community College
    # 'wioa_1d3': None,         # suppress a bad auto-link
}


def _blocklisted(wioa_name: str, college_name: str) -> bool:
    wl, cl = wioa_name.lower(), college_name.lower()
    return any(wf in wl and cf in cl for wf, cf in BLOCKLIST)


def find_parent(
    wioa_org: Organization,
    colleges: list,
    threshold: int,
) -> tuple:
    """
    Find the best IPEDS college match for a WIOA provider.

    Two-signal strategy
    -------------------
    Primary  : partial_ratio -- catches 'Park University-Parkville' matching
               'Park University' because the shorter string is fully contained.
    Secondary: token_set_ratio as tiebreaker.
    City     : First word of city must match to prevent cross-city false positives.

    Returns (best_match_org | None, confidence_float_0_to_1).
    """
    best_match = None
    best_score = 0.0

    wioa_name = wioa_org.name.lower()
    wioa_city = (wioa_org.city or "").lower()

    for college in colleges:
        college_name = college.name.lower()
        college_city = (college.city or "").lower()

        if _blocklisted(wioa_name, college_name):
            continue

        # City guard: first word of city must match (allows Overland Park / Kansas City both = "overland" / "kansas")
        if wioa_city and college_city:
            wioa_first = wioa_city.split()[0]
            coll_first = college_city.split()[0]
            if (wioa_city not in college_city and college_city not in wioa_city
                    and wioa_first != coll_first):
                continue

        partial = fuzz.partial_ratio(wioa_name, college_name)
        tset = fuzz.token_set_ratio(wioa_name, college_name)
        score = partial * 0.75 + tset * 0.25

        # Reject if partial is high but token_set is very low (substring accident)
        if partial >= threshold and tset < 60:
            continue

        if score > best_score and partial >= threshold:
            best_score = score
            best_match = college

    return best_match, round(best_score / 100, 3)


def run(threshold: int = DEFAULT_THRESHOLD, dry_run: bool = False, verbose: bool = False) -> dict:
    app = create_app()
    with app.app_context():
        all_orgs = db.session.query(Organization).all()
        colleges = [o for o in all_orgs if o.unitid]
        satellites = [o for o in all_orgs if not o.unitid]
        college_by_id = {o.org_id: o for o in colleges}

        print(f"  Colleges (IPEDS): {len(colleges)}")
        print(f"  Training providers (WIOA-only): {len(satellites)}")

        # Idempotency: clear previously auto-linked rows (keeps source='manual')
        if not dry_run:
            deleted = (
                db.session.query(Relationship)
                .filter_by(rel_type="parent_org", source="auto_fuzzy")
                .delete()
            )
            if deleted:
                print(f"  Cleared {deleted} stale auto_fuzzy parent_org rows.")

        linked = 0
        skipped = 0

        for sat in satellites:
            # --- Manual overrides take full precedence ---
            if sat.org_id in MANUAL_OVERRIDES:
                override_target = MANUAL_OVERRIDES[sat.org_id]
                if override_target is None:
                    if verbose:
                        print(f"  [Suppress] '{sat.name}' -- manual suppression")
                    skipped += 1
                    continue
                parent = college_by_id.get(override_target)
                if parent:
                    if verbose:
                        print(f"  [Manual]   '{sat.name}' -> '{parent.name}'")
                    if not dry_run:
                        db.session.add(Relationship(
                            from_entity_type="organization",
                            from_entity_id=sat.org_id,
                            to_entity_type="organization",
                            to_entity_id=parent.org_id,
                            rel_type="parent_org",
                            confidence=1.0,
                            source="manual",
                        ))
                    linked += 1
                else:
                    print(f"  [Warn] Manual override for '{sat.name}' references unknown org_id '{override_target}'")
                    skipped += 1
                continue

            # --- Fuzzy matching ---
            parent, score = find_parent(sat, colleges, threshold)
            if parent:
                if verbose:
                    print(f"  [Link]     '{sat.name}' -> '{parent.name}'  (conf={score})")
                if not dry_run:
                    db.session.add(Relationship(
                        from_entity_type="organization",
                        from_entity_id=sat.org_id,
                        to_entity_type="organization",
                        to_entity_id=parent.org_id,
                        rel_type="parent_org",
                        confidence=score,
                        source="auto_fuzzy",
                    ))
                linked += 1
            else:
                if verbose:
                    print(f"  [Skip]     '{sat.name}' -- no match above threshold {threshold}")
                skipped += 1

        if not dry_run:
            db.session.commit()
            print(f"\n  Committed {linked} parent_org links.")
        else:
            print(f"\n  [DRY RUN] Would write {linked} parent_org links, skipped {skipped}.")

        return {"linked": linked, "skipped": skipped}


def main():
    parser = argparse.ArgumentParser(
        description="Link WIOA satellite orgs to IPEDS parent colleges.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                        help=f"partial_ratio threshold (default: {DEFAULT_THRESHOLD})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview matches without writing to DB")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print each match/skip/suppress/manual decision")
    args = parser.parse_args()

    result = run(threshold=args.threshold, dry_run=args.dry_run, verbose=args.verbose)
    print(f"\nDone -- {result['linked']} linked, {result['skipped']} unmatched.")


if __name__ == "__main__":
    main()
