"""
An organisation's subdomain: `indore.example.org` is the company whose
`subdomain` is "indore".

The subdomain decides WHICH organisation a sign-in page belongs to and
limits sign-in there to that organisation's users. It is not what keeps one
organisation's data from another: that remains the signed token's company
plus Row-Level Security (docs/multi-tenancy.md). So a request that names no
subdomain, or names a false one, gains nothing.

Where the subdomain of a request comes from, in order:

1. the `X-Org-Subdomain` header (the frontend sends the label it is served
   from; needed when the API lives on another host);
2. the `Origin` header, then the `Host` header, when APP_BASE_DOMAIN is set
   and the host is one label below it.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

from fastapi import Request

from app.core.config import settings

HEADER = "X-Org-Subdomain"
# Labels that belong to the platform itself, never to an organisation.
RESERVED = frozenset({
    "www", "app", "api", "admin", "platform", "static", "assets", "cdn", "mail", "docs", "status",
    "auth", "login", "localhost", "test", "staging", "dev",
})
_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$")
MAX_LENGTH = 63


class InvalidSubdomain(ValueError):
    """The text cannot be used as an organisation's subdomain."""


def normalize(value: str) -> str:
    """`value` as a usable subdomain, or InvalidSubdomain with the reason."""
    label = value.strip().lower()
    if not _LABEL.match(label):
        raise InvalidSubdomain(
            "Use 3 to 63 lowercase letters, digits or hyphens, starting and ending with a letter or digit."
        )
    if "--" in label:
        raise InvalidSubdomain("Do not use two hyphens in a row.")
    if label in RESERVED:
        raise InvalidSubdomain(f"'{label}' is reserved and cannot be used.")
    return label


def suggest(name: str) -> str | None:
    """A subdomain made from an organisation's name, or None when the name
    has nothing usable ("Tehsil Office, Indore" -> "tehsil-office-indore")."""
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    label = re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", folded)).strip("-")[:MAX_LENGTH].strip("-")
    try:
        return normalize(label)
    except InvalidSubdomain:
        return None


def _label_under_base(host: str | None) -> str | None:
    base = (settings.app_base_domain or "").strip().lower().strip(".")
    if not host or not base:
        return None
    hostname = host.strip().lower().split(":")[0].strip(".")
    if not hostname.endswith("." + base):
        return None
    label = hostname[: -len(base) - 1]
    return label if "." not in label else None


def from_request(request: Request) -> str | None:
    """The organisation subdomain a request names, lower-cased; None when it
    names none or names one of the platform's own labels. The value is not
    checked against the database here."""
    named = request.headers.get(HEADER)
    if named is None:
        origin = request.headers.get("origin")
        named = _label_under_base(urlsplit(origin).netloc if origin else None) or _label_under_base(
            request.headers.get("host")
        )
    label = (named or "").strip().lower()
    if not label or label in RESERVED:
        return None
    return label
