"""Add occupation FTS

Revision ID: de0edbe1bb28
Revises: 4752b9ad344f
Create Date: 2026-03-29 11:59:56.114301

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'de0edbe1bb28'
down_revision: Union[str, Sequence[str], None] = '4752b9ad344f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create occupation_fts virtual table and sync triggers."""
    op.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS occupation_fts USING fts5(
            soc UNINDEXED,
            searchable_text,
            tokenize='porter ascii'
        )
    """)

    op.execute("""
        INSERT INTO occupation_fts (soc, searchable_text)
        SELECT soc, title FROM occupation
    """)

    op.execute("""
        INSERT INTO occupation_fts (soc, searchable_text)
        SELECT soc, alias_title FROM occupation_alias
    """)

    # Triggers for Occupation
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS occupation_fts_ai
        AFTER INSERT ON occupation BEGIN
            INSERT INTO occupation_fts (soc, searchable_text)
            VALUES (NEW.soc, NEW.title);
        END
    """)

    op.execute("""
        CREATE TRIGGER IF NOT EXISTS occupation_fts_ad
        AFTER DELETE ON occupation BEGIN
            DELETE FROM occupation_fts WHERE soc = OLD.soc AND searchable_text = OLD.title;
        END
    """)

    op.execute("""
        CREATE TRIGGER IF NOT EXISTS occupation_fts_au
        AFTER UPDATE ON occupation BEGIN
            DELETE FROM occupation_fts WHERE soc = OLD.soc AND searchable_text = OLD.title;
            INSERT INTO occupation_fts (soc, searchable_text)
            VALUES (NEW.soc, NEW.title);
        END
    """)

    # Triggers for OccupationAlias
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS occ_alias_fts_ai
        AFTER INSERT ON occupation_alias BEGIN
            INSERT INTO occupation_fts (soc, searchable_text)
            VALUES (NEW.soc, NEW.alias_title);
        END
    """)

    op.execute("""
        CREATE TRIGGER IF NOT EXISTS occ_alias_fts_ad
        AFTER DELETE ON occupation_alias BEGIN
            DELETE FROM occupation_fts WHERE soc = OLD.soc AND searchable_text = OLD.alias_title;
        END
    """)

    op.execute("""
        CREATE TRIGGER IF NOT EXISTS occ_alias_fts_au
        AFTER UPDATE ON occupation_alias BEGIN
            DELETE FROM occupation_fts WHERE soc = OLD.soc AND searchable_text = OLD.alias_title;
            INSERT INTO occupation_fts (soc, searchable_text)
            VALUES (NEW.soc, NEW.alias_title);
        END
    """)


def downgrade() -> None:
    """Drop FTS triggers and virtual table."""
    op.execute("DROP TRIGGER IF EXISTS occ_alias_fts_au")
    op.execute("DROP TRIGGER IF EXISTS occ_alias_fts_ad")
    op.execute("DROP TRIGGER IF EXISTS occ_alias_fts_ai")
    op.execute("DROP TRIGGER IF EXISTS occupation_fts_au")
    op.execute("DROP TRIGGER IF EXISTS occupation_fts_ad")
    op.execute("DROP TRIGGER IF EXISTS occupation_fts_ai")
    op.execute("DROP TABLE IF EXISTS occupation_fts")
