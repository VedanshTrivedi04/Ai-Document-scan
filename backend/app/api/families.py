"""
Families: one user, the head, enters the members of their household and
submits a document bundle (a case) for each.

Only the head manages a family. A member has no sign-in unless the head
creates one (when adding the member, or later): then the member signs in with
a temporary password, must change it at first sign-in, and sees only their
own data. The head can reset that password, switch the sign-in off, or remove
it. The company's reviewers can read a family (to review a member's case in
context) but not change it. Platform admins have no access here.

A tenant session may only read `users`, so these accounts are written through
a platform session, as the public sign-up does (app/api/auth.py).

The response carries the family-level checks (app/services/family_checks.py)
computed from each member's latest case, in the requested language.
"""
import secrets
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_tenant_db, require_company_role
from app.core.security import hash_password
from app.db import tenancy
from app.db.session import get_system_db
from app.models.case import Case, is_identity_case_type
from app.models.document import Document
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


class MemberLoginRequest(BaseModel):
    email: EmailStr = Field(description="The member's sign-in email; unique across the platform.")
    password: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="Leave out to have a temporary password generated; it is shown once, in `credentials`. "
        "Either way the member must change it at first sign-in.",
    )


class MemberCreateRequest(BaseModel):
    full_name: str = Field(max_length=255)
    relation: MemberRelation
    date_of_birth: date | None = None
    login: MemberLoginRequest | None = Field(
        default=None, description="Also create a sign-in for this member."
    )

    _name = field_validator("full_name")(_clean_name)


class MemberUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    relation: MemberRelation | None = None
    date_of_birth: date | None = None

    @field_validator("full_name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)


class PasswordResetRequest(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=128)


class LoginStateRequest(BaseModel):
    is_active: bool


_TEMPORARY_PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_EMAIL_TAKEN = "An account with that email already exists."


def _temporary_password() -> str:
    return "".join(secrets.choice(_TEMPORARY_PASSWORD_ALPHABET) for _ in range(12))


@contextmanager
def _platform(system_db: Session) -> Iterator[Session]:
    state = tenancy.snapshot(system_db)
    tenancy.bind_platform(system_db)
    try:
        yield system_db
    finally:
        tenancy.restore(system_db, state)


def _create_login_user(
    system_db: Session, head: User, member: FamilyMember, login: MemberLoginRequest
) -> tuple[User, str | None]:
    """The member's account, in the head's company. Returns it with the
    generated temporary password (None when the head chose one)."""
    email = str(login.email).strip()
    password = login.password or _temporary_password()
    with _platform(system_db):
        if system_db.execute(select(User.id).where(func.lower(User.email) == email.lower()).limit(1)).first():
            raise HTTPException(status.HTTP_409_CONFLICT, _EMAIL_TAKEN)
        user = User(
            email=email,
            full_name=member.full_name,
            role=UserRole.user,
            company_id=head.company_id,
            hashed_password=hash_password(password),
            is_active=True,
            must_change_password=True,
        )
        system_db.add(user)
        try:
            system_db.flush()
        except IntegrityError:
            system_db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, _EMAIL_TAKEN)
        system_db.commit()
        system_db.refresh(user)
    return user, (None if login.password else password)


def _discard_login_user(system_db: Session, user_id: uuid.UUID) -> None:
    with _platform(system_db):
        system_db.execute(delete(User).where(User.id == user_id))
        system_db.commit()


def _set_login_state(
    system_db: Session, user_id: uuid.UUID, *, is_active: bool | None = None, password: str | None = None
) -> None:
    with _platform(system_db):
        user = system_db.get(User, user_id)
        if user is None:
            return
        if is_active is not None:
            user.is_active = is_active
        if password is not None:
            user.hashed_password = hash_password(password)
            user.must_change_password = True
        system_db.commit()


def _credentials(member: FamilyMember, user: User, temporary_password: str | None) -> dict[str, Any]:
    return {"member_id": str(member.id), "email": user.email, "temporary_password": temporary_password}


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


def _login_member(family: Family, member_id: uuid.UUID) -> FamilyMember:
    member = _own_member(family, member_id)
    if member.relation == RELATION_SELF:
        raise HTTPException(status.HTTP_409_CONFLICT, "The head of the family already has an account.")
    return member


def _own_member(family: Family, member_id: uuid.UUID) -> FamilyMember:
    member = next((m for m in family.members if m.id == member_id), None)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such member in your family.")
    return member


def member_identity_cases(db: Session, family: Family, member: FamilyMember) -> list[Case]:
    """A member's identity bundles, oldest first. The head's also include
    identity cases the head submitted without naming a member."""
    cases = [c for c in member.cases if is_identity_case_type(c.case_type)]
    if member.relation == RELATION_SELF:
        standalone_cases = db.execute(
            select(Case).where(
                Case.submitted_by_user_id == family.head_user_id,
                Case.family_member_id.is_(None),
                Case.company_id == family.company_id,
            )
        ).scalars().all()
        cases.extend([c for c in standalone_cases if is_identity_case_type(c.case_type) and c not in cases])
    cases.sort(key=lambda c: c.created_at)
    return cases


