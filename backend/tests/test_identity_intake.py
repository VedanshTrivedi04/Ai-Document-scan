"""Identity bundles, intake to extraction (app/services/identity_documents.py):
images are accepted, only extraction is queued, the person's details are
stored with their page positions, and the case completes without the
invoice checks. Every person and document here is made up."""
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.tasks.document_processing as document_processing_module
from app.models import Base
from app.models.audit_log import AuditLog
from app.models.case import Case, CaseStatus, CaseType, is_identity_case_type
from app.models.document import Document, DocumentProcessingStatus
from app.models.user import User, UserRole
from app.services.identity_documents import (
    IDENTITY_DOCUMENT_TYPE_LABELS,
    IDENTITY_FIELD_NAMES,
    identity_extracted_fields,
    is_identity_extraction,
)
from app.services.llm_service import (
    AddressField,
    AmountFieldValue,
    DateFieldValue,
    FieldValue,
    GenderField,
    IdentityAnalysis,
    PersonNameField,
    _identity_json_schema,
)
from app.services.ocr_service import OCRPage, OCRResult, OCRWord
from app.services.risk_scoring_service import pipeline_status
from app.services.upload_validation import UploadRejected, validate_upload
from app.tasks.document_checks import run_cross_document_checks, run_document_checks
from app.tasks.document_processing import process_document
from app.tasks.duplicate_check_task import run_duplicate_check_task
from app.tasks.metadata_forensics_task import run_metadata_forensics
from app.tasks.signature_detection_task import run_signature_detection
from app.tasks.tampering_checks_task import run_tampering_checks
from app.tasks.visual_inconsistency_task import run_visual_inconsistency_review_task
from tests.conftest import tenant_task_factory
from tests.sample_files import make_image, make_pdf

LIMIT = 10 * 1024 * 1024

PIPELINE_TASKS = {
    "process_document": process_document,
    "run_metadata_forensics": run_metadata_forensics,
    "run_tampering_checks": run_tampering_checks,
    "run_duplicate_check_task": run_duplicate_check_task,
    "run_visual_inconsistency_review_task": run_visual_inconsistency_review_task,
    "run_signature_detection": run_signature_detection,
}


def _empty_name() -> PersonNameField:
    return PersonNameField(value=None, latin=None, confidence=0.0, uncertain=True)


def fake_identity_analysis(**overrides) -> IdentityAnalysis:
    """A made-up identity card for a made-up person."""
    fields = dict(
        document_type="national_id_card",
        document_type_confidence=0.95,
        full_name=PersonNameField(value="Asha Devi Verma", latin="Asha Devi Verma", confidence=0.95, uncertain=False),
        parent_or_spouse_name=PersonNameField(
            value="Mohan Lal Verma", latin="Mohan Lal Verma", confidence=0.9, uncertain=False
        ),
        date_of_birth=DateFieldValue(value="1991-04-12", raw_text="12/04/1991", confidence=0.95, uncertain=False),
        gender=GenderField(value="female", raw_text="Female", confidence=0.95, uncertain=False),
        address=AddressField(
            value="14 Nehru Marg, Ward 7, Indore 452001",
            latin="14 Nehru Marg, Ward 7, Indore 452001",
            postal_code="452001",
            confidence=0.9,
            uncertain=False,
        ),
        id_number=FieldValue(value="XXXX XXXX 4321", confidence=0.9, uncertain=False),
        annual_income=AmountFieldValue(value=None, currency=None, raw_text=None, confidence=0.0, uncertain=True),
        issuing_authority=FieldValue(value="Sample Identity Authority", confidence=0.8, uncertain=False),
        issue_date=DateFieldValue(value=None, raw_text=None, confidence=0.0, uncertain=True),
        additional_fields=[],
    )
    fields.update(overrides)
    return IdentityAnalysis(**fields)


def _words(line: str, y: float) -> list[OCRWord]:
    return [
        OCRWord(text=token, x=0.1 + i * 0.09, y=y, width=0.08, height=0.02)
        for i, token in enumerate(line.split())
    ]


