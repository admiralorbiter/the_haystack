from flask import Blueprint, render_template

# Define root blueprint
root_bp = Blueprint("root", __name__)


@root_bp.route("/")
def index():
    return render_template("home.html")


# These imports must be AFTER the blueprint definition — this is Flask's required pattern.
# ruff: noqa: E402, F401
from . import briefing, compare, fields, guided_search, map, programs, providers  # noqa: E402, F401
