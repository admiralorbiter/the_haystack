"""
Employers routes — Epic 10 (Apprenticeships)

Implements:
  GET /employers — directory of apprenticeship employers/sponsors
"""

from flask import render_template, request
from sqlalchemy import func

from models import Organization, db

from . import root_bp


@root_bp.route("/employers")
def employers_directory():
    page = request.args.get("page", 1, type=int)
    per_page = 20
    q = request.args.get("q", "").strip()

    # Query all organizations that are employers OR intermediaries
    query = db.session.query(Organization).filter(
        Organization.org_type.in_(["employer", "intermediary"]),
        Organization.is_active == True,
    )

    if q:
        query = query.filter(Organization.name.ilike(f"%{q}%"))

    # Default sort alphabetically
    query = query.order_by(Organization.name.asc())

    total_count = query.count()
    rows = query.offset((page - 1) * per_page).limit(per_page).all()

    total_pages = (total_count + per_page - 1) // per_page
    has_next = page < total_pages
    has_prev = page > 1

    return render_template(
        "employers/directory.html",
        rows=rows,
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
        from flask import abort

        abort(404)

    return render_template("employers/detail.html", org=org)
