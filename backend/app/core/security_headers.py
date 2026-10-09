"""
Response headers every API answer carries, so a browser treats it safely:
no MIME sniffing, no framing by another site, no referrer (signed file links
would travel in it) and no caching of answers that hold people's details.

A header a route set itself is left alone. Signed file links (GET /files/...)
keep their own caching and may be shown inside the app's pages.
"""
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings

_ALWAYS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
_NOT_FOR_FILES = {
    "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
}
_HSTS = "max-age=31536000; includeSubDomains"


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_file = scope.get("path", "").startswith("/files/")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                wanted = dict(_ALWAYS)
                if not is_file:
                    wanted.update(_NOT_FOR_FILES)
                if not settings.is_local_environment:
                    wanted["Strict-Transport-Security"] = _HSTS
                for name, value in wanted.items():
                    if name not in headers:
                        headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)
