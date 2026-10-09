"""document retention: file_deleted_at, private cases

Revision ID: c1a3e5b7d9f2
Revises: b9f3d5a7c1e2
Create Date: 2026-10-10 00:00:02.000000

`documents.file_deleted_at` and `bulk_uploads.file_deleted_at` record when a
stored file was removed (app/services/retention_service.py).
`cases.delete_on_logout` marks a private case, emptied when its submitter
signs out; `cases.data_removed_at` records when. Columns on existing tables:
their grants and row-level-security policies already cover them.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1a3e5b7d9f2"
down_revision: Union[str, None] = "b9f3d5a7c1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("file_deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("bulk_uploads", sa.Column("file_deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "cases", sa.Column("delete_on_logout", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("cases", sa.Column("data_removed_at", sa.DateTime(timezone=True), nullable=True))
    # The daily job looks for files still stored, oldest first.
    op.create_index(
        "ix_documents_file_retention",
        "documents",
        ["created_at"],
        postgresql_where=sa.text("file_deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_documents_file_retention", table_name="documents")
    op.drop_column("cases", "data_removed_at")
    op.drop_column("cases", "delete_on_logout")
    op.drop_column("bulk_uploads", "file_deleted_at")
    op.drop_column("documents", "file_deleted_at")
