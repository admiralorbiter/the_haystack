# The Haystack

The Haystack is a modular, place-based intelligence platform that maps the interconnected systems of any region — organizations, programs, supply chains, funding flows, workforce pathways, and civic conditions — through a unified, entity-centered UI.

**V1 starts in Kansas City** with training providers and programs from IPEDS. The architecture is multi-region from day one: add a new entry to the `region_county` table, run the loaders with `--region`, and Haystack activates for a new metro.

## Tech Stack
- **Backend:** Python + Flask
- **Database:** SQLite + SQLAlchemy + Alembic
- **Frontend:** Jinja2 + HTMX
- **Styling:** Vanilla CSS Custom Properties (Civic-Tech Theme)

## Quick Start

1. **Verify Python 3.11+ is installed.**
2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Run the local development server:**
   ```bash
   flask run
   ```

## Documentation
All internal project plans, dataset onboarding templates, AI collaboration guides, and UI playbooks are contained in the `/docs` directory. Look at `docs/HAYSTACK_MASTER_PLAN.md` for the overarching project philosophy.
