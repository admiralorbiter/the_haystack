"""
Briefing Builder routes.

INTENT (Epic 13):
    Users can ★ any Provider, Program, Occupation, or Industry.
    This route manages the briefing collection in the Flask session and renders the final print page.

ROUTES:
    POST /briefing/toggle    -> HTMX: add/remove an item to the session briefing
    POST /briefing/title     -> HTMX: update the briefing title
    GET  /briefing           -> full briefing review page
    GET  /briefing/print     -> print-optimized HTML one-pager with DB summary queries

Storage (V1): Flask session
"""

from flask import render_template, request, session, url_for
from . import root_bp
from models import db, Organization, Program, Occupation, IndustryQCEW, OccupationIndustry
from sqlalchemy import func

def _get_briefing():
    """Helper to safely fetch the briefing list from the session."""
    return session.get("briefing", [])

def _save_briefing(b_list):
    """Helper to safely save the briefing list to the session."""
    session["briefing"] = b_list
    session.modified = True

@root_bp.route("/briefing")
def briefing_page():
    briefings = _get_briefing()
    
    # Group the items by type for the review UI
    grouped = {
        "provider": [],
        "program": [],
        "occupation": [],
        "industry": []
    }
    for item in briefings:
        t = item.get("type")
        if t in grouped:
            grouped[t].append(item)
            
    title = session.get("briefing_title", "Untitled Research Briefing")
    
    return render_template(
        "briefing/index.html", 
        briefings=briefings,
        grouped=grouped,
        title=title
    )

@root_bp.route("/briefing/title", methods=["POST"])
def briefing_title():
    title = request.form.get("title", "").strip()
    if title:
        session["briefing_title"] = title
    return f"""<span class="badge success" hx-swap-oob="outerHTML:#title-saved-badge">Saved ✓</span>"""

@root_bp.route("/briefing/toggle", methods=["POST"])
def briefing_toggle():
    entity_type = request.form.get("entity_type")
    entity_id = request.form.get("entity_id")
    entity_name = request.form.get("entity_name")
    
    if not (entity_type and entity_id):
        return "Missing data", 400
        
    b_list = _get_briefing()
    
    # Check if already exists
    index_to_remove = None
    for i, item in enumerate(b_list):
        if item.get("type") == entity_type and str(item.get("id")) == str(entity_id):
            index_to_remove = i
            break
            
    if index_to_remove is not None:
        # It's in the list, so we remove it (toggle off)
        b_list.pop(index_to_remove)
        is_saved = False
    else:
        # It's not in the list, add it (toggle on)
        b_list.append({
            "type": entity_type,
            "id": entity_id,
            "name": entity_name or "Unknown Entity"
        })
        is_saved = True
        
    _save_briefing(b_list)
    
    # Render just the button to swap it back
    return render_template("partials/briefing_btn.html", 
        entity_type=entity_type, 
        entity_id=entity_id, 
        entity_name=entity_name, 
        is_saved=is_saved
    )

@root_bp.route("/briefing/print")
def briefing_print():
    briefings = _get_briefing()
    title = session.get("briefing_title", "Untitled Research Briefing")
    
    # We will build rich data dicts by querying the DB for the saved elements
    providers = []
    programs = []
    occupations = []
    industries = []
    
    # Pull IDs
    provider_ids = [item["id"] for item in briefings if item.get("type") == "provider"]
    prog_ids = [item["id"] for item in briefings if item.get("type") == "program"]
    occ_socs = [item["id"] for item in briefings if item.get("type") == "occupation"]
    ind_naics = [item["id"] for item in briefings if item.get("type") == "industry"]
    
    # 1. Fetch Providers
    if provider_ids:
        # Load the models, their grad rates, and IPEDS completions
        orgs = db.session.query(Organization).filter(Organization.org_id.in_(provider_ids)).all()
        for org in orgs:
            # Quick summary calculation for programs
            prog_stats = db.session.query(
                func.count(Program.program_id).label("count"),
                func.sum(Program.completions).label("completions")
            ).filter(Program.org_id == org.org_id).first()
            
            providers.append({
                "name": org.name,
                "location": f"{org.city}, {org.state}" if org.city and org.state else org.city or org.state or "Unknown",
                "type_name": org.org_type,
                "programs": prog_stats.count or 0,
                "completions": prog_stats.completions or 0,
            })
            
    # 2. Fetch Programs
    if prog_ids:
        progs = db.session.query(Program, Organization).join(Organization).filter(Program.program_id.in_(prog_ids)).all()
        for prog, org in progs:
            programs.append({
                "title": prog.name,
                "provider": org.name,
                "cip": prog.cip,
                "credential": prog.credential_type,
                "completions": prog.completions,
            })

    # 3. Fetch Occupations
    if occ_socs:
        from routes.career_grade import get_career_grades
        from routes.occupations import _get_kc_wage
        
        cg_df = get_career_grades()
        occs = db.session.query(Occupation).filter(Occupation.soc.in_(occ_socs)).all()
        
        for occ in occs:
            kc_wage = _get_kc_wage(occ.soc)
            proj = db.session.query(OccupationProjection).filter_by(soc=occ.soc).first()
            
            grade = cg_df.loc[occ.soc, "grade"] if occ.soc in cg_df.index else None
            
            occupations.append({
                "title": occ.title,
                "soc": occ.soc,
                "grade": grade,
                "wage": kc_wage.median_wage if kc_wage else None,
                "openings": proj.annual_openings if proj else None,
                "growth": proj.pct_change if proj else None
            })
            
    # 4. Fetch Industries
    if ind_naics:
        # Needs unique industry logic since we use OccupationIndustry mapped titles and QCEW counts
        title_map = {
            r.naics: r.industry_title
            for r in db.session.query(OccupationIndustry.naics, OccupationIndustry.industry_title).filter(OccupationIndustry.naics.in_(ind_naics)).all()
        }
        
        for naics in ind_naics:
            # Get latest QCEW summary
            q = db.session.query(
                IndustryQCEW.employment, 
                IndustryQCEW.avg_weekly_wage,
                IndustryQCEW.qcew_year,
                IndustryQCEW.qcew_qtr
            ).filter(IndustryQCEW.naics == naics).order_by(IndustryQCEW.qcew_year.desc(), IndustryQCEW.qcew_qtr.desc()).first()
            
            industries.append({
                "title": title_map.get(naics, f"NAICS {naics}"),
                "naics": naics,
                "employment": q.employment if q else None,
                "wage": q.avg_weekly_wage if q else None,
                "latest_qtr": f"{q.qcew_year} Q{q.qcew_qtr}" if q else "No data"
            })
            
    from datetime import datetime
    return render_template(
        "briefing/print.html",
        title=title,
        providers=providers,
        programs=programs,
        occupations=occupations,
        industries=industries,
        current_time=datetime.now()
    )
