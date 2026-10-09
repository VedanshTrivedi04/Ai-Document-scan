"""Pydantic schemas for the auth endpoints."""
import uuid

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class LoginRequest(BaseModel):
    email: EmailStr = Field(description="Account email (matched exactly as stored).")
    password: str = Field(description="Account password.")


class RegisterRequest(BaseModel):
    full_name: str = Field(
        min_length=1, max_length=255, description="Your display name."
    )
    email: EmailStr = Field(description="Email address — must be unique across the platform.")
    password: str = Field(
        min_length=8, max_length=128,
        description="Password (8–128 characters). Stored hashed; never logged."
    )


class TokenResponse(BaseModel):
    access_token: str = Field(description="JWT. Send as `Authorization: Bearer <token>`.")
    token_type: str = Field(default="bearer", description="Always `bearer`.")
    company_subdomain: str | None = Field(
        default=None,
        description="The subdomain of the user's organisation, if it has one: where this sign-in belongs.",
    )
    must_change_password: bool = Field(
        default=False,
        description="True when the account has a temporary password (set by a family head): "
        "send the person to change it (POST /auth/me/password) before anything else.",
    )


class CurrentUserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None = Field(description="Display name, if one was set.")
    role: UserRole = Field(
        description="`user` (submitter), `reviewer_l1`, `reviewer_l2` (company roles) or `platform_admin`."
    )
    role_label: str = Field(description='Display label, e.g. "Reviewer L2".')
    is_active: bool = Field(description="Deactivated accounts are rejected on every request.")
    is_platform_admin: bool = Field(description="True for platform admins, who belong to no company.")
    company_id: uuid.UUID | None = Field(description="The user's company; null for a platform admin.")
    company_name: str | None = Field(description="Display name of the user's company.")
    company_subdomain: str | None = Field(default=None, description="The company's subdomain, if it has one.")
    must_change_password: bool = Field(default=False, description="See TokenResponse.must_change_password.")


class UploadLimitsResponse(BaseModel):
    """The calling company's upload limits, as enforced on its next upload."""

    max_file_size_mb: int = Field(description="Largest document, in MB (1 MB = 1,048,576 bytes).")
    max_zip_size_mb: int = Field(description="Largest bulk-upload zip, in MB.")
    max_file_size_bytes: int
    max_zip_size_bytes: int


class RetentionPolicyResponse(BaseModel):
    """How long the caller's uploads are kept (app/services/retention_service.py)."""

    document_retention_days: int = Field(
        description="Days an uploaded file is kept before it is removed (what was read from it stays). 0: kept."
    )
    private_upload_available: bool = Field(
        description="Whether the caller may create a private case (`delete_on_logout`): a `user` of the public site."
    )


class ChangePasswordRequest(BaseModel):
    """Change your own password. The current password is required; a
    forgotten password is reset by a platform admin instead (there is no
    self-service reset)."""

    current_password: str = Field(description="Your current password.")
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="New password (8-128 chars); stored hashed."
    )
