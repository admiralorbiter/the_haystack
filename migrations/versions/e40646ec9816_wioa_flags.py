"""wioa_flags

Revision ID: e40646ec9816
Revises: d6be513242b8
Create Date: 2026-03-28 10:40:08.499372

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e40646ec9816'
down_revision: Union[str, Sequence[str], None] = 'd6be513242b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('program', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_wioa_eligible', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('is_apprenticeship', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('program', schema=None) as batch_op:
        batch_op.drop_column('is_apprenticeship')
        batch_op.drop_column('is_wioa_eligible')
