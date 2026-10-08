"""per-finding review

Revision ID: c3e7a9b1d5f4
Revises: b2d6f8a0c4e3
Create Date: 2026-10-09 00:00:02.000000

A reviewer accepts or dismisses each finding. Columns on an existing table:
no new row-level-security policy or grant is needed.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3e7a9b1d5f4"
down_revision: Union[str, None] = "b2d6f8a0c4e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "cross_document_findings"


def upgrade() -> None:
    postgres = op.get_bind().dialect.name == "postgresql"
    op.add_column(TABLE, sa.Column("detail", postgresql.JSONB() if postgres else sa.JSON(), nullable=True))
    op.add_column(
        TABLE, sa.Column("review_status", sa.String(16), nullable=False, server_default="pending")
    )
    op.add_column(
        TABLE,
        sa.Column(
            "reviewed_by_user_id",
            postgresql.UUID(as_uuid=True) if postgres else sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column(TABLE, sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(TABLE, sa.Column("review_note", sa.String(1000), nullable=True))


def downgrade() -> None:
    for column in ("review_note", "reviewed_at", "reviewed_by_user_id", "review_status", "detail"):
        op.drop_column(TABLE, column)