def fake_identity_ocr() -> OCRResult:
    lines = [
        "SAMPLE IDENTITY AUTHORITY",
        "Name: Asha Devi Verma",
        "S/O D/O: Mohan Lal Verma",
        "DOB: 12/04/1991 Female",
        "14 Nehru Marg, Ward 7, Indore 452001",
        "XXXX XXXX 4321",
    ]
    words = [word for i, line in enumerate(lines) for word in _words(line, 0.1 + i * 0.05)]
    line_spans = [
        OCRWord(text=line, x=0.1, y=0.1 + i * 0.05, width=0.8, height=0.02) for i, line in enumerate(lines)
    ]
    return OCRResult(text="\n".join(lines), pages=[OCRPage(page_number=1, words=words, lines=line_spans)])


# --- case types and labels ------------------------------------------------

def test_identity_case_types_are_recognised():
    assert is_identity_case_type(CaseType.identity_verification)
    assert is_identity_case_type("hiring_verification")
    assert not is_identity_case_type(CaseType.vendor_invoice)
    assert not is_identity_case_type(None)


def _assert_strict(schema: dict) -> None:
    """Azure OpenAI's strict mode: every object lists all its properties as
    required and allows no others."""
    if schema.get("type") == "object" or "object" in (schema.get("type") or []):
        assert set(schema["required"]) == set(schema["properties"])
        assert schema["additionalProperties"] is False
        for child in schema["properties"].values():
            _assert_strict(child)
    if "items" in schema:
        _assert_strict(schema["items"])


def test_identity_schema_is_strict_and_covers_every_field():
    schema = _identity_json_schema()
    _assert_strict(schema)
    assert set(IDENTITY_FIELD_NAMES) <= set(schema["properties"])
    assert "other" in IDENTITY_DOCUMENT_TYPE_LABELS


def test_stored_shape_keeps_null_core_fields_for_older_readers():
    stored = identity_extracted_fields(fake_identity_analysis())
    assert is_identity_extraction(stored)
    assert tuple(stored["identity_fields"]) == IDENTITY_FIELD_NAMES
    assert stored["identity_fields"]["full_name"]["latin"] == "Asha Devi Verma"
    assert stored["core_fields"]["issuer"]["value"] is None
    assert stored["core_fields"]["amount"]["value"] is None
    assert not is_identity_extraction({"core_fields": {}})


# --- upload validation ----------------------------------------------------

@pytest.mark.parametrize(
    "fmt, name, content_type",
    [("PNG", "id-card.png", "image/png"), ("JPEG", "id-card.jpg", "image/jpeg"), ("TIFF", "scan.tiff", "image/tiff")],
)
def test_images_are_accepted_when_allowed(fmt, name, content_type):
    validated = validate_upload(make_image(fmt), name, max_bytes=LIMIT, allow_images=True)
    assert validated.content_type == content_type
    assert validated.page_count == 1


def test_images_stay_refused_by_default():
    with pytest.raises(UploadRejected) as rejection:
        validate_upload(make_image("PNG"), "id-card.png", max_bytes=LIMIT)
    assert rejection.value.code == "unsupported_file_type"


def test_pdf_is_still_accepted_when_images_are_allowed():
    assert validate_upload(make_pdf(), "id.pdf", max_bytes=LIMIT, allow_images=True).content_type == "application/pdf"


def test_image_with_another_types_extension_is_a_mismatch():
    with pytest.raises(UploadRejected) as rejection:
        validate_upload(make_image("PNG"), "id-card.pdf", max_bytes=LIMIT, allow_images=True)
    assert rejection.value.code == "file_type_mismatch"


def test_truncated_image_is_corrupted():
    with pytest.raises(UploadRejected) as rejection:
        validate_upload(make_image("PNG", size=(400, 300))[:120], "id-card.png", max_bytes=LIMIT, allow_images=True)
    assert rejection.value.code == "file_corrupted"


def test_other_file_types_are_refused_even_when_images_are_allowed():
    with pytest.raises(UploadRejected) as rejection:
        validate_upload(b"PK\x03\x04 not a document", "bundle.zip", max_bytes=LIMIT, allow_images=True)
    assert rejection.value.code == "unsupported_file_type"
    assert "JPG" in rejection.value.message


# --- upload endpoint ------------------------------------------------------

@pytest.fixture
def enqueued(monkeypatch):
    calls: list[str] = []
    for name, task in PIPELINE_TASKS.items():
        monkeypatch.setattr(task, "delay", lambda *a, _n=name, **k: calls.append(_n))
    return calls


