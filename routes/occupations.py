"""
Occupations routes — Epic 11/12
Implements Labor-First navigation.
  GET /occupations                 — Directory of jobs sorted by wage/demand
  GET /occupations/<soc>           — Detail profile for an occupation
  GET /occupations/<soc>/tab/...   — View tabs (programs, etc)
"""

from flask import abort, render_template, request
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from models import (
    DatasetSource,
    Occupation,
    OccupationIndustry,
    OccupationProjection,
    OccupationSkill,
    OccupationWage,
    Organization,
    Program,
    ProgramOccupation,
    IndustryQCEW,
    RelatedOccupation,
    OrgFact,
    db,
)
from sqlalchemy import or_
import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent.parent / "db" / "haystack.db"

from .career_grade import get_career_grades
from . import root_bp
from .cip_utils import cip_title
from .qcew_utils import get_qcew_trends

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_occ(soc: str) -> Occupation:
    occ = (
        db.session.query(Occupation)
        .options(joinedload(Occupation.industries))
        .filter_by(soc=soc)
        .first()
    )
    if not occ:
        abort(404)
    return occ

def _get_kc_wage(soc: str) -> OccupationWage | None:
    return (
        db.session.query(OccupationWage)
        .filter(
            OccupationWage.soc == soc,
            OccupationWage.area_type == "msa",
            OccupationWage.area_name.like("%Kansas City%"),
        )
        .first()
    )

def _get_nat_wage(soc: str) -> OccupationWage | None:
    return (
        db.session.query(OccupationWage)
        .filter(
            OccupationWage.soc == soc,
            OccupationWage.area_type == "national",
        )
        .first()
    )


def _get_industry_trends(naics_list: list[str]) -> dict:
    """Thin wrapper around shared get_qcew_trends utility."""
    return get_qcew_trends(naics_list, db.session)

def _get_likely_employers(soc: str):
    inds = db.session.query(OccupationIndustry.naics).filter_by(soc=soc).order_by(OccupationIndustry.pct_of_occupation.desc()).limit(10).all()
    if not inds:
        return [], 0
        
    naics_6 = [i[0] for i in inds if i[0]]
    naics_3 = list(set([n[:3] for n in naics_6 if len(n) >= 3]))
    naics_2 = list(set([n[:2] for n in naics_6 if len(n) >= 2]))
    
    import random

    if naics_3:
        filters_3 = [Organization.naics_code.like(f"{prefix}%") for prefix in naics_3]
        pass1 = (
            db.session.query(Organization, OrgFact.value_text.label('employees'))
            .outerjoin(OrgFact, db.and_(OrgFact.org_id == Organization.org_id, OrgFact.fact_type == 'employees_total_range'))
            .filter(Organization.org_type == 'employer', or_(*filters_3))
            .all()
        )
        if pass1:
            random.shuffle(pass1)
            return pass1[:8], 3  # Level 3: Strong Match

    if naics_2:
        filters_2 = [Organization.naics_code.like(f"{prefix}%") for prefix in naics_2]
        pass2 = (
            db.session.query(Organization, OrgFact.value_text.label('employees'))
            .outerjoin(OrgFact, db.and_(OrgFact.org_id == Organization.org_id, OrgFact.fact_type == 'employees_total_range'))
            .filter(Organization.org_type == 'employer', or_(*filters_2))
            .all()
        )
        if pass2:
            random.shuffle(pass2)
            return pass2[:8], 2  # Level 2: Broad Match
            
    return [], 0


# ---------------------------------------------------------------------------
# Directory — GET /occupations
# ---------------------------------------------------------------------------

