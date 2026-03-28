import sys
import uuid
import pandas as pd
from pathlib import Path
from thefuzz import fuzz

# Ensure parent dir is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from models import db, Organization, OrgAlias, OrgContact, RegionCounty
from loaders.utils import PROJECT_ROOT, record_dataset_source

DATA_FILE = PROJECT_ROOT / "data" / "raw" / "apprenticeship" / "partner-finder-listings.csv"

# Use exact names from the CSV mapped to their verified IPEDS/WIOA org_id,
# or 'SKIP' to force a new entity creation instead of merging.
MANUAL_OVERRIDES = {
    # Example: 'Aviation Institute of Maintenance': 'wioa_abcd1234',
    # Example: 'Generic Training Corp': 'SKIP'
}

def find_fuzzy_match(new_org_name, candidates):
    """
    Find best fuzzy match for an organization.
    Returns (match_org_id, score) or (None, 0).
    """
    target_name = str(new_org_name).strip()
    
    # Check overrides hatch first
    if target_name in MANUAL_OVERRIDES:
        override_val = MANUAL_OVERRIDES[target_name]
        if override_val == 'SKIP':
            return None, 100.0
        return override_val, 100.0
        
    best_match = None
    best_score = 0.0
    
    # Very high threshold since we are automatically merging.
    THRESHOLD = 90
    
    target_name_lower = target_name.lower()
    for cand in candidates:
        if cand.name:
            # Token set ratio handles extra words well ("JCCC" vs "Johnson County Community College")
            # But we require a high partial ratio too to be safe.
            score = fuzz.token_set_ratio(target_name_lower, cand.name.lower())
            if score >= THRESHOLD and score > best_score:
                best_score = score
                best_match = cand.org_id
                
    return best_match, best_score

