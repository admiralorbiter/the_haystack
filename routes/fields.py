from flask import render_template
from . import root_bp

@root_bp.route('/fields')
def fields_directory():
    return "CIP Fields Directory (Stub)"

@root_bp.route('/fields/<cip>')
def field_detail(cip):
    return f"CIP Field Detail for {cip} (Stub)"
