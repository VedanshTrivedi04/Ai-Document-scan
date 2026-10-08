"""companies.subdomain

Revision ID: f6b0d2e4a8c7
Revises: e5a9c1d3f7b6
Create Date: 2026-10-09 00:00:05.000000

The label each company's site is reached at. Existing companies get one made
from their name. A column on an existing table: the table-level grants and
the row-level-security policy on `companies` already cover it.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6b0d2e4a8c7"
down_revision: Union[str, None] = "e5a9c1d3f7b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.services import subdomains

    op.add_column("companies", sa.Column("subdomain", sa.String(length=63), nullable=True))
    op.create_unique_constraint("uq_companies_subdomain", "companies", ["subdomain"])

    bind = op.get_bind()
    taken: set[str] = set()
    for company_id, name in bind.execute(sa.text("SELECT id, name FROM companies ORDER BY created_at")).all():
        base = subdomains.suggest(name)
        if base is None:
            continue
        candidate = next(
            (
                c
                for c in (
                    base[: subdomains.MAX_LENGTH - len(suffix)].rstrip("-") + suffix
                    for suffix in ("", *(f"-{n}" for n in range(2, 1000)))
                )
                if c not in taken
            ),
            None,
        )
        if candidate is None:
            continue
        taken.add(candidate)
        bind.execute(
            sa.text("UPDATE companies SET subdomain = :subdomain WHERE id = :id"),
            {"subdomain": candidate, "id": company_id},
        )


def downgrade() -> None:
    op.drop_constraint("uq_companies_subdomain", "companies", type_="unique")
    op.drop_column("companies", "subdomain")
