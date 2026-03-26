"""
Guided / Inverse Search route stub.

INTENT (Epic 10):
    Instead of users knowing what they're looking for, this route lets them
    describe a *need* and traces backward through the entity model to find
    providers and programs that satisfy it.

    Step 1: What outcome do you need?
    Step 2: Refine (depends on choice)
    Step 3: Pre-filtered directory results

ROUTE:
    GET /search/guided              -> renders the 3-step guided form
    GET /search/guided?step=2&...  -> HTMX fragment: next step
    GET /search/guided/results      -> HTMX fragment: filtered directory result list

See HAYSTACK_EPICS.md Epic 10 for full design spec.
"""
from . import root_bp

@root_bp.route('/search/guided')
def guided_search():
    return "Guided Search (Stub — Epic 10)"
