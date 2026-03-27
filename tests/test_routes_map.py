import pytest

from models import db, Organization

def test_map_page(client, seeded_program):
    """Test map HTML renders correctly."""
    resp = client.get("/map")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Provider Map" in html
    assert "Associate&#39;s degree" in html or "Associate's degree" in html

def test_map_api_no_filters(client, seeded_program, seeded_second_org):
    """Test map API returns all providers with coordinates."""
    resp = client.get("/api/map/providers.geojson")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) >= 2  # seeded_program and seeded_second_org

    # Verify first feature matching seeded_program
    f1 = next(f for f in data["features"] if f["properties"]["org_id"] == seeded_program["org_id"])
    assert f1["geometry"]["coordinates"] == [-94.5786, 39.0997]
    assert f1["properties"]["name"] == "Test Community College"
    assert f1["properties"]["top_credential"] == "Associate's degree"  # 42 vs None
    assert f1["properties"]["completions"] == 42 # 42 + None

def test_map_api_credential_filter(client, seeded_program, seeded_second_org):
    """Test filtering by credential_type."""
    # Should match only the second org (Bachelor's degree)
    resp = client.get("/api/map/providers.geojson?cred=Bachelor's+degree")
    data = resp.get_json()
    assert len(data["features"]) == 1
    assert data["features"][0]["properties"]["org_id"] == seeded_second_org["org_id"]

def test_map_api_cip_filter(client, seeded_program, seeded_second_org):
    """Test filtering by cip_family."""
    # Should match only the first org (51.xxxx)
    resp = client.get("/api/map/providers.geojson?cip=51")
    data = resp.get_json()
    assert len(data["features"]) == 1
    assert data["features"][0]["properties"]["org_id"] == seeded_program["org_id"]

def test_map_api_empty_results(client, seeded_program):
    """Test valid filter that yields no results -> returns valid empty FeatureCollection."""
    resp = client.get("/api/map/providers.geojson?cip=99")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 0

def test_map_api_skips_missing_coords(app, client, seeded_program):
    """Test providers lacking geographic coordinates are not included in the payload."""
    with app.app_context():
        # Create org without lat/lon
        org = Organization(org_id="no-loc", name="Hidden College", org_type="training", lat=None, lon=None)
        db.session.add(org)
        db.session.commit()
        
    resp = client.get("/api/map/providers.geojson")
    data = resp.get_json()
    
    # "Hidden College" should not be in features
    assert not any(f["properties"]["org_id"] == "no-loc" for f in data["features"])
