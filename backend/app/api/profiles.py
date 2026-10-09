"""
The verified profile of the person an identity case is about, and forms
pre-filled from it (app/services/person_profile.py, form_templates.py).

Reading follows the case's own visibility: the applicant who submitted the
case, the company's reviewers, and platform admins (audited, read-only).
Choosing which document is right for a disputed detail is a reviewer action.
"""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api.auth import get_current_user, get_tenant_db, require_company_role
from app.api.case_access import ensure_can_act, ensure_can_manage_case, load_visible_case, scoped_company_id
from app.api.tenant_access import CaseScope, get_case_scope
from app.models.base import utcnow
from app.models.case import Case, CaseStatus, CaseType, is_identity_case_type
from app.models.user import User, UserRole, has_rank, role_label
from app.services import form_templates
from app.services.audit_service import record_event
from app.services.case_profile import load_profile, profile_documents
from app.services.person_profile import PROFILE_FIELDS
from app.services.translation_service import normalize_language

router = APIRouter(tags=["profile"])

_reviewer = require_company_role(UserRole.reviewer_l1)
_DECIDED_CASE = (CaseStatus.approved, CaseStatus.rejected, CaseStatus.closed)
_NOT_IDENTITY = "This case is not a person's document bundle, so it has no profile."


class ProfileChoiceRequest(BaseModel):
    document_id: uuid.UUID | None = Field(
        description="The document whose value is the right one for this detail; null removes the choice."
    )


def _case_profile(db: Session, case: Case) -> dict[str, Any]:
    if not is_identity_case_type(case.case_type):
        raise HTTPException(status.HTTP_409_CONFLICT, _NOT_IDENTITY)
    return load_profile(db, case)


@router.get(
    "/cases/{case_id}/profile",
    summary="Verified profile of the person a case is about",
    description=(
        "One entry per detail (`full_name`, `parent_or_spouse_name`, `date_of_birth`, `gender`, "
        "`address`, `annual_income`) with `status`: `agreed` (the documents agree; `value` and its "
        "source document are given), `conflict` (unresolved contradiction; no value, `candidates` "
        "listed, `suggested_document_id` and `documents_to_correct` when most documents agree), "
        "`chosen` (a reviewer picked the right document) or `missing`. Also `postal_code`, "
        "`id_numbers` by document type, `counts` and `ready` (no conflict left). Identity cases only."
    ),
    responses={
        401: {"description": "Missing, invalid or expired bearer token, or the user is inactive."},
        404: {"description": "No such case (or, for a `user`, not one they submitted)."},
        409: {"description": "The case is not an identity or hiring verification case."},
    },
)
def get_profile(case_id: uuid.UUID, scope: CaseScope = Depends(get_case_scope)) -> dict[str, Any]:
    case = load_visible_case(scope.db, case_id, scope.ctx.user)
    return _case_profile(scope.db, case)


@router.put(
    "/cases/{case_id}/profile/{field_name}",
    summary="Choose the right document for a disputed detail",
    description=(
        "Company reviewers only. Sets which document's value is the final one for `field_name`; the "
        "detail then has status `chosen`. `document_id: null` removes the choice. Returns the "
        "updated profile. Writes a `profile_value_chosen` audit event."
    ),
    responses={
        401: {"description": "Missing, invalid or expired bearer token, or the user is inactive."},
        403: {"description": "Requires a company reviewer role; a `reviewer_l1` also gets 403 on a case escalated to L2."},
        404: {"description": "No such case in your company, or no such detail."},
        409: {"description": "Not an identity case, or the case is already decided."},
        422: {"description": "The document is not part of this case or does not state this detail."},
    },
)
def choose_profile_value(
    case_id: uuid.UUID,
    field_name: str,
    payload: ProfileChoiceRequest,
    actor: User = Depends(require_company_role(UserRole.user)),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    case = db.execute(
        select(Case).where(Case.id == case_id, Case.company_id == scoped_company_id(db))
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")

    # Authorisation: a company reviewer (L1/L2), the head of the case's family, or the
    # submitter of a case that belongs to no family member. A family member signed in
    # on their own cannot: their head does.
    is_reviewer = has_rank(actor.role, UserRole.reviewer_l1)
    ensure_can_manage_case(db, actor, case, "choose profile values for this case")
    if is_reviewer:
        ensure_can_act(actor, case)

    if not is_identity_case_type(case.case_type):
        raise HTTPException(status.HTTP_409_CONFLICT, _NOT_IDENTITY)
    if field_name not in PROFILE_FIELDS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such profile detail")
    if case.status in _DECIDED_CASE:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This case is already {case.status.value}; its profile can no longer be changed.",
        )

    overrides = dict(case.profile_overrides or {})
    chosen = None
    if payload.document_id is None:
        overrides.pop(field_name, None)
    else:
        chosen = next(
            (d for d in profile_documents(db, case) if d.id == str(payload.document_id)), None
        )
        if chosen is None or (chosen.identity_fields.get(field_name) or {}).get("value") in (None, ""):
            raise HTTPException(
                422,
                "That document is not part of this case or does not state this detail.",
            )
        overrides[field_name] = {
            "document_id": chosen.id,
            "chosen_by_user_id": str(actor.id),
            "chosen_at": utcnow().isoformat(),
        }
    case.profile_overrides = overrides
    flag_modified(case, "profile_overrides")
    record_event(
        db,
        "profile_value_chosen",
        case_id=case.id,
        actor_user_id=actor.id,
        event_data={
            "field_name": field_name,
            "document_id": chosen.id if chosen else None,
            "document_type": chosen.document_type if chosen else None,
            "actor_role": role_label(actor.role),
        },
    )
    db.commit()
    return _case_profile(db, case)


@router.get(
    "/forms",
    summary="Forms that can be pre-filled",
    description="Sample application forms. `case_type` limits the list to forms for that kind of case.",
)
def list_forms(
    case_type: CaseType | None = Query(default=None),
    lang: str = Query(default="en"),
    _: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    language = normalize_language(lang)
    return [
        form_templates.describe_form(form, language)
        for form in form_templates.forms_for(case_type.value if case_type else None)
    ]


@router.get(
    "/cases/{case_id}/forms/{form_id}",
    summary="A form pre-filled from the case's verified profile",
    description=(
        "Each field has `status`: `filled` (`value`, `display_value` and the source document are "
        "given), `needs_attention` (the documents dispute the detail; left empty, see `note`) or "
        "`to_fill` (the applicant enters it). `ready` is false while any field needs attention."
    ),
    responses={
        401: {"description": "Missing, invalid or expired bearer token, or the user is inactive."},
        404: {"description": "No such case (or, for a `user`, not one they submitted), or no such form for this kind of case."},
        409: {"description": "The case is not an identity or hiring verification case."},
    },
)
def prefilled_form(
    case_id: uuid.UUID,
    form_id: str,
    lang: str = Query(default="en"),
    scope: CaseScope = Depends(get_case_scope),
) -> dict[str, Any]:
    case = load_visible_case(scope.db, case_id, scope.ctx.user)
    profile = _case_profile(scope.db, case)
    form = form_templates.get_form(form_id)
    if form is None or case.case_type.value not in form.case_types:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such form for this kind of case")
    return {
        "case_id": str(case.id),
        "case_number": case.case_number,
        "checks_complete": profile["checks_complete"],
        **form_templates.prefill(form, profile, language=normalize_language(lang)),
    }
