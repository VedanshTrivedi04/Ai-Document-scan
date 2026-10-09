"""family member sign-in: family_members.user_id, users.must_change_password

Revision ID: a8e2c4f6b1d9
Revises: d9e1f3a5b7c2
Create Date: 2026-10-10 00:00:00.000000

A family head can create a sign-in for a member. `family_members.user_id`
links the member to that account; `users.must_change_password` makes the
person replace the temporary password at first sign-in. Both are columns on
existing tables, so the grants and row-level-security policies already cover
them.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a8e2c4f6b1d9"
down_revision: Union[str, None] = "d9e1f3a5b7c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("family_members", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_family_members_user_id", "family_members", "users", ["user_id"], ["id"])
    op.create_unique_constraint("uq_family_members_user_id", "family_members", ["user_id"])


def downgrade() -> None:
    op.drop_constraint("uq_family_members_user_id", "family_members", type_="unique")
    op.drop_constraint("fk_family_members_user_id", "family_members", type_="foreignkey")
    op.drop_column("family_members", "user_id")
    op.drop_column("users", "must_change_password")
