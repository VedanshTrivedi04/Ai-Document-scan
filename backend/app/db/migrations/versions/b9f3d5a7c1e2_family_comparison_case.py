"""family comparison case: case type, cases.family_id, cases.comparison_member_ids

Revision ID: b9f3d5a7c1e2
Revises: a8e2c4f6b1d9
Create Date: 2026-10-10 00:00:01.000000

A case of type `family_comparison` records a family head comparing the
verified details of family members with each other. Columns on an existing
table: the grants and row-level-security policy on `cases` already cover them.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b9f3d5a7c1e2"
down_revision: Union[str, None] = "a8e2c4f6b1d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        # ALTER TYPE ... ADD VALUE cannot run inside a transaction block.
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE case_type ADD VALUE IF NOT EXISTS 'family_comparison'")
    op.add_column("cases", sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "cases", sa.Column("comparison_member_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.create_foreign_key("fk_cases_family_id", "cases", "families", ["family_id"], ["id"])
    op.create_index("ix_cases_family_id", "cases", ["family_id"])


def downgrade() -> None:
    op.drop_index("ix_cases_family_id", table_name="cases")
    op.drop_constraint("fk_cases_family_id", "cases", type_="foreignkey")
    op.drop_column("cases", "comparison_member_ids")
    op.drop_column("cases", "family_id")
    # PostgreSQL cannot drop a value from an enum type; it stays.
