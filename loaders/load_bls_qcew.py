"""
Load BLS QCEW (Quarterly Census of Employment and Wages) Local Trend Data
Parses county-level CSVs directly from ZIP archives to power Dataset C2.

Usage:
    python loaders/load_bls_qcew.py
"""

import zipfile
import csv
import io
import sys
from pathlib import Path

# Make project root importable from this script location
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from config import Config
from models import db, IndustryQCEW
from loaders import utils

def load_all_qcew(session: Session, data_dir: Path):
    """
    Parse all 202* QCEW data from ZIP files and load into IndustryQCEW.
    """
    qcew_dir = data_dir / "qcew"
    if not qcew_dir.exists():
        print(f"[warn] QCEW data directory not found: {qcew_dir}")
        return

    # 1. Get KC Area FIPs to limit our processing
    target_fips = utils.get_kc_county_fips(session)
    if not target_fips:
        print("[error] Could not determine KC County FIPS. Aborting QCEW load.")
        return
        
    print(f"Loading QCEW data for {len(target_fips)} KC FIPS over existing data")
    
    # 2. Clear existing QCEW data to prevent duplicates on re-run
    session.execute(delete(IndustryQCEW))
    session.commit()

    total_records = 0

    # 3. Iterate through zip files
    zip_files = sorted(qcew_dir.glob("*.zip"))
    if not zip_files:
        print("[warn] No .zip files found in data/raw/qcew")
        return

    for zpath in zip_files:
        print(f"Processing archive: {zpath.name}...")
        try:
            with zipfile.ZipFile(zpath, 'r') as z:
                # Find the target FIPS files without unzipping the whole archive
                for fips in target_fips:
                    fips_files = [n for n in z.namelist() if fips in n and n.endswith('.csv')]
                    
                    for fname in fips_files:
                        with z.open(fname) as f:
                            text_content = io.TextIOWrapper(f, encoding='utf-8')
                            reader = csv.DictReader(text_content)
                            
                            records = []
                            for row in reader:
                                # We use specific ownership codes to get granular data, skipping 0 (Total) to avoid double counting.
                                # 1=Federal, 2=State, 3=Local, 5=Private
                                if row.get("own_code") not in ("1", "2", "3", "5"):
                                    continue
                                                                
                                try:
                                    estab_str = row.get("qtrly_estabs_count")
                                    estab = int(estab_str) if estab_str and estab_str != "N" else None
                                    
                                    empl_str = row.get("month3_emplvl")
                                    empl = int(empl_str) if empl_str and empl_str != "N" else None
                                    
                                    wage_str = row.get("avg_wkly_wage")
                                    wage = float(wage_str) if wage_str and wage_str != "N" else None
                                    
                                    qcew_record = IndustryQCEW(
                                        naics=row.get("industry_code"),
                                        county_fips=row.get("area_fips"),
                                        year=int(row.get("year", 0)),
                                        quarter=int(row.get("qtr", 0)),
                                        establishments=estab,
                                        employment=empl,
                                        avg_weekly_wage=wage
                                    )
                                    records.append(qcew_record)
                                except Exception as parse_e:
                                    pass
                            
                            if records:
                                session.add_all(records)
                                session.commit()
                                total_records += len(records)
                                print(f"  Loaded {len(records)} records for FIPS {fips}")
                                
        except zipfile.BadZipFile:
            print(f"[error] Corrupt ZIP file: {zpath.name}")

    print(f"Finished loading {total_records} QCEW records.")
    
    # 4. Record the dataset loaded
    utils.record_dataset_source(
        session=session,
        source_id="c2_qcew",
        name="Quarterly Census of Employment and Wages (QCEW) - Local",
        version="Most Recent 3 Years",
        url="https://www.bls.gov/cew/downloadable-data.htm",
        record_count=total_records,
        notes="Loaded own_code=0 for KC Area FIPS",
    )
    session.commit()

def main():
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    with Session(engine) as session:
        load_all_qcew(session, utils.RAW_DIR)

if __name__ == "__main__":
    main()
