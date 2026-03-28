"""
Field of Study (CIP) routes — Epic 5

Implements:
  GET /fields                               — directory: all CIP families in KC, sorted by completions
  GET /fields/<cip_family>                  — detail page (2-digit code e.g. '51', '52')
  GET /fields/<cip_family>/tab/overview     — HTMX: top programs, providers, occupations
  GET /fields/<cip_family>/tab/programs     — HTMX: full paginated program table for this field
  GET /fields/<cip_family>/tab/occupations  — HTMX: all linked occupations with program count
  GET /fields/<cip_family>/tab/methods      — HTMX: CIP taxonomy, data methods
"""

from flask import abort, render_template, request
from sqlalchemy import func

from models import (
    DatasetSource, Occupation, Organization,
    Program, ProgramOccupation, db,
)

from .cip_utils import CIP_FAMILY_NAMES, cip_family_label, cip_title
from .programs import _ipeds_cip_enrollment_by_family
from . import root_bp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_family(cip_family: str) -> str:
    """
    Validate and normalize a 2-digit CIP family code.
    Accepts '51', '51.3801' (strips to '51'), '9' (zero-pads to '09').
    Returns normalized 2-digit string, or aborts 404 if unknown.
    """
    # Strip to first two digits
    code = cip_family.split(".")[0][:2].zfill(2)
    if code not in CIP_FAMILY_NAMES:
        abort(404)
    return code


def _field_snapshot(cip_family: str) -> dict:
    """Compute snapshot strip metrics for a CIP family."""
    like = f"{cip_family}.%"

    program_count = (
        db.session.query(func.count(Program.program_id))
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(Program.cip.like(like), Organization.org_type == "training")
        .scalar() or 0
    )

    provider_count = (
        db.session.query(func.count(func.distinct(Program.org_id)))
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(Program.cip.like(like), Organization.org_type == "training")
        .scalar() or 0
    )

    total_completions = (
        db.session.query(func.sum(Program.completions))
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(Program.cip.like(like), Organization.org_type == "training")
        .scalar()
    )

    # Linked occupations: distinct SOC codes across all programs in this family
    occ_count = (
        db.session.query(func.count(func.distinct(ProgramOccupation.soc)))
        .join(Program, Program.program_id == ProgramOccupation.program_id)
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(Program.cip.like(like), Organization.org_type == "training")
        .scalar() or 0
    )

    # Top credential: most common credential_type in this family
    top_cred_row = (
        db.session.query(Program.credential_type, func.count(Program.program_id).label("n"))
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(Program.cip.like(like), Organization.org_type == "training")
        .group_by(Program.credential_type)
        .order_by(func.count(Program.program_id).desc())
        .first()
    )
    top_credential = top_cred_row.credential_type if top_cred_row else "—"

    ds = (
        db.session.query(DatasetSource)
        .filter(DatasetSource.source_id.like("ipeds_c_%"))
        .order_by(DatasetSource.loaded_at.desc())
        .first()
    )

    return {
        "cip_family": cip_family,
        "family_label": CIP_FAMILY_NAMES.get(cip_family, cip_family),
        "program_count": program_count,
        "provider_count": provider_count,
        "total_completions": total_completions,
        "linked_occupations": occ_count,
        "top_credential": top_credential,
        "data_source": ds.name if ds else "IPEDS",
        "data_as_of": ds.loaded_at.strftime("%Y-%m-%d") if ds and ds.loaded_at else "Unknown",
    }


def _top_programs(cip_family: str, limit: int = 10):
    """Top programs in this CIP family by completions."""
    rows = (
        db.session.query(Program, Organization.name.label("org_name"))
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(Program.cip.like(f"{cip_family}.%"), Organization.org_type == "training")
        .order_by(Program.completions.desc().nulls_last())
        .limit(limit)
        .all()
    )
    return [
        {
            "program": r.Program,
            "cip_title": cip_title(r.Program.name),
            "org_name": r.org_name,
        }
        for r in rows
    ]


def _top_providers(cip_family: str, limit: int = 5):
    """Providers offering programs in this CIP family, sorted by completions."""
    rows = (
        db.session.query(
            Organization,
            func.count(Program.program_id).label("prog_count"),
            func.sum(Program.completions).label("completions"),
        )
        .join(Program, Program.org_id == Organization.org_id)
        .filter(Program.cip.like(f"{cip_family}.%"), Organization.org_type == "training")
        .group_by(Organization.org_id)
        .order_by(func.sum(Program.completions).desc().nulls_last())
        .limit(limit)
        .all()
    )
    return [
        {
            "org": r.Organization,
            "prog_count": r.prog_count,
            "completions": r.completions,
        }
        for r in rows
    ]


def _top_occupations(cip_family: str, limit: int = 8):
    """
    Distinct occupations linked to programs in this CIP family,
    sorted by the number of programs that map to them.
    """
    rows = (
        db.session.query(
            Occupation,
            func.count(func.distinct(ProgramOccupation.program_id)).label("prog_count"),
        )
        .join(ProgramOccupation, ProgramOccupation.soc == Occupation.soc)
        .join(Program, Program.program_id == ProgramOccupation.program_id)
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(Program.cip.like(f"{cip_family}.%"), Organization.org_type == "training")
        .group_by(Occupation.soc)
        .order_by(func.count(func.distinct(ProgramOccupation.program_id)).desc())
        .limit(limit)
        .all()
    )
    return [{"occ": r.Occupation, "prog_count": r.prog_count} for r in rows]


