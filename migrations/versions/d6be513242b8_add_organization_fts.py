"""add organization_fts

Revision ID: d6be513242b8
Revises: a3f7e8b2c1d5
Create Date: 2026-03-27 12:26:14.326766

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6be513242b8'
down_revision: Union[str, Sequence[str], None] = 'a3f7e8b2c1d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create organization_fts virtual table and sync triggers."""
    op.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS organization_fts USING fts5(
            org_id UNINDEXED,
            name,
            tokenize='porter ascii'
        )
    """)

    op.execute("""
        INSERT INTO organization_fts (org_id, name)
        SELECT org_id, name FROM organization
    """)

    op.execute("""
        CREATE TRIGGER IF NOT EXISTS organization_fts_ai
        AFTER INSERT ON organization BEGIN
            INSERT INTO organization_fts (org_id, name)
            VALUES (NEW.org_id, NEW.name);
        END
    """)

    op.execute("""
        CREATE TRIGGER IF NOT EXISTS organization_fts_ad
        AFTER DELETE ON organization BEGIN
            DELETE FROM organization_fts WHERE org_id = OLD.org_id;
        END
    """)

    op.execute("""
        CREATE TRIGGER IF NOT EXISTS organization_fts_au
        AFTER UPDATE ON organization BEGIN
            DELETE FROM organization_fts WHERE org_id = OLD.org_id;
            INSERT INTO organization_fts (org_id, name)
            VALUES (NEW.org_id, NEW.name);
        END
    """)


def downgrade() -> None:
    """Drop FTS triggers and virtual table."""
    op.execute("DROP TRIGGER IF EXISTS organization_fts_au")
    op.execute("DROP TRIGGER IF EXISTS organization_fts_ad")
    op.execute("DROP TRIGGER IF EXISTS organization_fts_ai")
    op.execute("DROP TABLE IF EXISTS organization_fts")
