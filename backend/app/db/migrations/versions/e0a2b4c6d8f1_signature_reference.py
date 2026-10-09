"""reference signature for identity cases, and its risk rules

Revision ID: e0a2b4c6d8f1
Revises: b9f3d5a7c1e2, d9e1f3a5b7c2
Create Date: 2026-10-10 12:00:00.000000

cases.signature_reference_document_id: the document whose signature the others
are compared with (app/services/signature_local.py). Two new risk rules
(identity.signature_*), added like the other rule migrations: version 1 only,
a company already holding the rule is left alone, non-destructive downgrade.
"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.services.risk_rule_seed import SIGNATURE_RULES

revision: str = "e0a2b4c6d8f1"
# A merge: the family-comparison migration and the identity-rules migration were written
# on separate branches; both must be applied before this one.
down_revision: Union[str, Sequence[str], None] = ("b9f3d5a7c1e2", "d9e1f3a5b7c2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_RULE_IDS = tuple(r["rule_id"] for r in SIGNATURE_RULES)


def _columns():
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
    op.add_column("cases", sa.Column("signature_reference_document_id", postgresql.UUID(as_uuid=True), nullable=True))
    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    templates = sa.table("risk_rule_templates", *_columns())
    rules = sa.table(
        "risk_rules", *_columns(),
        sa.column("company_id", postgresql.UUID(as_uuid=True)), sa.column("version", sa.Integer),
        sa.column("effective_from", sa.DateTime(timezone=True)), sa.column("change_note", sa.String),
    )
    for spec in SIGNATURE_RULES:
        rule_id = spec["rule_id"]
        common = {k: spec[k] for k in ("rule_id", "category", "check_type", "condition", "weight", "severity", "reason_template")}
        common.update(is_active=True, created_at=now, updated_at=now)
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
            op.bulk_insert(rules, [
                {"id": uuid.uuid4(), **common, "company_id": c, "version": 1, "effective_from": now,
                 "change_note": "Default rule set (signature comparison)"}
                for c in companies
            ])


def downgrade() -> None:
    ids = ", ".join(f"'{r}'" for r in NEW_RULE_IDS)
    op.execute(f"UPDATE risk_rules SET is_active = false WHERE rule_id IN ({ids})")
    op.execute(f"UPDATE risk_rule_templates SET is_active = false WHERE rule_id IN ({ids})")
    op.drop_column("cases", "signature_reference_document_id")
