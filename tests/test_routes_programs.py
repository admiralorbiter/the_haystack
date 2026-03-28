import pytest
from app import create_app
from models import db

def test_programs_directory(client, seeded_program):
    """Test the main /programs directory renders correctly."""
    res = client.get("/programs")
    assert res.status_code == 200
    assert b"Nursing" in res.data

def test_programs_directory_pagination(client, seeded_program):
    """Test /programs pagination out of bounds doesn't crash."""
    res = client.get("/programs?page=999")
    assert res.status_code == 200

def test_programs_directory_filters(client, seeded_program):
    """Test applying filters to /programs."""
    res = client.get("/programs?org=invalid-org-id&cred=invalid&cip=99")
    assert res.status_code == 200

def test_programs_directory_search(client, seeded_program):
    """Test searching in /programs."""
    res = client.get("/programs?q=nursing")
    assert res.status_code == 200
    res2 = client.get("/programs?q=radiology")
    assert res.status_code == 200

def test_programs_directory_sorting(client, seeded_program):
    """Test sorting in /programs."""
    for sort in ["name", "provider", "field", "occupations", "invalid"]:
        res = client.get(f"/programs?sort={sort}")
        assert res.status_code == 200

def test_program_detail_valid(client, seeded_program):
    """Test a valid program detail page renders."""
    prog_id = seeded_program["program_id"]
    res = client.get(f"/programs/{prog_id}")
    assert res.status_code == 200
    assert b"Nursing" in res.data

def test_program_detail_invalid(client, seeded_program):
    """Test an invalid program returns 404."""
    res = client.get("/programs/not_a_real_id")
    assert res.status_code == 404

def test_program_tabs(client, seeded_program):
    """Test all HTMX tabs for a program."""
    prog_id = seeded_program["program_id"]
    tabs = ["overview", "occupations", "outcomes", "scorecard", "geography", "methods"]
    for tab in tabs:
        res = client.get(f"/programs/{prog_id}/tab/{tab}")
        assert res.status_code == 200

def test_program_suppression_completions(client, seeded_program):
    """Test detail and directory filtering for suppressed completions."""
    prog_id = seeded_program["suppressed_id"]
    res = client.get(f"/programs/{prog_id}")
    assert res.status_code == 200
    
    # Test comp filter
    res2 = client.get("/programs?comp=suppressed")
    assert res2.status_code == 200
    res3 = client.get("/programs?comp=low")
    assert res3.status_code == 200
    res4 = client.get("/programs?comp=high")
    assert res4.status_code == 200
