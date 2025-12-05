"""add_generalized_to_strategies

Revision ID: add_generalized_to_strategies
Revises: 6aec9b694526
Create Date: 2025-01-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_generalized_to_strategies'
down_revision = '6aec9b694526'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add generalized field
    op.add_column('user_strategies', sa.Column('generalized', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    # Add per_symbol_performance field
    op.add_column('user_strategies', sa.Column('per_symbol_performance', postgresql.JSON(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('user_strategies', 'per_symbol_performance')
    op.drop_column('user_strategies', 'generalized')

