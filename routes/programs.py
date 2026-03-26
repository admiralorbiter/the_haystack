from flask import render_template
from . import root_bp

@root_bp.route('/programs')
def programs_directory():
    return "Program Directory (Stub)"

@root_bp.route('/programs/<program_id>')
def program_detail(program_id):
    return "Program Detail (Stub)"
