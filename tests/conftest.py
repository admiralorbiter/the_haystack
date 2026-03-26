"""
Pytest shared fixtures for The Haystack.

Usage: pytest tests/
All tests use the in-memory SQLite config (TestingConfig) so they never
touch the real haystack.db file.
"""

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
