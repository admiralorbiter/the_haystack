from flask import Blueprint, render_template
from sqlalchemy import func

# Define root blueprint
root_bp = Blueprint("root", __name__)


@root_bp.route("/")
def index():
    from models import Organization, Program, ProgramOccupation, db

    # ── Regional summary stats ────────────────────────────────────────────
    provider_count = db.session.query(func.count(Organization.org_id)).scalar() or 0
    program_count  = db.session.query(func.count(Program.program_id)).scalar() or 0
    total_completions = (
        db.session.query(func.sum(Program.completions))
        .filter(Program.completions.isnot(None))
        .scalar() or 0
    )
    occ_count = (
        db.session.query(func.count(func.distinct(ProgramOccupation.soc)))
        .scalar() or 0
    )

    return render_template(
        "home.html",
        provider_count=provider_count,
        program_count=program_count,
        total_completions=total_completions,
        occ_count=occ_count,
    )


# These imports must be AFTER the blueprint definition — this is Flask's required pattern.
# ruff: noqa: E402, F401
from . import briefing, compare, employers, fields, guided_search, map, programs, providers, search  # noqa: E402, F401
