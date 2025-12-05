"""Add broker_connected and broker_provider fields to users table

Revision ID: add_broker_fields
Revises: add_has_seen_tutorial
Create Date: 2025-11-21 20:30:50.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_broker_fields'
down_revision: Union[str, None] = 'add_has_seen_tutorial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add broker_connected column to users table
    op.add_column('users', sa.Column('broker_connected', sa.Boolean(), nullable=False, server_default='false'))
    # Add broker_provider column to users table
    op.add_column('users', sa.Column('broker_provider', sa.String(length=32), nullable=True))


def downgrade() -> None:
    # Remove broker columns from users table
    op.drop_column('users', 'broker_provider')
    op.drop_column('users', 'broker_connected')

