"""
Auth endpoints (POST /auth/login, GET /auth/me) and the dependencies every
other router uses for identity, role and tenant checks.

Every protected endpoint applies TWO mandatory checks:

1. Role — `require_company_role(min)` for company users (ranked user <
   reviewer_l1 < reviewer_l2), `require_platform_admin` for platform-only
   routes, or `require_reader(min)` for read-only routes that platform admins
   may also use for support.
2. Tenant — the request's data session (`get_tenant_db`) is bound to the
   caller's company, so every query it runs is filtered to that company in the
   application layer AND by PostgreSQL Row-Level Security. A resource id from
   another company therefore resolves to "not found" (404). Platform admins
   have no company: routes they may use bind the session to the company of the
   resource they are reading (app/api/tenant_access.py), and that access is
   audited.

The JWT carries `role`, `company_id` (null for platform admins) and
`is_platform_admin`, but the user is always re-read from the database and the
token's company must still match it — a moved, demoted or deactivated
account, or a suspended company, takes effect on the next request.
"""
import uuid
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
    verify_password_or_dummy,
)
from app.db import tenancy
from app.db.session import get_db, get_system_db
from app.models.company import Company
from app.models.user import User, UserRole, has_rank, role_label
from app.schemas.auth import (
    ChangePasswordRequest,
    CurrentUserResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    RetentionPolicyResponse,
    UploadLimitsResponse,
)
from app.services import login_throttle, subdomains, token_revocation
from app.services.audit_service import record_event
from app.services.storage_service import StorageService, get_storage_service

router = APIRouter(prefix="/auth", tags=["auth"])

_bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED = {"WWW-Authenticate": "Bearer"}


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=detail, headers=_UNAUTHORIZED)


def token_claims(user: User) -> dict:
    return {
        "role": user.role.value,
        "company_id": str(user.company_id) if user.company_id else None,
        "is_platform_admin": user.is_platform_admin,
    }


def _company_is_active(system_db: Session, company_id: uuid.UUID | None) -> bool:
    return _company_state(system_db, company_id)[0]


def _company_state(system_db: Session, company_id: uuid.UUID | None) -> tuple[bool, str | None]:
    """(whether the company may be used, its subdomain). A platform admin
    belongs to no company: usable, no subdomain."""
    if company_id is None:
        return True, None
    row = system_db.execute(
        select(Company.is_active, Company.subdomain).where(Company.id == company_id)
    ).first()
    return (bool(row[0]), row[1]) if row else (False, None)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    system_db: Session = Depends(get_system_db),
) -> User:
    """The authenticated user, loaded through the platform path (identity
    lookup happens before we know which company the caller belongs to)."""
    if credentials is None:
        raise _unauthorized("Not authenticated")

    payload = decode_access_token(credentials.credentials)
    if payload is None or "sub" not in payload:
        raise _unauthorized("Invalid or expired token")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, TypeError):
        raise _unauthorized("Invalid or expired token")
    # Signed out, or issued before the account's password last changed.
    if token_revocation.is_revoked(payload):
        raise _unauthorized("Invalid or expired token")
    request.state.token_payload = payload

    state = tenancy.snapshot(system_db)
    tenancy.bind_platform(system_db)
    try:
        user = system_db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if user is None or not user.is_active:
            raise _unauthorized("User not found or inactive")
        # The token's tenant claim must still describe this account: a user
        # moved to another company (or promoted out of one) needs a new token.
        claimed_company = payload.get("company_id")
        actual_company = str(user.company_id) if user.company_id else None
        if "company_id" in payload and claimed_company != actual_company:
            raise _unauthorized("Your account's company changed. Please sign in again.")
        if bool(payload.get("is_platform_admin", user.is_platform_admin)) != user.is_platform_admin:
            raise _unauthorized("Your account's role changed. Please sign in again.")
        active, company_subdomain = _company_state(system_db, user.company_id)
        if not active:
            raise _unauthorized("Your company's account is suspended.")
        # A sign-in is only good on its own organisation's site.
        requested = subdomains.from_request(request)
        if requested is not None and requested != company_subdomain:
            raise _unauthorized("This sign-in belongs to a different organisation. Please sign in again.")
    finally:
        tenancy.restore(system_db, state)
    return user


@dataclass(frozen=True)
class AuthContext:
    """Who is calling and which company they are confined to."""

    user: User

    @property
    def is_platform_admin(self) -> bool:
        return self.user.is_platform_admin

    @property
    def company_id(self) -> uuid.UUID | None:
        return self.user.company_id


def get_auth_context(user: User = Depends(get_current_user)) -> AuthContext:
    return AuthContext(user=user)


