"""
Shared case-visibility rule for every router that works on a case's contents.

Tenant first: the session passed in is bound to exactly one company (see
app/api/tenant_access.py), and every lookup here also filters by that company
explicitly — a case of another company is a 404 for everyone.

Within the company, every reviewer (L1 or L2) may SEE every case; a `user`
(submitter) only the cases they submitted, plus the cases of a family they
head (a member's bundle, a family comparison) and the cases about themselves
when they are a family member with a sign-in of their own. A case that is missing and a case
that belongs to someone else are indistinguishable to a submitter — both are a
404, never a 403 — so case ids cannot be probed. A platform admin (support
access, already audited by the case scope) may see any case of the company the
request is bound to.

Seeing is not acting: `can_act_on_case` is the tier rule for approve/reject/
escalate. A case assigned to the L2 tier stays readable by a `reviewer_l1` (GET
endpoints use `load_visible_case`) but every action on it is a 403. Platform
admins never act on cases.
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import tenancy
from app.models.case import Case, CaseTier
from app.models.family import Family, FamilyMember
from app.models.user import User, UserRole, has_rank


def scoped_company_id(db: Session) -> uuid.UUID:
    company_id = tenancy.bound_company_id(db)
    if company_id is None:
        raise tenancy.TenantContextError("This operation needs a session bound to a company.")
    return company_id


def is_family_head_of_case(db: Session, user: User, case: Case) -> bool:
    """Whether `user` heads the family the case belongs to (through the
    member it is about, or the family a comparison case is for)."""
    if case.family_id is None and case.family_member_id is None:
        return False
    stmt = select(Family.id).where(Family.company_id == case.company_id, Family.head_user_id == user.id)
    if case.family_id is not None:
        stmt = stmt.where(Family.id == case.family_id)
    else:
        stmt = stmt.join(FamilyMember, FamilyMember.family_id == Family.id).where(
            FamilyMember.id == case.family_member_id
        )
    return db.execute(stmt.limit(1)).first() is not None


def is_the_member_of_case(db: Session, user: User, case: Case) -> bool:
    """Whether the case is about the family member whose own sign-in is `user`."""
    if case.family_member_id is None:
        return False
    return (
        db.execute(
            select(FamilyMember.id).where(
                FamilyMember.id == case.family_member_id,
                FamilyMember.user_id == user.id,
                FamilyMember.company_id == case.company_id,
            )
        ).first()
        is not None
    )


def user_may_see_case(db: Session, user: User, case: Case) -> bool:
    if user.role != UserRole.user:
        return True
    return (
        case.submitted_by_user_id == user.id
        or is_family_head_of_case(db, user, case)
        or is_the_member_of_case(db, user, case)
    )


def can_manage_case(db: Session, user: User, case: Case) -> bool:
    """Who may settle a case's profile conflicts and accept or dismiss its
    findings: a company reviewer, the head of the case's family, or the
    submitter of a case that belongs to no family member. A member with a
    sign-in of their own does not: the head does."""
    if user.is_platform_admin:
        return False
    if has_rank(user.role, UserRole.reviewer_l1):
        return True
    if case.family_member_id is None and case.family_id is None:
        return case.submitted_by_user_id == user.id
    return is_family_head_of_case(db, user, case)


def ensure_can_manage_case(db: Session, user: User, case: Case, what: str) -> None:
    """403 unless `user` may manage the case (see `can_manage_case`)."""
    if not can_manage_case(db, user, case):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only the family head or a company reviewer can {what}.",
        )


def load_visible_case(db: Session, case_id: uuid.UUID, user: User, *options) -> Case:
    """The case, or 404 — including when it belongs to another company or a
    submitter asks for someone else's. `options` are SQLAlchemy loader
    options passed straight to the query."""
    stmt = select(Case).where(Case.id == case_id, Case.company_id == scoped_company_id(db))
    if options:
        stmt = stmt.options(*options)
    case = db.execute(stmt).scalar_one_or_none()
    if case is None or not user_may_see_case(db, user, case):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return case


# The lowest role that may act on a case assigned to each tier.
_MIN_ROLE_FOR_TIER: dict[CaseTier, UserRole] = {
    CaseTier.l1: UserRole.reviewer_l1,
    CaseTier.l2: UserRole.reviewer_l2,
}


def can_act_on_case(user: User, case: Case) -> bool:
    """Whether `user` may approve/reject/escalate `case` given its tier.
    Always False across companies and for platform admins."""
    if user.is_platform_admin or user.company_id != case.company_id:
        return False
    return has_rank(user.role, _MIN_ROLE_FOR_TIER[case.assigned_tier])


def ensure_can_act(user: User, case: Case) -> None:
    if not can_act_on_case(user, case):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This case has been escalated to an L2 reviewer. You can view it but not act on it.",
        )
