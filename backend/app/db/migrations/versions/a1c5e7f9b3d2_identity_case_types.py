"""identity and hiring verification case types

Revision ID: a1c5e7f9b3d2
Revises: f3b7d1e8a4c5
Create Date: 2026-10-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a1c5e7f9b3d2"
down_revision: Union[str, None] = "f3b7d1e8a4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_VALUES = ("identity_verification", "hiring_verification")


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block.
    with op.get_context().autocommit_block():
        for value in NEW_VALUES:
            op.execute(f"ALTER TYPE case_type ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # PostgreSQL cannot drop a value from an enum type; the values stay.
    pass
