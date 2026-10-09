"""
Document retention jobs (Celery beat, on housekeeping_queue). The rules are in
app/services/retention_service.py.

* `purge_expired_files`: once a day at DOCUMENT_RETENTION_HOUR_UTC. Removes
  the stored files (and OCR text) of documents, and the zips of bulk uploads,
  older than DOCUMENT_RETENTION_DAYS.
* `purge_private_cases`: every ten minutes. Empties private cases whose
  submitter's session has run out without a sign-out.

Both are safe to run again: an item already handled is skipped, and one whose
file could not be removed is retried on the next run.
"""
from __future__ import annotations

from app.services import retention_service
from app.tasks.celery_app import celery_app


@celery_app.task(name="purge_expired_files")
def purge_expired_files() -> dict:
    return retention_service.purge_expired_files()


@celery_app.task(name="purge_private_cases")
def purge_private_cases() -> dict:
    return retention_service.purge_private_cases()
