"""
Loads O*NET data into the Occupation model.

Reads:
  - data/raw/onet/db_29_0_text/Job Zones.txt

Note: We assume SOC codes in the DB match the standard NCES format (e.g. 11-1021).
O*NET uses 11-1021.00. We will strip the '.00' to match.
"""

import csv
import sys
from pathlib import Path

# Fix path to allow importing app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from models import Occupation, db

app = create_app("default")

ONET_DIR = (
    Path(__file__).resolve().parent.parent / "data" / "raw" / "onet" / "db_29_0_text"
)
JOB_ZONES_TXT = ONET_DIR / "Job Zones.txt"


def load_job_zones():
    if not JOB_ZONES_TXT.exists():
        print(f"ERROR: Not found {JOB_ZONES_TXT}")
        sys.exit(1)

    print("Loading O*NET Job Zones...")
    with app.app_context():
        # Load all existing occupations into memory dict
        occupations = {occ.soc: occ for occ in Occupation.query.all()}

        count = 0
        with open(JOB_ZONES_TXT, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                onet_soc = row.get("O*NET-SOC Code")
                if not onet_soc:
                    continue
                # Convert 11-1021.00 -> 11-1021
                soc = onet_soc.split(".")[0]

                job_zone_str = row.get("Job Zone")
                if job_zone_str and soc in occupations:
                    occ = occupations[soc]
                    jz_val = int(job_zone_str)
                    # Use max if sub-SOCs map to same base SOC
                    if occ.job_zone is None or jz_val > occ.job_zone:
                        occ.job_zone = jz_val
                        count += 1

        db.session.commit()
        print(f"✓ Updated Job Zones for {count} occupations.")


if __name__ == "__main__":
    load_job_zones()
