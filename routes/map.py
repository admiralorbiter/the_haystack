import json
from collections import defaultdict
from flask import render_template, request, jsonify
from sqlalchemy import func

from models import Organization, Program, Region, db
from . import root_bp
from .providers import _CIP_FAMILY_NAMES

@root_bp.route("/map")
def map_view():
    # Only pick training providers
    all_creds = (
        db.session.query(Program.credential_type)
        .filter(Program.org_id.in_(
            db.session.query(Organization.org_id).filter_by(org_type="training")
        ))
        .distinct()
        .order_by(Program.credential_type)
        .all()
    )
    
    region = db.session.query(Region).filter_by(slug="kansas-city").first()
    default_lat = region.default_lat if region and region.default_lat else 39.0997
    default_lon = region.default_lon if region and region.default_lon else -94.5786
    default_zoom = region.default_zoom if region and region.default_zoom else 10

    cred_filter = request.args.get("cred", "").strip()
    cip_filter = request.args.get("cip", "").strip()

    return render_template(
        "map/index.html",
        all_creds=[r.credential_type for r in all_creds],
        cred_filter=cred_filter,
        cip_filter=cip_filter,
        default_lat=default_lat,
        default_lon=default_lon,
        default_zoom=default_zoom,
    )

@root_bp.route("/api/map/providers.geojson")
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