def member_details(db: Session, family: Family) -> list[family_checks.MemberDetails]:
    """Every member as the family checks take them: as entered, with the
    profile of their latest bundle."""
    out = []
    for member in family.members:
        cases = member_identity_cases(db, family, member)
        profile = load_profile(db, cases[-1]) if cases else None
        out.append(
            family_checks.MemberDetails(str(member.id), member.full_name, member.relation, member.date_of_birth, profile)
        )
    return out


def _view(db: Session, family: Family, language: str) -> dict[str, Any]:
    language = normalize_language(language)
    members_out: list[dict[str, Any]] = []
    details: list[family_checks.MemberDetails] = []
    relation_labels = dict(
        zip(family_checks.RELATION_LABELS, translate(list(family_checks.RELATION_LABELS.values()), language))
    )
    for member in family.members:
        login_user = db.get(User, member.user_id) if member.user_id else None
        cases = member_identity_cases(db, family, member)
        profiles = {c.id: load_profile(db, c) for c in cases}
        documents_by_case: dict[uuid.UUID, list[Document]] = {c.id: [] for c in cases}
        if cases:
            for document in db.execute(
                select(Document)
                .where(Document.case_id.in_(list(documents_by_case)), Document.company_id == family.company_id)
                .order_by(Document.created_at)
            ).scalars():
                documents_by_case[document.case_id].append(document)
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
                "has_login": login_user is not None,
                "login": None
                if login_user is None
                else {
                    "email": login_user.email,
                    "is_active": login_user.is_active,
                    "must_change_password": login_user.must_change_password,
                },
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
                        "documents": [
                            {
                                "id": str(d.id),
                                "filename": d.original_filename,
                                "document_type": d.document_type,
                                "processing_status": d.processing_status.value,
                            }
                            for d in documents_by_case[c.id]
                        ],
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


@router.get(
    "/family/me",
    summary="The family you belong to as a member",
    description="For a member with a sign-in of their own: who they are in the family and their own cases and "
    "documents, and nothing about the other members. `null` for everyone else, including the head.",
)
def get_my_membership(user: User = Depends(_member), db: Session = Depends(get_tenant_db)) -> dict[str, Any] | None:
    member = db.execute(
        select(FamilyMember).where(FamilyMember.user_id == user.id, FamilyMember.company_id == user.company_id)
    ).scalar_one_or_none()
    if member is None:
        return None
    family = db.execute(
        select(Family).where(Family.id == member.family_id).options(selectinload(Family.members).selectinload(FamilyMember.cases))
    ).scalar_one()
    cases = member_identity_cases(db, family, member)
    documents: dict[uuid.UUID, list[Document]] = {c.id: [] for c in cases}
    if cases:
        for document in db.execute(
            select(Document).where(Document.case_id.in_(list(documents)), Document.company_id == family.company_id)
            .order_by(Document.created_at)
        ).scalars():
            documents[document.case_id].append(document)
    profiles = {c.id: load_profile(db, c) for c in cases}
    return {
        "member_id": str(member.id),
        "full_name": member.full_name,
        "relation": member.relation,
        "family_name": family.name,
        "latest_case_id": str(cases[-1].id) if cases else None,
        "profile_ready": profiles[cases[-1].id]["ready"] if cases else None,
        "cases": [
            {
                "id": str(c.id),
                "case_number": c.case_number,
                "status": c.status.value,
                "created_at": c.created_at.isoformat(),
                "document_count": profiles[c.id]["document_count"],
                "open_conflicts": profiles[c.id]["open_conflicts"],
                "documents": [
                    {
                        "id": str(d.id),
                        "filename": d.original_filename,
                        "document_type": d.document_type,
                        "processing_status": d.processing_status.value,
                    }
                    for d in documents[c.id]
                ],
            }
            for c in reversed(cases)
        ],
    }


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
    if db.execute(select(FamilyMember.id).where(FamilyMember.user_id == user.id)).first() is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Your account belongs to a family; only its head can set up a family."
        )
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
    system_db: Session = Depends(get_system_db),
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
    created: tuple[User, str | None] | None = None
    if payload.login is not None:
        try:
            created = _create_login_user(system_db, user, member, payload.login)
        except HTTPException:
            db.rollback()
            raise
        member.user_id = created[0].id
        record_event(
            db, "family_member_login_created", actor_user_id=user.id,
            event_data={
                "family_id": str(family.id), "member_id": str(member.id),
                "user_id": str(created[0].id), "email": created[0].email,  # never the password
            },
        )
    try:
        db.commit()
    except Exception:
        db.rollback()
        if created is not None:
            _discard_login_user(system_db, created[0].id)
        raise
    db.expire_all()
    view = _view(db, _own_family(db, user), lang)
    if created is not None:
        view["credentials"] = _credentials(member, created[0], created[1])
    return view