# ---------------------------------------------------------------------------
# Directory — GET /fields
# ---------------------------------------------------------------------------

@root_bp.route("/fields")
def fields_directory():
    sort = request.args.get("sort", "completions")

    # Aggregate by 2-digit CIP family using func.substr
    family_col = func.substr(Program.cip, 1, 2).label("family")
    q = (
        db.session.query(
            family_col,
            func.count(Program.program_id).label("program_count"),
            func.count(func.distinct(Program.org_id)).label("provider_count"),
            func.sum(Program.completions).label("total_completions"),
        )
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(Organization.org_type == "training", Program.cip.contains("."))
        .group_by(family_col)
    )

    if sort == "programs":
        q = q.order_by(func.count(Program.program_id).desc())
    elif sort == "providers":
        q = q.order_by(func.count(func.distinct(Program.org_id)).desc())
    elif sort == "name":
        q = q.order_by(family_col.asc())
    else:
        sort = "completions"
        q = q.order_by(func.sum(Program.completions).desc().nulls_last())

    rows = q.all()

    fields = [
        {
            "cip_family": r.family,
            "family_label": CIP_FAMILY_NAMES.get(r.family, f"CIP {r.family}"),
            "program_count": r.program_count,
            "provider_count": r.provider_count,
            "total_completions": r.total_completions,
            # True when all programs in this field are WIOA-only (no IPEDS-sourced data)
            "wioa_only": r.total_completions is None and r.program_count > 0,
        }
        for r in rows
        if r.family and r.family in CIP_FAMILY_NAMES  # skip unknown/aggregate families
    ]

    return render_template(
        "fields/directory.html",
        fields=fields,
        total_count=len(fields),
        sort=sort,
    )


# ---------------------------------------------------------------------------
# Detail — GET /fields/<cip_family>
# ---------------------------------------------------------------------------

@root_bp.route("/fields/<cip_family>")
def field_detail(cip_family: str):
    code = _validate_family(cip_family)
    snapshot = _field_snapshot(code)
    top_programs = _top_programs(code, limit=10)
    top_providers = _top_providers(code, limit=5)
    top_occs = _top_occupations(code, limit=8)
    enrollment_by_cip = _ipeds_cip_enrollment_by_family(code, limit=10)

    if request.headers.get("HX-Request"):
        return render_template(
            "fields/partials/tab_overview.html",
            cip_family=code,
            snapshot=snapshot,
            top_programs=top_programs,
            top_providers=top_providers,
            top_occs=top_occs,
            enrollment_by_cip=enrollment_by_cip,
        )

    return render_template(
        "fields/detail.html",
        cip_family=code,
        snapshot=snapshot,
        top_programs=top_programs,
        top_providers=top_providers,
        top_occs=top_occs,
        enrollment_by_cip=enrollment_by_cip,
    )


# ---------------------------------------------------------------------------
# HTMX tab fragments
# ---------------------------------------------------------------------------

@root_bp.route("/fields/<cip_family>/tab/overview")
def field_tab_overview(cip_family: str):
    code = _validate_family(cip_family)
    snapshot = _field_snapshot(code)
    enrollment_by_cip = _ipeds_cip_enrollment_by_family(code, limit=10)
    return render_template(
        "fields/partials/tab_overview.html",
        cip_family=code,
        snapshot=snapshot,
        top_programs=_top_programs(code, limit=10),
        top_providers=_top_providers(code, limit=5),
        top_occs=_top_occupations(code, limit=8),
        enrollment_by_cip=enrollment_by_cip,
    )


@root_bp.route("/fields/<cip_family>/tab/programs")
def field_tab_programs(cip_family: str):
    code = _validate_family(cip_family)
    page = max(1, int(request.args.get("page", 1) or 1))
    per_page = 50

    q = (
        db.session.query(Program, Organization.name.label("org_name"))
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(Program.cip.like(f"{code}.%"), Organization.org_type == "training")
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
        }
        for r in rows
    ]
    total_pages = max(1, -(-total_count // per_page))

    return render_template(
        "fields/partials/tab_programs.html",
        cip_family=code,
        programs=programs,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
    )


@root_bp.route("/fields/<cip_family>/tab/occupations")
def field_tab_occupations(cip_family: str):
    code = _validate_family(cip_family)
    rows = (
        db.session.query(
            Occupation,
            func.count(func.distinct(ProgramOccupation.program_id)).label("prog_count"),
        )
        .join(ProgramOccupation, ProgramOccupation.soc == Occupation.soc)
        .join(Program, Program.program_id == ProgramOccupation.program_id)
        .join(Organization, Organization.org_id == Program.org_id)
        .filter(Program.cip.like(f"{code}.%"), Organization.org_type == "training")
        .group_by(Occupation.soc)
        .order_by(func.count(func.distinct(ProgramOccupation.program_id)).desc())
        .all()
    )
    occ_links = [{"occ": r.Occupation, "prog_count": r.prog_count} for r in rows]
    return render_template(
        "fields/partials/tab_occupations.html",
        cip_family=code,
        snapshot=_field_snapshot(code),
        occ_links=occ_links,
    )


@root_bp.route("/fields/<cip_family>/tab/methods")
def field_tab_methods(cip_family: str):
    code = _validate_family(cip_family)
    return render_template(
        "fields/partials/tab_methods.html",
        cip_family=code,
        family_label=CIP_FAMILY_NAMES.get(code, code),
    )
