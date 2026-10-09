"""
Family comparison cases: the head compares the verified details of family
members with each other (and with the head's own), and records the result as
a case.

A comparison case holds no documents. It names the members compared
(`cases.comparison_member_ids`, the head always included) and runs the family
checks of app/services/family_checks.py on their verified profiles. Each
check that finds a conflict is stored as a finding (`cross_document_findings`,
`finding_type` "family_check"), so the head, or a company reviewer, accepts or
dismisses it with the same endpoint as any other finding
(PATCH /cases/{id}/findings/{finding_id}), and every step is audited.

The checks themselves are computed on every read, from the members' current
profiles, so the result follows their documents. The stored findings keep the
decisions: `POST .../refresh` re-runs the checks and keeps the decision on any
conflict that is still there (matched on the member and the check).

The head creates and refreshes; company reviewers can read (to review a
member's case in context). Everyone else gets 404.
"""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_tenant_db, require_company_role
from app.api.families import _family_of, member_details
from app.models.case import Case, CaseStatus, CaseType
from app.models.cross_document_finding import (
    REVIEW_PENDING,
    CrossDocumentFinding,
    FindingSeverity,
    finding_resolution,
)
from app.models.family import RELATION_SELF, Family, FamilyMember
from app.models.user import User, UserRole, has_rank
from app.services import family_checks
from app.services.audit_service import record_event
from app.services.translation_service import normalize_language, translate

router = APIRouter(tags=["family"])

_member = require_company_role(UserRole.user)
FINDING_TYPE = "family_check"
MAX_MEMBERS = 20


class ComparisonCreateRequest(BaseModel):
    member_ids: list[uuid.UUID] = Field(
        min_length=1,
        max_length=MAX_MEMBERS,
        description="The members to compare with the head (GET /family). The head is always included.",
    )


def _own_family(db: Session, user: User) -> Family:
    family = _family_of(db, user)
    if family is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You have not set up a family yet.")
    return family


def _load_comparison(db: Session, case_id: uuid.UUID, user: User, *, head_only: bool) -> tuple[Case, Family]:
    """The comparison case and its family, or 404. A reviewer may read any in
    the company; changing needs the head."""
    case = db.execute(
        select(Case).where(
            Case.id == case_id,
            Case.company_id == user.company_id,
            Case.case_type == CaseType.family_comparison,
        )
    ).scalar_one_or_none()
    family = (
        db.execute(
            select(Family)
            .where(Family.id == case.family_id, Family.company_id == user.company_id)
            .options(selectinload(Family.members).selectinload(FamilyMember.cases))
        ).scalar_one_or_none()
        if case is not None and case.family_id is not None
        else None
    )
    is_head = family is not None and family.head_user_id == user.id
    may_read = is_head or (not head_only and has_rank(user.role, UserRole.reviewer_l1))
    if case is None or family is None or not may_read:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comparison not found")
    return case, family


def _selected(family: Family, details: list[family_checks.MemberDetails], case: Case):
    wanted = set(case.comparison_member_ids or [])
    head_id = next((str(m.id) for m in family.members if m.relation == RELATION_SELF), None)
    return [d for d in details if d.id in wanted or d.id == head_id]


def _key(member_id: str, check: str) -> tuple[str, str]:
    return member_id, check


def _sync_findings(db: Session, case: Case, checks: list[dict[str, Any]]) -> None:
    """Make the stored findings the conflicts in `checks`, keeping the decision
    on those still present."""
    existing = db.execute(
        select(CrossDocumentFinding).where(
            CrossDocumentFinding.case_id == case.id, CrossDocumentFinding.company_id == case.company_id
        )
    ).scalars().all()
    by_key = {_key((f.detail or {}).get("member_id", ""), (f.detail or {}).get("check", f.field_name)): f for f in existing}
    current = set()
    for check in checks:
        if check["result"] != family_checks.CONFLICT:
            continue
        key = _key(check["member_id"], check["check"])
        current.add(key)
        finding = by_key.get(key)
        severity = FindingSeverity(check["severity"] if check["severity"] != "info" else "low")
        if finding is None:
            db.add(
                CrossDocumentFinding(
                    company_id=case.company_id,
                    case_id=case.id,
                    field_name=check["check"],
                    finding_type=FINDING_TYPE,
                    severity=severity,
                    description=check["summary"][:2048],
                    document_ids=[],
                    classification="conflict",
                    reason=check["check"],
                    detail={"member_id": check["member_id"], "check": check["check"]},
                )
            )
        else:
            finding.severity = severity
            finding.description = check["summary"][:2048]
    for key, finding in by_key.items():
        if key not in current:
            db.delete(finding)
    db.flush()


