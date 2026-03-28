import pytest
from flask import url_for
from models import db, Organization, Program, Occupation

def test_guided_search_root_renders_wrapper(client):
    """Test the base GET /search/guided route."""
    response = client.get(url_for("root.guided_search"))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "What outcome do you need?" in html
    assert "hx-get" in html
    assert "guided-step-2" in html


def test_guided_search_step2_outcomes(client):
    """Test that all 4 valid outcomes return a proper Step 2 HTMX fragment."""
    valid_outcomes = {
        "training": "What job are you aiming for?",
        "field": "What field of study?",
        "jobs": "Which program?",
        "roi": "What type of credential?"
    }
    
    for outcome, expected_text in valid_outcomes.items():
        response = client.get(url_for("root.guided_search_step2", outcome=outcome))
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert expected_text in html

    # Invalid outcome returns 400 empty state
    response = client.get(url_for("root.guided_search_step2", outcome="hax0r"))
    assert response.status_code == 400
    assert "Please select a goal" in response.get_data(as_text=True)


def test_api_search_occupations(app, client):
    """Test occupation typeahead API."""
    with app.app_context():
        occ1 = Occupation(soc="11-1000", title="Chief Executives")
        occ2 = Occupation(soc="29-1000", title="Registered Nurses")
        db.session.add_all([occ1, occ2])
        db.session.commit()

    # Query exactly matches
    resp = client.get(url_for("root.api_search_occupations", q="nurse"))
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Registered Nurses" in html
    assert "29-1000" in html
    assert "Chief Executives" not in html

    # Empty/short query returns nothing
    resp = client.get(url_for("root.api_search_occupations", q="n"))
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == ""


def test_api_search_programs(app, client):
    """Test program typeahead API."""
    with app.app_context():
        org = Organization(org_id="org-guided-1", unitid="112233", name="Guided College", org_type="training")
        p1 = Program(program_id="p-guided-1", org_id="org-guided-1", name="Welding Tech", cip="48.0508", credential_type="Certificate")
        p2 = Program(program_id="p-guided-2", org_id="org-guided-1", name="Nursing BSN", cip="51.3801", credential_type="Bachelor's")
        db.session.add_all([org, p1, p2])
        db.session.commit()

    resp = client.get(url_for("root.api_search_programs", q="Weld"))
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Welding Tech" in html
    assert "Guided College" in html
    assert "Nursing BSN" not in html


def test_guided_search_resolve(client):
    """Test resolution redirects correctly based on outcome parameter."""
    
    # 1. Training (SOC provided)
    resp = client.get(url_for("root.guided_search_resolve", outcome="training", soc="29-1141"))
    assert resp.status_code == 302
    assert "/programs" in resp.headers["Location"]
    assert "soc=29-1141" in resp.headers["Location"]
    
    # 2. Field (CIP provided)
    resp = client.get(url_for("root.guided_search_resolve", outcome="field", cip_family="51"))
    assert resp.status_code == 302
    assert "/fields/51" in resp.headers["Location"]
    
    # 3. Jobs (Program ID provided)
    resp = client.get(url_for("root.guided_search_resolve", outcome="jobs", program_id="p-123"))
    assert resp.status_code == 302
    assert "/programs/p-123" in resp.headers["Location"]
    assert "#tab_occupations" in resp.headers["Location"]
    
    # 4. ROI (Cred provided)
    resp = client.get(url_for("root.guided_search_resolve", outcome="roi", cred_filter="Certificate (<1 year)"))
    assert resp.status_code == 302
    assert "/programs" in resp.headers["Location"]
    assert "cred=Certificate+(%3C1+year)" in resp.headers["Location"]

    # Invalid / Missing data
    resp = client.get(url_for("root.guided_search_resolve", outcome="training")) # missing soc
    assert resp.status_code == 302
    assert "Location" in resp.headers
    assert resp.headers["Location"].endswith("/search/guided")
