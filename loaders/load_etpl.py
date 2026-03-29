"""
Load WIOA Eligible Training Provider List (ETPL) into the Haystack database.
Source: DownloadPrograms.xlsx (from TrainingProviderResults.gov full data download).
"""

import argparse
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from thefuzz import fuzz

# Make project root importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from loaders.utils import (CROSSWALK_DIR, RAW_DIR, get_kc_county_fips,
                           normalize_cip, record_dataset_source)
from models import OrgAlias, Organization, Program, ProgramOccupation, db

SOURCE_ID = "wioa_etpl"
SOURCE_NAME = "Federal WIOA ETPL / RAPIDS"
CENSUS_ZCTA_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/rel/zcta_county_rel_10.txt"
)


def _str(val, default: str = "") -> str | None:
    """Safely convert a pandas value to string, returning None for NaN/empty."""
    import math

    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return None
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    return s if s and s.lower() != "nan" else None


def normalize_credential(raw_val: str | None) -> str:
    """Map messy WIOA string credentials to standard IPEDS buckets."""
    if not raw_val:
        return "Certificate"

    val = raw_val.lower()
    if "associate" in val or "aas" in val or "aa-" in val:
        return "Associate's degree"
    if "bachelor" in val or "ba-" in val or "bs-" in val:
        return "Bachelor's degree"
    if "master" in val:
        return "Master's degree"
    if "doctor" in val:
        return "Doctoral degree"

    return "Certificate"


def _get_kc_zips(session) -> set[str]:
    """Fetch the KC MSA FIPS codes and map them to ZIP codes via the Census ZCTA crosswalk."""
    kc_fips = get_kc_county_fips(session, "kansas-city")
    crosswalk_path = CROSSWALK_DIR / "zcta_county_rel_10.txt"

    # Download and cache Census Zip to County crosswalk if missing
    if not crosswalk_path.exists():
        print("  Downloading Census ZCTA-to-County crosswalk...")
        CROSSWALK_DIR.mkdir(parents=True, exist_ok=True)
        try:
            df = pd.read_csv(CENSUS_ZCTA_URL, dtype=str)
            df.to_csv(crosswalk_path, index=False)
        except Exception as e:
            print(f"[error] Failed to download crosswalk: {e}", file=sys.stderr)
            sys.exit(1)

    df = pd.read_csv(crosswalk_path, dtype=str)

    # The Census columns are ZCTA5 and GEOID
    df_kc = df[df["GEOID"].isin(kc_fips)]
    zips = set(df_kc["ZCTA5"].dropna().str.zfill(5))
    print(f"  Mapped {len(kc_fips)} MSA counties to {len(zips)} unique ZIP codes.")
    return zips