def _run(db: Session, case: Case, family: Family, language: str) -> list[dict[str, Any]]:
    selected = _selected(family, member_details(db, family), case)
    return family_checks.run_family_checks(selected, language)


def _view(db: Session, case: Case, family: Family, language: str, user: User) -> dict[str, Any]:
    language = normalize_language(language)
    details = member_details(db, family)
    selected = _selected(family, details, case)
    checks = family_checks.run_family_checks(selected, language)
    findings = {
        _key((f.detail or {}).get("member_id", ""), (f.detail or {}).get("check", f.field_name)): f
        for f in db.execute(
            select(CrossDocumentFinding)
            .where(CrossDocumentFinding.case_id == case.id, CrossDocumentFinding.company_id == case.company_id)
            .options(selectinload(CrossDocumentFinding.reviewed_by))
        ).scalars()
    }
    relation_labels = dict(
        zip(family_checks.RELATION_LABELS, translate(list(family_checks.RELATION_LABELS.values()), language))
    )
    out_checks = []
    counts = {"open": 0, "conflict_confirmed": 0, "no_issue": 0}
    for check in checks:
        finding = findings.get(_key(check["member_id"], check["check"]))
        item = {**check, "finding_id": None, "review_status": None, "review_note": None, "resolution": None,
                "reviewed_by_name": None, "reviewed_at": None}
        if check["result"] == family_checks.CONFLICT and finding is not None:
            resolution = finding_resolution(finding.classification, finding.review_status or REVIEW_PENDING)
            reviewer = finding.reviewed_by if finding.reviewed_by_user_id else None
            item.update(
                finding_id=str(finding.id),
                review_status=finding.review_status or REVIEW_PENDING,
                review_note=finding.review_note,
                resolution=resolution,
                reviewed_by_name=(reviewer.full_name or reviewer.email) if reviewer else None,
                reviewed_at=finding.reviewed_at.isoformat() if finding.reviewed_at else None,
            )
            counts[resolution] += 1
        out_checks.append(item)
    return {
        "id": str(case.id),
        "case_number": case.case_number,
        "status": case.status.value,
        "created_at": case.created_at.isoformat(),
        "family_id": str(family.id),
        "family_name": family.name,
        "is_head": family.head_user_id == user.id,
        # The head, or a company reviewer, accepts or dismisses the conflicts.
        "can_review": family.head_user_id == user.id or has_rank(user.role, UserRole.reviewer_l1),
        "language": language,
        "members": [
            {
                "id": d.id,
                "full_name": d.full_name,
                "relation": d.relation,
                "relation_label": relation_labels.get(d.relation, d.relation),
                "is_head": d.relation == RELATION_SELF,
                "document_count": d.profile["document_count"] if d.profile else 0,
                "profile_ready": d.profile["ready"] if d.profile else None,
            }
            for d in selected
        ],
        "checks": out_checks,
        "check_counts": family_checks.count_results(checks),
        "finding_counts": counts,
    }