@root_bp.route("/occupations")
def occupations_directory():
    sort = request.args.get("sort", "wage")
    zone_filter = request.args.get("zone", None)
    search_query = request.args.get("q", "").strip()
    
    page = max(1, int(request.args.get("page", 1) or 1))
    per_page = 50

    q = (
        db.session.query(Occupation)
        .outerjoin(
            OccupationWage, 
            (OccupationWage.soc == Occupation.soc) & 
            (OccupationWage.area_type == "msa") & 
            (OccupationWage.area_name.like("%Kansas City%"))
        )
        .outerjoin(OccupationProjection)
        .options(joinedload(Occupation.wages), joinedload(Occupation.projection))
    )

    if search_query:
        q = q.filter(
            db.or_(
                Occupation.title.ilike(f"%{search_query}%"),
                Occupation.soc.ilike(f"%{search_query}%")
            )
        )

    if zone_filter and zone_filter.isdigit():
        q = q.filter(Occupation.job_zone == int(zone_filter))

    if sort == "name":
        q = q.order_by(Occupation.title.asc())
    elif sort == "employment":
        q = q.order_by(OccupationWage.employment_count.desc().nulls_last())
    elif sort == "growth":
        q = q.order_by(OccupationProjection.pct_change.desc().nulls_last())
    else:  # default to wage
        sort = "wage"
        q = q.order_by(OccupationWage.median_wage.desc().nulls_last())

    total_count = q.count()
    rows = q.offset((page - 1) * per_page).limit(per_page).all()

    # Pre-calculate KC and National wage for rendering
    occs = []
    for o in rows:
        kc_wage = next((w for w in o.wages if w.area_type == 'msa' and 'Kansas City' in (w.area_name or '')), None)
        nat_wage = next((w for w in o.wages if w.area_type == 'national'), None)
        occs.append({
            "occ": o,
            "kc_wage": kc_wage,
            "nat_wage": nat_wage,
        })

    # Compute KC momentum per SOC via NAICS crosswalk
    # For each occupation, aggregate its top industries' QCEW trends
    all_socs = [o.soc for o in rows]
    # Get all NAICS codes for these SOCs, ordered by their proportion of the occupation
    matrix_rows = (
        db.session.query(OccupationIndustry.soc, OccupationIndustry.naics)
        .filter(OccupationIndustry.soc.in_(all_socs))
        .order_by(OccupationIndustry.soc, OccupationIndustry.pct_of_occupation.desc())
        .all()
    )
    soc_to_naics: dict[str, list[str]] = {}
    for mr in matrix_rows:
        soc_to_naics.setdefault(mr.soc, []).append(mr.naics)

    all_naics = list({n for ns in soc_to_naics.values() for n in ns})
    naics_trends = _get_industry_trends(all_naics)

    # For each SOC, find the trend of its primary employing industry
    occ_trends = {}
    for soc in all_socs:
        for naics in soc_to_naics.get(soc, []):
            t = naics_trends.get(naics)
            if t and t["yoy_pct"] is not None:
                occ_trends[soc] = t
                break  # we take the first one with data (since they are ordered by pct_of_occupation)

    total_pages = max(1, -(-total_count // per_page))

    return render_template(
        "occupations/directory.html",
        occupations=occs,
        total_count=total_count,
        sort=sort,
        zone_filter=zone_filter,
        search_query=search_query,
        page=page,
        total_pages=total_pages,
        occ_trends=occ_trends,
    )


# ---------------------------------------------------------------------------
# Detail — GET /occupations/<soc>
# ---------------------------------------------------------------------------

@root_bp.route("/occupations/<soc>")
def occupation_detail(soc: str):
    occ = _get_occ(soc)
    kc_wage = _get_kc_wage(soc)
    nat_wage = _get_nat_wage(soc)

    # Calculate linked programs offering this occupation
    program_count = (
        db.session.query(func.count(func.distinct(Program.program_id)))
        .join(ProgramOccupation, ProgramOccupation.program_id == Program.program_id)
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(ProgramOccupation.soc == soc, Organization.org_type == "training")
        .scalar() or 0
    )

    provider_count = (
        db.session.query(func.count(func.distinct(Program.org_id)))
        .join(ProgramOccupation, ProgramOccupation.program_id == Program.program_id)
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(ProgramOccupation.soc == soc, Organization.org_type == "training")
        .scalar() or 0
    )

    snapshot = {
        "soc": soc,
        "title": occ.title,
        "job_zone": occ.job_zone,
        "program_count": program_count,
        "provider_count": provider_count,
        "kc_wage": kc_wage,
        "nat_wage": nat_wage,
        "employment": kc_wage.employment_count if kc_wage else None
    }
    
    # Inject Career Grade
    cg_df = get_career_grades()
    if soc in cg_df.index:
        snapshot["grade"] = cg_df.loc[soc, "grade"]
        snapshot["tier"] = cg_df.loc[soc, "tier"]
    else:
        snapshot["grade"] = None
        snapshot["tier"] = None

    local_trends = _get_industry_trends([ind.naics for ind in occ.industries])
    employers, match_level = _get_likely_employers(soc)

    if request.headers.get("HX-Request"):
        return render_template(
            "occupations/partials/tab_overview.html",
            occ=occ,
            kc_wage=kc_wage,
            nat_wage=nat_wage,
            snapshot=snapshot,
            local_trends=local_trends,
            employers=employers,
            match_level=match_level
        )

    return render_template(
        "occupations/detail.html",
        occ=occ,
        snapshot=snapshot,
        kc_wage=kc_wage,
        nat_wage=nat_wage,
        local_trends=local_trends,
        employers=employers,
        match_level=match_level
    )

@root_bp.route("/occupations/<soc>/tab/overview")
def occupation_tab_overview(soc: str):
    occ = _get_occ(soc)
    kc_wage = _get_kc_wage(soc)
    nat_wage = _get_nat_wage(soc)
    local_trends = _get_industry_trends([ind.naics for ind in occ.industries])
    
    # Calculate linked programs for snapshot
    program_count = (
        db.session.query(func.count(func.distinct(Program.program_id)))
        .join(ProgramOccupation, ProgramOccupation.program_id == Program.program_id)
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(ProgramOccupation.soc == soc, Organization.org_type == "training")
        .scalar() or 0
    )
    
    snapshot = {
        "soc": soc,
        "title": occ.title,
        "job_zone": occ.job_zone,
        "program_count": program_count,
        "employment": kc_wage.employment_count if kc_wage else None
    }
    cg_df = get_career_grades()
    if soc in cg_df.index:
        snapshot["grade"] = cg_df.loc[soc, "grade"]
        snapshot["tier"] = cg_df.loc[soc, "tier"]
    else:
        snapshot["grade"] = None
        snapshot["tier"] = None
        
    employers, match_level = _get_likely_employers(soc)
        
    return render_template(
        "occupations/partials/tab_overview.html",
        occ=occ,
        snapshot=snapshot,
        kc_wage=kc_wage,
        nat_wage=nat_wage,
        local_trends=local_trends,
        employers=employers,
        match_level=match_level
    )

@root_bp.route("/occupations/<soc>/tab/programs")
def occupation_tab_programs(soc: str):
    occ = _get_occ(soc)
    
    page = max(1, int(request.args.get("page", 1) or 1))
    per_page = 50

    q = (
        db.session.query(
            Program, 
            Organization.name.label("org_name"),
            ProgramOccupation.confidence
        )
        .join(ProgramOccupation, ProgramOccupation.program_id == Program.program_id)
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(ProgramOccupation.soc == soc, Organization.org_type == "training")
        .order_by(Program.completions.desc().nulls_last())
    )

    total_count = q.count()
    rows = q.offset((page - 1) * per_page).limit(per_page).all()

    programs = [
        {
            "program": r.Program,
            "cip_title": cip_title(r.Program.name),
            "org_name": r.org_name,
            "org_id": r.Program.org_id,
            "confidence": r.confidence,
        }
        for r in rows
    ]
    total_pages = max(1, -(-total_count // per_page))

    return render_template(
        "occupations/partials/tab_programs.html",
        occ=occ,
        programs=programs,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
    )

@root_bp.route("/occupations/<soc>/tab/methods")
def occupation_tab_methods(soc: str):
    occ = _get_occ(soc)
    return render_template(
        "occupations/partials/tab_methods.html",
        occ=occ,
    )

@root_bp.route("/occupations/<soc>/tab/pathways")
def occupation_tab_pathways(soc: str):
    occ = _get_occ(soc)
    kc_wage = _get_kc_wage(soc)
    
    # 1. Fetch related occupations
    related_links = (
        db.session.query(RelatedOccupation, Occupation)
        .join(Occupation, Occupation.soc == RelatedOccupation.related_soc)
        .filter(RelatedOccupation.soc == soc)
        .all()
    )
    
    previous_steps = []
    lateral_moves = []
    next_steps = []
    
    current_zone = occ.job_zone or 0
    current_median = kc_wage.median_wage if kc_wage and kc_wage.median_wage else 0
    
    # Pre-fetch skills for current occupation to calculate skill gaps
    current_skills = {s.element_name: s.importance_score for s in occ.skills}
    
    for rel, rel_occ in related_links:
        target_kc_wage = _get_kc_wage(rel_occ.soc)
        target_median = target_kc_wage.median_wage if target_kc_wage and target_kc_wage.median_wage else 0
        
        target_zone = rel_occ.job_zone or 0
        
        wage_bump = target_median - current_median if (target_median and current_median) else None
        
        # Calculate Skill Gap (Top 3 skills that need the biggest numerical jump)
        target_skills = {s.element_name: s.importance_score for s in rel_occ.skills}
        skill_gaps = []
        for name, target_score in target_skills.items():
            current_score = current_skills.get(name, 0)
            diff = target_score - current_score
            if diff > 0:
                skill_gaps.append({"name": name, "bump": diff})
        skill_gaps = sorted(skill_gaps, key=lambda x: x["bump"], reverse=True)[:3]
        
        # Calculate local debt average for KC programs linked to this target
        # Join program_occupation -> program -> organization (unitid)
        # Then hit scorecard_field_of_study via raw sql
        debt_avg = None
        try:
            conn = sqlite3.connect(_DB_PATH)
            sc_row = conn.execute(
                '''
                SELECT AVG(s.DEBT_ALL_STGP_EVAL_MDN)
                FROM scorecard_field_of_study s
                JOIN organization o ON o.unitid = s.UNITID
                JOIN program p ON p.org_id = o.org_id
                JOIN program_occupation po ON po.program_id = p.program_id
                WHERE po.soc = ? AND s.DEBT_ALL_STGP_EVAL_MDN NOT IN ("PrivacySuppressed", "NULL", "")
                ''',
                (rel_occ.soc,)
            ).fetchone()
            conn.close()
            if sc_row and sc_row[0]:
                debt_avg = int(sc_row[0])
        except Exception:
            pass
        
        item = {
            "occ": rel_occ,
            "kc_wage": target_kc_wage,
            "wage_bump": wage_bump,
            "wage_bump_pct": (wage_bump / current_median * 100) if wage_bump and current_median else 0,
            "skill_gaps": skill_gaps,
            "debt_avg": debt_avg,
            "index_score": rel.index_score
        }
        
        if target_zone < current_zone:
            previous_steps.append(item)
        elif target_zone == current_zone:
            lateral_moves.append(item)
        else:
            # Strict Economic Filter for Next Steps: > 10% wage bump required.
            if item["wage_bump_pct"] >= 10:
                next_steps.append(item)
            elif item["wage_bump"] is None:
                # If we don't have wage data, we'll keep it as a potential step
                next_steps.append(item)
            else:
                # Looks like a step up in zone, but not a 10% wage bump.
                lateral_moves.append(item)
                
    # Sort them by wage bump or index score
    previous_steps = sorted(previous_steps, key=lambda x: x["index_score"] or 0, reverse=True)[:10]
    lateral_moves = sorted(lateral_moves, key=lambda x: x["index_score"] or 0, reverse=True)[:10]
    next_steps = sorted(next_steps, key=lambda x: x["wage_bump"] or x["index_score"] or 0, reverse=True)
    
    return render_template(
        "occupations/partials/tab_pathways.html",
        occ=occ,
        kc_wage=kc_wage,
        previous_steps=previous_steps,
        lateral_moves=lateral_moves,
        next_steps=next_steps
    )

