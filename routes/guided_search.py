"""
Guided / Inverse Search route handler.

Epic 10: Instead of users browsing, this route lets them describe a *need* and
traces backward through the entity model to find providers and programs.

ROUTE:
    GET /search/guided              -> renders the 3-step guided form wrapper
    GET /search/guided/step2        -> HTMX fragment: step 2 specific to outcome
    GET /search/guided/resolve      -> Handles final form submission and redirects

API:
    GET /api/search/occupations     -> HTMX typeahead for occupations (SOC)
    GET /api/search/programs        -> HTMX typeahead for programs
"""

import re

from flask import abort, redirect, render_template, request, url_for

from models import Occupation, Program, db
from routes.cip_utils import CIP_FAMILY_NAMES

from . import root_bp


# Same FTS logic from programs.py, duplicated or imported to avoid circular imports
def _fts_search_enabled() -> bool:
    try:
        cur = db.engine.connect().connection.cursor()
        cur.execute("SELECT COUNT(*) FROM program_fts LIMIT 1")
        return True
    except Exception:
        return False


def _fts_program_ids(query: str) -> list[str]:
    sanitized = re.sub(r"[^\w\s]", " ", query).strip()
    if not sanitized:
        return []
    try:
        cur = db.engine.connect().connection.cursor()
        rows = cur.execute(
            "SELECT program_id FROM program_fts WHERE program_fts MATCH ? ORDER BY rank",
            (f"{sanitized}*",),
        ).fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []


@root_bp.route("/search/guided")
def guided_search():
    """Renders the Step 1 outcome selection."""
    return render_template("search/guided.html")


@root_bp.route("/search/guided/step2")
def guided_search_step2():
    """Returns the HTMX fragment for Step 2 based on chosen outcome."""
    outcome = request.args.get("outcome")

    if outcome == "training":
        return render_template("search/partials/step2_training.html")
    elif outcome == "field":
        return render_template(
            "search/partials/step2_field.html", cip_families=CIP_FAMILY_NAMES
        )
    elif outcome == "jobs":
        return render_template("search/partials/step2_jobs.html")
    elif outcome == "roi":
        return render_template("search/partials/step2_roi.html")
    elif outcome == "apprenticeship":
        return render_template("search/partials/step2_apprenticeship.html")

    return "<div class='empty-state'>Please select a goal.</div>", 400


@root_bp.route("/search/guided/resolve")
def guided_search_resolve():
    """Processes Step 2 form values and redirects to the final directory view."""
    outcome = request.args.get("outcome")

    if outcome == "training":
        soc = request.args.get("soc", "").strip()
        if soc:
            return redirect(url_for("root.programs_directory", soc=soc))

    elif outcome == "field":
        cip_family = request.args.get("cip_family", "").strip()
        if cip_family:
            return redirect(url_for("root.field_detail", cip_family=cip_family))

    elif outcome == "jobs":
        program_id = request.args.get("program_id", "").strip()
        if program_id:
            # Anchor to the occupations tab on the program detail page
            return redirect(
                url_for("root.program_detail", program_id=program_id)
                + "#tab_occupations"
            )

    elif outcome == "roi":
        cred = request.args.get("cred_filter", "").strip()
        if cred:
            # ROI has a dedicated route to do the in-memory Scorecard earnings sorting
            return redirect(url_for("root.guided_search_roi_results", cred=cred))

    elif outcome == "apprenticeship":
        return redirect(url_for("root.hub_detail", slug="apprenticeships"))

    # Fallback if form is tampered or navigated directly
    return redirect(url_for("root.guided_search"))


# -----------------------------------------------------------------------------
# ROI Custom Result View
# -----------------------------------------------------------------------------


@root_bp.route("/search/guided/roi_results")
def guided_search_roi_results():
    from models import Organization
    from routes.programs import _scorecard_fos_for_program

    cred = request.args.get("cred", "").strip()
    if not cred:
        return redirect(url_for("root.guided_search"))

    programs = (
        db.session.query(Program, Organization)
        .join(Organization, Program.org_id == Organization.org_id)
        .filter(Program.credential_type == cred)
        .all()
    )

    results = []
    for p, org in programs:
        sc = _scorecard_fos_for_program(org.unitid, p.cip, p.credential_type)
        earnings = None
        if sc:
            earnings = sc.get("earn_2yr") or sc.get("earn_1yr")

        results.append(
            {
                "program": p,
                "organization": org,
                "earnings": earnings,
                "earnings_val": earnings if isinstance(earnings, int) else 0,
            }
        )

    # Sort descending by earnings, drop those with no data
    results = [r for r in results if r["earnings_val"] > 0]
    results.sort(key=lambda x: x["earnings_val"], reverse=True)

    return render_template("search/roi_results.html", results=results[:50], cred=cred)
