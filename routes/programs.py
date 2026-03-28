"""
Program routes — Epic 4

Implements:
  GET /programs                              — directory (filterable, FTS5 search, paginated)
  GET /programs/<program_id>                 — detail page (snapshot + overview tab, HTMX-deferred)
  GET /programs/<program_id>/tab/overview    — HTMX: description, provider card, similar programs
  GET /programs/<program_id>/tab/occupations — HTMX: linked SOC occupations ranked by confidence
  GET /programs/<program_id>/tab/outcomes    — HTMX: completions, suppression note, Scorecard stub
  GET /programs/<program_id>/tab/geography   — HTMX: provider location, map pin
  GET /programs/<program_id>/tab/methods     — HTMX: CIP/SOC explanation, suppression definition
"""

import sqlite3
from pathlib import Path

from .cip_utils import CIP_FAMILY_NAMES, cip_family_label, cip_title

from flask import abort, render_template, request
from sqlalchemy import func, text

from models import (
    DatasetSource, Occupation, Organization,
    Program, ProgramOccupation, RegionCounty, db,
)

from . import root_bp

_DB_PATH = Path(__file__).resolve().parent.parent / "db" / "haystack.db"

# Scorecard suppression markers (same set as providers.py)
_SC_SUPPRESS = {"", "PrivacySuppressed", "PS", "NULL"}

# Map Scorecard CREDLEV codes → fragments of our credential_type strings
_CREDLEV_MAP: dict[str, list[str]] = {
    "1":  ["certificate", "<", "1", "sub"],   # sub-baccalaureate < 1yr
    "2":  ["certificate", "1", "2", "sub"],   # sub-baccalaureate 1-2yr
    "3":  ["associate"],
    "4":  ["bachelor"],
    "5":  ["master"],
    "6":  ["doctor"],
    "7":  ["professional"],
    "8":  ["graduate", "certificate"],
}


def _cip_to_4digit(cip: str) -> str:
    """Convert 6-digit CIP (51.3801) to 4-digit Scorecard format (5138)."""
    if not cip:
        return ""
    clean = cip.replace(".", "")  # "513801"
    return clean[:4]  # "5138"


def _credlev_for_credential_type(credential_type: str) -> list[str]:
    """Return list of CREDLEV codes that plausibly match a credential_type string."""
    ct = (credential_type or "").lower()
    matches = []
    if "associate" in ct:
        matches.append("2")
    if "bachelor" in ct:
        matches.append("3")
    if "master" in ct:
        matches.append("5")
    if "doctor" in ct or "doctoral" in ct:
        matches.append("6")
    if "professional" in ct and "graduate" not in ct:
        matches.append("7")
    if "graduate" in ct and "certificate" in ct:
        matches.append("8")
    if "certificate" in ct and "baccalaureate" in ct:
        matches.append("4")
    if "certificate" in ct and not matches:
        matches.append("1")
    if not matches:
        matches = ["1", "2", "3", "4", "5", "6", "7", "8"]  # fallback: all
    return matches


def _scorecard_fos_for_program(unitid: str | None, cip: str | None, credential_type: str | None) -> dict | None:
    """
    Look up the Scorecard Field-of-Study row for a specific program.
    Joins on: UNITID + 4-digit CIP prefix + CREDLEV code(s).
    Returns the best-matching row as a dict, or None.
    """
    if not unitid or not cip:
        return None
    cip4 = _cip_to_4digit(cip)
    credlevs = _credlev_for_credential_type(credential_type or "")
    credlev_placeholders = ",".join("?" * len(credlevs))
    try:
        conn = sqlite3.connect(_DB_PATH)
        row = conn.execute(
            f"""
            SELECT CIPCODE_NORM, CIPDESC, CREDLEV, CREDDESC,
                   EARN_MDN_HI_1YR, EARN_MDN_HI_2YR, EARN_COUNT_WNE_HI_2YR,
                   EARN_MDN_4YR_NAT, EARN_COUNT_WNE_4YR_NAT,
                   DEBT_ALL_STGP_EVAL_MDN, DEBT_ALL_PP_EVAL_MDN,
                   IPEDSCOUNT1, IPEDSCOUNT2
            FROM scorecard_field_of_study
            WHERE UNITID = ?
              AND CIPCODE_NORM LIKE ?
              AND CREDLEV IN ({credlev_placeholders})
            LIMIT 1
            """,
            [str(unitid), f"{cip4[:2]}.{cip4[2:]}%"] + credlevs,
        ).fetchone()
        conn.close()
        if not row:
            return None

        def _sc_int(v):
            if v is None or str(v) in _SC_SUPPRESS:
                return None
            try:
                return int(float(str(v)))
            except (ValueError, TypeError):
                return None

        return {
            "cip_norm":       row[0],
            "cip_desc":       row[1],
            "credlev":        row[2],
            "creddesc":       row[3],
            "earn_1yr":       _sc_int(row[4]),
            "earn_2yr":       _sc_int(row[5]),
            "earn_count_2yr": _sc_int(row[6]),
            "earn_nat_4yr":   _sc_int(row[7]),
            "earn_nat_count": _sc_int(row[8]),
            "debt_stgp_mdn":  _sc_int(row[9]),
            "debt_pp_mdn":    _sc_int(row[10]),
            "ipeds_count1":   _sc_int(row[11]),
            "ipeds_count2":   _sc_int(row[12]),
        }
    except sqlite3.OperationalError:
        return None  # table not yet created (test DB)



