"""add_paper_account_profit_target_proposable

Revision ID: 627e159e11c2
Revises: 2611532bb11b
Create Date: 2025-11-18 19:58:59.482790

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '627e159e11c2'
down_revision: Union[str, None] = '2611532bb11b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user_paper_accounts table
    op.create_table(
        'user_paper_accounts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('balance', sa.Float(), nullable=False, server_default='100000.0'),
        sa.Column('starting_balance', sa.Float(), nullable=False, server_default='100000.0'),
        sa.Column('last_reset_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_user_paper_accounts_user_id'), 'user_paper_accounts', ['user_id'], unique=True)
    
    # Add daily_profit_target to user_trading_settings
    op.add_column('user_trading_settings', sa.Column('daily_profit_target', sa.Float(), nullable=True))
    
    # Add is_proposable to user_strategies
    op.add_column('user_strategies', sa.Column('is_proposable', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    # Remove is_proposable from user_strategies
    op.drop_column('user_strategies', 'is_proposable')
    
    # Remove daily_profit_target from user_trading_settings
    op.drop_column('user_trading_settings', 'daily_profit_target')
    
    # Drop user_paper_accounts table
    op.drop_index(op.f('ix_user_paper_accounts_user_id'), table_name='user_paper_accounts')
    op.drop_table('user_paper_accounts')
