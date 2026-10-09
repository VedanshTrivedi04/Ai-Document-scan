"""Document retention (app/services/retention_service.py): stored files are
removed after DOCUMENT_RETENTION_DAYS and what was read from them stays; a
private case is emptied when its submitter signs out. All data is made up."""
import uuid
from contextlib import contextmanager
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db import tenancy
from app.models.audit_log import AuditLog
from app.models.base import utcnow
from app.models.bulk_upload import BulkUpload, BulkUploadStatus
from app.models.case import Case, CaseStatus, CaseType
from app.models.company import Company
from app.models.cross_document_finding import CrossDocumentFinding
from app.models.document import Document, DocumentProcessingStatus
from app.models.document_check import DocumentCheck, DocumentCheckStatus, DocumentCheckType
from app.models.user import UserRole
from app.services import retention_service
from app.services.local_storage import LocalStorageService
from app.services.storage_service import StorageOperationError
from app.tasks.celery_app import HOUSEKEEPING_QUEUE, TASK_QUEUES, celery_app
from tests.conftest import _headers_for, _make_user

FIELDS = {"schema": "identity", "identity_fields": {"full_name": {"value": "Asha Rao"}}, "core_fields": {}}


def _document(db, storage, case, *, age_days=0, status=DocumentProcessingStatus.complete, name="id-card.pdf"):
    path = f"companies/{case.company_id}/cases/{case.id}/documents/{uuid.uuid4().hex}.pdf"
    url = storage.upload(path, b"%PDF-1.4 fake")
    when = utcnow() - timedelta(days=age_days)
    document = Document(
        case_id=case.id, uploaded_by_user_id=case.submitted_by_user_id, original_filename=name,
        blob_storage_path=url, file_hash=uuid.uuid4().hex * 2, content_type="application/pdf", file_size_bytes=13,
        document_type="national_id_card", processing_status=status, extracted_fields=dict(FIELDS),
        ocr_text="ASHA RAO 12/03/1982", created_at=when, updated_at=when,
    )
    db.add(document)
    db.commit()
    return document


def _case(db, user, *, private=False, case_type=CaseType.identity_verification, age_minutes=0):
    case_id = uuid.uuid4()
    when = utcnow() - timedelta(minutes=age_minutes)
    case = Case(
        id=case_id, case_number=f"CASE-{case_id.hex[:8].upper()}", case_type=case_type,
        submitted_by_user_id=user.id, status=CaseStatus.submitted, delete_on_logout=private,
        created_at=when, updated_at=when,
    )
    db.add(case)
    db.commit()
    return case


@pytest.fixture()
def jobs(db_session, fake_storage, monkeypatch):
    """Run the scheduled jobs against the test database and the fake storage."""

    @contextmanager
    def _system():
        state = tenancy.snapshot(db_session)
        tenancy.bind_platform(db_session)
        try:
            yield db_session
        finally:
            tenancy.restore(db_session, state)

    class _Shared:
        """The suite shares one session; a job 'closing' its session must not end it."""

        def __init__(self, company_id):
            self._state = tenancy.snapshot(db_session)
            tenancy.restore(db_session, (None, None))
            tenancy.bind_company(db_session, company_id)

        def __getattr__(self, name):
            return getattr(db_session, name)

        def close(self):
            tenancy.restore(db_session, self._state)

    monkeypatch.setattr(retention_service, "_sessions", lambda: (None, _system, lambda _f, company_id: _Shared(company_id)))
    monkeypatch.setattr(retention_service, "_storage", lambda: fake_storage)
    monkeypatch.setattr(settings, "document_retention_days", 24)
    return retention_service


# --- storage ---------------------------------------------------------------

def test_local_storage_deletes_a_file_and_tolerates_one_already_gone(tmp_path):
    storage = LocalStorageService(str(tmp_path), "documents", "http://localhost/files")
    url = storage.upload("companies/c/cases/k/documents/a.pdf", b"x")
    assert storage.delete(url) is True
    assert storage.delete(url) is False
    with pytest.raises(StorageOperationError):
        storage.download_bytes(url)


