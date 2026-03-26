from flask import render_template
from . import root_bp
from mock_data import MOCK_PROVIDER

@root_bp.route('/providers')
def providers_directory():
    return "Provider Directory (Stub)"

@root_bp.route('/providers/mock')
def provider_detail_mock():
    return render_template('providers/detail.html', provider=MOCK_PROVIDER)

@root_bp.route('/providers/<org_id>')
def provider_detail(org_id):
    return "Provider Detail (Stub)"
