"""
Industries routes — Epic 18 Foundation
Implements:
  GET /industries         — directory of all KC-tracked NAICS industries
  GET /industries/<naics> — detail profile for an industry showing time-series data
"""

from flask import render_template, abort
from sqlalchemy import func

from models import IndustryQCEW, OccupationIndustry, db
from . import root_bp
from .qcew_utils import get_qcew_trends


@root_bp.route("/industries")
def industries_directory():
    """Directory of all KC-tracked NAICS industries with current employment and YoY momentum."""
    title_map = {
        r.naics: r.industry_title
        for r in db.session.query(OccupationIndustry.naics, OccupationIndustry.industry_title).all()
    }

    # Get all NAICS that have titles (excludes BLS roll-up aggregate codes)
    named_naics = list(title_map.keys())
    if not named_naics:
        return render_template("industries/directory.html", industries=[], latest_quarter="N/A")

    # Get employment + establishments + wage for each named NAICS across latest available data
    # We pull all data and let qcew_utils decide the complete quarter per NAICS
    trends = get_qcew_trends(named_naics, db.session)

    # Also pull establishment + wage data for the ref quarter per NAICS
    # We need the latest complete quarter globally for meta display
    latest_global = (
        db.session.query(IndustryQCEW.year, IndustryQCEW.quarter)
        .order_by(IndustryQCEW.year.desc(), IndustryQCEW.quarter.desc())
        .first()
    )

    # Build the industry list from trends (only industries that have QCEW data + title)
    industries = []
    for naics, t in trends.items():
        title = title_map.get(naics)
        if not title:
            continue
        if t["latest_emp"] < 50:
            continue

        # Get supplemental establishment + wage data for this naics's ref quarter
        ref_label = t["ref_quarter"]  # e.g. "Q2 2025"
        ref_q_parts = ref_label.split()
        ref_qtr = int(ref_q_parts[0][1])
        ref_yr = int(ref_q_parts[1])

        supp = (
            db.session.query(
                func.sum(IndustryQCEW.establishments).label("estabs"),
                func.avg(IndustryQCEW.avg_weekly_wage).label("wage"),
            )
            .filter(
                IndustryQCEW.naics == naics,
                IndustryQCEW.year == ref_yr,
                IndustryQCEW.quarter == ref_qtr,
            )
            .first()
        )

        industries.append({
            "naics": naics,
            "title": title,
            "employment": t["latest_emp"],
            "establishments": supp.estabs or 0 if supp else 0,
            "wage": supp.wage or 0 if supp else 0,
            "yoy_pct": t["yoy_pct"],
            "direction": t["direction"],
            "trend_slope_pct": t["trend_slope_pct"],
            "trend_direction": t["trend_direction"],
            "ref_quarter": t["ref_quarter"],
            "is_complete": t["is_complete"],
        })

    industries.sort(key=lambda x: x["employment"], reverse=True)
    latest_quarter = f"Q{latest_global.quarter} {latest_global.year}" if latest_global else "N/A"

    return render_template(
        "industries/directory.html",
        industries=industries,
        latest_quarter=latest_quarter,
    )


@root_bp.route("/industries/<naics>")
def industry_detail(naics: str):
    # Fetch all time-series data for this NAICS
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

    ind_name_row = db.session.query(OccupationIndustry.industry_title).filter_by(naics=naics).first()

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

    # Get trend analysis using the shared utility
    trend_result = get_qcew_trends([naics], db.session).get(naics)

    # Reference quarter snapshot (from correct complete quarter)
    snapshot = None
    if trend_result:
        ref_label = trend_result["ref_quarter"]
        ref_parts = ref_label.split()
        ref_qtr = int(ref_parts[0][1])
        ref_yr = int(ref_parts[1])
        snapshot_row = next(
            (p for p in chart_data if p["year"] == ref_yr and p["qtr"] == ref_qtr),
            chart_data[-1] if chart_data else None
        )
        snapshot = snapshot_row

    return render_template(
        "industries/detail.html",
        naics=naics,
        title=title,
        history=chart_data,
        latest=chart_data[-1] if chart_data else None,
        snapshot=snapshot,
        trend=trend_result,
    )