def _get_program_or_404(program_id: str) -> Program:
    """Fetch a program by program_id. Aborts 404 if not found."""
    prog = db.session.query(Program).filter_by(program_id=program_id).first()
    if not prog:
        abort(404)
    return prog


def _program_snapshot(prog: Program, org: Organization) -> dict:
    """Compute all snapshot strip metrics for a program."""
    occ_count = (
        db.session.query(func.count(ProgramOccupation.soc))
        .filter_by(program_id=prog.program_id)
        .scalar() or 0
    )
    ds = (
        db.session.query(DatasetSource)
        .filter(DatasetSource.source_id.like("ipeds_c_%"))
        .order_by(DatasetSource.loaded_at.desc())
        .first()
    )
    sc_fos = _scorecard_fos_for_program(org.unitid, prog.cip, prog.credential_type)
    return {
        "org": org,
        "cip_title": cip_title(prog.name),
        "cip_family_label": cip_family_label(prog.cip),
        "credential_type": prog.credential_type,
        "completions": prog.completions,
        "linked_occupations": occ_count,
        "sc_earn_2yr": sc_fos.get("earn_2yr") if sc_fos else None,
        "data_source": ds.name if ds else "IPEDS",
        "data_as_of": ds.loaded_at.strftime("%Y-%m-%d") if ds and ds.loaded_at else "Unknown",
    }


