"""Update trades table with new fields for Feature 4

Revision ID: 269f9ef621ff
Revises: a9139906eddd
Create Date: 2025-11-17 18:36:24.229212

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '269f9ef621ff'
down_revision: Union[str, None] = 'a9139906eddd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types first
    assettype_enum = sa.Enum('STOCK', 'CRYPTO', 'FOREX', 'OTHER', name='assettype')
    assettype_enum.create(op.get_bind(), checkfirst=True)
    
    tradestatus_enum = sa.Enum('OPEN', 'CLOSED', name='tradestatus')
    tradestatus_enum.create(op.get_bind(), checkfirst=True)
    
    tradesource_enum = sa.Enum('MANUAL', 'BRAIN', name='tradesource')
    tradesource_enum.create(op.get_bind(), checkfirst=True)
    
    # Add columns with defaults for existing rows
    op.add_column('trades', sa.Column('asset_type', assettype_enum, nullable=False, server_default='STOCK'))
    op.add_column('trades', sa.Column('status', tradestatus_enum, nullable=False, server_default='OPEN'))
    op.add_column('trades', sa.Column('source', tradesource_enum, nullable=False, server_default='MANUAL'))
    op.add_column('trades', sa.Column('realized_pnl', sa.Float(), nullable=True))
    op.add_column('trades', sa.Column('group_id', sa.String(), nullable=True))
    
    # Update status for existing closed trades (if closed_at is set, mark as CLOSED)
    op.execute("UPDATE trades SET status = 'CLOSED' WHERE closed_at IS NOT NULL")
    
    op.alter_column('trades', 'quantity',
               existing_type=sa.INTEGER(),
               type_=sa.Float(),
               existing_nullable=False)
    op.create_index(op.f('ix_trades_group_id'), 'trades', ['group_id'], unique=False)
    op.create_foreign_key(None, 'trades', 'groups', ['group_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint(None, 'trades', type_='foreignkey')
    op.drop_index(op.f('ix_trades_group_id'), table_name='trades')
    op.alter_column('trades', 'quantity',
               existing_type=sa.Float(),
               type_=sa.INTEGER(),
               existing_nullable=False)
    op.drop_column('trades', 'group_id')
    op.drop_column('trades', 'realized_pnl')
    op.drop_column('trades', 'source')
    op.drop_column('trades', 'status')
    op.drop_column('trades', 'asset_type')
    
    # Drop enum types
    sa.Enum(name='tradesource').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='tradestatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='assettype').drop(op.get_bind(), checkfirst=True)

