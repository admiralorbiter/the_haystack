"""
Hubs/Collections Route Handler

Powers curated portals across the site (e.g. Apprenticeships).
Built to handle scaling logic without adding one-off templates per dataset.
"""

from flask import abort, render_template
from sqlalchemy import func

from models import Organization, Program, Occupation, OccupationWage, ProgramOccupation, db
from routes.cip_utils import cip_title

from . import root_bp


def _get_apprenticeship_orgs():
    return (
        db.session.query(Organization)
        .filter(
            Organization.is_apprenticeship_partner == True,
            Organization.is_active == True,
        )
        .order_by(Organization.name)
        .all()
    )


def _get_apprenticeship_progs():
    rows = (
        db.session.query(
            Program,
            Organization.name.label("org_name"),
            Organization.org_id.label("_org_id"),
        )
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
            "org_id": r._org_id,
            "completions": r.Program.completions,
        }
        for r in rows
    ]


def _get_high_roi_progs():
    rows = (
        db.session.query(
            Program,
            Organization.name.label("org_name"),
            Organization.org_id.label("_org_id"),
        )
        .join(Organization, Program.org_id == Organization.org_id)
        .join(ProgramOccupation, ProgramOccupation.program_id == Program.program_id)
        .join(Occupation, Occupation.soc == ProgramOccupation.soc)
        .join(OccupationWage, OccupationWage.soc == Occupation.soc)
        .filter(
            Occupation.job_zone <= 3,
            OccupationWage.area_type == "msa",
            OccupationWage.area_name.like("%Kansas City%"),
            OccupationWage.median_wage >= 55000,
            Organization.org_type == "training"
        )
        .distinct()
        .order_by(Program.name)
        .all()
    )
    return [
        {
            "program_id": r.Program.program_id,
            "name": r.Program.name,
            "cip_title": cip_title(r.Program.cip),
            "cred": r.Program.credential_type,
            "org_name": r.org_name,
            "org_id": r._org_id,
            "completions": r.Program.completions,
        }
        for r in rows
    ]

def _get_high_roi_occs():
    rows = (
        db.session.query(Occupation, OccupationWage)
        .join(OccupationWage, OccupationWage.soc == Occupation.soc)
        .join(ProgramOccupation, ProgramOccupation.soc == Occupation.soc)
        .join(Program, Program.program_id == ProgramOccupation.program_id)
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(
            Occupation.job_zone <= 3,
            OccupationWage.area_type == "msa",
            OccupationWage.area_name.like("%Kansas City%"),
            OccupationWage.median_wage >= 55000,
            Organization.org_type == "training"
        )
        .distinct(Occupation.soc)
        .order_by(OccupationWage.median_wage.desc().nulls_last())
        .all()
    )
    def format_jobs(count):
        return f" | {count:,.0f} Local Jobs" if count else ""

    return [
        {
            "program_id": r.Occupation.soc, # Using program_id as the primary key field for the template
            "name": r.Occupation.title,
            "bright_outlook": r.Occupation.bright_outlook,
            "cip_title": f"Zone {r.Occupation.job_zone} | ${r.OccupationWage.median_wage:,.0f} Median{format_jobs(r.OccupationWage.employment_count)}",
            "cred": "Occupation",
            "org_name": "View Profile",
            "org_id": "occ_" + r.Occupation.soc, # We'll handle this in the template
        }
        for r in rows
    ]


HUBS_CONFIG = {
    "high-roi": {
        "title": "Quick Payoff Careers",
        "badge": "STAFF PICK",
        "icon": "💸",
        "description": "Discover high-yield careers in Kansas City requiring roughly an Associate's degree or less (Job Zone 3 and below), paying over $55,000 median locally. These are structurally 'hidden gems'.",
        "tabs": [
            {
                "id": "occupations",
                "label": "Target Careers",
                "icon": "💼",
                "count": 0,
                "data_func": _get_high_roi_occs,
            },
            {
                "id": "training",
                "label": "Fast-Track Programs",
                "icon": "🎓",
                "count": 0,
                "data_func": _get_high_roi_progs,
            },
        ],
    },
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
                "data_func": _get_apprenticeship_orgs,
            },
            {
                "id": "training",
                "label": "Training Programs",
                "icon": "🎓",
                "count": 0,
                "data_func": _get_apprenticeship_progs,
            },
        ],
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
        rendered_tabs.append(
            {
                "id": tab["id"],
                "label": tab["label"],
                "icon": tab["icon"],
                "count": len(data),
                "data": data,
            }
        )

    return render_template("hubs/detail.html", slug=slug, hub=hub, tabs=rendered_tabs)
