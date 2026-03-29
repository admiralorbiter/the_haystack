"""
Search routes — Epic 8

Implements:
  GET /search?q=<query>  — global search across Providers, Programs, and Fields
"""

import sqlite3
from pathlib import Path

from flask import render_template, request
from sqlalchemy import func

from models import Organization, Program, db

from . import root_bp
from .cip_utils import CIP_FAMILY_NAMES, cip_title

_DB_PATH = Path(__file__).resolve().parent.parent / "db" / "haystack.db"


def _fts_org_ids(query: str, limit: int = 5) -> list[str]:
    safe_q = query.replace('"', "").replace("'", "").strip()
    if not safe_q:
        return []
    try:
        conn = sqlite3.connect(_DB_PATH)
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT org_id FROM organization_fts WHERE organization_fts MATCH ? ORDER BY rank LIMIT ?",
            (safe_q + "*", limit),
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except sqlite3.OperationalError:
        return []


def _fts_program_ids(query: str, limit: int = 5) -> list[str]:
    safe_q = query.replace('"', "").replace("'", "").strip()
    if not safe_q:
        return []
    try:
        conn = sqlite3.connect(_DB_PATH)
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT program_id FROM program_fts WHERE program_fts MATCH ? ORDER BY rank LIMIT ?",
            (safe_q + "*", limit),
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except sqlite3.OperationalError:
        return []


@root_bp.route("/search")
def search_view():
    q = request.args.get("q", "").strip()

    org_results = []
    prog_results = []
    field_results = []
    occ_results = []

    if not q:
        return render_template("search/results.html", q=q, orgs=[], progs=[], fields=[], occs=[])

    # 1. Search Organizations
    org_ids = _fts_org_ids(q, limit=5)
    if not org_ids:
        # fallback to ILIKE if FTS fails or returns nothing (test databases often lack FTS rows)
        like_pat = f"%{q}%"
        fallback_orgs = (
            db.session.query(Organization)
            .filter(Organization.name.ilike(like_pat))
            .limit(5)
            .all()
        )
        org_ids = [o.org_id for o in fallback_orgs]

    if org_ids:
        org_rows = (
            db.session.query(Organization)
            .filter(Organization.org_id.in_(org_ids), Organization.is_active == True)
            .all()
        )
        org_dict = {o.org_id: o for o in org_rows}
        # Maintain FTS rank order
        org_results = [org_dict[uuid] for uuid in org_ids if uuid in org_dict]

    # 2. Search Programs
    prog_ids = _fts_program_ids(q, limit=5)
    if not prog_ids:
        like_pat = f"%{q}%"
        fallback_progs = (
            db.session.query(Program)
            .filter(Program.name.ilike(like_pat))
            .limit(5)
            .all()
        )
        prog_ids = [p.program_id for p in fallback_progs]

    if prog_ids:
        pr_rows = (
            db.session.query(Program, Organization.name.label("org_name"))
            .join(Organization, Organization.org_id == Program.org_id)
            .filter(Program.program_id.in_(prog_ids))
            .all()
        )
        pr_dict = {r.Program.program_id: r for r in pr_rows}
        for uuid in prog_ids:
            if uuid in pr_dict:
                r = pr_dict[uuid]
                prog_results.append(
                    {
                        "program": r.Program,
                        "cip_title": cip_title(r.Program.name),
                        "org_name": r.org_name,
                    }
                )

    # 3. Search Fields
    q_lower = q.lower()
    for code, name in CIP_FAMILY_NAMES.items():
        if q_lower in name.lower() or q_lower in code:
            field_results.append({"code": code, "name": name})
            if len(field_results) >= 5:
                break

    # 4. Search Occupations
    def _fts_occ_ids(query: str, limit: int = 5) -> list[str]:
        safe_q = query.replace('"', "").replace("'", "").strip()
        if not safe_q:
            return []
        try:
            conn = sqlite3.connect(_DB_PATH)
            cur = conn.cursor()
            rows = cur.execute(
                "SELECT soc FROM occupation_fts WHERE occupation_fts MATCH ? GROUP BY soc ORDER BY MIN(rank) LIMIT ?",
                (safe_q + "*", limit),
            ).fetchall()
            conn.close()
            return [r[0] for r in rows]
        except sqlite3.OperationalError:
            return []

    occ_ids = _fts_occ_ids(q, limit=5)
    if occ_ids:
        from models import Occupation
        occ_rows = db.session.query(Occupation).filter(Occupation.soc.in_(occ_ids)).all()
        occ_dict = {o.soc: o for o in occ_rows}
        occ_results = [occ_dict[soc] for soc in occ_ids if soc in occ_dict]

    try:
        from models import SearchEvent

        total = len(org_results) + len(prog_results) + len(field_results) + len(occ_results)
        se = SearchEvent(query_text=q[:500], result_count=total)
        db.session.add(se)
        db.session.commit()
    except Exception:
        db.session.rollback()

    return render_template(
        "search/results.html",
        q=q,
        orgs=org_results,
        progs=prog_results,
        fields=field_results,
        occs=occ_results,
    )