@router.post(
    "/family/members/{member_id}/login",
    status_code=201,
    summary="Create a sign-in for a member",
    description="For a member added without one. The response carries `credentials` once; a generated "
    "temporary password is not shown again (reset it to get a new one). 409 if the member already has a "
    "sign-in or the email is taken.",
)
def create_member_login(
    member_id: uuid.UUID,
    payload: MemberLoginRequest,
    lang: str = Query(default="en"),
    user: User = Depends(_member),
    db: Session = Depends(get_tenant_db),
    system_db: Session = Depends(get_system_db),
) -> dict[str, Any]:
    family = _own_family(db, user)
    member = _login_member(family, member_id)
    if member.user_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This member already has a sign-in.")
    created = _create_login_user(system_db, user, member, payload)
    try:
        member.user_id = created[0].id
        record_event(
            db, "family_member_login_created", actor_user_id=user.id,
            event_data={
                "family_id": str(family.id), "member_id": str(member.id),
                "user_id": str(created[0].id), "email": created[0].email,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        _discard_login_user(system_db, created[0].id)
        raise
    db.expire_all()
    view = _view(db, _own_family(db, user), lang)
    view["credentials"] = _credentials(member, created[0], created[1])
    return view


@router.post(
    "/family/members/{member_id}/login/reset-password",
    summary="Reset a member's password",
    description="Sets a new temporary password (the one sent, or a generated one shown once in "
    "`credentials`). The member must change it at next sign-in. Tokens already issued stay valid "
    "until they expire.",
)
def reset_member_password(
    member_id: uuid.UUID,
    payload: PasswordResetRequest,
    lang: str = Query(default="en"),
    user: User = Depends(_member),
    db: Session = Depends(get_tenant_db),
    system_db: Session = Depends(get_system_db),
) -> dict[str, Any]:
    family = _own_family(db, user)
    member = _login_member(family, member_id)
    login_user = db.get(User, member.user_id) if member.user_id else None
    if login_user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This member has no sign-in.")
    password = payload.password or _temporary_password()
    _set_login_state(system_db, login_user.id, password=password)
    record_event(
        db, "family_member_password_reset", actor_user_id=user.id,
        event_data={"family_id": str(family.id), "member_id": str(member.id), "user_id": str(login_user.id)},
    )
    db.commit()
    db.expire_all()
    view = _view(db, _own_family(db, user), lang)
    view["credentials"] = _credentials(member, login_user, None if payload.password else password)
    return view


@router.patch(
    "/family/members/{member_id}/login",
    summary="Switch a member's sign-in on or off",
    description="`is_active: false` stops the member signing in (their documents stay).",
)
def set_member_login_state(
    member_id: uuid.UUID,
    payload: LoginStateRequest,
    lang: str = Query(default="en"),
    user: User = Depends(_member),
    db: Session = Depends(get_tenant_db),
    system_db: Session = Depends(get_system_db),
) -> dict[str, Any]:
    family = _own_family(db, user)
    member = _login_member(family, member_id)
    if member.user_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This member has no sign-in.")
    _set_login_state(system_db, member.user_id, is_active=payload.is_active)
    record_event(
        db, "family_member_login_enabled" if payload.is_active else "family_member_login_disabled",
        actor_user_id=user.id,
        event_data={"family_id": str(family.id), "member_id": str(member.id), "user_id": str(member.user_id)},
    )
    db.commit()
    db.expire_all()
    return _view(db, _own_family(db, user), lang)


@router.delete(
    "/family/members/{member_id}/login",
    summary="Remove a member's sign-in",
    description="Switches the account off and detaches it from the member; the member and their "
    "documents stay. The email stays used by the switched-off account.",
)
def remove_member_login(
    member_id: uuid.UUID,
    lang: str = Query(default="en"),
    user: User = Depends(_member),
    db: Session = Depends(get_tenant_db),
    system_db: Session = Depends(get_system_db),
) -> dict[str, Any]:
    family = _own_family(db, user)
    member = _login_member(family, member_id)
    if member.user_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This member has no sign-in.")
    login_user_id = member.user_id
    _set_login_state(system_db, login_user_id, is_active=False)
    member.user_id = None
    record_event(
        db, "family_member_login_removed", actor_user_id=user.id,
        event_data={"family_id": str(family.id), "member_id": str(member.id), "user_id": str(login_user_id)},
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
    system_db: Session = Depends(get_system_db),
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
    login_user_id = member.user_id
    family.members.remove(member)
    db.commit()
    if login_user_id is not None:
        _set_login_state(system_db, login_user_id, is_active=False)
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
