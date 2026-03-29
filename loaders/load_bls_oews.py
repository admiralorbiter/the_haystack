"""
Loads BLS OEWS (May 2024) into the OccupationWage model.

Reads:
  - data/raw/bls/oesm24all/all_data_M_2024.xlsx
  
Filters to:
  - National (AREA_TYPE = 1)
  - Missouri & Kansas (AREA_TYPE = 2)
  - Kansas City MSA (AREA_TYPE = 4)
  
Extracts only detailed occupations (O_GROUP = 'detailed').
"""

import sys
from pathlib import Path

import pandas as pd

# Fix path to allow importing app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from models import Occupation, OccupationWage, db

BLS_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "raw"
    / "bls"
    / "oesm24all"
    / "all_data_M_2024.xlsx"
)

app = create_app("default")


def clean_wage(val):
    """Convert BLS missing values (*, #, **) to None, otherwise float."""
    if pd.isna(val) or val in ("*", "#", "**"):
        return None
    try:
        return float(val)
    except ValueError:
        return None


def main():
    if not BLS_FILE.exists():
        print(f"ERROR: BLS data not found at {BLS_FILE}")
        sys.exit(1)

    print(f"Loading BLS OEWS data from {BLS_FILE.name}...")

    # Read excel - specifying columns limits memory usage
    columns = [
        "AREA",
        "AREA_TITLE",
        "AREA_TYPE",
        "OCC_CODE",
        "O_GROUP",
        "TOT_EMP",
        "A_MEAN",
        "A_PCT25",
        "A_MEDIAN",
        "A_PCT75",
    ]
    df = pd.read_excel(BLS_FILE, usecols=lambda c: c in columns)

    # Filter to detailed occupations
    df = df[df["O_GROUP"] == "detailed"]

    # Identify target areas
    is_national = df["AREA_TYPE"] == 1
    is_state = df["AREA_TITLE"].isin(["Missouri", "Kansas"])
    is_kc_msa = df["AREA_TITLE"].str.contains("Kansas City", case=False, na=False) & (
        df["AREA_TYPE"] == 4
    )

    target_df = df[is_national | is_state | is_kc_msa].copy()

    with app.app_context():
        # Map area type codes to string
        area_type_map = {1: "national", 2: "state", 4: "msa"}

        # Keep track of existing SOCs to avoid foreign key violations
        valid_socs = {occ.soc for occ in Occupation.query.all()}

        print("Clearing old wage data...")
        db.session.query(OccupationWage).delete()

        insert_count = 0
        wages_to_insert = []

        print("Inserting valid wages...")
        for _, row in target_df.iterrows():
            soc = str(row["OCC_CODE"]).strip()
            if soc not in valid_socs:
                continue

            area_code = str(row["AREA"])
            area_title = str(row["AREA_TITLE"])
            area_type = area_type_map.get(row["AREA_TYPE"], "unknown")

            wages_to_insert.append(
                OccupationWage(
                    soc=soc,
                    area_type=area_type,
                    area_code=area_code,
                    area_name=area_title,
                    employment_count=clean_wage(row["TOT_EMP"]),
                    annual_mean_wage=clean_wage(row["A_MEAN"]),
                    median_wage=clean_wage(row["A_MEDIAN"]),
                    pct_25_wage=clean_wage(row["A_PCT25"]),
                    pct_75_wage=clean_wage(row["A_PCT75"]),
                )
            )

            insert_count += 1
            if len(wages_to_insert) >= 1000:
                db.session.bulk_save_objects(wages_to_insert)
                wages_to_insert = []

        if wages_to_insert:
            db.session.bulk_save_objects(wages_to_insert)

        db.session.commit()
        print(f"✓ Inserted {insert_count} wage records.")


if __name__ == "__main__":
    main()
