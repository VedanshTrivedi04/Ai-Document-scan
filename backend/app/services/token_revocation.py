"""
Revoking access tokens before they expire, kept in the broker Redis (the
client of app/services/login_throttle.py) so every API replica agrees.

* One token: sign-out revokes the token it was called with, by its `jti`,
  until that token would have expired anyway.
* All of an account's tokens: a password change or reset refuses every token
  issued before it. A person changing their own password keeps the session
  they did it from.

Tokens issued before `jti` existed carry none: they cannot be revoked one at a
time, only by the per-account cutoff, and expire on their own.

Fails open, like the sign-in throttle: if Redis is unreachable, tokens are
accepted on their signature and expiry alone (the outage is logged).
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from app.core.config import settings
from app.services import login_throttle

logger = logging.getLogger("fddt.token_revocation")

_TOKEN_KEY = "fddt:jwt:revoked:{jti}"
_CUTOFF_KEY = "fddt:jwt:cutoff:{user_id}"


def _lifetime_seconds() -> int:
    return max(1, settings.jwt_access_token_expire_minutes) * 60


def revoke(payload: dict[str, Any]) -> None:
    """Refuse this token from now on."""
    jti = payload.get("jti")
    if not jti:
        return
    try:
        remaining = int(float(payload.get("exp", 0)) - time.time()) + 1
        if remaining > 0:
            login_throttle._redis().set(_TOKEN_KEY.format(jti=jti), "1", ex=remaining)
    except Exception:  # noqa: BLE001
        logger.warning("token revocation unavailable (Redis); token not revoked", exc_info=True)


def revoke_all_for_user(user_id: uuid.UUID, keep: dict[str, Any] | None = None) -> None:
    """Refuse every token issued to this account until now, except the token
    whose payload is `keep`."""
    keep_jti = (keep or {}).get("jti") or ""
    try:
        login_throttle._redis().set(
            _CUTOFF_KEY.format(user_id=user_id), f"{time.time()!r}|{keep_jti}", ex=_lifetime_seconds()
        )
    except Exception:  # noqa: BLE001
        logger.warning("token revocation unavailable (Redis); sessions not ended", exc_info=True)


def is_revoked(payload: dict[str, Any]) -> bool:
    jti = payload.get("jti")
    try:
        client = login_throttle._redis()
        if jti and client.get(_TOKEN_KEY.format(jti=jti)) is not None:
            return True
        raw = client.get(_CUTOFF_KEY.format(user_id=payload.get("sub")))
        if raw is None:
            return False
        cutoff, _, keep_jti = (raw.decode() if isinstance(raw, bytes) else str(raw)).partition("|")
        if jti and jti == keep_jti:
            return False
        return float(payload.get("iat", 0)) < float(cutoff)
    except Exception:  # noqa: BLE001
        logger.warning("token revocation unavailable (Redis); not checked", exc_info=True)
        return False
