"""
Document retention: how long an uploaded file is kept, and removing a private
case's data.

Two rules, both irreversible:

* **Files expire.** DOCUMENT_RETENTION_DAYS (default 24) after a document was
  uploaded, its stored file and its OCR text are removed. Everything read from
  the document stays: the extracted details, the findings, the verified
  profile, the audit trail. The zip of a bulk upload expires the same way.
  `purge_expired_files` does this once a day (app/tasks/retention_task.py).
  0 days switches it off.

* **Private cases.** A case created with `delete_on_logout` is emptied when its
  submitter signs out (POST /auth/logout): the files, the OCR text, the
  extracted details, the check results, the findings and the profile choices.
  The emptied case stays as a record with `data_removed_at` set and status
  `closed`. If the submitter never signs out, `purge_private_cases` empties it
  once the sign-in token it was created under must have run out
  (JWT_ACCESS_TOKEN_EXPIRE_MINUTES after the case was created).

What is not removed, because those tables are append-only by design (the
database refuses updates to them): the audit log, case actions, risk
assessments and generated reports. Signature references are a reviewer's
reference library, not an upload, and are kept too.

A file whose removal fails (storage unreachable) keeps `file_deleted_at` NULL,
so the next run tries again; nothing is recorded as removed that was not.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, exists, null, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.base import utcnow
from app.models.bulk_upload import BulkUpload, BulkUploadStatus
from app.models.case import Case, CaseStatus
from app.models.cross_document_finding import CrossDocumentFinding
from app.models.document import Document, DocumentProcessingStatus
from app.models.document_check import DocumentCheck
from app.services.audit_service import record_event
from app.services.storage_service import StorageOperationError, StorageService

logger = logging.getLogger("fddt.retention")

REASON_EXPIRED = "retention_period"
REASON_LOGOUT = "private_case_sign_out"
REASON_SESSION_ENDED = "private_case_session_ended"

REMOVED_FILENAME = "removed document"
_FILE_GONE = "The file was removed before it could be read."
_UNFINISHED = (DocumentProcessingStatus.pending, DocumentProcessingStatus.processing)


def retention_days() -> int:
    return max(0, settings.document_retention_days)


def file_expires_at(created_at: datetime | None, file_deleted_at: datetime | None = None) -> datetime | None:
    """When a file uploaded at `created_at` will be removed; None when it is
    already gone or retention is switched off."""
    if created_at is None or file_deleted_at is not None or retention_days() == 0:
        return None
    return created_at + timedelta(days=retention_days())


def remove_document_file(
    db: Session,
    storage: StorageService,
    document: Document,
    *,
    reason: str,
    actor_user_id: uuid.UUID | None = None,
) -> bool:
    """Remove one document's stored file and OCR text; what was read from it
    stays. False when the file was already removed. Raises
    StorageOperationError if the storage refuses, leaving the row untouched."""
    if document.file_deleted_at is not None:
        return False
    storage.delete(document.blob_storage_path)
    document.file_deleted_at = utcnow()
    document.ocr_text = None
    if document.processing_status in _UNFINISHED:
        document.processing_status = DocumentProcessingStatus.failed
        document.processing_error = _FILE_GONE
    record_event(
        db,
        "document_file_deleted",
        case_id=document.case_id,
        document_id=document.id,
        actor_user_id=actor_user_id,
        company_id=document.company_id,
        event_data={"reason": reason, "retention_days": retention_days()},
    )
    return True


def wipe_case_data(
    db: Session,
    storage: StorageService,
    case: Case,
    *,
    reason: str,
    actor_user_id: uuid.UUID | None = None,
) -> dict[str, int]:
    """Empty a case: its files and everything read from them. Safe to run
    again (a file that could not be removed is retried). The caller commits."""
    documents = db.execute(
        select(Document).where(Document.case_id == case.id, Document.company_id == case.company_id)
    ).scalars().all()
    files_removed = files_failed = 0
    for document in documents:
        if document.file_deleted_at is None:
            try:
                storage.delete(document.blob_storage_path)
                document.file_deleted_at = utcnow()
                files_removed += 1
            except StorageOperationError as exc:
                files_failed += 1
                logger.warning("case %s: could not remove a file: %s", case.id, exc)
        document.ocr_text = None
        # SQL NULL, not the JSON value null: "nothing stored" is what the cleanup job looks for.
        document.extracted_fields = null()
        document.document_type = None
        document.processing_error = None
        document.original_filename = REMOVED_FILENAME
        if document.processing_status in _UNFINISHED:
            document.processing_status = DocumentProcessingStatus.failed
            document.processing_error = _FILE_GONE
    if documents:
        db.execute(
            update(DocumentCheck)
            .where(
                DocumentCheck.document_id.in_([d.id for d in documents]),
                DocumentCheck.company_id == case.company_id,
            )
            .values(result=null(), confidence=None, error_message=None)
        )
    db.execute(
        delete(CrossDocumentFinding).where(
            CrossDocumentFinding.case_id == case.id, CrossDocumentFinding.company_id == case.company_id
        )
    )
    first_time = case.data_removed_at is None
    case.profile_overrides = null()
    if first_time:
        case.data_removed_at = utcnow()
        case.status = CaseStatus.closed
    if first_time or files_removed:
        record_event(
            db,
            "case_data_removed",
            case_id=case.id,
            actor_user_id=actor_user_id,
            company_id=case.company_id,
            event_data={
                "reason": reason,
                "documents": len(documents),
                "files_removed": files_removed,
                "files_failed": files_failed,
            },
        )
    return {"documents": len(documents), "files_removed": files_removed, "files_failed": files_failed}


def private_cases_of(db: Session, user_id: uuid.UUID, company_id: uuid.UUID) -> list[Case]:
    """The user's private cases that still hold data."""
    return list(
        db.execute(
            select(Case)
            .where(
                Case.submitted_by_user_id == user_id,
                Case.company_id == company_id,
                Case.delete_on_logout.is_(True),
                Case.data_removed_at.is_(None),
            )
            .order_by(Case.created_at)
        ).scalars()
    )


