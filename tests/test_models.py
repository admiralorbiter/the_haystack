"""
Model tests — tests/test_models.py

Validates SQLAlchemy schema definitions, relationships, and constraints
using the in-memory SQLite database (TestingConfig).
"""

from models import Organization, Program, OrgAlias, Region, RegionCounty, db

def test_organization_creates_with_uuid(app):
    """
    Organization `org_id` should generate a valid UUID string
    automatically on insertion.
    """
    with app.app_context():
        org = Organization(
            name="Test Org",
            org_type="training",
            city="Kansas City",
            state="MO",
            county_fips="29095"
        )
        db.session.add(org)
        db.session.commit()
        
        assert org.org_id is not None
        assert isinstance(org.org_id, str)
        assert len(org.org_id) == 36  # UUID length

def test_program_organization_relationship(app):
    """
    Programs should link to their parent Organization via
    foreign key and the `programs` relationship list.
    """
    with app.app_context():
        # Setup parent
        org = Organization(name="Parent Org", org_type="employer")
        db.session.add(org)
        db.session.flush() # Get the org_id without committing

        # Create child program linked to parent
        prog = Program(
            org_id=org.org_id,
            name="Coding Bootcamp",
            credential_type="Certificate",
            cip="11.0101"
        )
        db.session.add(prog)
        db.session.commit()

        # Validate relationship loaded correctly
        assert len(org.programs) == 1
        assert org.programs[0].name == "Coding Bootcamp"
        assert prog.organization.name == "Parent Org"

def test_org_alias_deduplication_anchor(app):
    """
    The deduplication anchor (OrgAlias) should point many source records
    to a single canonical Organization.
    """
    with app.app_context():
        org = Organization(name="Canonical University", org_type="training")
        db.session.add(org)
        db.session.flush()

        alias1 = OrgAlias(
            org_id=org.org_id,
            source="ipeds",
            source_id="12345",
            source_name="Canonical U"
        )
        alias2 = OrgAlias(
            org_id=org.org_id,
            source="scorecard",
            source_id="99999",
            source_name="Can. Univ."
        )
        
        db.session.add_all([alias1, alias2])
        db.session.commit()

        # Retrieve testing the backref or just query
        aliases = db.session.query(OrgAlias).filter_by(org_id=org.org_id).all()
        assert len(aliases) == 2
        assert {a.source for a in aliases} == {"ipeds", "scorecard"}

def test_region_county(app):
    """
    Region definitions (KC MSA) should hold multiple counties
    """
    with app.app_context():
        kc = Region(region_id="test-msa", name="Test MSA", slug="test-msa")
        county1 = RegionCounty(region_id="test-msa", county_fips="11111", county_name="County A", state="MO")
        county2 = RegionCounty(region_id="test-msa", county_fips="22222", county_name="County B", state="KS")
        
        db.session.add_all([kc, county1, county2])
        db.session.commit()
        
        counties = db.session.query(RegionCounty).filter_by(region_id="test-msa").all()
        assert len(counties) == 2
