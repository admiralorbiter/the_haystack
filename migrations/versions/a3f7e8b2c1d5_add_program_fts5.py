"""Add program_fts FTS5 virtual table and sync triggers

Revision ID: a3f7e8b2c1d5
Revises: 6ca14d68c2f6
Create Date: 2026-03-26

Implements a SQLite FTS5 full-text search index over the program table.
Indexed columns:
  - program_id  (for JOIN back to program table)
  - name        (CIP title portion — displayed in results)
  - cip         (raw CIP code, e.g. "51.3801")
  - org_name    (denormalized from organization — allows "Donnelly" to surface programs)

Uses the 'porter' tokenizer for English stemming (nursing → nurse).
Triggers on program INSERT/UPDATE/DELETE keep the FTS index synchronized
automatically, so no loader changes are needed.

Downgrade drops the FTS table and all associated triggers.
"""
from typing import Sequence, Union
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a3f7e8b2c1d5'
down_revision: Union[str, Sequence[str], None] = '6ca14d68c2f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create program_fts virtual table and sync triggers."""

    # FTS5 virtual table — content='' means it's a "contentless" shadow table.
    # We use content=program so SQLite can rebuild it from the real table,
    # but store our own denormalized org_name column via triggers.
    op.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS program_fts USING fts5(
            program_id UNINDEXED,
            name,
            cip UNINDEXED,
            org_name,
            tokenize='porter ascii'
        )
    """)

    # Populate FTS from existing data (one-time backfill)
    op.execute("""
        INSERT INTO program_fts (program_id, name, cip, org_name)
        SELECT p.program_id, p.name, p.cip, o.name
        FROM program p
        JOIN organization o ON p.org_id = o.org_id
    """)

    # INSERT trigger — fires when a new program row is added
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS program_fts_ai
        AFTER INSERT ON program BEGIN
            INSERT INTO program_fts (program_id, name, cip, org_name)
            SELECT NEW.program_id, NEW.name, NEW.cip, o.name
            FROM organization o WHERE o.org_id = NEW.org_id;
        END
    """)

    # DELETE trigger — removes the matching FTS row
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS program_fts_ad
        AFTER DELETE ON program BEGIN
            DELETE FROM program_fts WHERE program_id = OLD.program_id;
        END
    """)

    # UPDATE trigger — delete old FTS row and insert fresh one
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS program_fts_au
        AFTER UPDATE ON program BEGIN
            DELETE FROM program_fts WHERE program_id = OLD.program_id;
            INSERT INTO program_fts (program_id, name, cip, org_name)
            SELECT NEW.program_id, NEW.name, NEW.cip, o.name
            FROM organization o WHERE o.org_id = NEW.org_id;
        END
    """)


def downgrade() -> None:
    """Drop FTS triggers and virtual table."""
    op.execute("DROP TRIGGER IF EXISTS program_fts_au")
    op.execute("DROP TRIGGER IF EXISTS program_fts_ad")
    op.execute("DROP TRIGGER IF EXISTS program_fts_ai")
    op.execute("DROP TABLE IF EXISTS program_fts")
