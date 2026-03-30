"""
Employers routes — Epic 10 (Apprenticeships)

Implements:
  GET /employers — directory of apprenticeship employers/sponsors
"""

from flask import render_template, request, abort
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from models import Organization, OrgFact, OccupationIndustry, Occupation, db

from . import root_bp

def _get_naics_title(naics_code):
    if not naics_code:
        return "Unclassified"
    # Find canonical title from crosswalk
    row = db.session.query(OccupationIndustry.industry_title).filter(OccupationIndustry.naics.like(f"{naics_code}%")).first()
    return row[0] if row else f"Sector {naics_code}"

@root_bp.route("/employers")
def employers_directory():
    page = request.args.get("page", 1, type=int)
    per_page = 20
    q = request.args.get("q", "").strip()

    # Query all organizations that are employers OR intermediaries
    query = (
        db.session.query(Organization, OrgFact.value_text)
        .outerjoin(OrgFact, db.and_(OrgFact.org_id == Organization.org_id, OrgFact.fact_type == 'employees_total_range'))
        .filter(
            Organization.org_type.in_(["employer", "intermediary"]),
            Organization.is_active == True,
        )
    )

    if q:
        query = query.filter(Organization.name.ilike(f"%{q}%"))

    # Default sort alphabetically
    query = query.order_by(Organization.name.asc())

    total_count = query.count()
    rows = query.offset((page - 1) * per_page).limit(per_page).all()
    
    # Bundle row results and attach dynamic industry titles
    bundled_rows = []
    for org, employees in rows:
        bundled_rows.append({
            "org": org,
            "employees": employees,
            "industry_title": _get_naics_title(org.naics_code)
        })

    total_pages = (total_count + per_page - 1) // per_page
    has_next = page < total_pages
    has_prev = page > 1

    return render_template(
        "employers/directory.html",
        rows=bundled_rows,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev,
        q=q,
    )

@root_bp.route("/employers/<org_id>")
def employer_detail(org_id: str):
    org = db.session.query(Organization).filter_by(org_id=org_id).first()
    if not org or org.org_type not in ["employer", "intermediary"]:
        abort(404)
        
    # Get regional employees fact
    emp_fact = db.session.query(OrgFact).filter_by(org_id=org_id, fact_type='employees_total_range').first()
    employees = emp_fact.value_text if emp_fact else None
    
    industry_title = _get_naics_title(org.naics_code)
    
    # Inversion Query: Find likely careers hired by this NAICS
    likely_careers = []
    if org.naics_code:
        # We find top SOCs that employ highly in this NAICS substring
        careers = (
            db.session.query(Occupation, func.max(OccupationIndustry.pct_of_occupation).label('max_pct'))
            .join(OccupationIndustry, OccupationIndustry.soc == Occupation.soc)
            .filter(OccupationIndustry.naics.like(f"{org.naics_code}%"))
            .group_by(Occupation.soc)
            .order_by(db.func.max(OccupationIndustry.pct_of_occupation).desc())
            .limit(10)
            .all()
        )
        likely_careers = [c[0] for c in careers]

    return render_template(
        "employers/detail.html", 
        org=org,
        employees=employees,
        industry_title=industry_title,
        likely_careers=likely_careers
    )