def get_tenant_db(
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Session:
    """The request's data session, bound to the caller's company. For a
    platform admin it is returned unbound — a platform route must bind it to
    the company it is acting on (app/api/tenant_access.py) before use, and an
    unbound session refuses to touch tenant data."""
    if not ctx.is_platform_admin:
        tenancy.bind_company(db, ctx.company_id)
    return db


_NO_PERMISSION = "You don't have permission to perform this action."


def require_company_role(minimum: UserRole):
    """403 unless the caller is a COMPANY user ranked at least `minimum`.
    Platform admins are refused: they have read-only support access and
    never act inside a company (approve, upload, ...)."""

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_platform_admin:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Platform admins have read-only support access to company data.",
            )
        if not has_rank(current_user.role, minimum):
            raise HTTPException(status.HTTP_403_FORBIDDEN, _NO_PERMISSION)
        return current_user

    return dependency


def require_reader(minimum: UserRole):
    """Read-only routes: company users ranked at least `minimum`, plus
    platform admins (support access — audited per resource by
    app/api/tenant_access.py)."""

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_platform_admin or has_rank(current_user.role, minimum):
            return current_user
        raise HTTPException(status.HTTP_403_FORBIDDEN, _NO_PERMISSION)

    return dependency


def require_platform_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requires the platform admin role.")
    return current_user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and obtain a JWT",
    description=(
        "Exchanges email + password for a bearer token (HS256; lifetime from "
        "JWT_ACCESS_TOKEN_EXPIRE_MINUTES). The token carries `role`, `company_id` (null for a "
        "platform admin) and `is_platform_admin`. An unknown email, a wrong password, a "
        "deactivated account and a suspended company all return the same 401 so accounts "
        "cannot be enumerated. When the request names an organisation's subdomain "
        "(`X-Org-Subdomain`, or the host under APP_BASE_DOMAIN), only that organisation's users can "
        "sign in there; any other account, including a platform admin, gets the same 401. Throttled (app/services/login_throttle.py): after "
        "LOGIN_MAX_FAILED_ATTEMPTS failures an email address is refused for LOGIN_LOCKOUT_MINUTES, "
        "and each client IP gets LOGIN_MAX_ATTEMPTS_PER_IP_PER_MINUTE attempts per minute; both "
        "answer 429 with a Retry-After header."
    ),
    responses={
        401: {"description": "Incorrect email or password (or the account/company is inactive)."},
        429: {"description": "Too many sign-in attempts for this email address or from this IP."},
    },
)
def login(
    payload: LoginRequest, request: Request, system_db: Session = Depends(get_system_db)
) -> TokenResponse:
    email = str(payload.email)
    blocked = login_throttle.check(email, request.client.host if request.client else None)
    if blocked is not None:
        minutes = max(1, -(-blocked.retry_after_seconds // 60))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many sign-in attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}.",
            headers={"Retry-After": str(blocked.retry_after_seconds)},
        )
    user = system_db.execute(
        select(User).where(func.lower(User.email) == str(payload.email).lower())
    ).scalar_one_or_none()
    active, company_subdomain = _company_state(system_db, user.company_id) if user else (False, None)
    # On an organisation's own site only that organisation's users sign in.
    # Someone else's account is answered exactly like a wrong password.
    requested = subdomains.from_request(request)
    wrong_organisation = requested is not None and requested != company_subdomain
    # Checked first and for every address, known or not: the answer must not
    # come back faster for an address that has no account.
    password_ok = verify_password_or_dummy(payload.password, user.hashed_password if user else None)
    if (
        user is None
        or not user.is_active
        or not password_ok
        or not active
        or wrong_organisation
    ):
        login_throttle.record_failure(email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    login_throttle.record_success(email)
    access_token = create_access_token(subject=str(user.id), extra_claims=token_claims(user))
    return TokenResponse(
        access_token=access_token,
        company_subdomain=company_subdomain,
        must_change_password=user.must_change_password,
    )


# ---------------------------------------------------------------------------
# Public citizen self-registration
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    summary="Create a citizen account (public)",
    description=(
        "Lets any visitor create their own account without admin involvement. "
        "The new account is placed in the Default Company (DEFAULT_COMPANY_NAME) "
        "with the `user` role — exactly the same as a platform admin creating an "
        "account there by hand. The response carries a ready-to-use bearer token "
        "so the caller is logged in immediately after registration. "
        "Rate-limited per IP (LOGIN_MAX_ATTEMPTS_PER_IP_PER_MINUTE). "
        "Returns 409 when the email is already taken, 503 when the Default "
        "Company does not exist (a platform admin removed it)."
    ),
    responses={
        409: {"description": "An account with that email already exists."},
        422: {"description": "Validation error (e.g. password shorter than 8 chars)."},
        429: {"description": "Too many requests from this IP."},
        503: {"description": "The Default Company does not exist — contact the platform admin."},
    },
)
def register(
    payload: RegisterRequest,
    request: Request,
    system_db: Session = Depends(get_system_db),
) -> TokenResponse:
    """Self-register a citizen. No authentication required."""
    from sqlalchemy.exc import IntegrityError

    # Reuse IP throttle so bots cannot spam account creation either.
    ip = request.client.host if request.client else None
    blocked = login_throttle.check("__register__", ip)
    if blocked is not None:
        minutes = max(1, -(-blocked.retry_after_seconds // 60))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Try again in {minutes} minute{'s' if minutes != 1 else ''}.",
            headers={"Retry-After": str(blocked.retry_after_seconds)},
        )

    # Resolve the Default Company — where public citizens live.
    default_company = system_db.execute(
        select(Company).where(Company.name == settings.default_company_name, Company.is_active.is_(True))
    ).scalar_one_or_none()
    if default_company is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The public registration portal is not available right now. "
                "Please contact the platform administrator."
            ),
        )

    email = str(payload.email).strip()

    # Duplicate-email check (fast path before the write).
    existing = system_db.execute(
        select(User.id).where(func.lower(User.email) == email.lower()).limit(1)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists. Please sign in instead.",
        )

    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        role=UserRole.user,
        company_id=default_company.id,
        hashed_password=hash_password(payload.password),
        is_active=True,
    )
    system_db.add(user)
    try:
        system_db.flush()
    except IntegrityError:
        system_db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists. Please sign in instead.",
        )

    record_event(
        system_db,
        "user_self_registered",
        actor_user_id=user.id,
        company_id=user.company_id,
        event_data={
            "user_id": str(user.id),
            "email": user.email,
            "company_id": str(user.company_id),
            "company_name": default_company.name,
        },
    )
    system_db.commit()
    system_db.refresh(user)

    access_token = create_access_token(subject=str(user.id), extra_claims=token_claims(user))
    # company_subdomain is intentionally None for the public portal — no redirect.
    return TokenResponse(access_token=access_token, company_subdomain=None)


