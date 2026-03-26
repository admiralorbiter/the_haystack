from . import root_bp


@root_bp.route("/compare/providers")
def compare_providers():
    return "Compare Providers View (Stub)"


@root_bp.route("/compare/programs")
def compare_programs():
    return "Compare Programs View (Stub)"
