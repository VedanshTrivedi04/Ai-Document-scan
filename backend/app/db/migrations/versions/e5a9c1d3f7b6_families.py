"""families, family_members, cases.family_member_id

Revision ID: e5a9c1d3f7b6
Revises: d4f8b0c2e6a5
Create Date: 2026-10-09 00:00:04.000000

Both new tables are tenant-owned. Each gets Row-Level Security with the usual
`tenant_isolation` policy for the app role and `platform_all` for the platform
role, plus explicit grants. The app role may delete a family member (a head
removing someone added by mistake) but not a family.
"""
import os
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5a9c1d3f7b6"
down_revision: Union[str, None] = "d4f8b0c2e6a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_APP_GRANTS = {"families": "SELECT, INSERT, UPDATE", "family_members": "SELECT, INSERT, UPDATE, DELETE"}
_IDENT = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def _role(env_name: str, default: str) -> str:
    from app.core.config import settings

    name = os.environ.get(env_name, getattr(settings, default))
    if not _IDENT.match(name):
        raise ValueError(f"{env_name}={name!r} is not a plain lowercase role name")
    return name


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    platform_role = _role("DATABASE_PLATFORM_USER", "database_platform_user")
    app_role = _role("DATABASE_APP_USER", "database_app_user")

    op.create_table(
        "families",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("company_id", _uuid(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("head_user_id", _uuid(), sa.ForeignKey("users.id"), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("head_user_id", name="uq_families_head_user_id"),
    )
    op.create_table(
        "family_members",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("company_id", _uuid(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("family_id", _uuid(), sa.ForeignKey("families.id"), nullable=False, index=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("relation", sa.String(length=16), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        *_timestamps(),
    )
    op.add_column(
        "cases", sa.Column("family_member_id", _uuid(), sa.ForeignKey("family_members.id"), nullable=True)
    )
    op.create_index("ix_cases_family_member_id", "cases", ["family_member_id"])

    # ---- tenant isolation (the database half of the two layers) ----------
    for table, app_grants in _APP_GRANTS.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} AS PERMISSIVE FOR ALL TO {app_role} "
            f"USING (company_id = fddt_current_company_id()) "
            f"WITH CHECK (company_id = fddt_current_company_id())"
        )
        op.execute(
            f"CREATE POLICY platform_all ON {table} AS PERMISSIVE FOR ALL TO {platform_role} "
            f"USING (true) WITH CHECK (true)"
        )
        op.execute(f"REVOKE ALL ON {table} FROM {app_role}")
        op.execute(f"GRANT {app_grants} ON {table} TO {app_role}")
        op.execute(f"REVOKE ALL ON {table} FROM {platform_role}")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {platform_role}")


def downgrade() -> None:
    op.drop_index("ix_cases_family_member_id", table_name="cases")
    op.drop_column("cases", "family_member_id")
    op.drop_table("family_members")
    op.drop_table("families")
