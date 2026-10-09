"""backfill_faces.py: documents extracted before the face models were installed
get their photographs read afterwards, and the case is re-checked."""
import contextlib
import uuid

import pytest

import backfill_faces
from app.models.audit_log import AuditLog
from app.models.case import CaseType
from app.models.document import Document, DocumentProcessingStatus
from app.models.user import User, UserRole
from app.services import face_service
from tests.helpers_risk import make_case


@pytest.fixture()
def world(db_session, monkeypatch):
    user = User(email="a@x.com", hashed_password="x", role=UserRole.user, is_active=True)
    db_session.add(user)
    db_session.commit()
    case = make_case(db_session, user)
    case.case_type = CaseType.identity_verification

    def document(name, faces):
        fields = {"schema": "identity", "identity_fields": {}, "core_fields": {}}
        if faces is not None:
            fields["faces"] = faces
        row = Document(
            case_id=case.id, uploaded_by_user_id=user.id, original_filename=name, blob_storage_path=f"p/{name}",
            file_hash=uuid.uuid4().hex * 2, content_type="image/jpeg",
            processing_status=DocumentProcessingStatus.complete, extracted_fields=fields,
        )
        db_session.add(row)
        return row

    old = document("old.jpg", {"status": "unavailable", "items": []})
    never = document("never.jpg", None)
    done = document("done.jpg", {"status": "ok", "items": [{"embedding": [1.0]}]})
    broken = document("broken.jpg", {"status": "failed", "items": [], "error": "x"})
    db_session.commit()

    @contextlib.contextmanager
    def session():
        yield db_session

    rechecked: list[tuple] = []
    storage = type("S", (), {"download_bytes": staticmethod(lambda path: path.encode())})()
    monkeypatch.setattr(backfill_faces, "system_session", session)
    monkeypatch.setattr(backfill_faces, "get_storage_service_for_task", lambda: storage)
    monkeypatch.setattr(backfill_faces, "run_cross_document_checks", lambda *a: rechecked.append(a))
    monkeypatch.setattr(face_service, "models_installed", lambda: True)
    monkeypatch.setattr(
        face_service, "analyse_document", lambda content: {"status": "ok", "items": [{"embedding": [0.5], "bounding_box": {}}]}
    )
    return {"old": old, "never": never, "done": done, "broken": broken, "case": case, "rechecked": rechecked}


def _faces(row):
    return (row.extracted_fields.get("faces") or {}).get("status")


def test_documents_without_a_face_result_are_read_and_the_case_is_rechecked(world, db_session, capsys):
    backfill_faces.main([])
    db_session.expire_all()
    assert _faces(world["old"]) == "ok" and len(world["old"].extracted_fields["faces"]["items"]) == 1
    assert _faces(world["never"]) == "ok"
    assert world["done"].extracted_fields["faces"]["items"] == [{"embedding": [1.0]}]  # untouched
    assert _faces(world["broken"]) == "failed"  # only with --retry-failed
    assert world["rechecked"] == [(str(world["case"].id), str(world["case"].company_id))]
    events = db_session.query(AuditLog).filter_by(event_type="faces_backfilled").all()
    assert len(events) == 2


def test_retry_failed_and_dry_run(world, db_session):
    backfill_faces.main(["--dry-run"])
    db_session.expire_all()
    assert _faces(world["old"]) == "unavailable" and world["rechecked"] == []
    backfill_faces.main(["--retry-failed"])
    db_session.expire_all()
    assert _faces(world["broken"]) == "ok"


def test_it_refuses_to_run_without_the_models(world, monkeypatch):
    monkeypatch.setattr(face_service, "models_installed", lambda: False)
    with pytest.raises(SystemExit):
        backfill_faces.main([])
