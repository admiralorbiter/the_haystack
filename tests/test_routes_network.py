from config import TestingConfig
from models import Organization, Program, ProgramOccupation, db


def test_network_page_200(client):
    """GET /network returns 200."""
    res = client.get("/network")
    assert res.status_code == 200
    assert b"Network Explorer" in res.data


def test_network_page_has_canvas(client):
    """GET /network has the cytoscape div."""
    res = client.get("/network")
    assert b'id="cy"' in res.data


def test_api_network_empty_db(client):
    """Empty DB should not crash."""
    res = client.get("/api/v1/network/providers")
    assert res.status_code == 200
    data = res.get_json()
    assert data["nodes"] == []
    assert data["edges"] == []


def test_api_network_json_shape(client, app):
    """With data, returns properly shaped nodes and edges."""
    with app.app_context():
        # Setup two providers that share a CIP and SOC to trigger an edge
        org1 = Organization(org_id="json_o1", name="Org 1 JSON", org_type="training", city="KC", is_active=True)
        org2 = Organization(org_id="json_o2", name="Org 2 JSON", org_type="training", city="KC", is_active=True)
        db.session.add_all([org1, org2])
        
        # Share CIP 51
        p11 = Program(program_id="json_p11", org_id="json_o1", name="P1", credential_type="cert", cip="51.1001", completions=10)
        p12 = Program(program_id="json_p12", org_id="json_o1", name="P12", credential_type="cert", cip="52.0101", completions=10)
        p21 = Program(program_id="json_p21", org_id="json_o2", name="P2", credential_type="cert", cip="51.1001", completions=10)
        p22 = Program(program_id="json_p22", org_id="json_o2", name="P22", credential_type="cert", cip="52.0101", completions=10)
        db.session.add_all([p11, p12, p21, p22])
        
        # Share SOC 29-1141
        db.session.add(ProgramOccupation(program_id="json_p11", soc="29-1141.00"))
        db.session.add(ProgramOccupation(program_id="json_p12", soc="11-1011.00"))
        db.session.add(ProgramOccupation(program_id="json_p21", soc="29-1141.00"))
        db.session.add(ProgramOccupation(program_id="json_p22", soc="11-1011.00"))
        
        db.session.commit()

    # Test 'both' mode
    res = client.get("/api/v1/network/providers")
    assert res.status_code == 200
    data = res.get_json()
    
    # Check nodes
    nodes = data["nodes"]
    assert len(nodes) == 2
    n0 = nodes[0]["data"]
    assert "id" in n0
    assert "label" in n0
    assert "completions" in n0
    assert n0["cip_family"] in ("51", "52")
    
    # Check edges
    edges = data["edges"]
    assert len(edges) == 1
    e0 = edges[0]["data"]
    assert "source" in e0
    assert "target" in e0
    assert "weight" in e0
    assert e0["edge_type"] == "both"
    
    with app.app_context():
        db.session.query(ProgramOccupation).filter(ProgramOccupation.program_id.startswith("json_p")).delete()
        db.session.query(Program).filter(Program.org_id.in_(["json_o1", "json_o2"])).delete()
        db.session.query(Organization).filter(Organization.org_id.in_(["json_o1", "json_o2"])).delete()
        db.session.commit()