def load_etpl(session, dry_run=False, verbose=False) -> dict:
    file_path = RAW_DIR / "wioa" / "DownloadPrograms.xlsx"
    if not file_path.exists():
        print(f"[error] Missing file: {file_path}", file=sys.stderr)
        sys.exit(1)

    print(f"  Reading WIOA ETPL from {file_path.name}...")
    # Using openpyxl to read the xlsx data download
    df = pd.read_excel(file_path, dtype=str)

    # Clean Zip
    df["zip_clean"] = (
        df["zip"].fillna("").astype(str).str.replace(r"\D", "", regex=True).str[:5]
    )

    # Filter by MSA Zips
    kc_zips = _get_kc_zips(session)
    kc_df = df[df["zip_clean"].isin(kc_zips)].copy()

    print(f"  Matched {len(kc_df)} training programs in KC MSA ZIP codes.")
    if len(kc_df) == 0:
        return {"loaded_orgs": 0, "loaded_progs": 0, "failed": 0}

    # Pre-load existing orgs for fuzzy matching
    existing_orgs = session.query(Organization).all()

    loaded_orgs = 0
    loaded_progs = 0
    failed = 0

    # Track created orgs in this run to attach multiple programs to the same new org
    # structure: { (name_lower, city_lower): org_id }
    new_orgs_cache = {}

    for _, row in kc_df.iterrows():
        provider_name = _str(row.get("d101_eligible_training_provider", "")) or ""
        program_name = _str(row.get("d105_program_name", "")) or ""
        address = _str(row.get("address", ""))
        city = _str(row.get("city", ""))
        state = _str(row.get("state", ""))
        zip_code = row["zip_clean"]

        if not provider_name or not program_name:
            continue

        city_lower = city.lower() if city else ""
        name_lower = provider_name.lower()

        org_id = None

        # 1. Fuzzy match against existing organizations
        cache_key = (name_lower, city_lower)
        if cache_key in new_orgs_cache:
            org_id = new_orgs_cache[cache_key]
        else:
            best_match = None
            best_score = 0

            for o in existing_orgs:
                if not o.city and not city:
                    score = fuzz.token_sort_ratio(name_lower, o.name.lower())
                elif o.city and city and city_lower in o.city.lower():
                    score = fuzz.token_sort_ratio(name_lower, o.name.lower())
                else:
                    score = 0

                if score > 85 and score > best_score:
                    best_score = score
                    best_match = o

            if best_match:
                org_id = best_match.org_id
                best_match.last_seen_in_source = datetime.now(timezone.utc)
                best_match.is_active = True
                if verbose:
                    print(
                        f"    [Merge] WIOA '{provider_name}' -> IPEDS '{best_match.name}'"
                    )
            else:
                # 2. Create new organization
                org_id = f"wioa_{uuid.uuid4().hex[:8]}"
                new_org = Organization(
                    org_id=org_id,
                    name=provider_name,
                    org_type="training",
                    city=city,
                    state=state,
                    website=_str(row.get("d107_program_url", "")),
                    last_seen_in_source=datetime.now(timezone.utc),
                    is_active=True,
                )
                if not dry_run:
                    session.add(new_org)
                new_orgs_cache[cache_key] = org_id
                loaded_orgs += 1
                if verbose:
                    print(f"    [New Org] {provider_name} in {city}, {state}")

        # 3. Create Program
        entity_type = _str(row.get("d104_entity_type", "")) or ""
        is_apprenticeship = "Apprenticeship" in entity_type

        # Duration fallback
        try:
            weeks = int(float(row.get("d114_program_length_weeks", 0)))
        except (ValueError, TypeError):
            weeks = None

        new_prog = Program(
            org_id=org_id,
            name=program_name,
            credential_type=normalize_credential(
                _str(row.get("d109_associated_credential", ""))
            ),
            cip=normalize_cip(_str(row.get("d110_cip_code", ""))) or "99.9999",
            modality=(
                "In-Person"
                if "in-person"
                in (_str(row.get("d116_program_format", "")) or "").lower()
                else "Hybrid"
            ),
            duration_weeks=weeks,
            is_wioa_eligible=True,
            is_apprenticeship=is_apprenticeship,
        )
        if not dry_run:
            session.add(new_prog)
            session.flush()

            # Map SOCs
            seen_socs = set()
            for i in [1, 2, 3]:
                soc = str(row.get(f"d11{6+i}_program_soc_occupation_{i}", "")).strip()
                if soc and len(soc) > 5:
                    if len(soc) > 7 and "-" in soc:
                        soc = soc[:7]  # e.g. "29-203100" -> "29-2031"
                    if " " in soc:
                        soc = soc.split(" ")[0]  # in case of messy formatting

                    if soc in seen_socs:
                        continue
                    seen_socs.add(soc)

                    try:
                        po = ProgramOccupation(
                            program_id=new_prog.program_id, soc=soc, source="wioa_etpl"
                        )
                        session.add(po)
                    except Exception:
                        pass  # avoid failing if format is completely messed up

        loaded_progs += 1

    if not dry_run:
        session.commit()
        record_dataset_source(
            session,
            source_id=SOURCE_ID,
            name=SOURCE_NAME,
            version="2024",
            url=file_path.name,
            record_count=loaded_progs,
            notes=f"KC MSA match: {loaded_orgs} new orgs, {loaded_progs} programs.",
        )
        session.commit()

    return {"loaded_orgs": loaded_orgs, "loaded_progs": loaded_progs, "failed": failed}


def main():
    parser = argparse.ArgumentParser(description="Load WIOA ETPL into the database.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    from app import create_app
    from models import db

    app = create_app()
    with app.app_context():
        res = load_etpl(db.session, dry_run=args.dry_run, verbose=args.verbose)

    print("\nResults:")
    print(f"  New Providers (Orgs): {res['loaded_orgs']}")
    print(f"  New Programs Loaded:  {res['loaded_progs']}")


if __name__ == "__main__":
    main()
