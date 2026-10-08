import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.models.case import CaseStatus, CaseTier, CaseType, RiskTier
from app.schemas.document import CaseDocumentSummary
from app.services.case_flag_service import CaseFlag, CaseFlagType, ForensicFinding
from app.services.check_summaries import risk_reason_short
from app.models.cross_document_finding import REVIEW_PENDING, finding_resolution
from app.services.field_exception_service import cross_document_regions, identity_finding_regions
from app.services.identity_messages import build_message


class CaseCreateRequest(BaseModel):
    case_type: CaseType = Field(
        description="Case-level category chosen at submission. Independent of each document's own "
        "`document_type`, which the classification step fills in later."
    )
    family_member_id: uuid.UUID | None = Field(
        default=None,
        description="The family member this bundle is for (GET /family). Only the head of that "
        "family may set it, and only on an identity or hiring verification case.",
    )


class CaseResponse(BaseModel):
    id: uuid.UUID
    case_number: str
    case_type: CaseType
    status: CaseStatus
    assigned_tier: CaseTier
    risk_tier: RiskTier | None
    submitted_by_user_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class UserSummary(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None

    model_config = {"from_attributes": True}


class CaseFlagSchema(BaseModel):
    """Wire shape of app/services/case_flag_service.py's CaseFlag: the
    case's real risk tier (low/medium/high), or "pending" until scored."""

    flag: CaseFlagType
    label: str
    description: str
    score: int | None = None

    @classmethod
    def from_case_flag(cls, case_flag: CaseFlag) -> "CaseFlagSchema":
        return cls(
            flag=case_flag.flag,
            label=case_flag.label,
            description=case_flag.description,
            score=case_flag.score,
        )


class CaseListItem(BaseModel):
    id: uuid.UUID
    case_number: str
    case_type: CaseType
    status: CaseStatus
    assigned_tier: CaseTier
    risk_tier: RiskTier | None
    submitted_by: UserSummary | None = None
    created_at: datetime
    document_count: int
    flag: CaseFlagSchema
    can_act: bool = Field(
        description="Whether the caller may approve/reject/escalate this case given its tier. "
        "False for submitters, and for a `reviewer_l1` on an L2-assigned case (read-only). "
        "Does not reflect status — a decided case is still `can_act` but every action is a 409."
    )


class CrossDocumentFindingSummary(BaseModel):
    """One `cross_document_findings` row (System Specification section 3.1,
    "Cross-document validation & reconciliation") — a shared field
    (amount/date/issuer) that disagreed between two of this case's
    documents. Case-level, not per-document — see app/services/
    cross_document_service.py and app/tasks/document_checks.py."""

    id: uuid.UUID
    field_name: str
    finding_type: str
    severity: str
    description: str
    document_ids: list[str] | None
    created_at: datetime
    # One highlight region per involved document whose field location is
    # known (app/services/field_exception_service.py) — drawn as a field-
    # exception box on each document, each captioned with what the other
    # showed. Empty when the fields weren't located.
    regions: list[dict[str, Any]] = []
    # Identity contradiction findings only (app/services/identity_comparison.py):
    # "harmless_variant" or "conflict", the named reason, and what each of
    # the two documents shows. Null on invoice reconciliation findings.
    classification: str | None = None
    reason: str | None = None
    evidence: list[dict[str, Any]] | None = None
    # The finding in the requested language (`?lang=`): {language,
    # field_label, severity_label, summary, explanation, action, text} -
    # app/services/identity_messages.py. Identity findings only.
    message: dict[str, str] | None = None
    # The decision a reviewer made on this finding: "pending", "accepted"
    # (the finding is right) or "dismissed" (it is not).
    review_status: str = "pending"
    review_note: str | None = None
    reviewed_at: datetime | None = None
    reviewed_by_name: str | None = None
    # The finding once that decision is applied: "open" (a conflict nobody
    # has decided), "conflict_confirmed" or "no_issue".
    resolution: str = "open"

    model_config = {"from_attributes": True}

    @classmethod
    def from_finding(
        cls, finding, documents_by_id: dict[str, Any] | None = None, language: str = "en"
    ) -> "CrossDocumentFindingSummary":
        reviewer = finding.reviewed_by if finding.reviewed_by_user_id else None
        review = {
            "review_status": finding.review_status or REVIEW_PENDING,
            "review_note": finding.review_note,
            "reviewed_at": finding.reviewed_at,
            "reviewed_by_name": (reviewer.full_name or reviewer.email) if reviewer else None,
            "resolution": finding_resolution(finding.classification, finding.review_status or REVIEW_PENDING),
        }
        if finding.evidence:
            return cls(
                id=finding.id,
                field_name=finding.field_name,
                finding_type=finding.finding_type,
                severity=finding.severity.value,
                description=finding.description,
                document_ids=finding.document_ids,
                created_at=finding.created_at,
                regions=identity_finding_regions(finding.field_name, finding.evidence),
                classification=finding.classification,
                reason=finding.reason,
                evidence=finding.evidence,
                message=build_message(
                    finding.field_name, finding.classification, finding.reason, finding.severity.value,
                    finding.evidence, finding.detail, language,
                ),
                **review,
            )
        return cls(
            **review,
            id=finding.id,
            field_name=finding.field_name,
            finding_type=finding.finding_type,
            severity=finding.severity.value,
            description=finding.description,
            document_ids=finding.document_ids,
            created_at=finding.created_at,
            regions=cross_document_regions(finding.field_name, finding.document_ids, documents_by_id or {}),
        )


class ForensicFindingSummary(BaseModel):
    """One medium/high-severity finding from a flagged metadata_forensics/
    error_level_analysis/copy_move_detection check — the per-document
    counterpart to CrossDocumentFindingSummary, both shown together in
    the case detail "Explainable findings" panel. See app/services/
    case_flag_service.py's get_forensic_findings for what feeds this and
    why it's a temporary stand-in for the real risk-scoring engine."""

    document_id: uuid.UUID
    document_filename: str
    check_type: str
    check_type_label: str
    finding: str
    severity: str
    description: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_finding(cls, finding: ForensicFinding) -> "ForensicFindingSummary":
        return cls(
            document_id=finding.document_id,
            document_filename=finding.document_filename,
            check_type=finding.check_type,
            check_type_label=finding.check_type_label,
            finding=finding.finding,
            severity=finding.severity,
            description=finding.description,
        )


class RiskReasonSchema(BaseModel):
    """One fired rule, as frozen at scoring time (rendered text, weight and
    rule version) — see app/models/case_risk_assessment.py."""

    rule_id: str
    rule_version: int
    category: str
    check_type: str
    severity: str
    weight: float
    reason: str
    document_id: uuid.UUID | None
    document_filename: str | None
    # Short form (app/services/check_summaries.py), computed when read.
    title: str = ""
    short: str = ""


class RiskAssessmentSchema(BaseModel):
    id: uuid.UUID
    score: int
    raw_score: float
    tier: RiskTier
    computed_at: datetime
    triggered_reasons: list[RiskReasonSchema]
    thresholds: dict[str, int]
    # Rule families whose points were capped together: {"metadata": {"cap", "points"}}.
    group_caps: dict[str, dict[str, float]] = {}

    @classmethod
    def from_assessment(cls, a, summaries: dict[str, dict[str, Any]] | None = None) -> "RiskAssessmentSchema":
        """`summaries`: {document_id: {check_type: check summary}} of the
        case's documents, for each reason's short line."""
        snapshot = a.risk_rules_version_snapshot or {}

        def reason(r: dict) -> RiskReasonSchema:
            title, short = risk_reason_short(r, (summaries or {}).get(str(r.get("document_id"))))
            return RiskReasonSchema(**{**r, "title": title, "short": short})

        return cls(
            id=a.id,
            score=a.score,
            raw_score=a.raw_score,
            tier=a.tier,
            computed_at=a.computed_at,
            triggered_reasons=[reason(r) for r in (a.triggered_reasons or [])],
            thresholds=snapshot.get("thresholds", {}),
            group_caps=snapshot.get("group_caps") or {},
        )


class PipelineStatusSchema(BaseModel):
    """Whether every automated check has finished. `pending` names what is
    still outstanding — shown to the reviewer when Approve is disabled."""

    complete: bool
    pending: list[str]


class CaseActionSchema(BaseModel):
    """A reviewer decision/note on the case (approve/reject/escalate)."""

    id: uuid.UUID
    action_type: str
    actor_name: str | None
    actor_role: str | None = Field(
        default=None, description="Display label of the actor's role when they acted, e.g. 'Reviewer L1'."
    )
    notes: str | None
    created_at: datetime


class FindingCounts(BaseModel):
    """The findings of a case by where they stand. `open` are conflicts
    nobody has decided yet; `ignored_as_harmless` are the differences the
    check itself judged harmless and no reviewer overruled."""

    open: int = 0
    conflict_confirmed: int = 0
    no_issue: int = 0
    ignored_as_harmless: int = 0

    @classmethod
    def from_findings(cls, findings: list["CrossDocumentFindingSummary"]) -> "FindingCounts":
        counts = cls()
        for finding in findings:
            setattr(counts, finding.resolution, getattr(counts, finding.resolution) + 1)
            if finding.classification == "harmless_variant" and finding.resolution == "no_issue":
                counts.ignored_as_harmless += 1
        return counts


class FindingReviewRequest(BaseModel):
    decision: Literal["accepted", "dismissed", "pending"] = Field(
        ...,
        description="`accepted`: the finding is right. `dismissed`: it is not. `pending`: undo a decision.",
    )
    note: str | None = Field(default=None, max_length=1000, description="Optional reason for the decision.")


class FindingReviewResponse(BaseModel):
    finding: CrossDocumentFindingSummary
    finding_counts: FindingCounts


class CaseFamilyMember(BaseModel):
    """The family member a case was submitted for."""

    id: uuid.UUID
    family_id: uuid.UUID
    full_name: str
    relation: str


class CaseDetail(CaseListItem):
    family_member: CaseFamilyMember | None = None
    documents: list[CaseDocumentSummary]
    cross_document_findings: list[CrossDocumentFindingSummary]
    finding_counts: FindingCounts = FindingCounts()
    language: str = "en"
    forensic_findings: list[ForensicFindingSummary]
    assessment: RiskAssessmentSchema | None
    pipeline: PipelineStatusSchema
    actions: list[CaseActionSchema]


class ApproveRequest(BaseModel):
    note: str | None = Field(
        default=None,
        max_length=4000,
        description="Justification. Optional for low-risk cases; at least 10 characters (after "
        "trimming) is required to approve a medium- or high-risk case.",
    )


class RejectRequest(BaseModel):
    reason: str = Field(
        ..., max_length=4000, description="Why the case is rejected. Required and must not be blank."
    )

    @field_validator("reason")
    @classmethod
    def _reason_required(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("A reason is required to reject a case.")
        return v


class EscalateRequest(BaseModel):
    reason: str = Field(
        ..., max_length=4000, description="Why the case needs an L2 reviewer. Required and must not be blank."
    )

    @field_validator("reason")
    @classmethod
    def _reason_required(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("A reason is required to escalate a case.")
        return v


class CaseDecisionResponse(BaseModel):
    case_id: uuid.UUID
    status: CaseStatus
    assigned_tier: CaseTier
    action: CaseActionSchema


class AuditLogEntrySchema(BaseModel):
    """One `audit_log` row scoped to a case — System Specification section 3.5's
    "review history/timeline ... built from the same audit log." Every
    event_type here is a real one already written by app/services/
    audit_service.py's call sites (case creation, uploads, and each
    Celery check task) — nothing here is synthesized for display."""

    id: uuid.UUID
    event_type: str
    actor_name: str | None
    document_id: uuid.UUID | None
    event_data: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
