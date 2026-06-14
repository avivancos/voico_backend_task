"""add indexes for filter/sort columns

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-14 00:00:00.000000

Task 2 introduces filtering/sorting on caller_name, duration_seconds, label and created_at. At the
current seed size (~100 rows) these indexes are not yet necessary, but they keep those access
patterns O(log n) as the table grows and keep the schema honest (the model declares index=True for
the same columns). status and phone_number were already indexed by 0001.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(op.f("ix_calls_caller_name"), "calls", ["caller_name"], unique=False)
    op.create_index(op.f("ix_calls_duration_seconds"), "calls", ["duration_seconds"], unique=False)
    op.create_index(op.f("ix_calls_label"), "calls", ["label"], unique=False)
    op.create_index(op.f("ix_calls_created_at"), "calls", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_calls_created_at"), table_name="calls")
    op.drop_index(op.f("ix_calls_label"), table_name="calls")
    op.drop_index(op.f("ix_calls_duration_seconds"), table_name="calls")
    op.drop_index(op.f("ix_calls_caller_name"), table_name="calls")