def load_apprenticeships():
    app = create_app()
    with app.app_context():
        if not DATA_FILE.exists():
            print(f"File not found: {DATA_FILE}")
            return

        print("Reading Apprenticeship Partner Finder data...")
        df = pd.read_csv(DATA_FILE)
        
        # We will attempt to match existing IPEDS or WIOA providers.
        # It's safest to only match against 'training' providers to avoid collapsing distinct employers.
        existing_training_orgs = db.session.query(Organization).filter(
            Organization.org_type == 'training'
        ).all()
        
        print(f"Loaded {len(existing_training_orgs)} existing training providers for fuzzy matching.")

        # Load zip2fips crosswalk
        import json, re
        zip2fips_path = PROJECT_ROOT / "data" / "geography" / "zip2fips.json"
        zip2fips = {}
        if zip2fips_path.exists():
            with open(zip2fips_path, "r") as f:
                zip2fips = json.load(f)
                
        # Load KC MSA valid county FIPS
        kc_counties = db.session.query(RegionCounty.county_fips).filter_by(region_id='kc-msa').all()
        kc_fips_set = {str(c.county_fips).zfill(5) for c in kc_counties}

        # Cache mapping of already-processed names to ID in this run to bundle multi-row employers
        session_cache = {}
        
        added = 0
        merged = 0

        for _, row in df.iterrows():
            org_name = str(row.get("ORGANIZATION NAME", "")).strip()
            if not org_name or org_name.lower() == 'nan':
                continue
                
            raw_type = str(row.get("ORGANIZATION TYPE", "")).strip()
            city = str(row.get("CITY", "")).strip()
            state = str(row.get("STATE", "")).strip()
            address = str(row.get("ADDRESS", "")).strip()
            website = str(row.get("ORGANIZATION URL", "")).strip()
            if website.lower() == "does not apply":
                website = None
                
            contact_person = str(row.get("CONTACT PERSON", "")).strip()
            contact_email = str(row.get("EMAIL", "")).strip()
            contact_phone = str(row.get("PHONE", "")).strip()

            def _clean_contact(val):
                v_low = val.lower()
                if not v_low or v_low == "nan" or "does not apply" in v_low or v_low == "undefined" or v_low == "none@none.com":
                    return None
                return val

            contact_person = _clean_contact(contact_person)
            contact_email = _clean_contact(contact_email)
            contact_phone = _clean_contact(contact_phone)
            
            # Extract ZIP and geofence
            zip_raw = str(row.get("ZIP", "")).strip()
            zip_match = re.match(r'^(\d{5})', zip_raw)
            county_fips = None
            if zip_match:
                zip_code = zip_match.group(1)
                county_fips = zip2fips.get(zip_code)
                if isinstance(county_fips, list):
                    # Some zip codes span multiple counties. We'll generously check the first matched one.
                    county_fips = county_fips[0]
                
            # If the CSV entity mapper tells us they aren't in our MSA, completely ignore the entity.
            # (If it's missing FIPS, we still skip since we only want in-region for employers)
            if not county_fips or county_fips not in kc_fips_set:
                continue
                
            cache_key = f"{org_name.lower()}|{city.lower()}|{state.lower()}"
            
            # Map raw type to system enum
            if raw_type.lower() == 'employer':
                sys_type = 'employer'
            elif raw_type.lower() in ('educator', 'training provider'):
                sys_type = 'training'
            else:
                sys_type = 'intermediary'
                
            if cache_key in session_cache:
                # We already processed this org in this file (e.g. they sponsor multiple things)
                continue

            match_id, score = None, 0
            
            # Safe fuzzy match ONLY for entities that act as Educators or Sponsors (Intermediaries)
            # Employers should strictly be separate entities unless we specifically built an employer list previously.
            if sys_type in ('training', 'intermediary'):
                match_id, score = find_fuzzy_match(org_name, existing_training_orgs)
                
            if match_id:
                # Merge logic
                org_record = db.session.query(Organization).get(match_id)
                org_record.is_apprenticeship_partner = True
                
                # Only overwrite the role if it doesn't already have one, or maybe append
                if not org_record.apprenticeship_role:
                    org_record.apprenticeship_role = raw_type
                    
                if county_fips and not org_record.county_fips:
                    org_record.county_fips = county_fips
                
                # Add contact if we have data and it doesn't already exist for this org
                if contact_person or contact_email or contact_phone:
                    existing_contact = db.session.query(OrgContact).filter_by(org_id=match_id, contact_role="Apprenticeship Partner").first()
                    if not existing_contact:
                        new_contact = OrgContact(
                            org_id=match_id,
                            contact_name=contact_person,
                            contact_email=contact_email,
                            contact_phone=contact_phone,
                            contact_role="Apprenticeship Partner"
                        )
                        db.session.add(new_contact)
                    
                session_cache[cache_key] = match_id
                merged += 1
                
            else:
                # Create logic
                new_id = f"appr_{uuid.uuid4().hex[:8]}"
                new_org = Organization(
                    org_id=new_id,
                    name=org_name,
                    org_type=sys_type,
                    city=city,
                    state=state,
                    county_fips=county_fips,
                    website=website,
                    is_apprenticeship_partner=True,
                    apprenticeship_role=raw_type
                )
                db.session.add(new_org)
                
                if contact_person or contact_email or contact_phone:
                    new_contact = OrgContact(
                        org_id=new_id,
                        contact_name=contact_person,
                        contact_email=contact_email,
                        contact_phone=contact_phone,
                        contact_role="Apprenticeship Partner"
                    )
                    db.session.add(new_contact)
                
                session_cache[cache_key] = new_id
                added += 1

        db.session.commit()
        
        # Record sync metadata
        record_dataset_source(
            session=db.session,
            source_id="apprenticeship_partner_finder",
            name="Apprenticeship Partner Finder",
            version="2026-03",
            url="https://www.apprenticeship.gov/partner-finder/listings",
            record_count=added + merged,
            notes="Loads organizational base for Employers, Sponsors, and Educators. Merges with existing training providers via fuzzy match."
        )
        db.session.commit()

        print(f"Apprenticeship Load Complete: {added} new organizations added, {merged} merged with existing.")

if __name__ == "__main__":
    load_apprenticeships()
