from flask import render_template, request
from sqlalchemy import func

from models import DatasetSource, Organization, Program, RegionCounty, db
from routes.cip_utils import CIP_FAMILY_NAMES

from . import root_bp


@root_bp.route("/network")
def network_page():
    # Pass CIP and County dictionaries for the filter dropdowns
    all_counties = (
        db.session.query(
            RegionCounty.county_fips, RegionCounty.county_name, RegionCounty.state
        )
        .filter(
            RegionCounty.county_fips.in_(
                db.session.query(Organization.county_fips)
                .filter_by(org_type="training", is_active=True)
                .filter(Organization.county_fips.isnot(None))
            )
        )
        .order_by(RegionCounty.county_name)
        .all()
    )

    # Base query for nodes limits
    limit = int(request.args.get("limit", 50))
    edge_mode = request.args.get("edge", "both").lower()

    # Get data-as-of date
    ds_hd = (
        db.session.query(DatasetSource)
        .filter(DatasetSource.source_id.like("ipeds_hd_%"))
        .order_by(DatasetSource.loaded_at.desc())
        .first()
    )

    return render_template(
        "network/index.html",
        cip_families=CIP_FAMILY_NAMES,
        all_counties=all_counties,
        edge_mode=edge_mode,
        node_count=limit,
        ds_hd=ds_hd,
    )