def test_a_file_expires_the_configured_days_after_upload(monkeypatch):
    uploaded = utcnow()
    monkeypatch.setattr(settings, "document_retention_days", 24)
    assert retention_service.file_expires_at(uploaded) == uploaded + timedelta(days=24)
    assert retention_service.file_expires_at(uploaded, file_deleted_at=utcnow()) is None
    monkeypatch.setattr(settings, "document_retention_days", 0)
    assert retention_service.file_expires_at(uploaded) is None


# --- the daily job ---------------------------------------------------------

def test_only_files_past_the_period_are_removed_and_the_details_stay(jobs, db_session, fake_storage, plain_user):
    case = _case(db_session, plain_user)
    old = _document(db_session, fake_storage, case, age_days=25)
    fresh = _document(db_session, fake_storage, case, age_days=23)

    result = jobs.purge_expired_files()

    assert (result["documents_due"], result["documents_removed"], result["failed"]) == (1, 1, 0)
    db_session.expire_all()
    old, fresh = db_session.get(Document, old.id), db_session.get(Document, fresh.id)
    assert old.file_deleted_at is not None and old.ocr_text is None
    # What was read from the document is untouched.
    assert old.extracted_fields == FIELDS and old.document_type == "national_id_card"
    assert old.original_filename == "id-card.pdf" and old.processing_status == DocumentProcessingStatus.complete
    assert fresh.file_deleted_at is None and fresh.ocr_text == "ASHA RAO 12/03/1982"
    assert len(fake_storage.uploads) == 1  # only the fresh file is still stored

    event = db_session.execute(
        select(AuditLog).where(AuditLog.event_type == "document_file_deleted")
    ).scalar_one()
    assert event.document_id == old.id and event.company_id == case.company_id
    assert event.event_data == {"reason": "retention_period", "retention_days": 24}

    # Running it again finds nothing more.
    assert jobs.purge_expired_files()["documents_due"] == 0


def test_a_dry_run_only_counts(jobs, db_session, fake_storage, plain_user):
    old = _document(db_session, fake_storage, _case(db_session, plain_user), age_days=40)
    result = jobs.purge_expired_files(dry_run=True)
    assert result["documents_due"] == 1 and result["documents_removed"] == 0 and result["dry_run"] is True
    db_session.expire_all()
    assert db_session.get(Document, old.id).file_deleted_at is None and len(fake_storage.uploads) == 1


def test_zero_days_switches_removal_off(jobs, db_session, fake_storage, plain_user, monkeypatch):
    _document(db_session, fake_storage, _case(db_session, plain_user), age_days=400)
    monkeypatch.setattr(settings, "document_retention_days", 0)
    assert jobs.purge_expired_files() == {"skipped": "retention_disabled"}
    assert len(fake_storage.uploads) == 1


def test_a_storage_failure_leaves_the_document_for_the_next_run(jobs, db_session, fake_storage, plain_user, monkeypatch):
    old = _document(db_session, fake_storage, _case(db_session, plain_user), age_days=30)

    def refuse(_url):
        raise StorageOperationError("storage unreachable")

    monkeypatch.setattr(fake_storage, "delete", refuse)
    result = jobs.purge_expired_files()
    assert result["documents_removed"] == 0 and result["failed"] == 1
    db_session.expire_all()
    document = db_session.get(Document, old.id)
    assert document.file_deleted_at is None and document.ocr_text is not None  # nothing claimed as removed


def test_an_unread_document_whose_file_expired_is_marked_failed(jobs, db_session, fake_storage, plain_user):
    stuck = _document(db_session, fake_storage, _case(db_session, plain_user), age_days=30,
                      status=DocumentProcessingStatus.pending)
    jobs.purge_expired_files()
    db_session.expire_all()
    document = db_session.get(Document, stuck.id)
    assert document.processing_status == DocumentProcessingStatus.failed and "removed" in document.processing_error


