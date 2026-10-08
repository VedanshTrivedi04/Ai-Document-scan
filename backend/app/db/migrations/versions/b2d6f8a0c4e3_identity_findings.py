"""identity contradiction findings

Revision ID: b2d6f8a0c4e3
Revises: a1c5e7f9b3d2
Create Date: 2026-10-09 00:00:01.000000

Adds what the identity contradiction check stores on a finding
(classification, reason, evidence) and the `critical` severity. No new
table, so no new row-level-security policy or grant is needed.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2d6f8a0c4e3"
down_revision: Union[str, None] = "a1c5e7f9b3d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    postgres = op.get_bind().dialect.name == "postgresql"
    if postgres:
        # ALTER TYPE ... ADD VALUE cannot run inside a transaction block.
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE finding_severity ADD VALUE IF NOT EXISTS 'critical'")
    json_type = postgresql.JSONB() if postgres else sa.JSON()
    op.add_column("cross_document_findings", sa.Column("classification", sa.String(32), nullable=True))
    op.add_column("cross_document_findings", sa.Column("reason", sa.String(64), nullable=True))
    op.add_column("cross_document_findings", sa.Column("evidence", json_type, nullable=True))


def downgrade() -> None:
    # The `critical` enum value stays: PostgreSQL cannot drop an enum value.
    op.drop_column("cross_document_findings", "evidence")
    op.drop_column("cross_document_findings", "reason")
    op.drop_column("cross_document_findings", "classification")
