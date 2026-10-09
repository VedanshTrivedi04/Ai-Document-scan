"""
A reviewer's decision on one finding of a case.

Each cross-document finding can be accepted (the finding is right),
dismissed (it is not) or set back to pending. This is separate from the
decision on the case as a whole (app/api/case_actions.py): a reviewer works
through the findings first, then approves or rejects the case.

Every decision is written to the audit log with the reviewer, their role at
the time, the previous decision and the note.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_tenant_db, require_company_role
from app.api.case_access import ensure_can_act, ensure_can_manage_case, scoped_company_id
from app.models.base import utcnow
from app.models.case import Case, CaseStatus
from app.models.cross_document_finding import REVIEW_PENDING, CrossDocumentFinding
from app.models.user import User, UserRole, has_rank, role_label
from app.schemas.case import (
    CrossDocumentFindingSummary,
    FindingCounts,
    FindingReviewRequest,
    FindingReviewResponse,
)
from app.services.audit_service import record_event
from app.services.identity_messages import warm_up as warm_up_messages
from app.services.risk_scoring_service import request_case_scoring
from app.services.translation_service import normalize_language

router = APIRouter(prefix="/cases", tags=["findings"])

_reviewer = require_company_role(UserRole.reviewer_l1)
_DECIDED_CASE = (CaseStatus.approved, CaseStatus.rejected, CaseStatus.closed)


@router.patch(
    "/{case_id}/findings/{finding_id}",
    response_model=FindingReviewResponse,
    summary="Accept or dismiss one finding",
    description=(
        "Company reviewers only. `accepted` means the finding is right, `dismissed` means it is not, "
        "`pending` undoes a decision. For a conflict, dismissing clears it; for a difference the check "
        "judged harmless, dismissing means the reviewer considers it a real conflict (see `resolution` "
        "in the response). Returns the finding and the case's updated counts. Writes a "
        "`finding_reviewed` audit event."
    ),
    responses={
        401: {"description": "Missing, invalid or expired bearer token, or the user is inactive."},
        403: {"description": "Requires a company reviewer role; a `reviewer_l1` also gets 403 on a case escalated to L2."},
        404: {"description": "No such case in your company, or no such finding in that case."},
        409: {"description": "The case is already decided; its findings can no longer be changed."},
    },
)
def review_finding(
    case_id: uuid.UUID,
    finding_id: uuid.UUID,
    payload: FindingReviewRequest,
    lang: str = Query(default="en", description="Language of the returned finding's `message`."),
    actor: User = Depends(require_company_role(UserRole.user)),
    db: Session = Depends(get_tenant_db),
) -> FindingReviewResponse:
    company_id = scoped_company_id(db)
    case = db.execute(select(Case).where(Case.id == case_id, Case.company_id == company_id)).scalar_one_or_none()
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    # A company reviewer (subject to the case's tier), or the head of the case's family.
    if has_rank(actor.role, UserRole.reviewer_l1):
        ensure_can_act(actor, case)
    else:
        ensure_can_manage_case(db, actor, case, "review these findings")
    if case.status in _DECIDED_CASE:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This case is already {case.status.value}; its findings can no longer be changed.",
        )

    findings = db.execute(
        select(CrossDocumentFinding)
        .where(CrossDocumentFinding.case_id == case_id, CrossDocumentFinding.company_id == company_id)
        .order_by(CrossDocumentFinding.created_at)
    ).scalars().all()
    finding = next((f for f in findings if f.id == finding_id), None)
    if finding is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")

    previous = finding.review_status
    note = (payload.note or "").strip() or None
    undone = payload.decision == REVIEW_PENDING
    finding.review_status = payload.decision
    finding.review_note = None if undone else note
    finding.reviewed_by_user_id = None if undone else actor.id
    finding.reviewed_at = None if undone else utcnow()
    record_event(
        db,
        "finding_reviewed",
        case_id=case_id,
        actor_user_id=actor.id,
        event_data={
            "finding_id": str(finding.id),
            "field_name": finding.field_name,
            "classification": finding.classification,
            "reason": finding.reason,
            "severity": finding.severity.value,
            "decision": payload.decision,
            "previous_decision": previous,
            "note": note,
            "actor_role": role_label(actor.role),
        },
    )
    db.commit()
    # A dismissed conflict no longer counts toward the case's risk.
    request_case_scoring(case_id, company_id)

    language = normalize_language(lang)
    warm_up_messages(language)
    summaries = [CrossDocumentFindingSummary.from_finding(f, None, language) for f in findings]
    return FindingReviewResponse(
        finding=next(s for s in summaries if s.id == finding_id),
        finding_counts=FindingCounts.from_findings(summaries),
    )
