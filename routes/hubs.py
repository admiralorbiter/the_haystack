"""
Hubs/Collections Route Handler

Powers curated portals across the site (e.g. Apprenticeships).
Built to handle scaling logic without adding one-off templates per dataset.
"""

from flask import render_template, abort
from sqlalchemy import func
from . import root_bp
from models import db, Organization, Program
from routes.cip_utils import cip_title

def _get_apprenticeship_orgs():
    return db.session.query(Organization).filter(
        Organization.is_apprenticeship_partner == True
    ).order_by(Organization.name).all()

def _get_apprenticeship_progs():
    rows = (
        db.session.query(Program, Organization.name.label("org_name"), Organization.org_id.label("_org_id"))
        .join(Organization, Program.org_id == Organization.org_id)
        .filter(Program.is_apprenticeship == True)
        .order_by(Program.name)
        .all()
    )
    # Format to a standard dict shape
    return [
        {
            "program_id": r.Program.program_id,
            "name": r.Program.name,
            "cip_title": cip_title(r.Program.cip),
            "cred": r.Program.credential_type,
            "org_name": r.org_name,
            "org_id": r._org_id
        }
        for r in rows
    ]

HUBS_CONFIG = {
    "apprenticeships": {
        "title": "Apprenticeships & WBL",
        "badge": "KC REGION",
        "icon": "📇",
        "description": "Explore registered apprenticeship sponsors and technical training pathways operating across the Kansas City region.",
        "tabs": [
            {
                "id": "sponsors",
                "label": "Regional Sponsors",
                "icon": "🏢",
                "count": 0,
                "data_func": _get_apprenticeship_orgs
            },
            {
                "id": "training",
                "label": "Training Programs",
                "icon": "🎓",
                "count": 0,
                "data_func": _get_apprenticeship_progs
            }
        ]
    }
}

@root_bp.route("/hubs/")
def hubs_index():
    return render_template("hubs/index.html", hubs=HUBS_CONFIG)

@root_bp.route("/hubs/<slug>")
def hub_detail(slug):
    if slug not in HUBS_CONFIG:
        abort(404)
        
    hub = HUBS_CONFIG[slug]
    
    # Execute the queries and populate data payloads
    # Overwriting a copy of the config for request safety
    rendered_tabs = []
    
    for tab in hub["tabs"]:
        data = tab["data_func"]()
        rendered_tabs.append({
            "id": tab["id"],
            "label": tab["label"],
            "icon": tab["icon"],
            "count": len(data),
            "data": data
        })
        
    return render_template(
        "hubs/detail.html",
        slug=slug,
        hub=hub,
        tabs=rendered_tabs
    )