def wipe_private_cases_of(db: Session, storage: StorageService, user_id: uuid.UUID, company_id: uuid.UUID) -> list[str]:
    """Empty every private case of a user who is signing out. Returns their
    case numbers. The caller commits."""
    removed = []
    for case in private_cases_of(db, user_id, company_id):
        wipe_case_data(db, storage, case, reason=REASON_LOGOUT, actor_user_id=user_id)
        removed.append(case.case_number)
    return removed


# ---------------------------------------------------------------------------
# Scheduled jobs (app/tasks/retention_task.py). They find their work through
# the platform session and do it in a session bound to the owning company,
# one item per transaction.
# ---------------------------------------------------------------------------

def _storage() -> StorageService:
    from app.services.storage_service import get_storage_service_for_task

    return get_storage_service_for_task()


def _sessions():
    from app.db.session import SessionLocal, system_session
    from app.tasks.tenant import open_task_session

    return SessionLocal, system_session, open_task_session


def purge_expired_files(dry_run: bool = False) -> dict[str, Any]:
    """Remove the files (documents, bulk-upload zips) past the retention
    period. `dry_run` only counts them."""
    days = retention_days()
    if days == 0:
        return {"skipped": "retention_disabled"}
    session_factory, system_session, open_task_session = _sessions()
    cutoff = utcnow() - timedelta(days=days)
    limit = max(1, settings.document_retention_batch_size)

    with system_session() as db:
        documents = db.execute(
            select(Document.id, Document.company_id)
            .where(Document.file_deleted_at.is_(None), Document.created_at < cutoff)
            .order_by(Document.created_at)
            .limit(limit)
        ).all()
        zips = db.execute(
            select(BulkUpload.id, BulkUpload.company_id)
            .where(
                BulkUpload.file_deleted_at.is_(None),
                BulkUpload.created_at < cutoff,
                BulkUpload.status.in_((BulkUploadStatus.complete, BulkUploadStatus.failed)),
            )
            .order_by(BulkUpload.created_at)
            .limit(limit)
        ).all()

    result: dict[str, Any] = {
        "retention_days": days,
        "cutoff": cutoff.isoformat(),
        "documents_due": len(documents),
        "zips_due": len(zips),
        "documents_removed": 0,
        "zips_removed": 0,
        "failed": 0,
        "dry_run": dry_run,
    }
    if dry_run:
        return result

    storage = _storage()
    for document_id, company_id in documents:
        db = open_task_session(session_factory, company_id)
        try:
            document = db.get(Document, document_id)
            if document is not None and remove_document_file(db, storage, document, reason=REASON_EXPIRED):
                db.commit()
                result["documents_removed"] += 1
        except StorageOperationError as exc:
            db.rollback()
            result["failed"] += 1
            logger.warning("document %s: file not removed: %s", document_id, exc)
        finally:
            db.close()

    for bulk_id, company_id in zips:
        db = open_task_session(session_factory, company_id)
        try:
            bulk = db.get(BulkUpload, bulk_id)
            if bulk is None or bulk.file_deleted_at is not None:
                continue
            storage.delete(bulk.blob_storage_path)
            bulk.file_deleted_at = utcnow()
            record_event(
                db,
                "bulk_upload_file_deleted",
                company_id=company_id,
                event_data={"bulk_upload_id": str(bulk.id), "reason": REASON_EXPIRED, "retention_days": days},
            )
            db.commit()
            result["zips_removed"] += 1
        except StorageOperationError as exc:
            db.rollback()
            result["failed"] += 1
            logger.warning("bulk upload %s: zip not removed: %s", bulk_id, exc)
        finally:
            db.close()

    if result["documents_removed"] or result["zips_removed"] or result["failed"]:
        logger.warning("retention_files_removed %s", result)
    return result


def purge_private_cases() -> dict[str, int]:
    """Empty private cases whose submitter never signed out, and finish any
    that were emptied while a document was still being read."""
    session_factory, system_session, open_task_session = _sessions()
    session_ended = utcnow() - timedelta(minutes=max(1, settings.jwt_access_token_expire_minutes))
    leftover = exists().where(
        Document.case_id == Case.id,
        or_(Document.file_deleted_at.is_(None), Document.extracted_fields.is_not(None), Document.ocr_text.is_not(None)),
    )
    with system_session() as db:
        due = db.execute(
            select(Case.id, Case.company_id)
            .where(
                Case.delete_on_logout.is_(True),
                or_(
                    and_(Case.data_removed_at.is_(None), Case.created_at < session_ended),
                    and_(Case.data_removed_at.is_not(None), leftover),
                ),
            )
            .order_by(Case.created_at)
            .limit(max(1, settings.document_retention_batch_size))
        ).all()

    storage = _storage() if due else None
    emptied = 0
    for case_id, company_id in due:
        db = open_task_session(session_factory, company_id)
        try:
            case = db.get(Case, case_id)
            if case is None:
                continue
            wipe_case_data(db, storage, case, reason=REASON_SESSION_ENDED)
            db.commit()
            emptied += 1
        except Exception:  # noqa: BLE001 - one bad case must not stop the rest
            db.rollback()
            logger.exception("private case %s could not be emptied", case_id)
        finally:
            db.close()
    if emptied:
        logger.warning("private_cases_emptied %s", emptied)
    return {"due": len(due), "emptied": emptied}
