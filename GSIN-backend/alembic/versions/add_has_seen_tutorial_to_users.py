"""Add has_seen_tutorial field to users table

Revision ID: add_has_seen_tutorial
Revises: fd9605a69669
Create Date: 2025-11-21 20:22:57.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_has_seen_tutorial'
down_revision: Union[str, None] = '0a9a7ad98d32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add has_seen_tutorial column to users table
    op.add_column('users', sa.Column('has_seen_tutorial', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    # Remove has_seen_tutorial column from users table
    op.drop_column('users', 'has_seen_tutorial')

