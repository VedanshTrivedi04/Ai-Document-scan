"""
Password hashing and JWT issuing/verification for the simple email/password
auth flow described in SPECIFICATION.md section 2 (Auth). Role and tenant
checks live in app/api/auth.py; revocation (sign-out, password change) in
app/services/token_revocation.py.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import ALLOWED_JWT_ALGORITHMS, settings

# Checked against when a sign-in names an address with no account, so that
# answer takes as long as a wrong password does.
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"no-such-account", bcrypt.gensalt()).decode("utf-8")


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def verify_password_or_dummy(plain_password: str, hashed_password: str | None) -> bool:
    """`verify_password`, spending the same time when there is no account to
    check against (always False then)."""
    if hashed_password is None:
        verify_password(plain_password, _DUMMY_PASSWORD_HASH)
        return False
    return verify_password(plain_password, hashed_password)


def _algorithm() -> str:
    # Never sign or accept anything but HMAC-SHA2, whatever JWT_ALGORITHM says.
    algorithm = settings.jwt_algorithm.upper()
    if algorithm not in ALLOWED_JWT_ALGORITHMS:
        raise RuntimeError(f"JWT_ALGORITHM must be one of {sorted(ALLOWED_JWT_ALGORITHMS)}.")
    return algorithm


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    to_encode: dict[str, Any] = {
        "sub": subject,
        # Sub-second, so "issued before the password changed" is exact.
        "iat": now.timestamp(),
        "exp": expire,
        # Names this one token, so it can be revoked on its own.
        "jti": uuid.uuid4().hex,
    }
    if extra_claims:
        to_encode.update(extra_claims)
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=_algorithm())


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[_algorithm()],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError:
        return None
