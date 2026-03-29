"""
Load IPEDS Demographics data from Fall Enrollment (ef2024a) and Completions (c2024_a)
into OrganizationDemographics and ProgramDemographics.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import db, Organization, Program, OrganizationDemographics, ProgramDemographics, OrganizationCompletionsDemographics
from loaders.utils import RAW_DIR

def _pct(val: float, total: float) -> float | None:
    if total is None or total <= 0:
        return 0.0
    if pd.isna(val) or val is None:
        return 0.0
    return float(val) / float(total)

def load_organization_demographics(session: Session, year: str) -> int:
    """Load Fall Enrollment from ef{year}a.csv into OrganizationDemographics."""
    file_path = RAW_DIR / "ipeds" / year / f"ef{year}a.csv"
    if not file_path.exists():
        print(f"[error] Missing file: {file_path}", file=sys.stderr)
        return 0

    print(f"Loading Organization Demographics from {file_path.name}...")
    df = pd.read_csv(file_path, dtype=str)
    
    # Filter for EFALEVEL == '1' (All students total)
    df = df[df['EFALEVEL'] == '1']
    
    # Fetch existing organizations that have a UNITID
    orgs = session.query(Organization).filter(Organization.unitid.isnot(None)).all()
    org_dict = {o.unitid: o.org_id for o in orgs}
    
    # Clear existing OrganizationDemographics for these orgs
    session.query(OrganizationDemographics).filter(OrganizationDemographics.org_id.in_(org_dict.values())).delete(synchronize_session=False)
    
    loaded = 0
    for _, row in df.iterrows():
        unitid = row.get("UNITID")
        if unitid not in org_dict:
            continue
            
        org_id = org_dict[unitid]
        
        try:
            total = float(row.get("EFTOTLT", 0) or 0)
            if total <= 0:
                continue

            demo = OrganizationDemographics(
                org_id=org_id,
                total_enrollment=int(total),
                pct_men=_pct(row.get("EFTOTLM", 0), total),
                pct_women=_pct(row.get("EFTOTLW", 0), total),
                pct_white=_pct(row.get("EFWHITT", 0), total),
                pct_black=_pct(row.get("EFBKAAT", 0), total),
                pct_hispanic=_pct(row.get("EFHISPT", 0), total),
                pct_asian=_pct(row.get("EFASIAT", 0), total),
                pct_native=_pct(row.get("EFAIANT", 0), total),
                pct_pacific=_pct(row.get("EFNHPIT", 0), total),
                pct_two_or_more=_pct(row.get("EF2MORT", 0), total),
                pct_unknown=_pct(row.get("EFUNKNT", 0), total),
                pct_non_resident=_pct(row.get("EFNRALT", 0), total)
            )
            session.add(demo)
            loaded += 1
        except Exception as e:
            print(f"Error loading org demo for UNITID {unitid}: {e}")
            
    print(f"  Loaded {loaded} OrganizationDemographics.")
    return loaded


def load_program_demographics(session: Session, year: str) -> int:
    """Load Completions from c{year}_a.csv into ProgramDemographics."""
    file_path = RAW_DIR / "ipeds" / year / f"c{year}_a.csv"
    if not file_path.exists():
        print(f"[error] Missing file: {file_path}", file=sys.stderr)
        return 0

    print(f"Loading Program Demographics from {file_path.name}...")
    df = pd.read_csv(file_path, dtype=str)
    
    # Filter for MAJORNUM == '1' (First major)
    df = df[df['MAJORNUM'] == '1']
    
    # Convert numerical columns representing demographics
    numeric_cols = [
        "CTOTALT", "CTOTALM", "CTOTALW", "CWHITT", "CBKAAT", "CHISPT",
        "CASIAT", "CAIANT", "CNHPIT", "C2MORT", "CUNKNT", "CNRALT"
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Aggregate completions across all Award Levels (AWLEVEL) for a given UNITID and CIPCODE
    grouped = df.groupby(["UNITID", "CIPCODE"])[numeric_cols].sum().reset_index()
    
    # Fetch existing programs linked to organizations with UNITIDs
    orgs = session.query(Organization).filter(Organization.unitid.isnot(None)).all()
    org_dict = {o.unitid: o.org_id for o in orgs}
    
    programs = session.query(Program).filter(Program.org_id.in_(org_dict.values())).all()
    
    # Create lookup map (org_id, cip) -> program_id
    # We strip trailing dots from CIPCODE in lookup since IPEDS CIPs sometimes have them or don't
    # Actually, IPEDS CIPCODE is like "11.0101". Program.cip is also "11.0101".
    prog_map = {}
    for p in programs:
        prog_map[(p.org_id, p.cip)] = p.program_id
        
    # Clear existing ProgramDemographics and OrganizationCompletionsDemographics
    session.query(ProgramDemographics).filter(ProgramDemographics.program_id.in_(prog_map.values())).delete(synchronize_session=False)
    session.query(OrganizationCompletionsDemographics).filter(OrganizationCompletionsDemographics.org_id.in_(org_dict.values())).delete(synchronize_session=False)
    
    loaded = 0
    for _, row in grouped.iterrows():
        unitid = str(row.get("UNITID", ""))
        cip = str(row.get("CIPCODE", ""))
        
        # IPEDS CIPCODE sometimes has trailing zeros or missing dots in some raw formats, 
        # but c2024_a usually has it as "11.0101". 
        if cip.endswith("."):
            cip = cip[:-1]
            
        if unitid not in org_dict:
            continue
            
        org_id = org_dict[unitid]
        
        # IPEDS "99.0000" or similar represents the institutional grand total
        if cip == "99.0000" or cip == "99" or cip == "99.0":
            total = float(row.get("CTOTALT", 0) or 0)
            if total > 0:
                demo = OrganizationCompletionsDemographics(
                    org_id=org_id,
                    total_completions=int(total),
                    pct_men=_pct(row.get("CTOTALM", 0), total),
                    pct_women=_pct(row.get("CTOTALW", 0), total),
                    pct_white=_pct(row.get("CWHITT", 0), total),
                    pct_black=_pct(row.get("CBKAAT", 0), total),
                    pct_hispanic=_pct(row.get("CHISPT", 0), total),
                    pct_asian=_pct(row.get("CASIAT", 0), total),
                    pct_native=_pct(row.get("CAIANT", 0), total),
                    pct_pacific=_pct(row.get("CNHPIT", 0), total),
                    pct_two_or_more=_pct(row.get("C2MORT", 0), total),
                    pct_unknown=_pct(row.get("CUNKNT", 0), total),
                    pct_non_resident=_pct(row.get("CNRALT", 0), total)
                )
                session.add(demo)
            continue
            
        if (org_id, cip) not in prog_map:
            continue
            
        program_id = prog_map[(org_id, cip)]
        
        try:
            total = float(row.get("CTOTALT", 0) or 0)
            if total <= 0:
                continue

            demo = ProgramDemographics(
                program_id=program_id,
                total_completions=int(total),
                pct_men=_pct(row.get("CTOTALM", 0), total),
                pct_women=_pct(row.get("CTOTALW", 0), total),
                pct_white=_pct(row.get("CWHITT", 0), total),
                pct_black=_pct(row.get("CBKAAT", 0), total),
                pct_hispanic=_pct(row.get("CHISPT", 0), total),
                pct_asian=_pct(row.get("CASIAT", 0), total),
                pct_native=_pct(row.get("CAIANT", 0), total),
                pct_pacific=_pct(row.get("CNHPIT", 0), total),
                pct_two_or_more=_pct(row.get("C2MORT", 0), total),
                pct_unknown=_pct(row.get("CUNKNT", 0), total),
                pct_non_resident=_pct(row.get("CNRALT", 0), total)
            )
            session.add(demo)
            loaded += 1
        except Exception as e:
            print(f"Error loading program demo for Program {program_id}: {e}")
            
    print(f"  Loaded {loaded} ProgramDemographics.")
    return loaded

def main():
    parser = argparse.ArgumentParser(description="Load IPEDS Demographics data.")
    parser.add_argument("--year", default="2024", help="Year of data to load")
    args = parser.parse_args()

    from app import create_app
    app = create_app()
    with app.app_context():
        load_organization_demographics(db.session, args.year)
        load_program_demographics(db.session, args.year)
        db.session.commit()

if __name__ == "__main__":
    main()
