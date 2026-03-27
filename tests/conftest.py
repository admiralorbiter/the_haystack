"""
Pytest shared fixtures for The Haystack.

Usage: pytest tests/
All tests use the in-memory SQLite config (TestingConfig) so they never
touch the real haystack.db file.
"""

import uuid
import pytest
from app import create_app


@pytest.fixture(scope="session")
def app():
    """Create a Flask app instance configured for testing."""
    app = create_app("testing")
    
    with app.app_context():
        from models import db
        db.create_all()
        
    yield app


@pytest.fixture(scope="session")
def client(app):
    """A test client for the Flask app."""
    return app.test_client()


@pytest.fixture(scope="session")
def runner(app):
    """A test CLI runner for the Flask app."""
    return app.test_cli_runner()


@pytest.fixture(scope="session")
def seeded_program(app):
    """
    Seeds one training organization + two programs into the in-memory test DB.
    Returns a dict with org_id, program_id (with completions), suppressed_id.
    Runs once per session.
    """
    from models import db, Organization, Program

    with app.app_context():
        org_id = str(uuid.uuid4())
        prog_id = str(uuid.uuid4())
        suppressed_id = str(uuid.uuid4())

        org = Organization(
            org_id=org_id,
            name="Test Community College",
            org_type="training",
            city="Kansas City",
            state="MO",
            county_fips="29095",
            lat=39.0997,
            lon=-94.5786,
        )
        prog = Program(
            program_id=prog_id,
            org_id=org_id,
            name="Nursing — Associate Degree",
            credential_type="Associate's degree",
            cip="51.3801",
            completions=42,
        )
        suppressed = Program(
            program_id=suppressed_id,
            org_id=org_id,
            name="Radiology Tech — Certificate",
            credential_type="Certificate (sub-baccalaureate, < 1 year)",
            cip="51.0911",
            completions=None,  # suppressed
        )

        db.session.add_all([org, prog, suppressed])
        db.session.commit()

    return {
        "org_id": org_id,
        "program_id": prog_id,
        "suppressed_id": suppressed_id,
    }