def test_an_old_bulk_upload_zip_is_removed_once_ingested(jobs, db_session, fake_storage, plain_user):
    def bulk(status, age_days):
        url = fake_storage.upload(f"companies/x/bulk-uploads/{uuid.uuid4().hex}.zip", b"PK")
        when = utcnow() - timedelta(days=age_days)
        row = BulkUpload(
            uploaded_by_user_id=plain_user.id, original_filename="cases.zip", case_type=CaseType.identity_verification,
            blob_storage_path=url, file_hash="0" * 64, zip_size_bytes=2, status=status, created_at=when, updated_at=when,
        )
        db_session.add(row)
        db_session.commit()
        return row.id

    done = bulk(BulkUploadStatus.complete, 30)
    running = bulk(BulkUploadStatus.ingesting, 30)
    recent = bulk(BulkUploadStatus.complete, 3)

    result = jobs.purge_expired_files()
    assert result["zips_removed"] == 1
    db_session.expire_all()
    assert db_session.get(BulkUpload, done).file_deleted_at is not None
    assert db_session.get(BulkUpload, running).file_deleted_at is None
    assert db_session.get(BulkUpload, recent).file_deleted_at is None


def test_the_jobs_are_scheduled_on_the_housekeeping_queue():
    assert TASK_QUEUES["purge_expired_files"] == HOUSEKEEPING_QUEUE
    assert TASK_QUEUES["purge_private_cases"] == HOUSEKEEPING_QUEUE
    scheduled = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    assert {"purge_expired_files", "purge_private_cases"} <= scheduled


# --- the API once a file is gone -------------------------------------------

def test_case_detail_still_works_and_says_the_file_is_gone(client, plain_headers, plain_user, db_session, fake_storage, jobs):
    case = _case(db_session, plain_user)
    old = _document(db_session, fake_storage, case, age_days=30)
    fresh = _document(db_session, fake_storage, case, age_days=1)
    jobs.purge_expired_files()

    detail = client.get(f"/cases/{case.id}", headers=plain_headers)
    assert detail.status_code == 200, detail.text
    documents = {d["id"]: d for d in detail.json()["documents"]}
    gone, kept = documents[str(old.id)], documents[str(fresh.id)]
    assert gone["file_url"] is None and gone["file_deleted_at"] and gone["file_expires_at"] is None
    assert gone["extracted_fields"]["identity_fields"]["full_name"]["value"] == "Asha Rao"
    assert kept["file_url"] and kept["file_deleted_at"] is None and kept["file_expires_at"]

    assert client.get(f"/cases/{case.id}/documents/{old.id}/file-url", headers=plain_headers).status_code == 410
    assert client.get(f"/cases/{case.id}/documents/{fresh.id}/file-url", headers=plain_headers).status_code == 200
    assert client.get(f"/cases/{case.id}/profile", headers=plain_headers).status_code == 200


# --- private cases ---------------------------------------------------------

@pytest.fixture()
def public_site(db_session, monkeypatch):
    """The test company stands in for the public site's company."""
    monkeypatch.setattr(settings, "default_company_name", db_session.get(Company, db_session.info["test_company_id"]).name)


def _private(client, headers, **extra):
    return client.post("/cases", headers=headers, json={"case_type": "identity_verification", "delete_on_logout": True, **extra})


def test_a_private_case_is_only_for_a_persons_documents_on_the_public_site(
    client, plain_headers, reviewer_headers, public_site, monkeypatch
):
    made = _private(client, plain_headers)
    assert made.status_code == 201, made.text
    listed = client.get("/cases", headers=plain_headers).json()
    assert [(c["id"], c["delete_on_logout"], c["data_removed_at"]) for c in listed] == [(made.json()["id"], True, None)]

    assert _private(client, reviewer_headers).status_code == 422  # reviewers keep their cases
    assert client.post(
        "/cases", headers=plain_headers, json={"case_type": "vendor_invoice", "delete_on_logout": True}
    ).status_code == 422
    monkeypatch.setattr(settings, "default_company_name", "Some Other Company")
    assert _private(client, plain_headers).status_code == 422  # inside an organisation


