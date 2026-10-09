"""
Files kept on this machine's disk instead of Azure Blob Storage
(`STORAGE_PROVIDER=local`). For development and demonstrations without a cloud
account; originals are still written once and never changed.

A stored file's durable URL is `local://<container>/<path>`. A browser fetches
it through GET /files/{token} (app/api/files.py), where the token carries the
path and an expiry and is signed with FILE_LINK_SECRET (the JWT secret when
that is unset), the same idea as a signed Blob Storage URL.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import shutil
import time
from pathlib import Path
from typing import BinaryIO
from urllib.parse import unquote, urlsplit

from app.core.config import settings
from app.services.storage_service import StorageOperationError, StorageService


def _sign(payload: str) -> str:
    secret = settings.file_link_secret or settings.jwt_secret_key
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]


def make_token(path: str, expires_in_minutes: int) -> str:
    payload = f"{int(time.time()) + expires_in_minutes * 60}|{path}"
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"{encoded}.{_sign(payload)}"


def read_token(token: str) -> str | None:
    """The file path a token grants, or None if it is forged or expired."""
    encoded, _, signature = token.partition(".")
    try:
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
        expires, path = payload.split("|", 1)
        fresh = int(expires) >= time.time()
    except (ValueError, UnicodeDecodeError):
        return None
    return path if fresh and hmac.compare_digest(signature, _sign(payload)) else None


class LocalStorageService(StorageService):
    def __init__(self, root: str, container_name: str, public_url: str):
        self._root = Path(root).resolve()
        self._container = container_name
        self._public_url = public_url.rstrip("/")
        self._root.mkdir(parents=True, exist_ok=True)

    def _relative(self, file_url: str) -> str:
        parts = urlsplit(file_url)
        return unquote(parts.path if parts.scheme else file_url).lstrip("/")

    def path_for(self, relative: str) -> Path:
        target = (self._root / relative).resolve()
        if self._root not in target.parents:
            raise StorageOperationError("That path is outside the storage folder.")
        return target

    def upload(self, blob_path: str, content: bytes | BinaryIO, content_type: str | None = None) -> str:
        target = self.path_for(blob_path)
        if target.exists():
            raise StorageOperationError(f"A file already exists at {blob_path}.")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "wb") as out:
                if isinstance(content, (bytes, bytearray)):
                    out.write(content)
                else:
                    shutil.copyfileobj(content, out)
        except OSError as exc:
            raise StorageOperationError(f"Failed to store the file: {exc}") from exc
        return f"local://{self._container}/{blob_path}"

    def get_download_url(self, file_url: str, expires_in_minutes: int = 15) -> str:
        return f"{self._public_url}/{make_token(self._relative(file_url), expires_in_minutes)}"

    def download_bytes(self, file_url: str) -> bytes:
        try:
            return self.path_for(self._relative(file_url)).read_bytes()
        except OSError as exc:
            raise StorageOperationError(f"Failed to read the file: {exc}") from exc

    def download_to(self, file_url: str, fileobj: BinaryIO) -> None:
        try:
            with open(self.path_for(self._relative(file_url)), "rb") as source:
                shutil.copyfileobj(source, fileobj)
        except OSError as exc:
            raise StorageOperationError(f"Failed to read the file: {exc}") from exc

    def delete(self, file_url: str) -> bool:
        target = self.path_for(self._relative(file_url))
        try:
            target.unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise StorageOperationError(f"Failed to delete the file: {exc}") from exc
