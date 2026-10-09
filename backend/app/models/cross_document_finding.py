"""
`cross_document_findings` table — case-level reconciliation results
(SPECIFICATION.md section 3.1, "Cross-document validation & reconciliation"):
shared fields (amount, date, vendor, ...) compared pairwise across every
document in a case, once all of that case's documents have been processed.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.company import TenantScopedMixin


REVIEW_PENDING, REVIEW_ACCEPTED, REVIEW_DISMISSED = "pending", "accepted", "dismissed"
REVIEW_STATUSES = (REVIEW_PENDING, REVIEW_ACCEPTED, REVIEW_DISMISSED)


class FindingSeverity(str, enum.Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class CrossDocumentFinding(TenantScopedMixin, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cross_document_findings"

    case_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    finding_type: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[FindingSeverity] = mapped_column(
        Enum(FindingSeverity, name="finding_severity"), default=FindingSeverity.low, nullable=False
    )
    description: Mapped[str] = mapped_column(String(2048), nullable=False)
    # IDs (as strings) of the documents involved in this finding.
    document_ids: Mapped[list | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )

    # Set by the identity contradiction check (app/services/
    # identity_comparison.py); null on invoice reconciliation findings.
    # `classification` is "harmless_variant" or "conflict", `reason` names
    # why, and `evidence` holds what each document shows and where:
    # [{document_id, document_type, document_filename, value, bounding_box}].
    classification: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence: Mapped[list | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )

    # Numbers a message quotes (e.g. {"ratio": 8.0}, {"years_apart": 15}).
    detail: Mapped[dict | None] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)

    # A reviewer's decision on this one finding: "accepted" (the finding is
    # right), "dismissed" (it is not) or "pending". See `finding_resolution`.
    review_status: Mapped[str] = mapped_column(
        String(16), default=REVIEW_PENDING, server_default=REVIEW_PENDING, nullable=False
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    case = relationship("Case", back_populates="cross_document_findings")
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])

    @property
    def severity_score(self) -> int:
        sev = (self.severity.value if hasattr(self.severity, "value") else str(self.severity or "")).lower()
        if sev == "critical":
            return 95 if self.field_name in ("full_name", "photo") else 90
        if sev == "high":
            return 75 if self.field_name in ("date_of_birth", "gender") else 70
        if sev == "medium":
            return 50
        if sev == "low":
            return 25
        return 0


def finding_resolution(classification: str | None, review_status: str) -> str:
    """What a finding amounts to once the reviewer's decision is applied:
    "open" (a conflict nobody has decided), "conflict_confirmed" or
    "no_issue". Dismissing a conflict clears it; dismissing a harmless
    variant means the reviewer considers it a real conflict."""
    harmless = classification == "harmless_variant"
    if review_status == REVIEW_PENDING:
        return "no_issue" if harmless else "open"
    agrees = review_status == REVIEW_ACCEPTED
    return "no_issue" if agrees == harmless else "conflict_confirmed"
