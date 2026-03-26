from flask import Blueprint, render_template

# Define root blueprint
root_bp = Blueprint('root', __name__)

@root_bp.route('/')
def index():
    return render_template('home.html')

# Import specific entity routes to attach them to the app
from . import providers
from . import programs
from . import fields
from . import map
from . import compare
from . import guided_search
from . import briefing
