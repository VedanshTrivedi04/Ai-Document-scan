"""case profile overrides

Revision ID: d4f8b0c2e6a5
Revises: c3e7a9b1d5f4
Create Date: 2026-10-09 00:00:03.000000

Which document a reviewer chose as the right one for a disputed detail of an
identity case. A column on an existing table: no new row-level-security
policy or grant is needed.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4f8b0c2e6a5"
down_revision: Union[str, None] = "c3e7a9b1d5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    postgres = op.get_bind().dialect.name == "postgresql"
    op.add_column(
        "cases", sa.Column("profile_overrides", postgresql.JSONB() if postgres else sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("cases", "profile_overrides")
