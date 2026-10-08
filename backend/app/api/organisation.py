"""
Which organisation a sign-in page is for.

`GET /organisation` needs no sign-in: the page calls it before anyone has
signed in, to show the organisation's name. It answers only for the
subdomain the request names (app/services/subdomains.py) and says no more
than that name. A subdomain nobody uses and a suspended organisation both
answer 404.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import tenancy
from app.db.session import get_system_db
from app.models.company import Company
from app.services import subdomains

router = APIRouter(tags=["organisation"])


class OrganisationResponse(BaseModel):
    subdomain: str | None = Field(description="Null on the platform's own site (no organisation named).")
    name: str | None = Field(description="The organisation's name; null on the platform's own site.")
    base_domain: str | None = Field(
        description="APP_BASE_DOMAIN, when configured: an organisation's site is <subdomain>.<base_domain>."
    )


@router.get(
    "/organisation",
    response_model=OrganisationResponse,
    summary="The organisation this site belongs to",
    description=(
        "Resolved from `?subdomain=`, else the `X-Org-Subdomain` header, else the request's host "
        "under APP_BASE_DOMAIN. With none of them, the platform's own site: `subdomain` and `name` "
        "are null. No sign-in needed."
    ),
    responses={404: {"description": "No active organisation uses this subdomain."}},
)
def current_organisation(
    request: Request,
    subdomain: str | None = Query(default=None, max_length=63),
    system_db: Session = Depends(get_system_db),
) -> OrganisationResponse:
    label = (subdomain or "").strip().lower() or subdomains.from_request(request)
    if not label or label in subdomains.RESERVED:
        return OrganisationResponse(subdomain=None, name=None, base_domain=settings.app_base_domain)

    state = tenancy.snapshot(system_db)
    tenancy.bind_platform(system_db)
    try:
        name = system_db.execute(
            select(Company.name).where(Company.subdomain == label, Company.is_active.is_(True))
        ).scalar_one_or_none()
    finally:
        tenancy.restore(system_db, state)
    if name is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No organisation uses this address.")
    return OrganisationResponse(subdomain=label, name=name, base_domain=settings.app_base_domain)
