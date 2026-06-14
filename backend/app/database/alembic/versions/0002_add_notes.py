"""add notes column to calls

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-13 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable column — a plain ADD COLUMN is SQLite-safe and needs no table rebuild.
    op.add_column("calls", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    # SQLite can only drop a column by rebuilding the table; batch mode handles that portably.
    with op.batch_alter_table("calls", schema=None) as batch_op:
        batch_op.drop_column("notes")
