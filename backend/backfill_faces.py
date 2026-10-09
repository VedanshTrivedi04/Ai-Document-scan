"""
Backfill: find the photographs on identity documents that were extracted
before the face models were installed (or before the photograph check
existed), then re-run each affected case's contradiction check so the
photographs are compared.

It reads only the stored original files. It does not run OCR or the language
model, does not change any extracted value, and never writes to the original
file. A decision a reviewer already made on a finding survives the re-run.

Usage (from backend/, venv active):
    python -m app.services.face_models                # once: install the models
    python backfill_faces.py                          # every identity document without a face result
    python backfill_faces.py CASE-30720157            # just these case numbers
    python backfill_faces.py --retry-failed ...       # also documents whose last attempt failed
    python backfill_faces.py --dry-run ...            # report, change nothing

Safe to re-run: a document that already has a face result is skipped.
"""
import copy
import sys

from sqlalchemy import select

from app.db.session import system_session
from app.models.case import Case, is_identity_case_type
from app.models.document import Document, DocumentProcessingStatus
from app.services import face_service
from app.services.audit_service import record_event
from app.services.identity_documents import is_identity_extraction
from app.services.storage_service import get_storage_service_for_task
from app.tasks.document_checks import run_cross_document_checks


def main(argv: list[str]) -> None:
    dry_run = "--dry-run" in argv
    retry_failed = "--retry-failed" in argv
    case_numbers = [a for a in argv if not a.startswith("--")]

    if not face_service.models_installed():
        sys.exit("The face models are not installed. Run: python -m app.services.face_models")

    redo = {None, face_service.STATUS_UNAVAILABLE} | ({face_service.STATUS_FAILED} if retry_failed else set())
    storage = get_storage_service_for_task()
    touched: dict[tuple, str] = {}
    with system_session() as db:
        stmt = (
            select(Document, Case)
            .join(Case, Case.id == Document.case_id)
            .where(Document.processing_status == DocumentProcessingStatus.complete)
            .order_by(Case.created_at, Document.created_at)
        )
        if case_numbers:
            stmt = stmt.where(Case.case_number.in_(case_numbers))
        done = skipped = failed = 0
        for doc, case in db.execute(stmt).all():
            if not is_identity_case_type(case.case_type) or not is_identity_extraction(doc.extracted_fields):
                continue
            status = (doc.extracted_fields.get("faces") or {}).get("status")
            if status not in redo:
                skipped += 1
                continue
            if dry_run:
                print(f"would read the photographs of {doc.original_filename} ({case.case_number})")
                continue
            try:
                result = face_service.analyse_document(storage.download_bytes(doc.blob_storage_path))
                updated = copy.deepcopy(doc.extracted_fields)
                updated["faces"] = result
                doc.extracted_fields = updated  # a new object, so the change is saved
                record_event(
                    db, "faces_backfilled", case_id=doc.case_id, document_id=doc.id,
                    event_data={"faces_found": len(result["items"]), "faces_status": result["status"]},
                )
                db.commit()
                touched[(str(case.id), str(case.company_id))] = case.case_number
                done += 1
                print(f"{doc.original_filename} ({case.case_number}): {len(result['items'])} face(s), {result['status']}")
            except Exception as exc:  # noqa: BLE001 - one bad document must not stop the rest
                db.rollback()
                failed += 1
                print(f"FAILED {doc.original_filename}: {exc}")
    for (case_id, company_id), number in touched.items():
        run_cross_document_checks(case_id, company_id)  # compares the photographs, keeps reviewer decisions
        print(f"re-checked {number}")
    print(f"done: {done}, skipped: {skipped}, failed: {failed}")


if __name__ == "__main__":
    main(sys.argv[1:])
