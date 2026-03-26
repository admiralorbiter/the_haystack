from flask import abort, render_template

from mock_data import MOCK_PROVIDER

from . import root_bp


@root_bp.route("/providers")
def providers_directory():
    return "Provider Directory (Stub)"


@root_bp.route("/providers/mock")
def provider_detail_mock():
    return render_template("providers/detail.html", provider=MOCK_PROVIDER)


@root_bp.route("/providers/<org_id>")
def provider_detail(org_id):
    # Stub: until DB is wired (Epic 3), all real IDs return 404.
    # This ensures the test suite correctly validates 404 handling
    # from day one, not just after the DB is built.
    abort(404)