def _private_case_rows(db: Session, user: User) -> list[dict]:
    from app.services import retention_service

    return [
        {"id": str(case.id), "case_number": case.case_number, "created_at": case.created_at.isoformat()}
        for case in retention_service.private_cases_of(db, user.id, user.company_id)
    ]


@router.get(
    "/private-cases",
    summary="My private cases that sign-out will empty",
    description=(
        "The caller's cases created with `delete_on_logout` that still hold data. Signing out "
        "(POST /auth/logout) removes their files and everything read from them."
    ),
    responses={401: {"description": "Missing, invalid or expired bearer token, or the user is inactive."}},
)
def list_private_cases(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_tenant_db)
) -> list[dict]:
    if current_user.is_platform_admin:
        return []
    return _private_case_rows(db, current_user)


@router.post(
    "/logout",
    summary="Sign out",
    description=(
        "Empties the caller's private cases (`delete_on_logout`): their files, the text read from them, "
        "the extracted details, the findings and the profile choices are removed for good; each emptied "
        "case stays as a closed record. Returns the case numbers emptied. The token the request was "
        "made with is revoked (app/services/token_revocation.py): it is refused from then on. A private "
        "case whose owner never signs out is emptied once that session has run out."
    ),
    responses={401: {"description": "Missing, invalid or expired bearer token, or the user is inactive."}},
)
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
    storage: StorageService = Depends(get_storage_service),
) -> dict:
    from app.services import retention_service

    removed: list = []
    if not current_user.is_platform_admin:
        removed = retention_service.wipe_private_cases_of(db, storage, current_user.id, current_user.company_id)
        db.commit()
    token_revocation.revoke(request.state.token_payload)
    return {"removed_cases": removed}


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Get the current user",
    description=(
        "Returns the authenticated user's profile, role and company. The role and company are "
        "re-read from the database on every request rather than trusted from the token, so a "
        "demotion, deactivation or company suspension takes effect immediately."
    ),
    responses={
        401: {"description": "Missing, invalid or expired bearer token, or the user is inactive."},
    },
)
def read_current_user(
    current_user: User = Depends(get_current_user),
    system_db: Session = Depends(get_system_db),
) -> CurrentUserResponse:
    company_name = company_subdomain = None
    if current_user.company_id is not None:
        row = system_db.execute(
            select(Company.name, Company.subdomain).where(Company.id == current_user.company_id)
        ).first()
        if row:
            company_name, company_subdomain = row
    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        role_label=role_label(current_user.role),
        is_active=current_user.is_active,
        is_platform_admin=current_user.is_platform_admin,
        company_id=current_user.company_id,
        company_name=company_name,
        company_subdomain=company_subdomain,
        must_change_password=current_user.must_change_password,
    )


