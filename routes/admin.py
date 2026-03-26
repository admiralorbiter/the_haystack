"""
Admin blueprint — Epic 2.5

Routes:
    GET  /admin                        — Dashboard: dataset sources + row counts
    GET  /admin/data/<table_slug>      — Paginated raw data explorer
    POST /admin/run/<loader_name>      — HTMX loader runner (streams stdout)

No auth — local dev only. Do not expose in production.
"""

import subprocess
import sys
from pathlib import Path

from flask import Blueprint, Response, abort, render_template, request, stream_with_context
from sqlalchemy import func

from models import DatasetSource, Occupation, Organization, Program, ProgramOccupation, db

admin_bp = Blueprint("admin", __name__)

# ---------------------------------------------------------------------------
# Whitelists — security boundary (unknown slugs/names → 404)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOADERS_DIR = PROJECT_ROOT / "loaders"

ALLOWED_TABLES: dict[str, db.Model] = {
    "organizations": Organization,
    "programs": Program,
    "occupations": Occupation,
    "program-occupations": ProgramOccupation,
}

ALLOWED_LOADERS: dict[str, Path] = {
    "load_cip_soc": LOADERS_DIR / "load_cip_soc.py",
    "load_ipeds_institutions": LOADERS_DIR / "load_ipeds_institutions.py",
    "load_ipeds_programs": LOADERS_DIR / "load_ipeds_programs.py",
}

PAGE_SIZE = 50


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@admin_bp.route("/")
def dashboard():
    sources = DatasetSource.query.order_by(DatasetSource.loaded_at.desc()).all()

    row_counts = {
        "Organizations": db.session.scalar(func.count(Organization.org_id)),
        "Programs": db.session.scalar(func.count(Program.program_id)),
        "Occupations": db.session.scalar(func.count(Occupation.soc)),
        "Program → Occupation Links": db.session.scalar(func.count(ProgramOccupation.program_id)),
    }

    table_links = {
        "Organizations": "organizations",
        "Programs": "programs",
        "Occupations": "occupations",
        "Program → Occupation Links": "program-occupations",
    }

    return render_template(
        "admin/dashboard.html",
        sources=sources,
        row_counts=row_counts,
        table_links=table_links,
        allowed_loaders=list(ALLOWED_LOADERS.keys()),
    )


# ---------------------------------------------------------------------------
# Per-table configuration: column display order + searchable column
# ---------------------------------------------------------------------------

TABLE_CONFIG: dict[str, dict] = {
    "organizations": {
        "display_cols": ["name", "org_type", "city", "state", "county_fips", "website", "lat", "lon", "unitid", "ein", "org_id"],
        "search_col": "name",
        "search_label": "organization name",
    },
    "programs": {
        "display_cols": ["name", "credential_type", "cip", "org_name", "completions", "modality", "duration_weeks", "program_id", "org_id"],
        "search_col": "name",
        "search_label": "program name",
    },
    "occupations": {
        "display_cols": ["title", "soc_major", "soc_minor", "soc"],
        "search_col": "title",
        "search_label": "occupation title",
    },
    "program-occupations": {
        "display_cols": ["program_id", "soc", "confidence", "source"],
        "search_col": "soc",
        "search_label": "SOC code",
    },
}


# ---------------------------------------------------------------------------
# Raw data explorer
# ---------------------------------------------------------------------------

@admin_bp.route("/data/<table_slug>")
def data_table(table_slug: str):
    model = ALLOWED_TABLES.get(table_slug)
    if model is None:
        abort(404)

    config = TABLE_CONFIG[table_slug]
    q = request.args.get("q", "").strip()

    # --- Pagination ---
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    # --- Sort: default to first display column ---
    raw_table_columns = [c.key for c in model.__table__.columns]
    display_cols = [c for c in config["display_cols"] if c in raw_table_columns or c == "org_name"]
    default_sort = config["display_cols"][0] if config["display_cols"][0] in raw_table_columns else raw_table_columns[0]

    sort_col = request.args.get("sort", default_sort)
    # org_name is a virtual column — sort by actual name col instead
    if sort_col == "org_name":
        sort_col = "name"
    if sort_col not in raw_table_columns:
        sort_col = default_sort
    sort_dir = request.args.get("dir", "asc")
    if sort_dir not in ("asc", "desc"):
        sort_dir = "asc"

    sort_attr = getattr(model, sort_col)
    order = sort_attr.asc() if sort_dir == "asc" else sort_attr.desc()

    # --- Programs: enrich with org name via join ---
    if table_slug == "programs":
        from sqlalchemy.orm import joinedload
        query = db.session.query(Program, Organization.name.label("org_name")).join(
            Organization, Program.org_id == Organization.org_id
        )
        if q:
            query = query.filter(Program.name.ilike(f"%{q}%"))
        total = query.count()
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(page, total_pages)
        results = query.order_by(order).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()

        rows_as_dicts = []
        for program, org_name in results:
            row = {col: getattr(program, col) for col in raw_table_columns}
            row["org_name"] = org_name
            rows_as_dicts.append(row)

    else:
        # Standard single-model query
        search_col_name = config.get("search_col")
        query = model.query
        if q and search_col_name and hasattr(model, search_col_name):
            search_attr = getattr(model, search_col_name)
            query = query.filter(search_attr.ilike(f"%{q}%"))

        total = query.count()
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(page, total_pages)
        rows = query.order_by(order).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()
        rows_as_dicts = [{col: getattr(row, col) for col in raw_table_columns} for row in rows]

    # Filter display_cols to only those actually available in rows
    available_cols = list(rows_as_dicts[0].keys()) if rows_as_dicts else display_cols
    final_cols = [c for c in display_cols if c in available_cols]

    return render_template(
        "admin/data_table.html",
        table_slug=table_slug,
        table_name=table_slug.replace("-", " ").title(),
        columns=final_cols,
        rows=rows_as_dicts,
        total=total,
        page=page,
        total_pages=total_pages,
        sort_col=sort_col,
        sort_dir=sort_dir,
        q=q,
        search_label=config.get("search_label", ""),
    )



# ---------------------------------------------------------------------------
# HTMX loader runner
# ---------------------------------------------------------------------------

@admin_bp.route("/run/<loader_name>", methods=["POST"])
def run_loader(loader_name: str):
    script_path = ALLOWED_LOADERS.get(loader_name)
    if script_path is None or not script_path.exists():
        abort(404)

    def generate():
        yield f"▶ Running {loader_name}...\n"
        yield "-" * 50 + "\n"
        process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        for line in process.stdout:
            yield line
        process.wait()
        yield "-" * 50 + "\n"
        if process.returncode == 0:
            yield "✅ Done.\n"
        else:
            yield f"❌ Exited with code {process.returncode}\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/plain",
        headers={"X-Content-Type-Options": "nosniff"},
    )
