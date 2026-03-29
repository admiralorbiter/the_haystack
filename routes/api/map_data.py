from flask import request, jsonify
from collections import defaultdict
from . import api_v1_bp
from models import db, Organization, Program

@api_v1_bp.route("/map/providers.geojson")
def map_providers_geojson():
    cred_filter = request.args.get("cred", "").strip()
    cip_filter = request.args.get("cip", "").strip()

    # Base query for all providers with lat/lon
    q = db.session.query(Organization).filter(
        Organization.org_type == "training",
        Organization.is_active == True,
        Organization.lat.isnot(None),
        Organization.lon.isnot(None)
    )
    
    if cred_filter:
        cred_org_ids = (
            db.session.query(Program.org_id)
            .filter(Program.credential_type == cred_filter)
            .distinct()
        )
        q = q.filter(Organization.org_id.in_(cred_org_ids))
    
    if cip_filter:
        cip_org_ids = (
            db.session.query(Program.org_id)
            .filter(Program.cip.like(f"{cip_filter}.%"))
            .distinct()
        )
        q = q.filter(Organization.org_id.in_(cip_org_ids))

    providers = q.all()
    
    provider_ids = [p.org_id for p in providers]
    if not provider_ids:
        return jsonify({"type": "FeatureCollection", "features": []})

    programs = db.session.query(Program).filter(Program.org_id.in_(provider_ids)).all()
    
    org_programs = defaultdict(list)
    for prog in programs:
        org_programs[prog.org_id].append(prog)
        
    features = []
    for org in providers:
        progs = org_programs.get(org.org_id, [])
        total_completions = sum(p.completions for p in progs if p.completions is not None)
        
        cred_completions = defaultdict(int)
        for p in progs:
            if p.completions is not None:
                cred_completions[p.credential_type] += p.completions
        
        top_credential = "—"
        if cred_completions:
            top_credential = sorted(cred_completions.items(), key=lambda x: x[1], reverse=True)[0][0]
            
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [org.lon, org.lat]
            },
            "properties": {
                "org_id": org.org_id,
                "name": org.name,
                "city": org.city or "",
                "top_credential": top_credential,
                "completions": total_completions
            }
        }
        features.append(feature)
        
    return jsonify({
        "type": "FeatureCollection",
        "features": features
    })
