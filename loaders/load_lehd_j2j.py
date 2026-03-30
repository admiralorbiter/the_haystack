"""
Load Census LEHD J2J Origin-Destination (Industry Level)
Parses state-level transitions to establish Industry Talent Flows.

Usage:
    python loaders/load_lehd_j2j.py
"""

import gzip
import csv
import io
import os
import sys
import requests
from pathlib import Path

# Make project root importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session
from config import Config
from models import db, IndustryFlowJ2J
from loaders import utils

# Using the most recent reliable Census Release (update this to roll forward)
CENSUS_RELEASE = "R2024Q1"
STATES = ['mo', 'ks']
TARGET_FILE_TPL = "{state}_j2jod_st_naics_sect.csv.gz"
DOWNLOAD_URL_TPL = f"https://lehd.ces.census.gov/data/j2j/{CENSUS_RELEASE}/{{state}}/{TARGET_FILE_TPL}"

def ensure_raw_files(data_dir: Path):
    """
    Check if the CSV.gz files exist in data/raw/j2j/
    If not, download them to ensure an offline cache.
    """
    lehd_dir = data_dir / "j2j"
    lehd_dir.mkdir(parents=True, exist_ok=True)
    
    files_ready = []
    
    # Common Census J2J OD patterns (they change slightly between releases)
    url_patterns = [
        # pattern 1: [type]_[state]_[geolvl]_[indlvl]
        f"https://lehd.ces.census.gov/data/j2j/{CENSUS_RELEASE}/{{state}}/j2jod_{{state}}_st_naics_sect.csv.gz",
        # pattern 2: [state]_[type]...
        f"https://lehd.ces.census.gov/data/j2j/{CENSUS_RELEASE}/{{state}}/{{state}}_j2jod_st_naics_sect.csv.gz",
        # pattern 3: latest release symlink
        f"https://lehd.ces.census.gov/data/j2j/latest_release/{{state}}/j2jod_{{state}}_st_naics_sect.csv.gz"
    ]
    
    for state in STATES:
        fname = f"j2jod_{state}_st_naics_sect.csv.gz"
        fpath = lehd_dir / fname
        
        if not fpath.exists():
            success = False
            for url_tpl in url_patterns:
                url = url_tpl.format(state=state)
                print(f"Trying to fetch {url}...")
                try:
                    r = requests.get(url, stream=True, timeout=15)
                    r.raise_for_status()
                    
                    with open(fpath, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                    print(f"  Successfully saved {fpath.name}")
                    success = True
                    break
                except Exception:
                    continue
                    
            if not success:
                print(f"[error] Automated Census API extraction failed for {state.upper()}.")
                print(f"Please manually download the Origin-Destination Sector file for {state.upper()}")
                print(f"from the LED Extraction Tool: https://ledextract.ces.census.gov/")
                print(f"and save it exactly as: {fpath}")
                continue
                
        files_ready.append((state.upper(), fpath))
        
    return files_ready

def load_j2j_flows(session: Session):
    """
    Parse J2J OD states and insert cross-industry flows into SQLite.
    """
    # Clear existing flows
    session.execute(delete(IndustryFlowJ2J))
    session.commit()
    
    total_loaded = 0
    lehd_dir = utils.RAW_DIR / "j2j"
    
    for state in STATES:
        fname = f"j2jod_{state}_all.csv.gz"
        fpath = lehd_dir / fname
        
        if not fpath.exists():
            print(f"[error] Missing {fname} in data/raw/j2j, skipping.")
            continue
            
        print(f"Processing {fpath.name}...")
        
        temporal_flows = {} # (orig, dest) -> { (year, qtr): count }
        max_year = 0
        
        with gzip.open(fpath, 'rt', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i % 500000 == 0 and i > 0:
                    sys.stdout.write(f"\r  Scanned {i:,} rows...")
                    sys.stdout.flush()
                    
                # The _all file is massive because it contains every demographic slice.
                # We strictly filter for the aggregate total slice:
                if row.get("geo_level") != "S": continue
                if row.get("ind_level") != "S": continue
                if row.get("geo_level_orig") != "S": continue
                if row.get("ind_level_orig") != "S": continue
                if row.get("sex") != "0": continue
                if row.get("agegrp") != "A00": continue
                if row.get("race") != "A0": continue
                if row.get("ethnicity") != "A0": continue
                if row.get("education") != "E0": continue
                if row.get("firmage") != "0": continue
                if row.get("firmsize") != "0": continue
                if row.get("ownercode") != "A00": continue
                
                orig = row.get("industry_orig")
                dest = row.get("industry") # wait, J2JOD target column is usually 'industry' or 'industry_dest'
                if "industry_dest" in row:
                    dest = row.get("industry_dest")
                
                # Exclude flows within the same industry
                if not orig or not dest or orig == dest:
                    continue
                    
                year = int(row.get("year", 0))
                qtr = int(row.get("quarter", 0))
                
                ee = row.get("EE")
                aqhire = row.get("AQHire")
                try:
                    transitions = int(ee or 0) + int(aqhire or 0)
                except ValueError:
                    transitions = 0
                
                if transitions == 0:
                    continue
                
                if year > max_year:
                    max_year = year
                    
                pair = (orig, dest)
                if pair not in temporal_flows:
                    temporal_flows[pair] = {}
                temporal_flows[pair][(year, qtr)] = transitions
                
            sys.stdout.write(f"\r  Finished scanning {i:,} rows.        \n")
            sys.stdout.flush()
        
        # Now collect the most recent 4 quarters available for each pair
        records = []
        for (orig, dest), timeseries in temporal_flows.items():
            sorted_times = sorted(timeseries.keys(), reverse=True)
            recent_transitions = sum([timeseries[k] for k in sorted_times[:4]])
            
            if recent_transitions > 0:
                records.append(IndustryFlowJ2J(
                    state=state.upper(),
                    origin_naics=orig,
                    destination_naics=dest,
                    transitions=recent_transitions
                ))
                
        if records:
            session.add_all(records)
            session.commit()
            total_loaded += len(records)
            print(f"  Loaded {len(records)} aggregated flow combinations for {state.upper()}")

    print(f"Successfully loaded {total_loaded} J2J Flow rows.")
    utils.record_dataset_source(
        session=session,
        source_id="c3_lehd_j2j",
        name="Census LEHD Job-to-Job (J2J) Origin-Destination",
        version=CENSUS_RELEASE,
        url="https://lehd.ces.census.gov/data/j2j/",
        record_count=total_loaded,
        notes="Aggregated trailing 4 quarters of cross-state NAICS transitions from _all archive."
    )
    session.commit()

def main():
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    with Session(engine) as session:
        load_j2j_flows(session)

if __name__ == "__main__":
    main()
