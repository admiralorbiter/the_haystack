"""
Compare routes — Epic 6

Implements:
  GET /compare/providers?ids=A,B  — side-by-side provider comparison
  GET /compare/programs?ids=A,B   — side-by-side program comparison

Design: URL-param driven (no session/localStorage). Max 2 items per comparison.
"""

import re
import sqlite3
from collections import Counter
from pathlib import Path

from flask import abort, render_template, request, url_for
from sqlalchemy import func

from models import (
    DatasetSource, Occupation, Organization,
    Program, ProgramOccupation, db,
)
from routes.cip_utils import CIP_FAMILY_NAMES, cip_family_code, cip_family_label, cip_title

from . import root_bp

_DB_PATH = Path(__file__).resolve().parent.parent / "db" / "haystack.db"

# Simple UUID-ish validator — prevents SQL injection attempts from reaching queries
_UUID_RE = re.compile(r"^[0-9a-f\-]{8,40}$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helpers — reused across both entity types
# ---------------------------------------------------------------------------

def _parse_ids(raw: str | None, max_count: int = 2) -> list[str]:
    """
    Parse a comma-separated ids param. Returns up to max_count validated IDs.
    Raises ValueError if fewer than 2 IDs remain after validation.
    """
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    # Accept UUIDs or any alphanumeric-dash string up to 40 chars
    valid = [p for p in parts if _UUID_RE.match(p)][:max_count]
    return valid


def _provider_metrics(org_id: str) -> dict:
    """
    Compute all comparison metrics for a provider.
    Returns a flat dict of scalar values (None for missing data).
    """
    programs = db.session.query(Program).filter_by(org_id=org_id).all()

    total_programs = len(programs)
    wioa_programs = sum(1 for p in programs if p.is_wioa_eligible)
    apprenticeship_programs = sum(1 for p in programs if p.is_apprenticeship)

    comp_values = [p.completions for p in programs if p.completions is not None]
    total_completions = sum(comp_values) if comp_values else None

    cred_counts = Counter(p.credential_type for p in programs)
    top_credential = cred_counts.most_common(1)[0][0] if cred_counts else None

    cip_families = Counter(
        p.cip.split(".")[0] for p in programs if p.cip and "." in p.cip
    )
    top_cip_code = cip_families.most_common(1)[0][0] if cip_families else None
    top_cip_label = (
        f"{CIP_FAMILY_NAMES.get(top_cip_code, '')} ({top_cip_code})"
        if top_cip_code else None
    )

    program_ids = [p.program_id for p in programs]
    occ_count = 0
    if program_ids:
        occ_count = (
            db.session.query(func.count(func.distinct(ProgramOccupation.soc)))
            .filter(ProgramOccupation.program_id.in_(program_ids))
            .scalar() or 0
        )

    return {
        "total_programs": total_programs,
        "wioa_programs": wioa_programs,
        "apprenticeship_programs": apprenticeship_programs,
        "total_completions": total_completions,
        "top_credential": top_credential,
        "top_cip_label": top_cip_label,
        "linked_occupations": occ_count,
    }


# ---------------------------------------------------------------------------
# IPEDS raw-table fetch (same pattern as providers.py)
# ---------------------------------------------------------------------------

_CALSYS = {
    "1": "Semester", "2": "Quarter", "3": "Trimester",
    "4": "4-1-4", "5": "Other", "6": "Varies", "7": "Continuous",
}
_OPENADMP = {"1": "Open Admission", "2": "Selective Admission"}


def _ipeds_compare(unitid: str) -> dict:
    """
    Pull all IPEDS fields needed for the compare table.
    Returns {} if unitid is None or DB query fails.
    """
    if not unitid:
        return {}

    query = """
    SELECT
        ic.CALSYS, ic.OPENADMP,
        cost.CHG1AT0, cost.CHG2AT0,
        adm.APPLCN, adm.ADMSSN,
        grn.GRTOTLT as gr_150_comp, grd.GRTOTLT as gr_150_cohort,
        grp.PGCMTOT as pell_comp, grp.PGADJCT as pell_adj,
        gr200.BAREVCT as gr200_cohort, gr200.BAGR200 as gr200_comp,
        effy.EFYTOTLT,
        dist.EFYDETOT,
        ef4d.STUFACR,
        sfa.NPIST2 as net_price,
        sfa24.UAGRNTP as any_grant_pct, sfa24.UPGRNTP as pell_pct,
        sfa24.UFLOANP as loan_pct
    FROM ipeds_ic2024 ic
    LEFT JOIN ipeds_cost1_2024 cost ON ic.UNITID = cost.UNITID
    LEFT JOIN ipeds_adm2024 adm ON ic.UNITID = adm.UNITID
    LEFT JOIN ipeds_gr2024 grd ON ic.UNITID = grd.UNITID AND grd.GRTYPE IN (2, 29) AND grd.GRTOTLT != '-1'
    LEFT JOIN ipeds_gr2024 grn ON ic.UNITID = grn.UNITID AND grn.GRTYPE IN (3, 30) AND grn.GRTOTLT != '-1'
    LEFT JOIN ipeds_gr2024_pell_ssl grp ON ic.UNITID = grp.UNITID AND grp.PSGRTYPE IN ('2','4') AND grp.PGCMTOT != '-1'
    LEFT JOIN ipeds_gr200_24 gr200 ON ic.UNITID = gr200.UNITID
    LEFT JOIN ipeds_effy2024 effy ON ic.UNITID = effy.UNITID AND effy.EFFYLEV = '1'
    LEFT JOIN ipeds_effy2024_dist dist ON ic.UNITID = dist.UNITID AND dist.EFFYDLEV = '1'
    LEFT JOIN ipeds_ef2024d ef4d ON ic.UNITID = ef4d.UNITID
    LEFT JOIN ipeds_sfa2223 sfa ON ic.UNITID = sfa.UNITID
    LEFT JOIN ipeds_sfa2324 sfa24 ON ic.UNITID = sfa24.UNITID
    WHERE ic.UNITID = ?
    """
    try:
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.cursor().execute(query, (unitid,)).fetchone()
        conn.close()
        if not row:
            return {}
        row = dict(row)
    except sqlite3.Error as exc:
        import sys
        print(f"[compare] IPEDS DB error for unitid={unitid!r}: {exc}", file=sys.stderr)
        return {}

    def _int(key):
        try:
            v = row.get(key)
            return int(v) if v and str(v) not in ("-1", "-2", "None", "") else None
        except (ValueError, TypeError):
            return None

    def _float(key):
        try:
            v = row.get(key)
            return float(v) if v and str(v) not in ("-1", "-2", "None", "") else None
        except (ValueError, TypeError):
            return None

    result = {}
    result["calendar"] = _CALSYS.get(str(row.get("CALSYS", "")), None)
    result["open_admissions"] = _OPENADMP.get(str(row.get("OPENADMP", "")), None)
    result["instate_tuition"] = _int("CHG1AT0")
    result["outstate_tuition"] = _int("CHG2AT0")
    result["net_price"] = _int("net_price")

    apps = _int("APPLCN")
    admits = _int("ADMSSN")
    if apps and admits and apps > 0:
        result["acceptance_rate"] = round(admits / apps * 100, 1)

    result["enrollment_total"] = _int("EFYTOTLT")

    de_total = _int("EFYDETOT")
    en_total = _int("EFYTOTLT")
    if de_total is not None and en_total and en_total > 0:
        result["distance_ed_pct"] = round(de_total / en_total * 100, 1)

    sf = _float("STUFACR")
    result["student_faculty_ratio"] = round(sf, 1) if sf else None

    gr150 = _int("gr_150_comp")
    gr150_co = _int("gr_150_cohort")
    if gr150 is not None and gr150_co and gr150_co > 0:
        result["grad_rate_150"] = round(gr150 / gr150_co * 100)

    pell = _int("pell_comp")
    pell_adj = _int("pell_adj")
    if pell is not None and pell_adj and pell_adj > 0:
        result["grad_rate_pell"] = round(pell / pell_adj * 100)

    gr200 = _int("gr200_comp")
    gr200_co = _int("gr200_cohort")
    if gr200 is not None and gr200_co and gr200_co > 0:
        result["grad_rate_200"] = round(gr200 / gr200_co * 100)

    result["any_grant_pct"] = _int("any_grant_pct")
    result["pell_pct"] = _int("pell_pct")
    result["loan_pct"] = _int("loan_pct")

    return result


# ---------------------------------------------------------------------------
# Winner logic — annotate which side wins each metric row
# ---------------------------------------------------------------------------

def _annotate_winner(val_a, val_b, higher_is_better: bool) -> tuple[str, str]:
    """
    Returns (label_a, label_b) where each is 'winner', 'loser', or 'tie'.
    If either value is None, both are 'neutral'.
    """
    if val_a is None or val_b is None:
        return "neutral", "neutral"
    if val_a == val_b:
        return "tie", "tie"
    if higher_is_better:
        return ("winner", "loser") if val_a > val_b else ("loser", "winner")
    else:
        return ("winner", "loser") if val_a < val_b else ("loser", "winner")


def _build_provider_rows(snap_a, snap_b, ipeds_a, ipeds_b) -> list[dict]:
    """
    Build the ordered list of comparison row dicts for provider compare template.
    Each row: {label, val_a, val_b, status_a, status_b, fmt, note}
    fmt: 'number', 'currency', 'percent', 'text', 'neutral'
    """
    def _row(label, val_a, val_b, fmt="number", higher=True, note=""):
        sa, sb = _annotate_winner(val_a, val_b, higher)
        return {
            "label": label,
            "val_a": val_a,
            "val_b": val_b,
            "status_a": sa,
            "status_b": sb,
            "fmt": fmt,
            "note": note,
        }

    rows = [
        # Programmatic
        _row("Programs Offered", snap_a["total_programs"], snap_b["total_programs"]),
        _row("WIOA Eligible", snap_a["wioa_programs"], snap_b["wioa_programs"], fmt="neutral", note="Funded alternative pathway"),
        _row("Apprenticeship", snap_a["apprenticeship_programs"], snap_b["apprenticeship_programs"], fmt="neutral", note="Registered DOL pathway"),
        _row("Annual Completions", snap_a["total_completions"], snap_b["total_completions"]),
        _row("Linked Occupations", snap_a["linked_occupations"], snap_b["linked_occupations"]),
        # Enrollment
        _row("Total Enrollment", ipeds_a.get("enrollment_total"), ipeds_b.get("enrollment_total"),
             fmt="neutral", higher=True, note="Headcount — larger = more students served"),
        _row("Distance Ed Share", ipeds_a.get("distance_ed_pct"), ipeds_b.get("distance_ed_pct"),
             fmt="percent", higher=False,
             note="% of enrollment via distance education — neutral signal"),
        # Admissions
        _row("Acceptance Rate", ipeds_a.get("acceptance_rate"), ipeds_b.get("acceptance_rate"),
             fmt="percent", higher=False,
             note="Lower = more selective (not inherently better)"),
        # Cost
        _row("In-State Tuition", ipeds_a.get("instate_tuition"), ipeds_b.get("instate_tuition"),
             fmt="currency", higher=False, note="Annual tuition & fees"),
        _row("Net Price", ipeds_a.get("net_price"), ipeds_b.get("net_price"),
             fmt="currency", higher=False, note="Average net price after grants/scholarships"),
        # Aid
        _row("Any Grant Recipients", ipeds_a.get("any_grant_pct"), ipeds_b.get("any_grant_pct"),
             fmt="percent", higher=True, note="% of undergrads receiving any grant aid"),
        _row("Pell Grant Recipients", ipeds_a.get("pell_pct"), ipeds_b.get("pell_pct"),
             fmt="percent", higher=True, note="% of undergrads receiving Pell grants (low-income signal)"),
        # Outcomes
        _row("150% Graduation Rate", ipeds_a.get("grad_rate_150"), ipeds_b.get("grad_rate_150"),
             fmt="percent", higher=True),
        _row("Pell Grad Rate", ipeds_a.get("grad_rate_pell"), ipeds_b.get("grad_rate_pell"),
             fmt="percent", higher=True, note="Graduation rate for Pell grant recipients"),
        _row("200% Graduation Rate", ipeds_a.get("grad_rate_200"), ipeds_b.get("grad_rate_200"),
             fmt="percent", higher=True, note="Completion within twice the normal time"),
        # Faculty
        _row("Student-Faculty Ratio", ipeds_a.get("student_faculty_ratio"),
             ipeds_b.get("student_faculty_ratio"),
             fmt="neutral", higher=False, note="Lower = smaller class sizes"),
    ]
    return rows


def _build_program_rows(prog_a, prog_b, org_a, org_b, occ_a, occ_b) -> list[dict]:
    """Build comparison rows for program compare."""
    def _row(label, val_a, val_b, fmt="number", higher=True, note=""):
        sa, sb = _annotate_winner(val_a, val_b, higher)
        return {
            "label": label,
            "val_a": val_a,
            "val_b": val_b,
            "status_a": sa,
            "status_b": sb,
            "fmt": fmt,
            "note": note,
        }

    return [
        _row("Annual Completions", prog_a.completions, prog_b.completions),
        _row("Linked Occupations", occ_a, occ_b),
    ]


def _winner_sentence(rows: list[dict], name_a: str, name_b: str) -> str:
    """
    Generate a plain-language summary of the most notable differences.
    E.g. "Provider A has a higher grad rate. Provider B costs less."
    Returns empty string if both have no data.
    """
    parts_a, parts_b = [], []
    for row in rows:
        if row["status_a"] == "winner":
            parts_a.append(row["label"].lower())
        elif row["status_b"] == "winner":
            parts_b.append(row["label"].lower())

    sentences = []
    if parts_a:
        sentences.append(f"{name_a} leads on: {', '.join(parts_a[:3])}.")
    if parts_b:
        sentences.append(f"{name_b} leads on: {', '.join(parts_b[:3])}.")
    if not sentences:
        return "No numeric data available to compare these entities."
    return " ".join(sentences)


# ---------------------------------------------------------------------------
# Provider compare — GET /compare/providers?ids=A,B
# ---------------------------------------------------------------------------

@root_bp.route("/compare/providers")
def compare_providers():
    raw = request.args.get("ids", "")
    ids = _parse_ids(raw)

    if len(ids) < 2:
        # Insufficient IDs — redirect to directory with a hint
        from flask import redirect
        return redirect(url_for("root.providers_directory"))

    id_a, id_b = ids[0], ids[1]

    org_a = (
        db.session.query(Organization)
        .filter_by(org_id=id_a, org_type="training")
        .first()
    )
    org_b = (
        db.session.query(Organization)
        .filter_by(org_id=id_b, org_type="training")
        .first()
    )

    if not org_a or not org_b:
        abort(404)

    snap_a = _provider_metrics(id_a)
    snap_b = _provider_metrics(id_b)
    ipeds_a = _ipeds_compare(org_a.unitid)
    ipeds_b = _ipeds_compare(org_b.unitid)

    rows = _build_provider_rows(snap_a, snap_b, ipeds_a, ipeds_b)
    summary = _winner_sentence(rows, org_a.name, org_b.name)

    ds = (
        db.session.query(DatasetSource)
        .filter(DatasetSource.source_id.like("ipeds_hd_%"))
        .order_by(DatasetSource.loaded_at.desc())
        .first()
    )

    return render_template(
        "compare/providers.html",
        org_a=org_a,
        org_b=org_b,
        snap_a=snap_a,
        snap_b=snap_b,
        ipeds_a=ipeds_a,
        ipeds_b=ipeds_b,
        rows=rows,
        summary=summary,
        id_a=id_a,
        id_b=id_b,
        data_as_of=ds.loaded_at.strftime("%Y-%m-%d") if ds and ds.loaded_at else "Unknown",
        data_source=ds.name if ds else "IPEDS",
    )


# ---------------------------------------------------------------------------
# Program compare — GET /compare/programs?ids=A,B
# ---------------------------------------------------------------------------

@root_bp.route("/compare/programs")
def compare_programs():
    raw = request.args.get("ids", "")
    ids = _parse_ids(raw)

    if len(ids) < 2:
        from flask import redirect
        return redirect(url_for("root.programs_directory"))

    id_a, id_b = ids[0], ids[1]

    prog_a = db.session.query(Program).filter_by(program_id=id_a).first()
    prog_b = db.session.query(Program).filter_by(program_id=id_b).first()

    if not prog_a or not prog_b:
        abort(404)

    org_a = db.session.query(Organization).filter_by(org_id=prog_a.org_id).first()
    org_b = db.session.query(Organization).filter_by(org_id=prog_b.org_id).first()

    if not org_a or not org_b:
        abort(404)

    occ_a = (
        db.session.query(func.count(ProgramOccupation.soc))
        .filter_by(program_id=id_a)
        .scalar() or 0
    )
    occ_b = (
        db.session.query(func.count(ProgramOccupation.soc))
        .filter_by(program_id=id_b)
        .scalar() or 0
    )

    rows = _build_program_rows(prog_a, prog_b, org_a, org_b, occ_a, occ_b)
    summary = _winner_sentence(rows, cip_title(prog_a.name), cip_title(prog_b.name))

    ds = (
        db.session.query(DatasetSource)
        .filter(DatasetSource.source_id.like("ipeds_c_%"))
        .order_by(DatasetSource.loaded_at.desc())
        .first()
    )

    cip_title_a = cip_title(prog_a.name)
    cip_title_b = cip_title(prog_b.name)
    cip_fam_a = cip_family_code(prog_a.cip)
    cip_fam_b = cip_family_code(prog_b.cip)
    cip_label_a = cip_family_label(prog_a.cip)
    cip_label_b = cip_family_label(prog_b.cip)

    return render_template(
        "compare/programs.html",
        prog_a=prog_a,
        prog_b=prog_b,
        org_a=org_a,
        org_b=org_b,
        occ_a=occ_a,
        occ_b=occ_b,
        rows=rows,
        summary=summary,
        id_a=id_a,
        id_b=id_b,
        cip_title_a=cip_title_a,
        cip_title_b=cip_title_b,
        cip_fam_a=cip_fam_a,
        cip_fam_b=cip_fam_b,
        cip_label_a=cip_label_a,
        cip_label_b=cip_label_b,
        data_as_of=ds.loaded_at.strftime("%Y-%m-%d") if ds and ds.loaded_at else "Unknown",
        data_source=ds.name if ds else "IPEDS",
    )
