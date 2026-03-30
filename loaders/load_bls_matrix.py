"""
Loads BLS Industry-Occupation Matrix (2024-2034) into the OccupationIndustry model.

Reads:
  - data/raw/emp/matrix.xlsx
  
Filters to:
  - Line items for both Occupation type and Industry type.
"""

import sys
from pathlib import Path
import pandas as pd

# Fix path to allow importing app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from models import Occupation, OccupationIndustry, db

BLS_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "raw"
    / "emp"
    / "matrix.xlsx"
)


def clean_num(val):
    """Convert BLS missing values (*, #, **, -, —) to None, otherwise float."""
    if pd.isna(val) or str(val).strip() in ("*", "#", "**", "-", "—"):
        return None
    try:
        return float(val)
    except ValueError:
        return None


def main():
    if not BLS_FILE.exists():
        print(f"[skip] BLS matrix data not found at {BLS_FILE}")
        sys.exit(0)

    print("Reading BLS matrix data...")
    df = pd.read_excel(BLS_FILE)
    
    # Identify dynamic column names (handling en-dashes vs hyphens just in case)
    cols = list(df.columns)
    
    col_occ_type = "Occupation type"
    col_ind_type = "Industry type"
    col_soc = "Occupation code"
    col_naics = "Industry code"
    col_ind_title = "Industry title"
    col_emp24 = "2024 Employment"
    col_pct_occ = "2024 Percent of Occupation"
    
    if not all([c in cols for c in [col_occ_type, col_ind_type, col_soc, col_naics, col_ind_title, col_emp24, col_pct_occ]]):
        print("ERROR: Could not map all required columns. Columns found:", cols)
        sys.exit(1)

    # Filter to only line items (detailed SOCs and NAICS)
    df = df[(df[col_occ_type] == "Line item") & (df[col_ind_type] == "Line item")]

    # Filter out empty SOCs
    df = df[df[col_soc].notna() & df[col_naics].notna()]

    app = create_app("default")
    with app.app_context():
        # Load existing valid SOCs to guarantee referential integrity
        valid_socs = {soc[0] for soc in db.session.query(Occupation.soc).all()}
        
        # We replace the entire table content safely since it's a 1:N spoke table
        db.session.query(OccupationIndustry).delete()
        print("Cleared existing OccupationIndustry records.")
        
        insert_count = 0
        skip_count = 0
        
        # Collect all rows in a list for bulk insert to speed up processing
        # This file is around 40k+ rows!
        db_rows = []
        
        for _, row in df.iterrows():
            soc = str(row[col_soc]).strip()
            # Handle potential ".0" suffixes from excel parsing
            if soc.endswith(".0"):
                soc = soc[:-2]
            
            if soc not in valid_socs:
                skip_count += 1
                continue
            
            naics = str(row[col_naics]).strip()
            if naics.endswith(".0"):
                naics = naics[:-2]
            
            ind_title = str(row[col_ind_title]).strip()
                
            emp24raw = clean_num(row[col_emp24])
            pctraw = clean_num(row[col_pct_occ])
            
            if pctraw is None:
                continue
            
            # BLS provides employment in *thousands* — multiply by 1000
            employment_2024 = int(emp24raw * 1000) if emp24raw is not None else None
            
            proj = OccupationIndustry(
                soc=soc,
                naics=naics,
                industry_title=ind_title,
                employment_2024=employment_2024,
                pct_of_occupation=pctraw,
            )
            db_rows.append(proj)
            insert_count += 1
            
            # Commit in chunks to save memory
            if insert_count % 5000 == 0:
                db.session.bulk_save_objects(db_rows)
                db.session.commit()
                db_rows = []
                print(f"  ... inserted {insert_count} records")

        if db_rows:
            db.session.bulk_save_objects(db_rows)
            db.session.commit()
            
        print(f"✅ Loaded {insert_count} matrix crosswalks. Skipped {skip_count} referencing unmatched SOCs.")

if __name__ == "__main__":
    main()
