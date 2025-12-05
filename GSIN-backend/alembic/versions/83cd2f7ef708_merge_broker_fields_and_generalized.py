"""merge_broker_fields_and_generalized

Revision ID: 83cd2f7ef708
Revises: add_broker_fields, add_generalized_to_strategies
Create Date: 2025-11-22 15:57:57.200178

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '83cd2f7ef708'
down_revision: Union[str, None] = ('add_broker_fields', 'add_generalized_to_strategies')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

