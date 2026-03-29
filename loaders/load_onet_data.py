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
    OccupationAlias,
    OccupationSkill,
    OccupationEducation,
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
ALTERNATE_TITLES_TXT = ONET_DIR / "Alternate Titles.txt"
SKILLS_TXT = ONET_DIR / "Skills.txt"
EDUCATION_TXT = ONET_DIR / "Education, Training, and Experience.txt"

EDUCATION_LEVELS = {
    1: "Less than a High School Diploma",
    2: "High School Diploma (or equivalent)",
    3: "Post-Secondary Certificate",
    4: "Some College Courses",
    5: "Associate's Degree",
    6: "Bachelor's Degree",
    7: "Post-Baccalaureate Certificate",
    8: "Master's Degree",
    9: "Post-Master's Certificate",
    10: "First Professional Degree",
    11: "Doctoral Degree",
    12: "Post-Doctoral Training"
}


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
        ALTERNATE_TITLES_TXT,
        SKILLS_TXT,
        EDUCATION_TXT,
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
        print("Clearing old relational tables...")
        db.session.query(OccupationTask).delete()
        db.session.query(OccupationTechSkill).delete()
        db.session.query(RelatedOccupation).delete()
        db.session.query(OccupationAlias).delete()
        db.session.query(OccupationSkill).delete()
        db.session.query(OccupationEducation).delete()
        
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

        # 6. Alternate Titles
        alias_count = 0
        with open(ALTERNATE_TITLES_TXT, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                soc = _clean_soc(row.get("O*NET-SOC Code", ""))
                alias_title = row.get("Alternate Title")
                short_title = row.get("Short Title")
                
                if not alias_title or soc not in occupations:
                    continue
                    
                db.session.add(OccupationAlias(
                    soc=soc,
                    alias_title=alias_title,
                    short_title=short_title if short_title != "n/a" else None
                ))
                alias_count += 1
        print(f"✓ Inserted {alias_count} alternate titles.")

        # 7. Core Skills
        # First read all skills and sort by importance, then take top 5
        skill_count = 0
        skills_raw_data = {}
        with open(SKILLS_TXT, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                soc = _clean_soc(row.get("O*NET-SOC Code", ""))
                scale_id = row.get("Scale ID")
                element_name = row.get("Element Name")
                
                if scale_id != "IM" or soc not in occupations:
                    continue
                
                try:
                    score = float(row.get("Data Value", 0))
                except ValueError:
                    score = 0.0
                
                if soc not in skills_raw_data:
                    skills_raw_data[soc] = []
                skills_raw_data[soc].append((element_name, score))

        for soc, soc_skills in skills_raw_data.items():
            # Sort by importance_score descending, take top 5
            top_skills = sorted(soc_skills, key=lambda x: x[1], reverse=True)[:5]
            for element_name, score in top_skills:
                db.session.add(OccupationSkill(
                    soc=soc,
                    element_name=element_name,
                    importance_score=score
                ))
                skill_count += 1
        print(f"✓ Inserted {skill_count} top core skills.")

        # 8. Education & Training Requirements
        ed_count = 0
        with open(EDUCATION_TXT, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                soc = _clean_soc(row.get("O*NET-SOC Code", ""))
                element_name = row.get("Element Name")
                scale_id = row.get("Scale ID")
                cat = row.get("Category")
                
                if element_name != "Required Level of Education" or scale_id != "RL" or soc not in occupations:
                    continue
                
                try:
                    pct = float(row.get("Data Value", 0))
                    cat_code = int(cat)
                except ValueError:
                    continue
                
                db.session.add(OccupationEducation(
                    soc=soc,
                    ed_level_code=cat_code,
                    ed_level_label=EDUCATION_LEVELS.get(cat_code, "Unknown"),
                    pct_workers=pct
                ))
                ed_count += 1
        print(f"✓ Inserted {ed_count} education requirement rows.")

        db.session.commit()
        print("✓ O*NET ingestion complete.")


if __name__ == "__main__":
    load_onet_data()
