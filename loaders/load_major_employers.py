import os
import sys
import pandas as pd
import difflib
import uuid
import re

# Setup app context
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app
from models import db, Organization, OrgFact, OrgFactType

# Basic string mappings for major classes in the source file
# Some map to 3-digit NAICS for precision, some 2-digit for broad coverage
BASE_MAP = {
    "Healthcare": "622", # Hospitals
    "Information Technology": "541", # Professional / computer services
    "Manufacturing": "31", # Broad manufacturing (31-33)
    "Distribution": "493", # Warehousing
    "Contact Centers": "561", # Administrative/support
    "Architectural Engineering": "541", # Engineering services
    "Bioscience": "541", # R&D
    "Insurance": "524",
    "Finance": "522",
    "Financial Services": "522",
    "Animal Health": "541",
    "Construction": "23",
    "Telecommunications": "517",
    "Retail": "44",
    "Restaurant": "722",
    "Legal": "541",
    "Energy": "221",
    "Accounting": "541",
    "Logistics": "488"
}

def infer_naics(industry_str, description_str):
    industry_str = str(industry_str).strip()
    description_str = str(description_str).strip().lower()

    if industry_str in BASE_MAP:
        return BASE_MAP[industry_str]

    # Description Hybrid Inference
    if "education" in description_str or "school" in description_str or "university" in description_str or "college" in description_str:
        return "61" # Educational Services
    if "government" in description_str or "city" in description_str or "county" in description_str:
        return "92" # Public Administration
    if "real estate" in description_str:
        return "53" # Real Estate
    if "law firm" in description_str or "legal" in description_str:
        return "54" # Professional, Scientific, and Tech (Legal is 5411)
    if "hotel" in description_str or "gaming" in description_str or "restaurant" in description_str:
        return "72" # Accommodation and Food Services
    if "trucking" in description_str or "railroad" in description_str or "airline" in description_str or "transportation" in description_str:
        return "48" # Transportation
    if "advertising" in description_str or "marketing" in description_str or "public relations" in description_str:
        return "54" # Professional Services
        
    if "auto parts" in description_str:
        return "423" # Merchant Wholesalers
    if "hospital" in description_str or "referral" in description_str or "care" in description_str:
        return "62"
    if "mfg" in description_str or "manufacturing" in description_str or "factory" in description_str:
        return "31"
    if "data center" in description_str or "software" in description_str:
        return "51"
    if "distribution" in description_str or "warehouse" in description_str:
        return "49"
    if "bank" in description_str or "finance" in description_str:
        return "52"
    
    # Check if there are multiple parts separated by semicolon
    if ";" in industry_str:
        parts = [p.strip() for p in industry_str.split(";")]
        # Exclude "Headquarters" or "Other" to find the real one
        for p in parts:
            if p in BASE_MAP and p not in ["Headquarters", "Other"]:
                return BASE_MAP[p]

    return None

def run():
    app = create_app()
    with app.app_context():
        file_path = os.path.join(app.root_path, "data", "raw", "employers", "Major Employers.xlsx")
        
        try:
            df = pd.read_excel(file_path)
        except Exception as e:
            print(f"Error loading file: {e}")
            return
            
        # Get existing employers for deduplication
        existing_orgs = db.session.query(Organization).filter_by(org_type="employer").all()
        existing_names = {org.name: org for org in existing_orgs}
        
        unmapped_rows = []
        upserted = 0
        skipped = 0

        for idx, row in df.iterrows():
            name = str(row.get('Account', '')).strip()
            desc = str(row.get('Description', '')).strip()
            industry = str(row.get('Major Employer Industry', '')).strip()
            employees = str(row.get('Total Regional Employees', '')).strip()

            if not name or name == 'nan':
                continue

            naics = infer_naics(industry, desc)
            if not naics:
                unmapped_rows.append(row)
                continue

            # Fuzzy match
            match = None
            if existing_names:
                matches = difflib.get_close_matches(name, existing_names.keys(), n=1, cutoff=0.85)
                if matches:
                    match = existing_names[matches[0]]

            if match:
                org = match
                org.naics_code = naics
                # Only update if null
                if not org.city:
                    org.city = "Kansas City"
            else:
                org = Organization(
                    org_id=str(uuid.uuid4()),
                    name=name,
                    org_type="employer",
                    city="Kansas City", # Implicitly from the KC Major Employers list
                    naics_code=naics
                )
                db.session.add(org)
                existing_names[name] = org # cache
                
            db.session.flush()

            # Add Employee Fact
            if employees and employees != 'nan':
                # Clear old employee ranges
                db.session.query(OrgFact).filter_by(org_id=org.org_id, fact_type=OrgFactType.EMPLOYEES_TOTAL_RANGE).delete()
                
                fact = OrgFact(
                    org_id=org.org_id,
                    fact_type=OrgFactType.EMPLOYEES_TOTAL_RANGE,
                    value_text=employees,
                    source="Major Employers.xlsx"
                )
                db.session.add(fact)
                
            upserted += 1

        db.session.commit()
        
        # Write unmapped QA file
        qa_dir = os.path.join(app.root_path, "data", "qa")
        os.makedirs(qa_dir, exist_ok=True)
        qa_path = os.path.join(qa_dir, "unmapped_employers.csv")
        
        if unmapped_rows:
            unmapped_df = pd.DataFrame(unmapped_rows)
            unmapped_df.to_csv(qa_path, index=False)
            
        print(f"Loaded {upserted} Major Employers")
        print(f"Skipped {len(unmapped_rows)} due to uncertain NAICS mappings (see {qa_path})")

if __name__ == "__main__":
    run()
