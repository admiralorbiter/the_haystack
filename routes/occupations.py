"""
Occupations routes — Epic 11/12
Implements Labor-First navigation.
  GET /occupations                 — Directory of jobs sorted by wage/demand
  GET /occupations/<soc>           — Detail profile for an occupation
  GET /occupations/<soc>/tab/...   — View tabs (programs, etc)
"""

from flask import abort, render_template, request
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from models import (
    DatasetSource,
    Occupation,
    OccupationIndustry,
    OccupationProjection,
    OccupationWage,
    Organization,
    Program,
    ProgramOccupation,
    IndustryQCEW,
    db,
)
from . import root_bp
from .cip_utils import cip_title
from .qcew_utils import get_qcew_trends

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_occ(soc: str) -> Occupation:
    occ = (
        db.session.query(Occupation)
        .options(joinedload(Occupation.industries))
        .filter_by(soc=soc)
        .first()
    )
    if not occ:
        abort(404)
    return occ

def _get_kc_wage(soc: str) -> OccupationWage | None:
    return (
        db.session.query(OccupationWage)
        .filter(
            OccupationWage.soc == soc,
            OccupationWage.area_type == "msa",
            OccupationWage.area_name.like("%Kansas City%"),
        )
        .first()
    )

def _get_nat_wage(soc: str) -> OccupationWage | None:
    return (
        db.session.query(OccupationWage)
        .filter(
            OccupationWage.soc == soc,
            OccupationWage.area_type == "national",
        )
        .first()
    )


def _get_industry_trends(naics_list: list[str]) -> dict:
    """Thin wrapper around shared get_qcew_trends utility."""
    return get_qcew_trends(naics_list, db.session)


# ---------------------------------------------------------------------------
# Directory — GET /occupations
# ---------------------------------------------------------------------------

