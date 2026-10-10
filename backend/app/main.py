"""
FastAPI application entrypoint.

Auth, cases, document upload + the analysis pipeline, risk scoring,
reviewer actions, per-case PDF report export, the admin Settings API and
the audit history, and the platform-admin API (companies, billing/usage, queue
monitor) are wired up. Multi-tenant: see docs/multi-tenancy.md. MIS/compliance reporting (app/api/reports.py) is still a stub.
"""
from fastapi import FastAPI

from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.bulk_uploads import router as bulk_uploads_router
from app.api.case_actions import router as case_actions_router
from app.api.case_reports import router as case_reports_router
from app.api.cases import router as cases_router
from app.api.documents import router as documents_router
from app.api.families import router as families_router
from app.api.family_comparisons import router as family_comparisons_router
from app.api.files import router as files_router
from app.api.findings import router as findings_router
from app.api.i18n import router as i18n_router
from app.api.organisation import router as organisation_router
from app.api.platform import router as platform_router
from app.api.profiles import router as profiles_router
from app.api.settings import router as settings_router
from app.api.signatures import router as signatures_router
from app.core.config import APP_FULL_NAME, APP_NAME, settings
from app.core.security_headers import SecurityHeadersMiddleware

app = FastAPI(
    title=f"{APP_NAME} — {APP_FULL_NAME} API",
    version="0.1.0",
    description=(
        f"{APP_NAME} ({APP_FULL_NAME}) backend. "
        f"Environment: {settings.environment}."
    ),
    # The API's map is not published outside a local environment (API_DOCS_ENABLED).
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth_router)
app.include_router(cases_router)
app.include_router(case_actions_router)
app.include_router(findings_router)
app.include_router(i18n_router)
app.include_router(organisation_router)
app.include_router(profiles_router)
app.include_router(families_router)
app.include_router(family_comparisons_router)
app.include_router(files_router)
app.include_router(case_reports_router)
app.include_router(documents_router)
app.include_router(bulk_uploads_router)
app.include_router(signatures_router)
app.include_router(settings_router)
app.include_router(audit_router)
app.include_router(platform_router)


@app.get(
    "/",
    tags=["health"],
    summary="Root health check",
    description="Returns {status: ok} so load balancers and platform health checks succeed.",
)
def root_check() -> dict[str, str]:
    return {"status": "ok", "app": APP_NAME}


@app.get(
    "/health",
    tags=["health"],
    summary="Liveness check",
    description=(
        "Unauthenticated. Returns `{status: ok}`, with `environment` in a local environment only; "
        "does not touch the database, Redis or Azure."
    ),
)
def health_check() -> dict[str, str]:
    if not settings.is_local_environment:
        return {"status": "ok"}
    return {"status": "ok", "environment": settings.environment}

