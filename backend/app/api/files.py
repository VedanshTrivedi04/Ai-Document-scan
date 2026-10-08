"""
Serves files held by the local storage provider (app/services/local_storage.py)
to the browser. Not used with Azure Blob Storage, whose signed URLs point at
Azure directly.

No sign-in: like a signed Blob Storage URL, the link itself is the permission.
It is signed, names one file and expires after a few minutes.
"""
import mimetypes

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.services.local_storage import LocalStorageService, read_token
from app.services.storage_service import StorageOperationError, get_storage_service_for_task

router = APIRouter(tags=["files"])

_NOT_VALID = "This link is not valid or has expired."


@router.get("/files/{token}", include_in_schema=False)
def get_file(token: str) -> FileResponse:
    storage = get_storage_service_for_task()
    path = read_token(token)
    if path is None or not isinstance(storage, LocalStorageService):
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_VALID)
    try:
        target = storage.path_for(path)
    except StorageOperationError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_VALID) from None
    if not target.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found.")
    media_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    return FileResponse(target, media_type=media_type, headers={"Cache-Control": "private, max-age=300"})
