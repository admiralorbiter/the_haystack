"""
Load WIOA Eligible Training Provider List (ETPL) into the Haystack database.
Source: TrainingProviderResults.gov Search Results.csv.
"""
import argparse
import sys
import uuid
import re
from pathlib import Path
from thefuzz import fuzz

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Make project root importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from models import db, Organization, Program, OrgAlias, ProgramOccupation
from loaders.utils import (
    RAW_DIR,
    CROSSWALK_DIR,
    get_kc_county_fips,
    record_dataset_source,
    normalize_cip
)

SOURCE_ID = "wioa_etpl"
SOURCE_NAME = "Federal WIOA ETPL / RAPIDS"
CENSUS_ZCTA_URL = "https://www2.census.gov/geo/docs/maps-data/data/rel/zcta_county_rel_10.txt"


def _str(val, default: str = "") -> str | None:
    """Safely convert a pandas value to string, returning None for NaN/empty."""
    import math
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return None
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    return s if s and s.lower() != 'nan' else None


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
    csv_path = RAW_DIR / "wioa" / "TrainingProviderResults.gov Search Results.csv"
    if not csv_path.exists():
        print(f"[error] Missing file: {csv_path}", file=sys.stderr)
        sys.exit(1)

    print(f"  Reading WIOA ETPL from {csv_path.name}...")
    # 'field_zip' might contain spaces or bad formatting
    df = pd.read_csv(csv_path, dtype=str, low_memory=False)
    df["zip_clean"] = df["field_zip"].fillna("").astype(str).str.replace(r"\D", "", regex=True).str[:5]

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
        provider_name = _str(row.get("field_etp", "")) or ""
        program_name = _str(row.get("field_program_name", "")) or ""
        address = _str(row.get("field_address", ""))
        city = _str(row.get("field_city", ""))
        state = _str(row.get("field_state", ""))
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
                if verbose:
                    print(f"    [Merge] WIOA '{provider_name}' -> IPEDS '{best_match.name}'")
            else:
                # 2. Create new organization
                org_id = f"wioa_{uuid.uuid4().hex[:8]}"
                new_org = Organization(
                    org_id=org_id,
                    name=provider_name,
                    org_type="training",
                    city=city,
                    state=state,
                    website=_str(row.get("field_program_url", ""))
                )
                if not dry_run:
                    session.add(new_org)
                new_orgs_cache[cache_key] = org_id
                loaded_orgs += 1
                if verbose:
                    print(f"    [New Org] {provider_name} in {city}, {state}")

        # 3. Create Program
        entity_type = str(row.get("field_entity_type", ""))
        is_apprenticeship = "Apprenticeship" in entity_type
        
        # Duration fallback
        try:
            weeks = int(float(row.get("field_program_length_weeks", 0)))
        except ValueError:
            weeks = None

        new_prog = Program(
            org_id=org_id,
            name=program_name,
            credential_type=_str(row.get("field_associated_credential", "")) or "Certificate",
            cip=normalize_cip(_str(row.get("field_cip_code", ""))) or "99.9999",
            modality="In-Person" if "in-person" in (_str(row.get("field_program_format", "")) or "").lower() else "Hybrid",
            duration_weeks=weeks,
            is_wioa_eligible=True,
            is_apprenticeship=is_apprenticeship
        )
        if not dry_run:
            session.add(new_prog)
            session.flush()
            
            # Map SOCs
            for i in [1, 2, 3]:
                soc = str(row.get(f"field_program_soc_occ_{i}", "")).strip()
                if soc and len(soc) > 5:
                    if len(soc) == 9 and soc[2] == "-":
                        soc = soc[:7] # e.g. "29-203100" -> "29-2031"
                    po = ProgramOccupation(
                        program_id=new_prog.program_id,
                        soc=soc,
                        source="wioa_etpl"
                    )
                    session.add(po)

        loaded_progs += 1

    if not dry_run:
        session.commit()
        record_dataset_source(
            session,
            source_id=SOURCE_ID,
            name=SOURCE_NAME,
            version="2024",
            url=csv_path.name,
            record_count=loaded_progs,
            notes=f"KC MSA match: {loaded_orgs} new orgs, {loaded_progs} programs."
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
