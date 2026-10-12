"""Make payment order_id unique

Revision ID: 4dbb40700f6a
Revises: 4568a5742eba
Create Date: 2026-10-11 15:04:20.231851

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4dbb40700f6a'
down_revision: Union[str, Sequence[str], None] = '4568a5742eba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_payments_order_id', 'payments', ['order_id']
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_payments_order_id', 'payments', type_='unique'
    )