def test_api_network_edge_mode_cip(client, app):
    """Edge=cip should only return cip type."""
    with app.app_context():
        # Setup two providers that share a CIP and SOC
        org1 = Organization(org_id="cip_o1", name="Org 1 CIP", org_type="training", is_active=True)
        org2 = Organization(org_id="cip_o2", name="Org 2 CIP", org_type="training", is_active=True)
        p11 = Program(program_id="cip_p11", org_id="cip_o1", name="P1", credential_type="c", cip="51.1001")
        p12 = Program(program_id="cip_p12", org_id="cip_o1", name="P2", credential_type="c", cip="52.0101")
        p21 = Program(program_id="cip_p21", org_id="cip_o2", name="P3", credential_type="c", cip="51.1001")
        p22 = Program(program_id="cip_p22", org_id="cip_o2", name="P4", credential_type="c", cip="52.0101")
        db.session.add_all([org1, org2, p11, p12, p21, p22])
        db.session.add(ProgramOccupation(program_id="cip_p11", soc="29-1141.00"))
        db.session.add(ProgramOccupation(program_id="cip_p12", soc="11-1011.00"))
        db.session.add(ProgramOccupation(program_id="cip_p21", soc="29-1141.00"))
        db.session.add(ProgramOccupation(program_id="cip_p22", soc="11-1011.00"))
        db.session.commit()

    res = client.get("/api/v1/network/providers?edge=cip")
    data = res.get_json()
    
    edges = data["edges"]
    assert len(edges) == 1
    assert edges[0]["data"]["edge_type"] == "cip"
    
    with app.app_context():
        db.session.query(ProgramOccupation).filter(ProgramOccupation.program_id.startswith("cip_p")).delete()
        db.session.query(Program).filter(Program.org_id.in_(["cip_o1", "cip_o2"])).delete()
        db.session.query(Organization).filter(Organization.org_id.in_(["cip_o1", "cip_o2"])).delete()
        db.session.commit()


def test_api_network_edge_mode_soc(client, app):
    """Edge=soc should only return soc type."""
    with app.app_context():
        # Setup two providers that share a CIP and SOC
        org1 = Organization(org_id="soc_o1", name="Org 1 SOC", org_type="training", is_active=True)
        org2 = Organization(org_id="soc_o2", name="Org 2 SOC", org_type="training", is_active=True)
        p11 = Program(program_id="soc_p11", org_id="soc_o1", name="P1", credential_type="c", cip="51.1001")
        p12 = Program(program_id="soc_p12", org_id="soc_o1", name="P2", credential_type="c", cip="52.0101")
        p21 = Program(program_id="soc_p21", org_id="soc_o2", name="P3", credential_type="c", cip="51.1001")
        p22 = Program(program_id="soc_p22", org_id="soc_o2", name="P4", credential_type="c", cip="52.0101")
        db.session.add_all([org1, org2, p11, p12, p21, p22])
        db.session.add(ProgramOccupation(program_id="soc_p11", soc="29-1141.00"))
        db.session.add(ProgramOccupation(program_id="soc_p12", soc="11-1011.00"))
        db.session.add(ProgramOccupation(program_id="soc_p21", soc="29-1141.00"))
        db.session.add(ProgramOccupation(program_id="soc_p22", soc="11-1011.00"))
        db.session.commit()

    res = client.get("/api/v1/network/providers?edge=soc")
    data = res.get_json()
    
    edges = data["edges"]
    assert len(edges) == 1
    assert edges[0]["data"]["edge_type"] == "soc"
    
    with app.app_context():
        db.session.query(ProgramOccupation).filter(ProgramOccupation.program_id.startswith("soc_p")).delete()
        db.session.query(Program).filter(Program.org_id.in_(["soc_o1", "soc_o2"])).delete()
        db.session.query(Organization).filter(Organization.org_id.in_(["soc_o1", "soc_o2"])).delete()
        db.session.commit()


def test_api_network_limit(client, app):
    """Limit parameter caps nodes."""
    with app.app_context():
        for i in range(5):
            org = Organization(org_id=f"lim_o{i}", name=f"Org {i} Lim", org_type="training", is_active=True)
            db.session.add(org)
            # Give descending completions so they are ordered reliably
            p = Program(program_id=f"lim_p{i}", org_id=f"lim_o{i}", name=f"p{i}", credential_type="c", cip="01.0000", completions=100-i)
            db.session.add(p)
        db.session.commit()

    res = client.get("/api/v1/network/providers?limit=3")
    data = res.get_json()
    
    assert len(data["nodes"]) == 3
    
    with app.app_context():
        db.session.query(Program).filter(Program.program_id.startswith("lim_p")).delete()
        db.session.query(Organization).filter(Organization.org_id.startswith("lim_o")).delete()
        db.session.commit()