def test_signing_out_empties_private_cases_and_leaves_the_others(
    client, plain_headers, plain_user, db_session, fake_storage, public_site
):
    private = db_session.get(Case, uuid.UUID(_private(client, plain_headers).json()["id"]))
    ordinary = _case(db_session, plain_user)
    private_doc = _document(db_session, fake_storage, private, name="asha-rao-id.pdf")
    ordinary_doc = _document(db_session, fake_storage, ordinary)
    db_session.add(DocumentCheck(
        document_id=private_doc.id, check_type=DocumentCheckType.field_validation,
        status=DocumentCheckStatus.completed, result={"details": ["Asha Rao"]}, confidence=0.9,
    ))
    db_session.add(CrossDocumentFinding(
        case_id=private.id, field_name="full_name", finding_type="identity_consistency",
        description="Asha Rao vs Asha Roy", document_ids=[], classification="conflict", reason="different_name",
    ))
    private.profile_overrides = {"full_name": {"document_id": str(private_doc.id)}}
    db_session.commit()

    waiting = client.get("/auth/private-cases", headers=plain_headers).json()
    assert [c["case_number"] for c in waiting] == [private.case_number]

    out = client.post("/auth/logout", headers=plain_headers)
    assert out.status_code == 200 and out.json() == {"removed_cases": [private.case_number]}

    db_session.expire_all()
    case, document = db_session.get(Case, private.id), db_session.get(Document, private_doc.id)
    assert case.data_removed_at is not None and case.status == CaseStatus.closed and case.profile_overrides is None
    assert document.file_deleted_at is not None
    assert (document.extracted_fields, document.ocr_text, document.document_type) == (None, None, None)
    assert document.original_filename == "removed document"  # a file name can carry a person's name
    check = db_session.execute(select(DocumentCheck).where(DocumentCheck.document_id == private_doc.id)).scalar_one()
    assert (check.result, check.confidence) == (None, None)
    assert db_session.execute(
        select(CrossDocumentFinding).where(CrossDocumentFinding.case_id == private.id)
    ).scalars().all() == []

    # The ordinary case is untouched, file and all.
    kept = db_session.get(Document, ordinary_doc.id)
    assert kept.file_deleted_at is None and kept.extracted_fields == FIELDS
    assert len(fake_storage.uploads) == 1

    event = db_session.execute(select(AuditLog).where(AuditLog.event_type == "case_data_removed")).scalar_one()
    assert event.case_id == private.id and event.event_data["reason"] == "private_case_sign_out"
    assert "Asha" not in str(event.event_data)

    # The token that signed out is spent; the person signs in again.
    assert client.get("/auth/private-cases", headers=plain_headers).status_code == 401
    again = _headers_for(plain_user)

    # Nothing left to remove; signing out again is harmless.
    assert client.get("/auth/private-cases", headers=again).json() == []
    assert client.post("/auth/logout", headers=again).json() == {"removed_cases": []}

    # The emptied case still opens, with nothing in it, and takes no more uploads.
    again = _headers_for(plain_user)
    detail = client.get(f"/cases/{private.id}", headers=again).json()
    assert detail["data_removed_at"] and detail["documents"][0]["file_url"] is None
    assert detail["documents"][0]["extracted_fields"] is None and detail["cross_document_findings"] == []
    refused = client.post(
        f"/cases/{private.id}/documents", headers=again, files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")}
    )
    assert refused.status_code == 409


def test_signing_out_never_touches_someone_elses_private_case(
    client, plain_headers, db_session, fake_storage, public_site
):
    other = _make_user(db_session, "other.citizen@example.com", UserRole.user, "Other Citizen")
    theirs = db_session.get(Case, uuid.UUID(_private(client, _headers_for(other)).json()["id"]))
    document = _document(db_session, fake_storage, theirs)

    assert client.post("/auth/logout", headers=plain_headers).json() == {"removed_cases": []}
    db_session.expire_all()
    assert db_session.get(Case, theirs.id).data_removed_at is None
    assert db_session.get(Document, document.id).extracted_fields == FIELDS