@router.get(
    "/me/upload-limits",
    response_model=UploadLimitsResponse,
    summary="Get my company's upload limits",
    description=(
        "The per-file and per-zip limits the caller's company is held to (set per company by a "
        "platform admin). Read fresh on every request, so upload screens always show the limit that "
        "will actually be enforced. Platform admins belong to no company: 404."
    ),
    responses={
        401: {"description": "Missing, invalid or expired bearer token, or the user is inactive."},
        404: {"description": "Platform admins have no company and therefore no upload limits."},
    },
)
def read_upload_limits(
    current_user: User = Depends(get_current_user),
    system_db: Session = Depends(get_system_db),
) -> UploadLimitsResponse:
    from app.services.upload_limits import company_upload_limits

    if current_user.company_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Platform admins have no upload limits.")
    state = tenancy.snapshot(system_db)
    tenancy.bind_platform(system_db)
    try:
        limits = company_upload_limits(system_db, current_user.company_id)
    finally:
        tenancy.restore(system_db, state)
    return UploadLimitsResponse(
        max_file_size_mb=limits.max_file_size_mb,
        max_zip_size_mb=limits.max_zip_size_mb,
        max_file_size_bytes=limits.max_file_bytes,
        max_zip_size_bytes=limits.max_zip_bytes,
    )


@router.get(
    "/me/retention",
    response_model=RetentionPolicyResponse,
    summary="How long my uploads are kept",
    description=(
        "The number of days an uploaded file is stored before it is removed automatically (the details "
        "read from it are kept; 0 means files are kept), and whether the caller may make a private "
        "upload that is removed at sign-out."
    ),
    responses={401: {"description": "Missing, invalid or expired bearer token, or the user is inactive."}},
)
def read_retention_policy(
    current_user: User = Depends(get_current_user),
    system_db: Session = Depends(get_system_db),
) -> RetentionPolicyResponse:
    company_name = None
    if current_user.company_id is not None:
        state = tenancy.snapshot(system_db)
        tenancy.bind_platform(system_db)
        try:
            company_name = system_db.execute(
                select(Company.name).where(Company.id == current_user.company_id)
            ).scalar_one_or_none()
        finally:
            tenancy.restore(system_db, state)
    return RetentionPolicyResponse(
        document_retention_days=max(0, settings.document_retention_days),
        private_upload_available=current_user.role == UserRole.user
        and company_name == settings.default_company_name,
    )


@router.post(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change my password",
    description=(
        "Any signed-in user (every role) changes their own password by giving the current one. "
        "The new password (8-128 characters, different from the current one) is stored hashed and "
        "the change is recorded in the audit log (never the password). A forgotten password cannot "
        "be reset here: a platform admin resets it (`POST /settings/users/{id}/reset-password`). "
        "Every other token of the account is revoked; the one this request was made with stays valid. "
        "After LOGIN_MAX_FAILED_ATTEMPTS wrong current passwords the account's changes are refused "
        "for LOGIN_LOCKOUT_MINUTES (429)."
    ),
    responses={
        400: {"description": "The current password is wrong, or the new one equals it."},
        401: {"description": "Missing, invalid or expired bearer token, or the user is inactive."},
        422: {"description": "The new password is shorter than 8 or longer than 128 characters."},
        429: {"description": "Too many wrong current passwords."},
    },
)
def change_my_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    system_db: Session = Depends(get_system_db),
) -> None:
    # A stolen token must not be a way to guess the password without limit.
    throttle_key = f"password-change:{current_user.id}"
    blocked = login_throttle.check(throttle_key, None)
    if blocked is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again later.",
            headers={"Retry-After": str(blocked.retry_after_seconds)},
        )
    if not verify_password(payload.current_password, current_user.hashed_password):
        login_throttle.record_failure(throttle_key)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")
    login_throttle.record_success(throttle_key)
    if verify_password(payload.new_password, current_user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The new password must differ from the current one.")
    state = tenancy.snapshot(system_db)
    tenancy.bind_platform(system_db)
    try:
        user = system_db.get(User, current_user.id)
        user.hashed_password = hash_password(payload.new_password)
        user.must_change_password = False
        record_event(
            system_db,
            "user_password_changed",
            actor_user_id=user.id,
            company_id=user.company_id,
            event_data={"user_id": str(user.id), "email": user.email},  # never the password
        )
        system_db.commit()
        token_revocation.revoke_all_for_user(user.id, keep=request.state.token_payload)
    finally:
        tenancy.restore(system_db, state)
