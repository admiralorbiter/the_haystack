"""
Briefing Builder route stub.

INTENT (Epic 12):
    Users can ★ any stat card, entity card, or comparison row as they browse.
    This route manages the briefing collection and renders the final briefing page.

ROUTES:
    POST /briefing/add       -> HTMX: add an item to the session briefing
    POST /briefing/remove    -> HTMX: remove an item
    GET  /briefing           -> full briefing page (collect + organize)
    GET  /briefing/export    -> print-optimized HTML one-pager

Storage (V1): Flask session
Storage (V2): Database-backed for logged-in users

See HAYSTACK_EPICS.md Epic 12 for full design spec.
"""
from flask import session, jsonify
from . import root_bp

@root_bp.route('/briefing')
def briefing_page():
    return "Briefing Builder (Stub — Epic 12)"

@root_bp.route('/briefing/add', methods=['POST'])
def briefing_add():
    # V1 stub: returns 200 so the HTMX ★ button feels responsive
    return '', 200
