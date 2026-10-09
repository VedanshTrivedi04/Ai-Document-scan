"""risk rules for contradictions between one person's documents

Revision ID: d9e1f3a5b7c2
Revises: f6b0d2e4a8c7
Create Date: 2026-10-09 13:00:00.000000

The identity contradiction check (app/services/identity_comparison.py) stored
its findings, but no risk rule looked at them: a case whose two cards named
different people scored 0 and sat at "low" in the reviewer queue. These rules
(`identity.*`, app/services/risk_rule_seed.py IDENTITY_RULES) score a conflict
by what it suggests: another person (different name, another face) is "high"
on its own, a possible slip of the pen is "medium" or less.

Same as the other rule migrations: new rules only, version 1, never an UPDATE of
an existing rule row; a company already holding a rule of the same id is left
alone. Non-destructive downgrade (scored history references every version row,
so the rules are switched off, not deleted).
"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.services.risk_rule_seed import IDENTITY_RULES

revision: str = "d9e1f3a5b7c2"
down_revision: Union[str, None] = "f6b0d2e4a8c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_RULE_IDS = tuple(rule["rule_id"] for rule in IDENTITY_RULES)


def _columns():  # fresh column objects per table (SQLAlchemy can't share them)
    return [
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("rule_id", sa.String),
        sa.column("category", sa.String),
        sa.column("check_type", sa.String),
        sa.column("condition", postgresql.JSONB),
        sa.column("weight", sa.Float),
        sa.column("severity", sa.String),
        sa.column("reason_template", sa.String),
        sa.column("is_active", sa.Boolean),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    templates = sa.table("risk_rule_templates", *_columns())
    rules = sa.table(
        "risk_rules",
        *_columns(),
        sa.column("company_id", postgresql.UUID(as_uuid=True)),
        sa.column("version", sa.Integer),
        sa.column("effective_from", sa.DateTime(timezone=True)),
        sa.column("change_note", sa.String),
    )
    for spec in IDENTITY_RULES:
        rule_id = spec["rule_id"]
        common = {
            "rule_id": rule_id,
            "category": spec["category"],
            "check_type": spec["check_type"],
            "condition": spec["condition"],
            "weight": spec["weight"],
            "severity": spec["severity"],
            "reason_template": spec["reason_template"],
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        if not bind.execute(sa.text("SELECT 1 FROM risk_rule_templates WHERE rule_id = :r"), {"r": rule_id}).first():
            op.bulk_insert(templates, [{"id": uuid.uuid4(), **common}])
        companies = bind.execute(
            sa.text(
                "SELECT id FROM companies c WHERE NOT EXISTS "
                "(SELECT 1 FROM risk_rules r WHERE r.company_id = c.id AND r.rule_id = :r)"
            ),
            {"r": rule_id},
        ).scalars().all()
        if companies:
            op.bulk_insert(
                rules,
                [
                    {
                        "id": uuid.uuid4(), **common, "company_id": company_id, "version": 1,
                        "effective_from": now,
                        "change_note": "Default rule set (contradictions between one person's documents)",
                    }
                    for company_id in companies
                ],
            )


def downgrade() -> None:
    ids = ", ".join(f"'{r}'" for r in NEW_RULE_IDS)
    op.execute(f"UPDATE risk_rules SET is_active = false WHERE rule_id IN ({ids})")
    op.execute(f"UPDATE risk_rule_templates SET is_active = false WHERE rule_id IN ({ids})")
