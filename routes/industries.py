"""
Industries routes — Future Epic 18 Foundation
Implements:
  GET /industries/<naics> — detail profile for an industry showing time-series data
"""

from flask import render_template, abort
from sqlalchemy import func

from models import IndustryQCEW, OccupationIndustry, db
from . import root_bp

@root_bp.route("/industries/<naics>")
def industry_detail(naics: str):
    # Fetch industry time-series data
    rows = (
        db.session.query(
            IndustryQCEW.year,
            IndustryQCEW.quarter,
            func.sum(IndustryQCEW.employment).label('total_emp'),
            func.sum(IndustryQCEW.establishments).label('total_estabs'),
            func.avg(IndustryQCEW.avg_weekly_wage).label('avg_wage')
        )
        .filter(IndustryQCEW.naics == naics)
        .group_by(IndustryQCEW.year, IndustryQCEW.quarter)
        .order_by(IndustryQCEW.year.desc(), IndustryQCEW.quarter.desc())
        .limit(12)
        .all()
    )

    # In Epic 18 we'll have a real Industry dictionary table, but for now we'll
    # query OccupationIndustry mapping to just grab the title of this NAICS.
    ind_name_row = db.session.query(OccupationIndustry.industry_title).filter_by(naics=naics).first()

    # If it has literally no QCEW data AND we don't even know what this industry is from the matrix, 
    # then it's a completely invalid NAICS code, abort 404.
    if not rows and not ind_name_row:
        abort(404, description=f"Data for NAICS {naics} doesn't exist.")

    title = ind_name_row.industry_title if ind_name_row else f"Industry (NAICS {naics})"

    # Prepare chart data in chronological order
    chart_data = []
    for r in reversed(rows):
        chart_data.append({
            "label": f"Q{r.quarter} {r.year}",
            "year": r.year,
            "qtr": r.quarter,
            "employment": r.total_emp or 0,
            "establishments": r.total_estabs or 0,
            "wage": r.avg_wage or 0
        })

    latest = chart_data[-1] if chart_data else None

    return render_template(
        "industries/detail.html",
        naics=naics,
        title=title,
        history=chart_data,
        latest=latest
    )
