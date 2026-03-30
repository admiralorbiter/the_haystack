"""
Loads BLS Employment Projections (2024-2034) into the OccupationProjection model.

Reads:
  - data/raw/emp/occupation.xlsx (Sheet: 'Table 1.2')
  
Filters to:
  - Line items (Detailed occupations)
"""

import sys
from pathlib import Path
import pandas as pd

# Fix path to allow importing app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from models import Occupation, OccupationProjection, db

BLS_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "raw"
    / "emp"
    / "occupation.xlsx"
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
        print(f"[skip] BLS data not found at {BLS_FILE}")
        sys.exit(0)

    print("Reading BLS projections...")
    # Skip the first row so Real headers become the dataframe columns
    df = pd.read_excel(BLS_FILE, sheet_name="Table 1.2", skiprows=1)
    
    # Identify dynamic column names (handling en-dashes vs hyphens)
    cols = list(df.columns)
    
    col_soc = "2024 National Employment Matrix code"
    col_type = "Occupation type"
    col_emp24 = "Employment, 2024"
    col_emp34 = "Employment, 2034"
    
    col_pct_change = next((c for c in cols if "percent" in c.lower() and "change" in c.lower() and "2024" in c), None)
    col_openings = next((c for c in cols if "openings" in c.lower() and "annual" in c.lower()), None)
    
    if not all([col_soc, col_type, col_emp24, col_emp34, col_pct_change, col_openings]):
        print("ERROR: Could not map all required columns. Columns found:", cols)
        sys.exit(1)

    # Filter to only line items (detailed SOCs)
    df = df[df[col_type] == "Line item"]

    # Filter out empty SOCs
    df = df[df[col_soc].notna()]

    app = create_app("default")
    with app.app_context():
        # Load existing valid SOCs to guarantee referential integrity
        valid_socs = {soc[0] for soc in db.session.query(Occupation.soc).all()}
        
        # We replace the entire table content safely since it's a 1:1 spoke table
        db.session.query(OccupationProjection).delete()
        print("Cleared existing OccupationProjection records.")
        
        insert_count = 0
        skip_count = 0
        
        for _, row in df.iterrows():
            soc = str(row[col_soc]).strip()
            # Handle potential ".0" suffixes from excel parsing
            if soc.endswith(".0"):
                soc = soc[:-2]
            
            if soc not in valid_socs:
                skip_count += 1
                continue
                
            emp24raw = clean_num(row[col_emp24])
            emp34raw = clean_num(row[col_emp34])
            pctraw = clean_num(row[col_pct_change])
            openingsraw = clean_num(row[col_openings])
            
            # BLS provides employment in *thousands* — multiply by 1000
            emp_2024 = int(emp24raw * 1000) if emp24raw is not None else None
            emp_2034 = int(emp34raw * 1000) if emp34raw is not None else None
            # Openings are also in *thousands* in Table 1.2!
            annual_openings = int(openingsraw * 1000) if openingsraw is not None else None
            
            proj = OccupationProjection(
                soc=soc,
                emp_2024=emp_2024,
                emp_2034=emp_2034,
                pct_change=pctraw,
                annual_openings=annual_openings
            )
            db.session.add(proj)
            insert_count += 1

        db.session.commit()
        print(f"✅ Loaded {insert_count} projections. Skipped {skip_count} unmatched SOCs.")

if __name__ == "__main__":
    main()