@root_bp.route("/occupations")
def occupations_directory():
    sort = request.args.get("sort", "wage")
    zone_filter = request.args.get("zone", None)
    
    page = max(1, int(request.args.get("page", 1) or 1))
    per_page = 50

    q = (
        db.session.query(Occupation)
        .outerjoin(
            OccupationWage, 
            (OccupationWage.soc == Occupation.soc) & 
            (OccupationWage.area_type == "msa") & 
            (OccupationWage.area_name.like("%Kansas City%"))
        )
        .outerjoin(OccupationProjection)
        .options(joinedload(Occupation.wages), joinedload(Occupation.projection))
    )

    if zone_filter and zone_filter.isdigit():
        q = q.filter(Occupation.job_zone == int(zone_filter))

    if sort == "name":
        q = q.order_by(Occupation.title.asc())
    elif sort == "employment":
        q = q.order_by(OccupationWage.employment_count.desc().nulls_last())
    elif sort == "growth":
        q = q.order_by(OccupationProjection.pct_change.desc().nulls_last())
    else:  # default to wage
        sort = "wage"
        q = q.order_by(OccupationWage.median_wage.desc().nulls_last())

    total_count = q.count()
    rows = q.offset((page - 1) * per_page).limit(per_page).all()

    # Pre-calculate KC and National wage for rendering
    occs = []
    for o in rows:
        kc_wage = next((w for w in o.wages if w.area_type == 'msa' and 'Kansas City' in (w.area_name or '')), None)
        nat_wage = next((w for w in o.wages if w.area_type == 'national'), None)
        occs.append({
            "occ": o,
            "kc_wage": kc_wage,
            "nat_wage": nat_wage,
        })

    # Compute KC momentum per SOC via NAICS crosswalk
    # For each occupation, aggregate its top industries' QCEW trends
    all_socs = [o.soc for o in rows]
    # Get all NAICS codes for these SOCs, ordered by their proportion of the occupation
    matrix_rows = (
        db.session.query(OccupationIndustry.soc, OccupationIndustry.naics)
        .filter(OccupationIndustry.soc.in_(all_socs))
        .order_by(OccupationIndustry.soc, OccupationIndustry.pct_of_occupation.desc())
        .all()
    )
    soc_to_naics: dict[str, list[str]] = {}
    for mr in matrix_rows:
        soc_to_naics.setdefault(mr.soc, []).append(mr.naics)

    all_naics = list({n for ns in soc_to_naics.values() for n in ns})
    naics_trends = _get_industry_trends(all_naics)

    # For each SOC, find the trend of its primary employing industry
    occ_trends = {}
    for soc in all_socs:
        for naics in soc_to_naics.get(soc, []):
            t = naics_trends.get(naics)
            if t and t["yoy_pct"] is not None:
                occ_trends[soc] = t
                break  # we take the first one with data (since they are ordered by pct_of_occupation)

    total_pages = max(1, -(-total_count // per_page))

    return render_template(
        "occupations/directory.html",
        occupations=occs,
        total_count=total_count,
        sort=sort,
        zone_filter=zone_filter,
        page=page,
        total_pages=total_pages,
        occ_trends=occ_trends,
    )


# ---------------------------------------------------------------------------
# Detail — GET /occupations/<soc>
# ---------------------------------------------------------------------------

@root_bp.route("/occupations/<soc>")
def occupation_detail(soc: str):
    occ = _get_occ(soc)
    kc_wage = _get_kc_wage(soc)
    nat_wage = _get_nat_wage(soc)

    # Calculate linked programs offering this occupation
    program_count = (
        db.session.query(func.count(func.distinct(Program.program_id)))
        .join(ProgramOccupation, ProgramOccupation.program_id == Program.program_id)
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(ProgramOccupation.soc == soc, Organization.org_type == "training")
        .scalar() or 0
    )

    provider_count = (
        db.session.query(func.count(func.distinct(Program.org_id)))
        .join(ProgramOccupation, ProgramOccupation.program_id == Program.program_id)
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(ProgramOccupation.soc == soc, Organization.org_type == "training")
        .scalar() or 0
    )

    snapshot = {
        "soc": soc,
        "title": occ.title,
        "job_zone": occ.job_zone,
        "program_count": program_count,
        "provider_count": provider_count,
        "kc_wage": kc_wage,
        "nat_wage": nat_wage,
        "employment": kc_wage.employment_count if kc_wage else None
    }

    local_trends = _get_industry_trends([ind.naics for ind in occ.industries])

    if request.headers.get("HX-Request"):
        return render_template(
            "occupations/partials/tab_overview.html",
            occ=occ,
            kc_wage=kc_wage,
            nat_wage=nat_wage,
            snapshot=snapshot,
            local_trends=local_trends
        )

    return render_template(
        "occupations/detail.html",
        occ=occ,
        snapshot=snapshot,
        kc_wage=kc_wage,
        nat_wage=nat_wage,
        local_trends=local_trends,
    )

@root_bp.route("/occupations/<soc>/tab/overview")
def occupation_tab_overview(soc: str):
    occ = _get_occ(soc)
    kc_wage = _get_kc_wage(soc)
    nat_wage = _get_nat_wage(soc)
    local_trends = _get_industry_trends([ind.naics for ind in occ.industries])
    return render_template(
        "occupations/partials/tab_overview.html",
        occ=occ,
        kc_wage=kc_wage,
        nat_wage=nat_wage,
        local_trends=local_trends,
    )

@root_bp.route("/occupations/<soc>/tab/programs")
def occupation_tab_programs(soc: str):
    occ = _get_occ(soc)
    
    page = max(1, int(request.args.get("page", 1) or 1))
    per_page = 50

    q = (
        db.session.query(
            Program, 
            Organization.name.label("org_name"),
            ProgramOccupation.confidence
        )
        .join(ProgramOccupation, ProgramOccupation.program_id == Program.program_id)
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(ProgramOccupation.soc == soc, Organization.org_type == "training")
        .order_by(Program.completions.desc().nulls_last())
    )

    total_count = q.count()
    rows = q.offset((page - 1) * per_page).limit(per_page).all()

    programs = [
        {
            "program": r.Program,
            "cip_title": cip_title(r.Program.name),
            "org_name": r.org_name,
            "org_id": r.Program.org_id,
            "confidence": r.confidence,
        }
        for r in rows
    ]
    total_pages = max(1, -(-total_count // per_page))

    return render_template(
        "occupations/partials/tab_programs.html",
        occ=occ,
        programs=programs,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
    )

@root_bp.route("/occupations/<soc>/tab/methods")
def occupation_tab_methods(soc: str):
    occ = _get_occ(soc)
    return render_template(
        "occupations/partials/tab_methods.html",
        occ=occ,
    )
