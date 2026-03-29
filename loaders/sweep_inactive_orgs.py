"""
Utility to sweep and soft-delete organizations not touched by recent loader runs.

Any organization with a last_seen_in_source date older than the specified threshold
is marked as inactive. Inactive organizations drop out of public directories but 
their detail pages remain accessible with an archiving banner.

Usage:
    python loaders/sweep_inactive_orgs.py --older-than-days 30
    python loaders/sweep_inactive_orgs.py --dry-run
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make project root importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from config import Config
from models import Organization, db


def sweep_inactive(session: Session, days: int, dry_run: bool = False) -> int:
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    print(f"Sweeping organizations last seen before: {cutoff_date.isoformat()}")

    query = (
        session.query(Organization)
        .filter(
            (Organization.last_seen_in_source < cutoff_date)
            | (Organization.last_seen_in_source.is_(None))
        )
        .filter(Organization.is_active == True)
    )

    stale_orgs = query.all()
    count = len(stale_orgs)

    if count == 0:
        print("  ✅ All active organizations are up-to-date. Nothing to sweep.")
        return 0

    if dry_run:
        print(f"\n  [DRY RUN] Would mark {count} organizations as inactive:")
        for o in stale_orgs[:10]:
            print(f"    - {o.name} (last seen: {o.last_seen_in_source})")
        if count > 10:
            print(f"    ... and {count - 10} more.")
        return 0

    for o in stale_orgs:
        o.is_active = False

    session.commit()
    print(f"  🚨 Swept {count} organizations to inactive state.")
    return count


def main():
    parser = argparse.ArgumentParser(
        description="Sweep stale organizations to inactive state."
    )
    parser.add_argument(
        "--older-than-days", type=int, default=30, help="Days threshold (default 30)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without modifying DB"
    )
    args = parser.parse_args()

    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    with Session(engine) as session:
        sweep_inactive(session, days=args.older_than_days, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