def _create_case(client, headers, case_type):
    response = client.post("/cases", json={"case_type": case_type}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _upload(client, headers, case_id, filename, content, declared):
    return client.post(
        f"/cases/{case_id}/documents", headers=headers, files={"file": (filename, content, declared)}
    )


@pytest.mark.parametrize("case_type", ["identity_verification", "hiring_verification"])
def test_identity_case_takes_an_image_and_queues_extraction_only(client, auth_headers, enqueued, case_type):
    case_id = _create_case(client, auth_headers, case_type)
    response = _upload(client, auth_headers, case_id, "id-card.png", make_image("PNG"), "image/png")
    assert response.status_code == 201, response.text
    assert response.json()["content_type"] == "image/png"
    assert enqueued == ["process_document"]


def test_identity_case_pdf_also_queues_extraction_only(client, auth_headers, enqueued):
    case_id = _create_case(client, auth_headers, "identity_verification")
    response = _upload(client, auth_headers, case_id, "income.pdf", make_pdf("Income certificate"), "application/pdf")
    assert response.status_code == 201, response.text
    assert enqueued == ["process_document"]


def test_invoice_case_still_refuses_images_and_runs_forensics(client, auth_headers, enqueued):
    case_id = _create_case(client, auth_headers, "vendor_invoice")
    refused = _upload(client, auth_headers, case_id, "invoice.png", make_image("PNG"), "image/png")
    assert refused.status_code == 415
    assert refused.json()["detail"]["code"] == "unsupported_file_type"
    assert enqueued == []

    accepted = _upload(client, auth_headers, case_id, "invoice.pdf", make_pdf(), "application/pdf")
    assert accepted.status_code == 201
    assert set(enqueued) == set(PIPELINE_TASKS)


# --- extraction task ------------------------------------------------------

@pytest.fixture()
def task_session_factory(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    factory = tenant_task_factory(monkeypatch, engine)
    monkeypatch.setattr(document_processing_module, "SessionLocal", factory)
    return factory


def _seed_case(factory, case_type: CaseType, filenames: list[tuple[str, str]]) -> tuple[uuid.UUID, list[uuid.UUID]]:
    session = factory()
    try:
        user = User(
            email=f"applicant-{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="not-a-real-hash",
            role=UserRole.user,
            is_active=True,
        )
        session.add(user)
        session.flush()
        case = Case(
            case_number=f"CASE-{uuid.uuid4().hex[:8].upper()}",
            case_type=case_type,
            submitted_by_user_id=user.id,
            status=CaseStatus.submitted,
        )
        session.add(case)
        session.flush()
        documents = [
            Document(
                case_id=case.id,
                uploaded_by_user_id=user.id,
                original_filename=name,
                blob_storage_path=f"https://fake.blob.core.windows.net/documents/{name}",
                file_hash=uuid.uuid4().hex * 2,
                content_type=content_type,
                file_size_bytes=100,
            )
            for name, content_type in filenames
        ]
        session.add_all(documents)
        session.commit()
        return case.id, [d.id for d in documents]
    finally:
        session.close()


@pytest.fixture()
def pipeline_fakes(monkeypatch):
    storage = MagicMock()
    storage.get_download_url.return_value = "https://fake.blob.core.windows.net/signed-url"
    storage.download_bytes.return_value = b"not an image"  # no face to find
    monkeypatch.setattr(document_processing_module, "get_storage_service_for_task", lambda: storage)

    ocr = MagicMock()
    ocr.analyze_url.return_value = fake_identity_ocr()
    ocr.analyze_bytes.return_value = fake_identity_ocr()
    monkeypatch.setattr(document_processing_module, "get_ocr_service", lambda: ocr)

    llm = MagicMock()
    llm.extract_identity.return_value = fake_identity_analysis()
    monkeypatch.setattr(document_processing_module, "get_llm_service", lambda: llm)

    calls = {"document_checks": [], "cross_document": []}
    monkeypatch.setattr(run_document_checks, "delay", lambda *a, **k: calls["document_checks"].append(a))
    monkeypatch.setattr(run_cross_document_checks, "delay", lambda *a, **k: calls["cross_document"].append(a))
    return {"storage": storage, "ocr": ocr, "llm": llm, "calls": calls}


def test_identity_document_stores_the_persons_details_with_positions(task_session_factory, pipeline_fakes):
    _, (document_id,) = _seed_case(
        task_session_factory, CaseType.identity_verification, [("id-card.png", "image/png")]
    )

    process_document(str(document_id), str(task_session_factory.company_id))

    session = task_session_factory()
    try:
        document = session.get(Document, document_id)
        assert document.processing_status == DocumentProcessingStatus.complete
        assert document.document_type == "national_id_card"
        assert "Asha Devi Verma" in document.ocr_text

        stored = document.extracted_fields
        assert stored["schema"] == "identity"
        fields = stored["identity_fields"]
        assert fields["full_name"]["value"] == "Asha Devi Verma"
        assert fields["date_of_birth"]["value"] == "1991-04-12"
        assert fields["address"]["postal_code"] == "452001"

        # Each located value points at its own line of the page.
        assert fields["full_name"]["bounding_box"]["page"] == 1
        assert fields["full_name"]["bounding_box"]["y"] == pytest.approx(0.15)
        assert fields["parent_or_spouse_name"]["bounding_box"]["y"] == pytest.approx(0.20)
        assert fields["date_of_birth"]["bounding_box"]["y"] == pytest.approx(0.25)
        assert fields["address"]["bounding_box"]["y"] == pytest.approx(0.30)
        assert fields["id_number"]["bounding_box"]["y"] == pytest.approx(0.35)
        assert "bounding_box" not in fields["annual_income"]

        event_data = session.execute(
            select(AuditLog.event_data).where(
                AuditLog.document_id == document_id, AuditLog.event_type == "document_processing_completed"
            )
        ).scalar_one()
        assert event_data["schema"] == "identity"
        assert event_data["fields_located"] >= 5
        # A document with no readable photograph is still processed; the check says why.
        assert stored["faces"]["items"] == []
        assert stored["faces"]["status"] in {"ok", "failed", "unavailable"}
        assert event_data["faces_found"] == 0
    finally:
        session.close()

    llm = pipeline_fakes["llm"]
    llm.extract_identity.assert_called_once()
    llm.classify_and_extract.assert_not_called()
    assert llm.extract_identity.call_args.kwargs["document_type_labels"] == IDENTITY_DOCUMENT_TYPE_LABELS
    # No invoice checks; the file is fetched once, for the photograph check.
    assert pipeline_fakes["calls"]["document_checks"] == []
    pipeline_fakes["storage"].download_bytes.assert_called_once()


def test_case_comparison_is_queued_once_every_document_has_finished(task_session_factory, pipeline_fakes):
    case_id, (first, second) = _seed_case(
        task_session_factory,
        CaseType.identity_verification,
        [("id-card.png", "image/png"), ("income.pdf", "application/pdf")],
    )
    company = str(task_session_factory.company_id)

    process_document(str(first), company)
    assert pipeline_fakes["calls"]["cross_document"] == []

    process_document(str(second), company)
    assert pipeline_fakes["calls"]["cross_document"] == [(str(case_id), company)]


def test_failed_identity_extraction_is_recorded_on_the_document(task_session_factory, pipeline_fakes):
    pipeline_fakes["llm"].extract_identity.side_effect = RuntimeError("model unavailable")
    _, (document_id,) = _seed_case(
        task_session_factory, CaseType.identity_verification, [("id-card.png", "image/png")]
    )

    process_document(str(document_id), str(task_session_factory.company_id))

    session = task_session_factory()
    try:
        document = session.get(Document, document_id)
        assert document.processing_status == DocumentProcessingStatus.failed
        assert "model unavailable" in document.processing_error
    finally:
        session.close()


def test_identity_case_is_complete_without_the_invoice_checks(task_session_factory, pipeline_fakes):
    case_id, (document_id,) = _seed_case(
        task_session_factory, CaseType.identity_verification, [("income.pdf", "application/pdf")]
    )
    company_id = task_session_factory.company_id
    session = task_session_factory()
    try:
        assert not pipeline_status(session, company_id, case_id).complete
    finally:
        session.close()

    process_document(str(document_id), str(company_id))

    session = task_session_factory()
    try:
        status = pipeline_status(session, company_id, case_id)
        assert status.complete, status.pending
    finally:
        session.close()


def test_invoice_case_still_waits_for_its_checks(task_session_factory):
    case_id, (document_id,) = _seed_case(
        task_session_factory, CaseType.vendor_invoice, [("invoice.pdf", "application/pdf")]
    )
    session = task_session_factory()
    try:
        document = session.get(Document, document_id)
        document.processing_status = DocumentProcessingStatus.complete
        session.commit()
        status = pipeline_status(session, task_session_factory.company_id, case_id)
        assert not status.complete
        assert any("Field validation" in item for item in status.pending)
    finally:
        session.close()
