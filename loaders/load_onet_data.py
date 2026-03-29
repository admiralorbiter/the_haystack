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
from models import (
    Occupation,
    OccupationTask,
    OccupationTechSkill,
    RelatedOccupation,
    db,
)

app = create_app("default")

ONET_DIR = (
    Path(__file__).resolve().parent.parent / "data" / "raw" / "onet" / "db_29_0_text"
)
JOB_ZONES_TXT = ONET_DIR / "Job Zones.txt"
OCCUPATION_DATA_TXT = ONET_DIR / "Occupation Data.txt"
TASK_STATEMENTS_TXT = ONET_DIR / "Task Statements.txt"
TECH_SKILLS_TXT = ONET_DIR / "Technology Skills.txt"
RELATED_OCCS_TXT = ONET_DIR / "Related Occupations.txt"


def _clean_soc(onet_soc: str) -> str:
    if not onet_soc:
        return ""
    return onet_soc.split(".")[0]


def load_onet_data():
    files = [
        JOB_ZONES_TXT,
        OCCUPATION_DATA_TXT,
        TASK_STATEMENTS_TXT,
        TECH_SKILLS_TXT,
        RELATED_OCCS_TXT,
    ]
    for f in files:
        if not f.exists():
            print(f"ERROR: Not found {f}")
            sys.exit(1)

    print("Loading O*NET data...")
    with app.app_context():
        # Load all existing occupations into memory dict
        occupations = {occ.soc: occ for occ in Occupation.query.all()}
        
        # 1. Job Zones
        jz_count = 0
        with open(JOB_ZONES_TXT, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                soc = _clean_soc(row.get("O*NET-SOC Code", ""))
                job_zone_str = row.get("Job Zone")
                if job_zone_str and soc in occupations:
                    occ = occupations[soc]
                    jz_val = int(job_zone_str)
                    if occ.job_zone is None or jz_val > occ.job_zone:
                        occ.job_zone = jz_val
                        jz_count += 1
        print(f"✓ Updated Job Zones for {jz_count} occupations.")

        # 2. Descriptions
        desc_count = 0
        with open(OCCUPATION_DATA_TXT, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                soc = _clean_soc(row.get("O*NET-SOC Code", ""))
                desc = row.get("Description")
                if desc and soc in occupations:
                    occ = occupations[soc]
                    # Don't overwrite if it already has one, or do overwrite to keep fresh?
                    # Since we are mapping multiple O*NET SOCs to one base SOC, keep the first one.
                    if not occ.description:
                        occ.description = desc
                        desc_count += 1
        print(f"✓ Updated Descriptions for {desc_count} occupations.")

        # Wipe old relational tables to keep idempotent
        print("Clearing old tasks, tech skills, and related occupations...")
        db.session.query(OccupationTask).delete()
        db.session.query(OccupationTechSkill).delete()
        db.session.query(RelatedOccupation).delete()
        
        # 3. Task Statements
        task_count = 0
        # We want top 5 core tasks per SOC
        tasks_per_soc = {}
        with open(TASK_STATEMENTS_TXT, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                soc = _clean_soc(row.get("O*NET-SOC Code", ""))
                task = row.get("Task")
                task_type = row.get("Task Type")
                
                if not task or task_type != "Core" or soc not in occupations:
                    continue
                    
                if soc not in tasks_per_soc:
                    tasks_per_soc[soc] = []
                    
                if len(tasks_per_soc[soc]) < 5:
                    tasks_per_soc[soc].append(task)
                    db.session.add(OccupationTask(
                        soc=soc,
                        task_statement=task,
                        task_type=task_type
                    ))
                    task_count += 1
        print(f"✓ Inserted {task_count} core tasks.")

        # 4. Tech Skills
        tech_count = 0
        skills_per_soc = {}
        with open(TECH_SKILLS_TXT, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                soc = _clean_soc(row.get("O*NET-SOC Code", ""))
                example = row.get("Example")
                hot = row.get("Hot Technology") == "Y"
                
                if not example or soc not in occupations:
                    continue
                    
                if soc not in skills_per_soc:
                    skills_per_soc[soc] = []
                    
                # Store up to 6 skills
                if len(skills_per_soc[soc]) < 6:
                    skills_per_soc[soc].append(example)
                    db.session.add(OccupationTechSkill(
                        soc=soc,
                        example=example,
                        hot_technology=hot
                    ))
                    tech_count += 1
        print(f"✓ Inserted {tech_count} tech skills.")

        # 5. Related Occupations
        related_count = 0
        rel_per_soc = {}
        with open(RELATED_OCCS_TXT, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                soc = _clean_soc(row.get("O*NET-SOC Code", ""))
                related_soc = _clean_soc(row.get("Related O*NET-SOC Code", ""))
                tier = row.get("Relatedness Tier")
                
                # We only want those relating to existing SOCs
                if soc not in occupations or related_soc not in occupations or soc == related_soc:
                    continue
                    
                if soc not in rel_per_soc:
                    rel_per_soc[soc] = set()
                
                # Dedup since multiple O*NET socs map to the same base soc
                if related_soc not in rel_per_soc[soc] and len(rel_per_soc[soc]) < 5:
                    try:
                        index_val = float(row.get("Index", 0))
                    except ValueError:
                        index_val = 0.0
                        
                    rel_per_soc[soc].add(related_soc)
                    db.session.add(RelatedOccupation(
                        soc=soc,
                        related_soc=related_soc,
                        relatedness_tier=tier,
                        index_score=index_val
                    ))
                    related_count += 1
        print(f"✓ Inserted {related_count} related occupations.")

        db.session.commit()
        print("✓ O*NET ingestion complete.")


if __name__ == "__main__":
    load_onet_data()
