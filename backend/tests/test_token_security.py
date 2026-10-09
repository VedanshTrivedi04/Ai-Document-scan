"""Token hardening: revocation on sign-out and password change
(app/services/token_revocation.py), required claims, the secret check at
start-up and the security headers on every answer."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from pydantic import ValidationError

from app.api.auth import token_claims
from app.core.config import Settings, settings
from app.core.security import create_access_token, decode_access_token
from app.services import local_storage, login_throttle
from tests.conftest import _headers_for

OLD = "TestPassword123!"


def _login(client, email, password=OLD):
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _signed(claims: dict) -> dict:
    token = jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return {"Authorization": f"Bearer {token}"}


def test_every_token_is_its_own(seeded_user):
    first = decode_access_token(create_access_token(str(seeded_user.id)))
    second = decode_access_token(create_access_token(str(seeded_user.id)))
    assert first["jti"] and first["jti"] != second["jti"]


def test_sign_out_revokes_that_token_only(client, seeded_user):
    here, elsewhere = _login(client, seeded_user.email), _login(client, seeded_user.email)
    assert client.post("/auth/logout", headers=here).status_code == 200
    assert client.get("/auth/me", headers=here).status_code == 401
    assert client.get("/auth/me", headers=elsewhere).status_code == 200


def test_changing_the_password_ends_the_other_sessions_and_keeps_this_one(client, seeded_user):
    here, elsewhere = _login(client, seeded_user.email), _login(client, seeded_user.email)
    changed = client.post(
        "/auth/me/password", headers=here, json={"current_password": OLD, "new_password": "BrandNewPass9"}
    )
    assert changed.status_code == 204
    assert client.get("/auth/me", headers=elsewhere).status_code == 401
    assert client.get("/auth/me", headers=here).status_code == 200
    assert client.get("/auth/me", headers=_login(client, seeded_user.email, "BrandNewPass9")).status_code == 200


def test_an_admin_reset_ends_the_users_sessions(client, plain_user, platform_admin_headers):
    signed_in = _login(client, plain_user.email)
    reset = client.post(
        f"/settings/users/{plain_user.id}/reset-password",
        headers=platform_admin_headers,
        json={"password": "BrandNewPassword123!"},
    )
    assert reset.status_code == 200
    assert client.get("/auth/me", headers=signed_in).status_code == 401
    assert client.get("/auth/me", headers=platform_admin_headers).status_code == 200
    assert client.get("/auth/me", headers=_login(client, plain_user.email, "BrandNewPassword123!")).status_code == 200


def test_a_token_from_before_jti_existed_still_works(client, seeded_user):
    now = datetime.now(timezone.utc)
    legacy = {"sub": str(seeded_user.id), "iat": now, "exp": now + timedelta(hours=1), **token_claims(seeded_user)}
    headers = _signed(legacy)
    assert client.get("/auth/me", headers=headers).status_code == 200
    # It cannot be revoked on its own, so signing out leaves it to expire.
    assert client.post("/auth/logout", headers=headers).status_code == 200


def test_a_token_without_an_expiry_or_issue_time_is_refused(client, seeded_user):
    now = datetime.now(timezone.utc)
    assert client.get("/auth/me", headers=_signed({"sub": str(seeded_user.id), "iat": now})).status_code == 401
    assert client.get(
        "/auth/me", headers=_signed({"sub": str(seeded_user.id), "exp": now + timedelta(hours=1)})
    ).status_code == 401


def test_a_token_signed_with_another_key_is_refused(client, seeded_user):
    now = datetime.now(timezone.utc)
    forged = jwt.encode(
        {"sub": str(seeded_user.id), "iat": now, "exp": now + timedelta(hours=1)}, "x" * 40, algorithm="HS256"
    )
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_revocation_fails_open_when_redis_is_down(client, seeded_user, monkeypatch):
    headers = _headers_for(seeded_user)

    def down():
        raise ConnectionError("redis unreachable")

    monkeypatch.setattr(login_throttle, "_redis", down)
    assert client.get("/auth/me", headers=headers).status_code == 200
    assert client.post("/auth/logout", headers=headers).status_code == 200


def test_wrong_current_passwords_are_throttled(client, seeded_user, monkeypatch):
    monkeypatch.setattr(settings, "login_max_failed_attempts", 3)
    headers = _headers_for(seeded_user)
    body = {"current_password": "not-it", "new_password": "BrandNewPass9"}
    for _ in range(3):
        assert client.post("/auth/me/password", headers=headers, json=body).status_code == 400
    blocked = client.post(
        "/auth/me/password", headers=headers, json={"current_password": OLD, "new_password": "BrandNewPass9"}
    )
    assert blocked.status_code == 429 and "Retry-After" in blocked.headers
    # Signing in is counted separately.
    _login(client, seeded_user.email)


def test_answers_carry_the_security_headers(client, auth_headers):
    for response in (client.get("/health"), client.get("/auth/me", headers=auth_headers), client.get("/auth/me")):
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert response.headers["Cache-Control"] == "no-store"
        assert "Strict-Transport-Security" not in response.headers  # local environment


def test_file_links_keep_their_own_caching_and_may_be_framed(client):
    response = client.get("/files/not-a-real-token")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "X-Frame-Options" not in response.headers and "Cache-Control" not in response.headers


def test_a_weak_secret_is_refused_outside_a_local_environment():
    for secret in ("changeme-in-.env", "change-this-to-a-long-random-string", "short"):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, ENVIRONMENT="production", JWT_SECRET_KEY=secret)
        assert Settings(_env_file=None, ENVIRONMENT="local", JWT_SECRET_KEY=secret).is_local_environment
    strong = Settings(_env_file=None, ENVIRONMENT="production", JWT_SECRET_KEY="k" * 48)
    assert strong.docs_enabled is False
    assert Settings(_env_file=None, ENVIRONMENT="production", JWT_SECRET_KEY="k" * 48, API_DOCS_ENABLED=True).docs_enabled
    assert Settings(_env_file=None, ENVIRONMENT="local").docs_enabled is True


def test_only_hmac_algorithms_are_accepted():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, JWT_ALGORITHM="none")


def test_file_links_can_be_signed_with_their_own_secret(monkeypatch):
    token = local_storage.make_token("companies/a/file.pdf", 5)
    assert local_storage.read_token(token) == "companies/a/file.pdf"
    monkeypatch.setattr(settings, "file_link_secret", "f" * 48)
    assert local_storage.read_token(token) is None
    assert local_storage.read_token(local_storage.make_token("companies/a/file.pdf", 5)) == "companies/a/file.pdf"
