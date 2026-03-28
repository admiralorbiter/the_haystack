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

from flask import render_template, request, redirect, url_for, abort
from . import root_bp
from models import db, Occupation, Program
from routes.cip_utils import CIP_FAMILY_NAMES
import re

# Same FTS logic from programs.py, duplicated or imported to avoid circular imports
def _fts_search_enabled() -> bool:
    try:
        cur = db.engine.connect().connection.cursor()
        cur.execute("SELECT COUNT(*) FROM program_fts LIMIT 1")
        return True
    except Exception:
        return False

def _fts_program_ids(query: str) -> list[str]:
    sanitized = re.sub(r'[^\w\s]', ' ', query).strip()
    if not sanitized:
        return []
    try:
        cur = db.engine.connect().connection.cursor()
        rows = cur.execute(
            "SELECT program_id FROM program_fts WHERE program_fts MATCH ? ORDER BY rank",
            (f"{sanitized}*",)
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
        return render_template("search/partials/step2_field.html", cip_families=CIP_FAMILY_NAMES)
    elif outcome == "jobs":
        return render_template("search/partials/step2_jobs.html")
    elif outcome == "roi":
        return render_template("search/partials/step2_roi.html")
    
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
            return redirect(url_for("root.program_detail", program_id=program_id) + "#tab_occupations")
            
    elif outcome == "roi":
        cred = request.args.get("cred_filter", "").strip()
        if cred:
            # We direct them to programs filtered by credential. 
            # Note: sorting by Scorecard earnings requires Phase 2 FTS extensions, defaults to completions.
            return redirect(url_for("root.programs_directory", cred=cred))
            
    # Fallback if form is tampered or navigated directly
    return redirect(url_for("root.guided_search"))


# -----------------------------------------------------------------------------
# HTMX API Endpoints for Typeaheads
# -----------------------------------------------------------------------------

@root_bp.route("/api/search/occupations")
def api_search_occupations():
    """Returns HTMX list of matching occupations for typeahead dropdown."""
    query = request.args.get("q", "").strip()
    if not query or len(query) < 2:
        return ""
        
    # Standard LIKE search for occupations
    like_query = f"%{query}%"
    results = (
        db.session.query(Occupation)
        .filter(Occupation.title.ilike(like_query) | Occupation.soc.ilike(like_query))
        .order_by(Occupation.title)
        .limit(10)
        .all()
    )
    return render_template("search/partials/typeahead_occupations.html", occupations=results)


@root_bp.route("/api/search/programs")
def api_search_programs():
    """Returns HTMX list of matching programs for typeahead dropdown."""
    query = request.args.get("q", "").strip()
    if not query or len(query) < 2:
        return ""
        
    if _fts_search_enabled():
        matched_ids = _fts_program_ids(query)
        if matched_ids:
            # We must maintain rank order from matched_ids
            programs = db.session.query(Program).filter(Program.program_id.in_(matched_ids)).all()
            id_map = {p.program_id: p for p in programs}
            results = [id_map[mid] for mid in matched_ids if mid in id_map][:10]
        else:
            results = []
    else:
        like_query = f"%{query}%"
        results = (
            db.session.query(Program)
            .filter(Program.name.ilike(like_query))
            .limit(10)
            .all()
        )
        
    return render_template("search/partials/typeahead_programs.html", programs=results)
