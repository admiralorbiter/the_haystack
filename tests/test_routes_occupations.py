import pytest
from flask import url_for

def test_occupations_directory(client, app):
    from models import Occupation, OccupationWage, db
    
    # Needs valid records to test happy path
    with app.app_context():
        occ1 = Occupation(soc="11-1021", title="General Managers", job_zone=4)
        occ1_wage = OccupationWage(soc="11-1021", area_type="msa", area_code="28140", area_name="Kansas City, MO-KS", median_wage=100000, employment_count=5000)
        db.session.add(occ1)
        db.session.add(occ1_wage)
        
        occ2 = Occupation(soc="29-1141", title="Registered Nurses", job_zone=3)
        occ2_wage = OccupationWage(soc="29-1141", area_type="msa", area_code="28140", area_name="Kansas City, MO-KS", median_wage=80000, employment_count=15000)
        db.session.add(occ2)
        db.session.add(occ2_wage)
        
        db.session.commit()

    with app.test_request_context():
        # Directory load
        resp = client.get(url_for("root.occupations_directory"))
        assert resp.status_code == 200
        assert b"General Managers" in resp.data
        assert b"Registered Nurses" in resp.data
        
        # Test zone filtering
        resp_filtered = client.get(url_for("root.occupations_directory", zone=3))
        assert resp_filtered.status_code == 200
        assert b"Registered Nurses" in resp_filtered.data
        assert b"General Managers" not in resp_filtered.data
        
        # Detail load
        resp_detail = client.get(url_for("root.occupation_detail", soc="11-1021"))
        assert resp_detail.status_code == 200
        assert b"General Managers" in resp_detail.data
        
        # Unknown Detail load -> 404
        resp_404 = client.get(url_for("root.occupation_detail", soc="99-9999"))
        assert resp_404.status_code == 404
        
        # HTMX partial loads
        resp_overview = client.get(url_for("root.occupation_tab_overview", soc="11-1021"))
        assert resp_overview.status_code == 200
        
        resp_programs = client.get(url_for("root.occupation_tab_programs", soc="11-1021"))
        assert resp_programs.status_code == 200

        resp_methods = client.get(url_for("root.occupation_tab_methods", soc="11-1021"))
        assert resp_methods.status_code == 200
