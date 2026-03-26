from . import root_bp


@root_bp.route("/map")
def map_view():
    return "Map View Workspace (Stub)"
