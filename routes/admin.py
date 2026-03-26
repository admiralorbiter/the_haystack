"""
Admin blueprint — Epic 2.5

Routes:
    GET  /admin                        — Dashboard: dataset sources + row counts
    GET  /admin/data/<table_slug>      — Paginated DB table explorer
    GET  /admin/raw                    — List all downloaded raw CSV files
    GET  /admin/raw/<path:file_path>   — Paginated raw CSV viewer with search
    POST /admin/run/<loader_name>      — HTMX loader runner (streams stdout)

No auth — local dev only. Do not expose in production.
"""

import csv
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

# ---------------------------------------------------------------------------
# IPEDS data dictionary — maps raw column codes to friendly labels
# Source: IPEDS data dictionaries (nces.ed.gov/ipeds)
# ---------------------------------------------------------------------------

IPEDS_COLUMNS: dict[str, str] = {
    # ── Identifiers ─────────────────────────────────────────────────────────
    "UNITID":       "Unit ID",
    "CIPCODE":      "CIP Code",
    "MAJORNUM":     "Major (1st/2nd)",
    "AWLEVEL":      "Award Level",

    # ── Institution ─────────────────────────────────────────────────────────
    "INSTNM":       "Institution Name",
    "IALIAS":       "Alias",
    "ADDR":         "Street Address",
    "CITY":         "City",
    "STABBR":       "State",
    "ZIP":          "ZIP Code",
    "FIPS":         "FIPS State Code",
    "OBEREG":       "Bureau Region",
    "CHFNM":        "Chief Admin Name",
    "CHFTITLE":     "Chief Admin Title",
    "GENTELE":      "Phone",
    "FAXTELE":      "Fax",
    "EIN":          "Tax ID (EIN)",
    "OPEID":        "OPE ID",
    "OPEFLAG":      "OPE Participation",
    "WEBADDR":      "Website",
    "ADMINURL":     "Admissions URL",
    "FAIDURL":      "Financial Aid URL",
    "APPLURL":      "Application URL",
    "NPRICURL":     "Net Price Calculator URL",
    "VETURL":       "Veterans URL",
    "ATHURL":       "Athletics URL",
    "DISAURL":      "Disability Services URL",

    # ── Classification ──────────────────────────────────────────────────────
    "SECTOR":       "Sector",
    "ICLEVEL":      "Level (2yr / 4yr)",
    "CONTROL":      "Control (Public / Private)",
    "HLOFFER":      "Highest Level Offered",
    "UGOFFER":      "Undergrad Programs",
    "GROFFER":      "Graduate Programs",
    "HDEGOFR1":     "Highest Degree Offered",
    "DEGGRANT":     "Degree Granting",
    "HBCU":         "HBCU",
    "HOSPITAL":     "Hospital",
    "MEDICAL":      "Medical School",
    "TRIBAL":       "Tribal College",
    "LOCALE":       "Locale",
    "OPENPUBL":     "Open to Public",
    "PSET4FLAG":    "4-Year Postsecondary",
    "PSEFLAG":      "Postsecondary Flag",
    "INSTCAT":      "Institution Category",
    "CCBASIC":      "Carnegie Basic Classification",
    "C18BASIC":     "Carnegie 2018 Basic",
    "C18IPUG":      "Carnegie 2018 UG Profile",
    "C18ISIZE":     "Carnegie 2018 Size",
    "C18UG":        "Carnegie 2018 UG Enrollment",
    "LONGITUD":     "Longitude",
    "LATITUDE":     "Latitude",
    "COUNTYCD":     "County Code",
    "COUNTYNM":     "County Name",
    "CNGDSTCD":     "Congressional District",
    "F1SYSTYP":     "System Type",
    "F1SYSNAM":     "System Name",
    "INSTSIZE":     "Institution Size",

    # ── IC (Institutional Characteristics) ─────────────────────────────────
    "CALSYS":       "Calendar System",
    "FT_UG":        "Full-Time UG Offered",
    "FT_FTUG":      "Full-Time/Full-Year UG",
    "FTGDNIDP":     "Full-Time Grad (Non-Deg)",
    "PT_UG":        "Part-Time UG Offered",
    "PT_FTUG":      "Part-Time/Full-Year UG",
    "PTGDNIDP":     "Part-Time Grad (Non-Deg)",
    "OPENADMP":     "Open Admissions",
    "CREDITS1":     "Dual Credit",
    "CREDITS2":     "Credit Accepted (AP)",
    "CREDITS3":     "Credit Accepted (Life Exp)",
    "CREDITS4":     "Credit Accepted (Clep)",
    "STUSRV1":      "Remedial Services",
    "STUSRV2":      "Academic Counseling",
    "STUSRV3":      "Employment Services",
    "STUSRV4":      "Daycare for Students",
    "LIBFAC":       "Library Facility",
    "ATHASSOC":     "Intercollegiate Athletics",
    "ENRLFT":       "Full-Time Enrollment",
    "ENRLPT":       "Part-Time Enrollment",
    "ENRLT":        "Total Enrollment",

    # ── Completions totals ───────────────────────────────────────────────────
    "CTOTALT":      "Completions Total",
    "CTOTALM":      "Completions Men",
    "CTOTALW":      "Completions Women",
    "CAIANT":       "AI/AN Total",
    "CASIAT":       "Asian Total",
    "CBKAAT":       "Black Total",
    "CHISPT":       "Hispanic Total",
    "CNHPIT":       "NH/PI Total",
    "CWHITT":       "White Total",
    "C2MORT":       "Two+ Races Total",
    "CUNKNT":       "Unknown Race Total",
    "CNRALT":       "Non-Resident Alien Total",
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


# ---------------------------------------------------------------------------
# Raw CSV file explorer
# ---------------------------------------------------------------------------

RAW_DIR = PROJECT_ROOT / "data" / "raw"
RAW_PAGE_SIZE = 100  # CSVs often have many columns — fewer rows per page


@admin_bp.route("/raw")
def raw_file_list():
    """List all downloaded CSV files in data/raw, grouped by directory."""
    groups: dict[str, list[dict]] = {}

    for csv_file in sorted(RAW_DIR.rglob("*.csv")):
        rel = csv_file.relative_to(RAW_DIR)
        group = str(rel.parent) if str(rel.parent) != "." else "root"
        size_mb = csv_file.stat().st_size / (1024 * 1024)

        # Peek at row count (fast: count newlines)
        with open(csv_file, "rb") as f:
            row_count = sum(1 for _ in f) - 1  # subtract header

        groups.setdefault(group, []).append({
            "name": csv_file.name,
            "path": str(rel).replace("\\", "/"),
            "size_mb": round(size_mb, 1),
            "row_count": row_count,
        })

    return render_template("admin/raw_file_list.html", groups=groups)


@admin_bp.route("/raw/<path:file_path>")
def raw_csv_view(file_path: str):
    """Paginated, searchable viewer for a single raw CSV file."""
    # Security: resolve path and ensure it stays inside RAW_DIR
    target = (RAW_DIR / file_path).resolve()
    if not str(target).startswith(str(RAW_DIR.resolve())):
        abort(404)
    if not target.exists() or target.suffix.lower() != ".csv":
        abort(404)

    q = request.args.get("q", "").strip().lower()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    sort_col = request.args.get("sort", "")
    sort_dir = request.args.get("dir", "asc")
    if sort_dir not in ("asc", "desc"):
        sort_dir = "asc"

    # Read the CSV — for large files we stream and filter in one pass
    all_rows: list[dict] = []
    columns: list[str] = []

    with open(target, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        search_col = columns[0] if columns else ""

        for row in reader:
            if q:
                if not any(q in str(v).lower() for v in row.values()):
                    continue
            all_rows.append(dict(row))

    # Validate sort column
    if sort_col not in columns:
        sort_col = columns[0] if columns else ""

    # Sort
    if sort_col:
        reverse = sort_dir == "desc"
        all_rows.sort(key=lambda r: (r.get(sort_col) or "").lower(), reverse=reverse)

    total = len(all_rows)
    total_pages = max(1, (total + RAW_PAGE_SIZE - 1) // RAW_PAGE_SIZE)
    page = min(page, total_pages)
    rows = all_rows[(page - 1) * RAW_PAGE_SIZE : page * RAW_PAGE_SIZE]

    return render_template(
        "admin/raw_csv_view.html",
        file_path=file_path,
        file_name=target.name,
        columns=columns,
        rows=rows,
        total=total,
        page=page,
        total_pages=total_pages,
        sort_col=sort_col,
        sort_dir=sort_dir,
        q=q,
        column_labels=IPEDS_COLUMNS,
    )

