"""
Families: one user, the head, enters the members of their household and
submits a document bundle (a case) for each.

Only the head manages a family. Members have no sign-in of their own. The
company's reviewers can read a family (to review a member's case in
context) but not change it. Platform admins have no access here.

The response carries the family-level checks (app/services/family_checks.py)
computed from each member's latest case, in the requested language.
"""
import uuid
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_tenant_db, require_company_role
from app.models.case import Case, is_identity_case_type
from app.models.family import RELATION_SELF, Family, FamilyMember
from app.models.user import User, UserRole, has_rank
from app.services import family_checks
from app.services.audit_service import record_event
from app.services.case_profile import load_profile
from app.services.translation_service import normalize_language, translate

router = APIRouter(tags=["family"])

_member = require_company_role(UserRole.user)
MemberRelation = Literal["spouse", "son", "daughter", "father", "mother", "other"]


def _clean_name(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError("must not be blank")
    return value


class FamilyCreateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255, description="Defaults to the head's name plus 'family'.")
    head_date_of_birth: date | None = None


class MemberCreateRequest(BaseModel):
    full_name: str = Field(max_length=255)
    relation: MemberRelation
    date_of_birth: date | None = None

    _name = field_validator("full_name")(_clean_name)


class MemberUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    relation: MemberRelation | None = None
    date_of_birth: date | None = None

    @field_validator("full_name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)


def _family_of(db: Session, user: User) -> Family | None:
    return db.execute(
        select(Family)
        .where(Family.head_user_id == user.id, Family.company_id == user.company_id)
        .options(selectinload(Family.members).selectinload(FamilyMember.cases))
    ).scalar_one_or_none()


def _own_family(db: Session, user: User) -> Family:
    family = _family_of(db, user)
    if family is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You have not set up a family yet.")
    return family


def _own_member(family: Family, member_id: uuid.UUID) -> FamilyMember:
    member = next((m for m in family.members if m.id == member_id), None)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such member in your family.")
    return member


def _view(db: Session, family: Family, language: str) -> dict[str, Any]:
    language = normalize_language(language)
    members_out: list[dict[str, Any]] = []
    details: list[family_checks.MemberDetails] = []
    relation_labels = dict(
        zip(family_checks.RELATION_LABELS, translate(list(family_checks.RELATION_LABELS.values()), language))
    )
    for member in family.members:
        cases = [c for c in member.cases if is_identity_case_type(c.case_type)]
        profiles = {c.id: load_profile(db, c) for c in cases}
        latest = cases[-1] if cases else None
        profile = profiles[latest.id] if latest else None
        details.append(
            family_checks.MemberDetails(
                str(member.id), member.full_name, member.relation, member.date_of_birth, profile
            )
        )
        members_out.append(
            {
                "id": str(member.id),
                "full_name": member.full_name,
                "relation": member.relation,
                "relation_label": relation_labels.get(member.relation, member.relation),
                "date_of_birth": member.date_of_birth.isoformat() if member.date_of_birth else None,
                "is_head": member.relation == RELATION_SELF,
                "latest_case_id": str(latest.id) if latest else None,
                # None until the member has a case; then whether its profile has no conflict left.
                "profile_ready": profile["ready"] if profile else None,
                "cases": [
                    {
                        "id": str(c.id),
                        "case_number": c.case_number,
                        "case_type": c.case_type.value,
                        "status": c.status.value,
                        "created_at": c.created_at.isoformat(),
                        "document_count": profiles[c.id]["document_count"],
                        "checks_complete": profiles[c.id]["checks_complete"],
                        "open_conflicts": profiles[c.id]["open_conflicts"],
                    }
                    for c in reversed(cases)
                ],
            }
        )
    checks = family_checks.run_family_checks(details, language)
    return {
        "id": str(family.id),
        "name": family.name,
        "head_user_id": str(family.head_user_id),
        "language": language,
        "members": members_out,
        "checks": checks,
        "check_counts": family_checks.count_results(checks),
    }


@router.get(
    "/family",
    summary="The family you are the head of",
    description="The family with its members, each member's cases, and the family-level checks. "
    "`null` when you have not set one up yet.",
)
def get_my_family(
    lang: str = Query(default="en"), user: User = Depends(_member), db: Session = Depends(get_tenant_db)
) -> dict[str, Any] | None:
    family = _family_of(db, user)
    return _view(db, family, lang) if family else None


@router.post(
    "/family",
    status_code=201,
    summary="Set up your family",
    description="Creates the family with you as its head and first member (relation `self`). "
    "A user can head one family (409 if you already have one).",
)
def create_family(
    payload: FamilyCreateRequest,
    lang: str = Query(default="en"),
    user: User = Depends(_member),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    if _family_of(db, user) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already set up a family.")
    head_name = (user.full_name or user.email).strip()
    family = Family(
        company_id=user.company_id,
        head_user_id=user.id,
        name=" ".join((payload.name or "").split()) or f"{head_name} family",
    )
    family.members.append(
        FamilyMember(
            company_id=user.company_id, full_name=head_name, relation=RELATION_SELF,
            date_of_birth=payload.head_date_of_birth,
        )
    )
    db.add(family)
    db.flush()
    record_event(db, "family_created", actor_user_id=user.id, event_data={"family_id": str(family.id)})
    db.commit()
    return _view(db, _own_family(db, user), lang)


@router.post("/family/members", status_code=201, summary="Add a member to your family")
def add_member(
    payload: MemberCreateRequest,
    lang: str = Query(default="en"),
    user: User = Depends(_member),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    family = _own_family(db, user)
    member = FamilyMember(
        company_id=user.company_id, family_id=family.id, full_name=payload.full_name,
        relation=payload.relation, date_of_birth=payload.date_of_birth,
    )
    db.add(member)
    db.flush()
    record_event(
        db, "family_member_added", actor_user_id=user.id,
        event_data={"family_id": str(family.id), "member_id": str(member.id), "relation": member.relation},
    )
    db.commit()
    db.expire_all()
    return _view(db, _own_family(db, user), lang)


@router.patch(
    "/family/members/{member_id}",
    summary="Correct a member's details",
    description="Only the fields sent are changed. Your own entry keeps the relation `self`.",
)
def update_member(
    member_id: uuid.UUID,
    payload: MemberUpdateRequest,
    lang: str = Query(default="en"),
    user: User = Depends(_member),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    family = _own_family(db, user)
    member = _own_member(family, member_id)
    changes = payload.model_dump(exclude_unset=True)
    if "relation" in changes and member.relation == RELATION_SELF:
        raise HTTPException(status.HTTP_409_CONFLICT, "Your own entry is the head of the family.")
    if changes.get("full_name") is None:
        changes.pop("full_name", None)
    if "relation" in changes and changes["relation"] is None:
        changes.pop("relation")
    for name, value in changes.items():
        setattr(member, name, value)
    record_event(
        db, "family_member_updated", actor_user_id=user.id,
        event_data={"family_id": str(family.id), "member_id": str(member.id), "fields": sorted(changes)},
    )
    db.commit()
    db.expire_all()
    return _view(db, _own_family(db, user), lang)


@router.delete(
    "/family/members/{member_id}",
    summary="Remove a member added by mistake",
    description="Refused (409) for your own entry and for a member who already has a case.",
)
def remove_member(
    member_id: uuid.UUID,
    lang: str = Query(default="en"),
    user: User = Depends(_member),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    family = _own_family(db, user)
    member = _own_member(family, member_id)
    if member.relation == RELATION_SELF:
        raise HTTPException(status.HTTP_409_CONFLICT, "The head of the family cannot be removed.")
    case_count = db.execute(
        select(func.count()).select_from(Case).where(
            Case.family_member_id == member.id, Case.company_id == user.company_id
        )
    ).scalar_one()
    if case_count:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This member already has documents submitted and cannot be removed."
        )
    record_event(
        db, "family_member_removed", actor_user_id=user.id,
        event_data={"family_id": str(family.id), "member_id": str(member.id), "relation": member.relation},
    )
    family.members.remove(member)
    db.commit()
    db.expire_all()
    return _view(db, _own_family(db, user), lang)


@router.get(
    "/families/{family_id}",
    summary="A family, for its head or a reviewer",
    description="The same view as GET /family. Readable by the head of that family and by the "
    "company's reviewers; anyone else gets 404.",
)
def get_family(
    family_id: uuid.UUID,
    lang: str = Query(default="en"),
    user: User = Depends(_member),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    family = db.execute(
        select(Family)
        .where(Family.id == family_id, Family.company_id == user.company_id)
        .options(selectinload(Family.members).selectinload(FamilyMember.cases))
    ).scalar_one_or_none()
    if family is None or not (family.head_user_id == user.id or has_rank(user.role, UserRole.reviewer_l1)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Family not found")
    return _view(db, family, lang)
