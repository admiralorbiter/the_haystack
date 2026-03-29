from flask import request, render_template
from . import api_v1_bp
from models import db, Occupation, Program
from routes.guided_search import _fts_search_enabled, _fts_program_ids

@api_v1_bp.route("/search/occupations")
def search_occupations():
    """Returns HTMX list of matching occupations for typeahead dropdown."""
    query = request.args.get("q", "").strip()
    if not query or len(query) < 2:
        return ""
        
    like_query = f"%{query}%"
    results = (
        db.session.query(Occupation)
        .filter(Occupation.title.ilike(like_query) | Occupation.soc.ilike(like_query))
        .order_by(Occupation.title)
        .limit(10)
        .all()
    )
    return render_template("search/partials/typeahead_occupations.html", occupations=results)


@api_v1_bp.route("/search/programs")
def search_programs():
    """Returns HTMX list of matching programs for typeahead dropdown."""
    query = request.args.get("q", "").strip()
    if not query or len(query) < 2:
        return ""
        
    if _fts_search_enabled():
        matched_ids = _fts_program_ids(query)
        if matched_ids:
            # Maintain rank order
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
