"""
Tests for Epic 8 search routes
"""
from unittest.mock import patch

@patch("routes.search._fts_org_ids", return_value=[])
@patch("routes.search._fts_program_ids", return_value=[])
def test_search_empty(mock_p, mock_o, client):
    """Empty search should return gracefully without errors."""
    resp = client.get("/search?q=")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Enter a query" in html

@patch("routes.search._fts_org_ids", return_value=[])
@patch("routes.search._fts_program_ids", return_value=[])
def test_search_no_results(mock_p, mock_o, client):
    """Search with no matches."""
    resp = client.get("/search?q=gobbldygook999")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "No results for" in html

@patch("routes.search._fts_org_ids", return_value=[])
@patch("routes.search._fts_program_ids", return_value=[])
def test_search_match_org(mock_p, mock_o, client, seeded_program):
    """Test matching an organization by name."""
    resp = client.get("/search?q=Test Community")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Test Community College" in html

@patch("routes.search._fts_org_ids", return_value=[])
@patch("routes.search._fts_program_ids", return_value=[])
def test_search_match_program(mock_p, mock_o, client, seeded_program):
    """Test matching a program by name."""
    resp = client.get("/search?q=Nursing")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Nursing" in html
    assert "Associate&#39;s degree" in html or "Associate's degree" in html

@patch("routes.search._fts_org_ids", return_value=[])
@patch("routes.search._fts_program_ids", return_value=[])
def test_search_match_field(mock_p, mock_o, client):
    """Test matching a field of study from static dictionary."""
    resp = client.get("/search?q=Health")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Health Professions" in html

@patch("routes.search._fts_org_ids", return_value=[])
@patch("routes.search._fts_program_ids", return_value=[])
def test_search_sql_injection_safe(mock_p, mock_o, client, seeded_program):
    """Ensure FTS MATCH syntax injection is caught and safe."""
    resp = client.get('/search?q=Nurs" AND')
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "500 Internal Server Error" not in html


@patch("routes.search.sqlite3.connect")
def test_search_fts_sqlite_operational_error(mock_connect, client):
    """Test that sqlite3.OperationalError is caught inside FTS helpers."""
    import sqlite3
    mock_connect.side_effect = sqlite3.OperationalError("no such table: organization_fts")
    
    # We call the functions directly to ensure exception block is covered
    from routes.search import _fts_org_ids, _fts_program_ids
    assert _fts_org_ids("nursing") == []
    assert _fts_program_ids("nursing") == []


@patch("routes.search.sqlite3.connect")
def test_search_fts_success(mock_connect, client):
    """Test FTS helpers returning row data."""
    mock_cursor = mock_connect.return_value.cursor.return_value
    mock_cursor.execute.return_value.fetchall.return_value = [("uuid-123",), ("uuid-456",)]
    
    from routes.search import _fts_org_ids, _fts_program_ids
    assert _fts_org_ids("nursing") == ["uuid-123", "uuid-456"]
    assert _fts_program_ids("nursing") == ["uuid-123", "uuid-456"]

def test_search_fts_empty_query():
    from routes.search import _fts_org_ids, _fts_program_ids
    assert _fts_org_ids("") == []
    assert _fts_program_ids("   ") == []

