"""
Seed script for KC MSA core geographic data.
Populates the `region` and `region_county` tables.
Idempotent execution.
"""
import sys
import os

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

# Need to import config and models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from models import Region, RegionCounty

# Standard Kansas City MSA (15 counties total between MO and KS)
# MO: 29
# KS: 20
KC_MSA_COUNTIES = [
    # Missouri (FIPS starts with 29)
    ("29013", "Bates", "MO"),
    ("29025", "Caldwell", "MO"),
    ("29037", "Cass", "MO"),
    ("29047", "Clay", "MO"),
    ("29049", "Clinton", "MO"),
    ("29095", "Jackson", "MO"),
    ("29107", "Lafayette", "MO"),
    ("29165", "Platte", "MO"),
    ("29177", "Ray", "MO"),
    # Kansas (FIPS starts with 20)
    ("20091", "Johnson", "KS"),
    ("20103", "Leavenworth", "KS"),
    ("20107", "Linn", "KS"),
    ("20121", "Miami", "KS"),
    ("20209", "Wyandotte", "KS"),
]

def seed():
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    
    with Session(engine) as session:
        # Check if region already exists
        existing_region = session.query(Region).filter_by(region_id="kc-msa").first()
        if existing_region:
            print("KC MSA Region already seeded. Skipping region insert.")
        else:
            kc_region = Region(
                region_id="kc-msa",
                name="Kansas City MSA",
                slug="kansas-city",
                default_lat=39.0997,
                default_lon=-94.5786,
                default_zoom=9
            )
            session.add(kc_region)
            print("Added Region: Kansas City MSA")

        # Insert counties if missing
        county_inserts = 0
        for fips, name, state in KC_MSA_COUNTIES:
            existing_county = session.query(RegionCounty).filter_by(
                region_id="kc-msa", county_fips=fips
            ).first()
            if not existing_county:
                session.add(RegionCounty(
                    region_id="kc-msa",
                    county_fips=fips,
                    county_name=name,
                    state=state
                ))
                county_inserts += 1

        if county_inserts > 0:
            print(f"Added {county_inserts} counties to RegionCounty layer.")
        else:
            print("All counties already seeded.")
            
        session.commit()
    print("Seeding complete.")


if __name__ == "__main__":
    seed()