def test_sign_out_needs_a_token_and_does_nothing_for_a_platform_admin(client, platform_admin_headers):
    assert client.post("/auth/logout").status_code == 401
    assert client.get("/auth/private-cases", headers=platform_admin_headers).json() == []
    assert client.post("/auth/logout", headers=platform_admin_headers).json() == {"removed_cases": []}


def test_a_private_case_is_emptied_when_the_session_has_run_out(jobs, db_session, fake_storage, plain_user, monkeypatch):
    monkeypatch.setattr(settings, "jwt_access_token_expire_minutes", 60)
    forgotten = _case(db_session, plain_user, private=True, age_minutes=61)
    current = _case(db_session, plain_user, private=True, age_minutes=10)
    ordinary = _case(db_session, plain_user, age_minutes=600)
    docs = {c.id: _document(db_session, fake_storage, c) for c in (forgotten, current, ordinary)}

    assert jobs.purge_private_cases() == {"due": 1, "emptied": 1}
    db_session.expire_all()
    assert db_session.get(Case, forgotten.id).data_removed_at is not None
    assert db_session.get(Document, docs[forgotten.id].id).extracted_fields is None
    for case in (current, ordinary):
        assert db_session.get(Case, case.id).data_removed_at is None
        assert db_session.get(Document, docs[case.id].id).extracted_fields == FIELDS
    event = db_session.execute(select(AuditLog).where(AuditLog.event_type == "case_data_removed")).scalar_one()
    assert event.event_data["reason"] == "private_case_session_ended"
    assert jobs.purge_private_cases() == {"due": 0, "emptied": 0}


def test_a_document_that_finished_reading_after_the_wipe_is_cleaned_up(jobs, db_session, fake_storage, plain_user):
    case = _case(db_session, plain_user, private=True)
    document = _document(db_session, fake_storage, case)
    retention_service.wipe_case_data(db_session, fake_storage, case, reason="private_case_sign_out")
    db_session.commit()
    # A reading task that was already running writes its result afterwards.
    document.extracted_fields = dict(FIELDS)
    db_session.commit()

    assert jobs.purge_private_cases() == {"due": 1, "emptied": 1}
    db_session.expire_all()
    assert db_session.get(Document, document.id).extracted_fields is None


def test_an_emptied_private_case_no_longer_counts_as_a_members_bundle(
    client, plain_headers, plain_user, db_session, fake_storage, public_site
):
    family = client.post("/family", headers=plain_headers, json={}).json()
    head = family["members"][0]
    made = _private(client, plain_headers, family_member_id=head["id"]).json()
    _document(db_session, fake_storage, db_session.get(Case, uuid.UUID(made["id"])))

    before = client.get("/family", headers=plain_headers).json()["members"][0]
    assert before["latest_case_id"] == made["id"] and before["cases"][0]["documents"][0]["file_deleted"] is False

    client.post("/auth/logout", headers=plain_headers)
    after = client.get("/family", headers=_headers_for(plain_user)).json()["members"][0]
    assert after["latest_case_id"] is None and after["cases"] == []


def test_the_retention_rule_is_told_to_the_upload_screen(
    client, plain_headers, reviewer_headers, platform_admin_headers, public_site, monkeypatch
):
    monkeypatch.setattr(settings, "document_retention_days", 24)
    assert client.get("/auth/me/retention", headers=plain_headers).json() == {
        "document_retention_days": 24, "private_upload_available": True,
    }
    # A reviewer, and a platform admin (no company), cannot make a private upload.
    assert client.get("/auth/me/retention", headers=reviewer_headers).json()["private_upload_available"] is False
    assert client.get("/auth/me/retention", headers=platform_admin_headers).json()["private_upload_available"] is False
    assert client.get("/auth/me/retention").status_code == 401