@router.post(
    "/family/comparisons",
    status_code=201,
    summary="Compare family members",
    description="Creates a family comparison case for the members named (the head is always included) and "
    "runs the family checks on their verified profiles. Conflicts become findings the head can accept or "
    "dismiss (PATCH /cases/{id}/findings/{finding_id}). Head only.",
)
def create_comparison(
    payload: ComparisonCreateRequest,
    lang: str = Query(default="en"),
    user: User = Depends(_member),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    family = _own_family(db, user)
    by_id = {m.id: m for m in family.members}
    unknown = [i for i in payload.member_ids if i not in by_id]
    if unknown:
        raise HTTPException(422, "Some of those people are not in your family.")
    head = next(m for m in family.members if m.relation == RELATION_SELF)
    others = [i for i in dict.fromkeys(payload.member_ids) if i != head.id]
    if not others:
        raise HTTPException(422, "Pick at least one member besides yourself.")

    case_id = uuid.uuid4()
    case = Case(
        id=case_id,
        company_id=user.company_id,
        case_number=f"CASE-{case_id.hex[:8].upper()}",
        case_type=CaseType.family_comparison,
        submitted_by_user_id=user.id,
        status=CaseStatus.submitted,
        family_id=family.id,
        comparison_member_ids=[str(head.id), *map(str, others)],
    )
    db.add(case)
    db.flush()
    _sync_findings(db, case, _run(db, case, family, "en"))
    record_event(
        db, "family_comparison_created", case_id=case.id, actor_user_id=user.id,
        event_data={"family_id": str(family.id), "member_ids": case.comparison_member_ids},
    )
    db.commit()
    db.expire_all()
    case, family = _load_comparison(db, case_id, user, head_only=True)
    return _view(db, case, family, lang, user)


@router.get(
    "/family/comparisons",
    summary="Your family comparisons",
    description="The comparisons made for your family, newest first, with how many conflicts are still open.",
)
def list_comparisons(user: User = Depends(_member), db: Session = Depends(get_tenant_db)) -> list[dict[str, Any]]:
    family = _family_of(db, user)
    if family is None:
        return []
    names = {str(m.id): m.full_name for m in family.members}
    cases = db.execute(
        select(Case)
        .where(
            Case.family_id == family.id,
            Case.company_id == user.company_id,
            Case.case_type == CaseType.family_comparison,
            Case.status != CaseStatus.closed,
        )
        .order_by(Case.created_at.desc())
    ).scalars().all()
    findings = db.execute(
        select(CrossDocumentFinding).where(
            CrossDocumentFinding.case_id.in_([c.id for c in cases] or [uuid.uuid4()]),
            CrossDocumentFinding.company_id == user.company_id,
        )
    ).scalars().all()
    out = []
    for case in cases:
        mine = [f for f in findings if f.case_id == case.id]
        out.append(
            {
                "id": str(case.id),
                "case_number": case.case_number,
                "created_at": case.created_at.isoformat(),
                "members": [names.get(i, "?") for i in case.comparison_member_ids or []],
                "conflicts": len(mine),
                "open_conflicts": sum(1 for f in mine if finding_resolution(f.classification, f.review_status) == "open"),
            }
        )
    return out


@router.get(
    "/family/comparisons/{case_id}",
    summary="A family comparison",
    description="The members compared and every check with its result and, for a conflict, the finding and the "
    "decision on it. Readable by the head and by company reviewers.",
)
def get_comparison(
    case_id: uuid.UUID,
    lang: str = Query(default="en"),
    user: User = Depends(_member),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    case, family = _load_comparison(db, case_id, user, head_only=False)
    return _view(db, case, family, lang, user)


@router.post(
    "/family/comparisons/{case_id}/refresh",
    summary="Run the comparison again",
    description="Re-runs the checks on the members' current profiles. A conflict that is still there keeps "
    "its decision; one that has gone is removed; a new one starts open. Head only.",
)
def refresh_comparison(
    case_id: uuid.UUID,
    lang: str = Query(default="en"),
    user: User = Depends(_member),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    case, family = _load_comparison(db, case_id, user, head_only=True)
    if case.status == CaseStatus.closed:
        raise HTTPException(status.HTTP_409_CONFLICT, "This comparison is closed.")
    _sync_findings(db, case, _run(db, case, family, "en"))
    record_event(
        db, "family_comparison_refreshed", case_id=case.id, actor_user_id=user.id,
        event_data={"family_id": str(family.id)},
    )
    db.commit()
    db.expire_all()
    case, family = _load_comparison(db, case_id, user, head_only=True)
    return _view(db, case, family, lang, user)


@router.delete(
    "/family/comparisons/{case_id}",
    status_code=204,
    summary="Close a comparison",
    description="Removes it from your list; the record and its audit trail stay. Head only.",
)
def close_comparison(
    case_id: uuid.UUID, user: User = Depends(_member), db: Session = Depends(get_tenant_db)
) -> None:
    case, family = _load_comparison(db, case_id, user, head_only=True)
    case.status = CaseStatus.closed
    record_event(
        db, "family_comparison_closed", case_id=case.id, actor_user_id=user.id,
        event_data={"family_id": str(family.id)},
    )
    db.commit()
