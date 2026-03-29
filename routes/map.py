import json
from collections import defaultdict

from flask import jsonify, render_template, request
from sqlalchemy import func

from models import Organization, Program, Region, db

from . import root_bp
from .providers import _CIP_FAMILY_NAMES


@root_bp.route("/map")
def map_view():
    # Only pick training providers
    all_creds = (
        db.session.query(Program.credential_type)
        .filter(
            Program.org_id.in_(
                db.session.query(Organization.org_id).filter_by(org_type="training")
            )
        )
        .distinct()
        .order_by(Program.credential_type)
        .all()
    )

    region = db.session.query(Region).filter_by(slug="kansas-city").first()
    default_lat = region.default_lat if region and region.default_lat else 39.0997
    default_lon = region.default_lon if region and region.default_lon else -94.5786
    default_zoom = region.default_zoom if region and region.default_zoom else 10

    cred_filter = request.args.get("cred", "").strip()
    cip_filter = request.args.get("cip", "").strip()

    return render_template(
        "map/index.html",
        all_creds=[r.credential_type for r in all_creds],
        cred_filter=cred_filter,
        cip_filter=cip_filter,
        default_lat=default_lat,
        default_lon=default_lon,
        default_zoom=default_zoom,
    )