def _fts_search_enabled() -> bool:
    """Check if program_fts table exists and has rows (safe for test DB)."""
    try:
        conn = sqlite3.connect(_DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM program_fts LIMIT 1")
        count = cur.fetchone()[0]
        conn.close()
        return count > 0
    except sqlite3.OperationalError:
        return False


def _fts_program_ids(query: str) -> list[str]:
    """
    Run an FTS5 MATCH query and return matching program_ids.
    Falls back to empty list on error (caller uses LIKE fallback).
    Sanitizes the query string to avoid FTS5 syntax errors.
    """
    # Strip FTS5 special characters that would cause parse errors
    safe_q = query.replace('"', '').replace("'", "").strip()
    if not safe_q:
        return []
    try:
        conn = sqlite3.connect(_DB_PATH)
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT program_id FROM program_fts WHERE program_fts MATCH ? ORDER BY rank",
            (safe_q + "*",),  # prefix match so "nurs" finds "nursing"
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except sqlite3.OperationalError:
        return []


# ---------------------------------------------------------------------------
# IPEDS raw-table helpers (sqlite3 direct — not SQLAlchemy models)
# ---------------------------------------------------------------------------

def _ipeds_enrollment_for_program(unitid: str, cip: str) -> dict | None:
    """
    Pull fall enrollment for the CIP *family* at a specific institution from
    ipeds_ef2024cp.

    ef2024cp reports at the CIP family level (e.g. '52.0000'), not 6-digit.
    EFCIPLEV=601 is the grand total row (all students, all credential levels).
    We match on the 2-digit family prefix (cip[:2] + '.0000').
    Returns dict with total/male/female, or None if not found.
    """
    if not unitid or not cip:
        return None
    # Build family-level CIP code: '52.0201' → '52.0000'
    family = cip.split(".")[0] if "." in cip else cip[:2]
    family_cip = f"{family}.0000"
    try:
        conn = sqlite3.connect(_DB_PATH)
        cur = conn.cursor()
        row = cur.execute(
            '''
            SELECT EFTOTLT, EFTOTLM, EFTOTLW
            FROM ipeds_ef2024cp
            WHERE UNITID = ? AND CIPCODE = ? AND EFCIPLEV = "601"
            LIMIT 1
            ''',
            (str(unitid), family_cip),
        ).fetchone()
        conn.close()
        if not row:
            return None
        def _int(v):
            try: return int(v)
            except (TypeError, ValueError): return None
        total, male, female = _int(row[0]), _int(row[1]), _int(row[2])
        if total is None:
            return None
        return {"total": total, "male": male, "female": female, "family_cip": family_cip}
    except sqlite3.OperationalError:
        return None


def _ipeds_completions_equity(unitid: str) -> dict | None:
    """
    Pull institution-level completion gender breakdown from ipeds_c2024_b.
    (c2024_b doesn't have per-CIP rows — it's institution totals)
    Returns dict or None.
    """
    if not unitid:
        return None
    try:
        conn = sqlite3.connect(_DB_PATH)
        cur = conn.cursor()
        row = cur.execute(
            'SELECT CSTOTLT, CSTOTLM, CSTOTLW FROM ipeds_c2024_b WHERE UNITID = ? LIMIT 1',
            (str(unitid),),
        ).fetchone()
        conn.close()
        if not row:
            return None
        def _int(v):
            try: return int(v)
            except (TypeError, ValueError): return None
        return {"total": _int(row[0]), "male": _int(row[1]), "female": _int(row[2])}
    except sqlite3.OperationalError:
        return None


def _ipeds_cip_enrollment_by_family(cip_family: str, limit: int = 10) -> list[dict]:
    """
    Pull total fall enrollment for a CIP family across all KC providers.

    ef2024cp uses family-level CIP codes (e.g. '52.0000') and EFCIPLEV=601
    for the grand total row.  We join to org_alias to filter KC institutions.
    Returns list of {org_name, enrolled} sorted by enrollment desc.
    """
    family_cip = f"{cip_family}.0000"
    try:
        conn = sqlite3.connect(_DB_PATH)
        cur = conn.cursor()
        rows = cur.execute(
            '''
            SELECT o.name, CAST(e.EFTOTLT AS INTEGER) as enrolled
            FROM ipeds_ef2024cp e
            JOIN org_alias a ON CAST(e.UNITID AS TEXT) = a.source_id AND a.source = "ipeds"
            JOIN organization o ON o.org_id = a.org_id
            WHERE e.CIPCODE = ? AND e.EFCIPLEV = "601"
            ORDER BY enrolled DESC
            LIMIT ?
            ''',
            (family_cip, limit),
        ).fetchall()
        conn.close()
        return [{"org_name": r[0], "enrolled": r[1]} for r in rows if r[1]]
    except sqlite3.OperationalError:
        return []


# ---------------------------------------------------------------------------
# Directory — GET /programs
# ---------------------------------------------------------------------------

@root_bp.route("/programs")
def programs_directory():
    cred_filter = request.args.get("cred", "").strip()
    cip_filter = request.args.get("cip", "").strip()
    org_filter = request.args.get("org", "").strip()
    soc_filter = request.args.get("soc", "").strip()
    comp_filter = request.args.get("comp", "").strip()
    search_q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "completions")
    page = max(1, int(request.args.get("page", 1) or 1))
    per_page = 50

    # Compare selection mode — user clicked ⊕ on one program, now picking a second
    comparing_id = request.args.get("comparing", "").strip()
    comparing_name = None
    if comparing_id:
        cmp_prog = db.session.query(Program).filter_by(program_id=comparing_id).first()
        comparing_name = cip_title(cmp_prog.name) if cmp_prog else None
        if not comparing_name:
            comparing_id = ""  # invalid id, clear it

    q = (
        db.session.query(
            Program,
            Organization.name.label("org_name"),
            Organization.org_id.label("org_id_val"),
            Organization.city.label("org_city"),
            func.count(ProgramOccupation.soc).label("occ_count"),
        )
        .join(Organization, Organization.org_id == Program.org_id)
        .outerjoin(ProgramOccupation, ProgramOccupation.program_id == Program.program_id)
        .filter(Organization.org_type == "training")
        .group_by(Program.program_id)
    )

    # FTS5 search — if query present try FTS first, fall back to LIKE
    fts_active = False
    if search_q:
        matched_ids = _fts_program_ids(search_q) if _fts_search_enabled() else []
        if matched_ids:
            q = q.filter(Program.program_id.in_(matched_ids))
            fts_active = True
        else:
            # LIKE fallback — match program name or org name
            like_pat = f"%{search_q}%"
            q = q.filter(
                Program.name.ilike(like_pat) | Organization.name.ilike(like_pat)
            )

    if cred_filter:
        q = q.filter(Program.credential_type == cred_filter)

    if cip_filter:
        q = q.filter(Program.cip.like(f"{cip_filter}.%"))

    if org_filter:
        q = q.filter(Program.org_id == org_filter)

    if soc_filter:
        q = q.filter(ProgramOccupation.soc == soc_filter)

    if comp_filter == "suppressed":
        q = q.filter(Program.completions.is_(None))
    elif comp_filter == "low":
        q = q.filter(Program.completions < 10, Program.completions.isnot(None))
    elif comp_filter == "medium":
        q = q.filter(Program.completions >= 10, Program.completions < 50)
    elif comp_filter == "high":
        q = q.filter(Program.completions >= 50)

    _SORT_SAFE = {"completions", "name", "provider", "field", "occupations"}
    if sort == "name":
        q = q.order_by(Program.name.asc())
    elif sort == "provider":
        q = q.order_by(Organization.name.asc())
    elif sort == "field":
        q = q.order_by(Program.cip.asc())
    elif sort == "occupations":
        q = q.order_by(func.count(ProgramOccupation.soc).desc())
    else:
        sort = "completions"
        q = q.order_by(Program.completions.desc().nulls_last())

    total_count = q.count()
    rows = q.offset((page - 1) * per_page).limit(per_page).all()

    # Filter option lists
    all_creds = (
        db.session.query(Program.credential_type)
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(Organization.org_type == "training")
        .distinct()
        .order_by(Program.credential_type)
        .all()
    )
    all_cip_families = sorted(
        {r[0].split(".")[0] for r in db.session.query(Program.cip).all() if r[0] and "." in r[0]}
    )
    all_orgs = (
        db.session.query(Organization.org_id, Organization.name)
        .filter_by(org_type="training")
        .order_by(Organization.name)
        .all()
    )

    programs = [
        {
            "program": row.Program,
            "cip_title": cip_title(row.Program.name),
            "cip_family_label": cip_family_label(row.Program.cip),
            "org_name": row.org_name,
            "org_id": row.org_id_val,
            "org_city": row.org_city,
            "occ_count": row.occ_count or 0,
        }
        for row in rows
    ]

    total_pages = max(1, -(-total_count // per_page))

    return render_template(
        "programs/directory.html",
        programs=programs,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        per_page=per_page,
        cred_filter=cred_filter,
        cip_filter=cip_filter,
        org_filter=org_filter,
        soc_filter=soc_filter,
        comp_filter=comp_filter,
        search_q=search_q,
        sort=sort,
        fts_active=fts_active,
        all_creds=[r.credential_type for r in all_creds],
        all_cip_families=all_cip_families,
        all_orgs=all_orgs,
        cip_family_names=CIP_FAMILY_NAMES,
        comparing_id=comparing_id,
        comparing_name=comparing_name,
    )


# ---------------------------------------------------------------------------
# Detail page — GET /programs/<program_id>
# ---------------------------------------------------------------------------

@root_bp.route("/programs/<program_id>")
def program_detail(program_id: str):
    prog = _get_program_or_404(program_id)
    org = db.session.query(Organization).filter_by(org_id=prog.org_id).first()
    if not org:
        abort(404)

    snapshot = _program_snapshot(prog, org)

    # Overview tab data (rendered server-side on first load)
    top_occupations = (
        db.session.query(Occupation, ProgramOccupation.confidence)
        .join(ProgramOccupation, ProgramOccupation.soc == Occupation.soc)
        .filter(ProgramOccupation.program_id == program_id)
        .order_by(ProgramOccupation.confidence.desc().nulls_last())
        .limit(5)
        .all()
    )

    # Similar programs — same CIP family, different programs, sorted by completions
    cip_family = prog.cip.split(".")[0] if prog.cip and "." in prog.cip else None
    similar_programs = []
    if cip_family:
        sim_rows = (
            db.session.query(Program, Organization.name.label("org_name"))
            .join(Organization, Organization.org_id == Program.org_id)
            .filter(
                Program.cip.like(f"{cip_family}.%"),
                Program.program_id != program_id,
                Organization.org_type == "training",
            )
            .order_by(Program.completions.desc().nulls_last())
            .limit(5)
            .all()
        )
        similar_programs = [
            {
                "program": r.Program,
                "cip_title": cip_title(r.Program.name),
                "org_name": r.org_name,
            }
            for r in sim_rows
        ]

    if request.headers.get("HX-Request"):
        return render_template(
            "programs/partials/tab_overview.html",
            prog=prog,
            org=org,
            snapshot=snapshot,
            top_occupations=top_occupations,
            similar_programs=similar_programs,
            cip_family_label=cip_family_label(prog.cip),
        )

    return render_template(
        "programs/detail.html",
        prog=prog,
        org=org,
        snapshot=snapshot,
        top_occupations=top_occupations,
        similar_programs=similar_programs,
        cip_family_label=cip_family_label(prog.cip),
        active_tab="overview",
    )


# ---------------------------------------------------------------------------
# HTMX tab fragments
# ---------------------------------------------------------------------------

@root_bp.route("/programs/<program_id>/tab/overview")
def program_tab_overview(program_id: str):
    prog = _get_program_or_404(program_id)
    org = db.session.query(Organization).filter_by(org_id=prog.org_id).first_or_404()

    top_occupations = (
        db.session.query(Occupation, ProgramOccupation.confidence)
        .join(ProgramOccupation, ProgramOccupation.soc == Occupation.soc)
        .filter(ProgramOccupation.program_id == program_id)
        .order_by(ProgramOccupation.confidence.desc().nulls_last())
        .limit(5)
        .all()
    )

    cip_family = prog.cip.split(".")[0] if prog.cip and "." in prog.cip else None
    similar_programs = []
    if cip_family:
        sim_rows = (
            db.session.query(Program, Organization.name.label("org_name"))
            .join(Organization, Organization.org_id == Program.org_id)
            .filter(
                Program.cip.like(f"{cip_family}.%"),
                Program.program_id != program_id,
                Organization.org_type == "training",
            )
            .order_by(Program.completions.desc().nulls_last())
            .limit(5)
            .all()
        )
        similar_programs = [
            {
                "program": r.Program,
                "cip_title": cip_title(r.Program.name),
                "org_name": r.org_name,
            }
            for r in sim_rows
        ]

    return render_template(
        "programs/partials/tab_overview.html",
        prog=prog,
        org=org,
        snapshot=_program_snapshot(prog, org),
        top_occupations=top_occupations,
        similar_programs=similar_programs,
        cip_family_label=cip_family_label(prog.cip),
    )


@root_bp.route("/programs/<program_id>/tab/occupations")
def program_tab_occupations(program_id: str):
    prog = _get_program_or_404(program_id)
    occ_links = (
        db.session.query(Occupation, ProgramOccupation.confidence)
        .join(ProgramOccupation, ProgramOccupation.soc == Occupation.soc)
        .filter(ProgramOccupation.program_id == program_id)
        .order_by(ProgramOccupation.confidence.desc().nulls_last(), Occupation.title)
        .all()
    )
    return render_template(
        "programs/partials/tab_occupations.html",
        prog=prog,
        occ_links=occ_links,
    )


@root_bp.route("/programs/<program_id>/tab/outcomes")
def program_tab_outcomes(program_id: str):
    prog = _get_program_or_404(program_id)
    org = db.session.query(Organization).filter_by(org_id=prog.org_id).first()

    # IPEDS raw table lookups
    unitid = org.unitid if org else None
    enrollment = _ipeds_enrollment_for_program(unitid, prog.cip) if unitid else None
    completions_equity = _ipeds_completions_equity(unitid) if unitid else None

    return render_template(
        "programs/partials/tab_outcomes.html",
        prog=prog,
        org=org,
        enrollment=enrollment,
        completions_equity=completions_equity,
    )

@root_bp.route("/programs/<program_id>/tab/scorecard")
def program_tab_scorecard(program_id: str):
    prog = _get_program_or_404(program_id)
    org = db.session.query(Organization).filter_by(org_id=prog.org_id).first()
    unitid = org.unitid if org else None

    # Scorecard Field-of-Study earnings for this specific program
    sc_fos = _scorecard_fos_for_program(
        unitid, prog.cip, prog.credential_type
    ) if unitid else None

    return render_template(
        "programs/partials/tab_scorecard.html",
        prog=prog,
        org=org,
        sc_fos=sc_fos,
    )


@root_bp.route("/programs/<program_id>/tab/geography")
def program_tab_geography(program_id: str):
    prog = _get_program_or_404(program_id)
    org = db.session.query(Organization).filter_by(org_id=prog.org_id).first()
    county = None
    if org and org.county_fips:
        county = (
            db.session.query(RegionCounty)
            .filter_by(county_fips=org.county_fips)
            .first()
        )
    return render_template(
        "programs/partials/tab_geography.html",
        prog=prog,
        org=org,
        county=county,
    )


@root_bp.route("/programs/<program_id>/tab/methods")
def program_tab_methods(program_id: str):
    prog = _get_program_or_404(program_id)
    return render_template("programs/partials/tab_methods.html", prog=prog)
