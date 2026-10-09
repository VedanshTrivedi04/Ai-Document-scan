"""
End-to-end run of the real pipeline on the real sample documents.

Nothing about reading or judging a document is faked: the upload endpoint,
file validation, local storage, real OCR (PDF text layer, Tesseract for
scans and images), the real language model behind LLM_PROVIDER, face
detection, every forensic check, the contradiction check, risk scoring and
the reviewer endpoints all run. Only the database is replaced (in-memory
SQLite) and Celery's queue is replaced by an in-process one, so a run never
touches a real database.

Needs network access for the language model, so it is skipped unless asked:

    RUN_E2E=1 pytest tests/e2e -s

    E2E_PHOTO_BUNDLES=DIR   also run the photograph bundles written by
                            scripts/generate_photo_bundles.py
    E2E_REPORT=FILE         write what was observed, as JSON
    E2E_ONLY=B02,B07        run only these identity bundles / invoice cases
    E2E_LLM=live|oracle     live (default): the real language model.
                            oracle: only the LLM is replaced by a reader that looks the
                            card up in the ground truth by its OCR text. Everything else
                            (OCR, faces, forensics, comparison, API) stays real. Use it
                            when the model's quota is spent; it says nothing about the
                            model's own extraction accuracy, and reports are marked.
    E2E_LLM_CACHE=DIR       live mode: record each model reply there and replay it on the
                            next run, so a repeat run costs no quota.
"""
from __future__ import annotations

import io
import json
import os
import re
import time
import zipfile
from collections import deque
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import tenancy
from app.db.session import get_db, get_system_db
from app.main import app
from app.models import Base
from app.models.company import Company
from app.models.user import UserRole
from app.services import face_service
from app.services.risk_rule_seed import seed_risk_rules
from app.services.storage_service import get_storage_service, get_storage_service_for_task
from tests.conftest import _headers_for, _make_user, tenant_task_factory

pytestmark = pytest.mark.skipif(not os.environ.get("RUN_E2E"), reason="set RUN_E2E=1 to run against real samples")

SAMPLES = Path(__file__).resolve().parents[3] / "sample-documents"
BUNDLES = SAMPLES / "identity-bundles"
ONLY = {x.strip() for x in os.environ.get("E2E_ONLY", "").split(",") if x.strip()}
REPORT: dict = {"identity": {}, "photo": {}, "invoice": {}, "features": {}, "uploads": {}}

PHOTO_DIR = Path(os.environ["E2E_PHOTO_BUNDLES"]) if os.environ.get("E2E_PHOTO_BUNDLES") else None
LIVE_LLM = os.environ.get("E2E_LLM", "live") == "live"
REPORT["mode"] = "live LLM" if LIVE_LLM else "oracle reader (no model)"

_CONTENT_TYPES = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".tiff": "image/tiff"}


def _wanted(name: str) -> bool:
    return not ONLY or any(name.startswith(o) for o in ONLY)


# ---------------------------------------------------------------------------
# Language model: live (optionally recorded), or an oracle that reads cards from the ground truth
# ---------------------------------------------------------------------------

def _alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


class OracleReader:
    """Stands in for the language model only. Given the OCR text of a card it picks the
    ground-truth document the text belongs to (by name, number, type heading) and returns
    that document's details. Tolerates OCR noise; refuses text it cannot place."""

    _TITLES = {
        "national_id_card": "identity card", "tax_id_card": "tax identity card", "voter_id_card": "voter identity card",
        "income_certificate": "income certificate", "address_proof": "electricity bill", "marksheet": "statement of marks",
        "degree_certificate": "degree certificate", "experience_letter": "experience letter",
    }

    def __init__(self):
        from app.services.llm_service import IdentityAnalysis

        self._model = IdentityAnalysis
        self._docs: list[tuple[str, dict]] = []
        for truth_file in (BUNDLES / "ground_truth.json", (PHOTO_DIR or Path("-")) / "ground_truth.json"):
            if truth_file.is_file():
                for bundle in json.loads(truth_file.read_text(encoding="utf-8"))["bundles"]:
                    for doc in bundle["documents"]:
                        self._docs.append((bundle["id"], doc))

    def _score(self, text: str, flat: str, doc: dict) -> int:
        fields = doc["identity_fields"]
        score = 0
        number = (fields["id_number"]["value"] or "")
        digits = _alnum(number)
        if digits and "x" not in digits and digits in flat:
            score += 4
        elif digits and digits[-4:] in flat:
            score += 1
        tokens = {t for key in ("value", "latin") for t in str(fields["full_name"].get(key) or "").split() if len(t) >= 3}
        score += sum(1 for token in tokens if token.casefold() in text.casefold())
        dob = (fields["date_of_birth"].get("raw_text") or "")
        if dob and _alnum(dob) in flat:
            score += 2
        title = self._TITLES.get(doc["document_type"], "")
        if title and re.search(rf"(?<![a-z]){re.escape(title)}", text.casefold()):
            score += 2
            # "identity card" is also inside "tax identity card" and "voter identity card"
            if doc["document_type"] == "national_id_card" and re.search(r"(tax|voter) identity card", text.casefold()):
                score -= 3
        issue = (fields["issue_date"].get("raw_text") or "")
        if issue and _alnum(issue) in flat:
            score += 1
        return score

    def extract_identity(self, document_text: str, document_type_labels: list[str]):
        from app.services.llm_service import LLMOperationError

        flat = _alnum(document_text)
        ranked = sorted(((self._score(document_text, flat, d), b, d) for b, d in self._docs), key=lambda r: -r[0])
        tied = [r for r in ranked if r[0] == ranked[0][0]]
        same_card = all(r[2]["identity_fields"] == tied[0][2]["identity_fields"] and r[2]["document_type"] == tied[0][2]["document_type"] for r in tied)
        if not ranked or ranked[0][0] < 5 or not same_card:
            raise LLMOperationError("oracle reader: cannot place this document in the ground truth")
        _, _, doc = ranked[0]
        return self._model.model_validate(
            {**doc["identity_fields"], "document_type": doc["document_type"], "document_type_confidence": 0.9,
             "additional_fields": []}
        )

    def classify_and_extract(self, *args, **kwargs):
        from app.services.llm_service import LLMOperationError

        raise LLMOperationError("oracle mode: no language model, invoice extraction not available")

    def __getattr__(self, name):  # any other model call (issuer judgement, vision) is unavailable
        from app.services.llm_service import LLMConfigurationError

        raise LLMConfigurationError("oracle mode: no language model")


def _install_llm(mp) -> None:
    import app.tasks.document_checks as m_checks
    import app.tasks.document_processing as m_proc

    if not LIVE_LLM:
        reader = OracleReader()
        mp.setattr(m_proc, "get_llm_service", lambda: reader)
        mp.setattr(m_checks, "get_llm_service", lambda: reader)
        return
    cache_dir = os.environ.get("E2E_LLM_CACHE")
    if not cache_dir:
        return
    import hashlib

    from app.services.llm_openai_compatible import OpenAICompatibleLLMService

    folder = Path(cache_dir)
    folder.mkdir(parents=True, exist_ok=True)
    original = OpenAICompatibleLLMService._chat_json

    def cached(self, system_prompt, user_content, schema, max_tokens):
        key = hashlib.sha256(json.dumps([self._model, system_prompt, user_content, schema, max_tokens], sort_keys=True).encode()).hexdigest()
        path = folder / f"{key}.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        reply = original(self, system_prompt, user_content, schema, max_tokens)
        path.write_text(json.dumps(reply, ensure_ascii=False), encoding="utf-8")
        return reply

    mp.setattr(OpenAICompatibleLLMService, "_chat_json", cached)


# ---------------------------------------------------------------------------
# The world: app, database, in-process queue
# ---------------------------------------------------------------------------

class World:
    tasks: tuple = ()
    storage = None

    def __init__(self, client: TestClient, reviewer_headers: dict, submitter_headers: dict, queue: deque):
        self.client, self.reviewer, self.submitter, self.queue = client, reviewer_headers, submitter_headers, queue

    def drain(self) -> int:
        ran = 0
        while self.queue:
            task, args = self.queue.popleft()
            task(*args)
            ran += 1
        return ran

    def create_case(self, case_type: str) -> str:
        response = self.client.post("/cases", json={"case_type": case_type}, headers=self.submitter)
        assert response.status_code == 201, response.text
        return response.json()["id"]

    def upload(self, case_id: str, name: str, content: bytes):
        suffix = Path(name).suffix.lower()
        return self.client.post(
            f"/cases/{case_id}/documents",
            headers=self.submitter,
            files={"file": (name, content, _CONTENT_TYPES.get(suffix, "application/octet-stream"))},
        )

    def run_case(self, case_type: str, files: list[tuple[str, bytes]]) -> tuple[str, float]:
        started = time.time()
        case_id = self.create_case(case_type)
        for name, content in files:
            response = self.upload(case_id, name, content)
            assert response.status_code == 201, f"{name}: {response.status_code} {response.text[:300]}"
        self.drain()
        return case_id, time.time() - started

    def report_pdf(self, case_id: str) -> bytes:
        """Generate the case's PDF report and return the file's bytes."""
        response = self.client.post(f"/cases/{case_id}/reports", headers=self.reviewer)
        assert response.status_code in (200, 201), response.text[:300]
        from app.services.local_storage import read_token

        token = response.json()["download_url"].rsplit("/", 1)[-1].split("?")[0]
        return self.storage.path_for(read_token(token)).read_bytes()

    def detail(self, case_id: str, lang: str = "en") -> dict:
        response = self.client.get(f"/cases/{case_id}", params={"lang": lang}, headers=self.reviewer)
        assert response.status_code == 200, response.text
        return response.json()


@pytest.fixture(scope="module")
def world():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    tenancy.bind_platform(session)
    company = Company(name="E2E Company")
    session.add(company)
    session.commit()
    session.info["test_company_id"] = company.id
    tenancy.bind_company(session, company.id)
    seed_risk_rules(session, company.id)  # a new company starts with the platform's rule set
    session.commit()

    mp = pytest.MonkeyPatch()
    factory = tenant_task_factory(mp, engine)
    _install_llm(mp)

    import app.tasks.bulk_upload_task as m_bulk
    import app.tasks.document_checks as m_checks
    import app.tasks.document_processing as m_proc
    import app.tasks.duplicate_check_task as m_dup
    import app.tasks.metadata_forensics_task as m_meta
    import app.tasks.risk_scoring_task as m_risk
    import app.tasks.signature_comparison_task as m_sigcmp
    import app.tasks.signature_detection_task as m_sigdet
    import app.tasks.tampering_checks_task as m_tamper
    import app.tasks.visual_inconsistency_task as m_visual

    for module in (m_bulk, m_checks, m_proc, m_dup, m_meta, m_risk, m_sigcmp, m_sigdet, m_tamper, m_visual):
        mp.setattr(module, "SessionLocal", factory)

    queue: deque = deque()
    tasks = (
        m_proc.process_document, m_checks.run_document_checks, m_checks.run_cross_document_checks,
        m_meta.run_metadata_forensics, m_tamper.run_tampering_checks, m_dup.run_duplicate_check_task,
        m_visual.run_visual_inconsistency_review_task, m_sigdet.run_signature_detection,
        m_sigcmp.run_signature_comparison, m_risk.score_case_task, m_bulk.ingest_bulk_upload,
    )

    def _get_db():
        state = tenancy.snapshot(session)
        tenancy.restore(session, (None, None))
        try:
            yield session
        finally:
            tenancy.restore(session, state)

    def _get_system_db():
        state = tenancy.snapshot(session)
        tenancy.bind_platform(session)
        try:
            yield session
        finally:
            tenancy.restore(session, state)

    storage = get_storage_service_for_task()  # the real one: STORAGE_PROVIDER=local
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_system_db] = _get_system_db
    app.dependency_overrides[get_storage_service] = lambda: storage

    reviewer = _make_user(session, "e2e.reviewer@example.com", UserRole.reviewer_l2, "E2E Reviewer")
    submitter = _make_user(session, "e2e.submitter@example.com", UserRole.user, "E2E Submitter")
    with TestClient(app) as client:
        w = World(client, _headers_for(reviewer), _headers_for(submitter), queue)
        w.tasks = tasks
        w.storage = storage
        yield w
    app.dependency_overrides.clear()
    mp.undo()
    if os.environ.get("E2E_REPORT"):
        Path(os.environ["E2E_REPORT"]).write_text(json.dumps(REPORT, indent=2, default=str), encoding="utf-8")


@pytest.fixture(autouse=True)
def _real_delay_is_ours(world, _no_celery, monkeypatch):
    """conftest's autouse `_no_celery` turns every `.delay` into a no-op for each
    test; the end-to-end world needs its own in-process queue instead. Depending
    on `_no_celery` makes this run after it."""
    for task in world.tasks:
        monkeypatch.setattr(task, "delay", lambda *a, _t=task, **k: world.queue.append((_t, a)))
    return world


# ---------------------------------------------------------------------------
# 1. Identity bundles: the contradiction detector on real OCR + real LLM
# ---------------------------------------------------------------------------

def _truth():
    return json.loads((BUNDLES / "ground_truth.json").read_text(encoding="utf-8"))["bundles"]


def _identity_ids():
    return [b["id"] for b in _truth() if b["family"] is None and _wanted(b["id"])]


def _observed(detail: dict) -> set[tuple]:
    names = {d["id"]: d["original_filename"] for d in detail["documents"]}
    out = set()
    for f in detail["cross_document_findings"]:
        files = tuple(sorted(names.get(i, i) for i in f["document_ids"] or []))
        out.add((f["field_name"], files, f["classification"], f["reason"], f["severity"]))
    return out


def _expected(bundle: dict) -> set[tuple]:
    return {
        (e["field"], tuple(sorted(e["documents"])), e["classification"], e["reason"], e["severity"])
        for e in bundle["expected_findings"]
    }


@pytest.fixture(scope="module")
def identity_cases(world):
    return {}


@pytest.mark.parametrize("bundle_id", _identity_ids())
def test_identity_bundle_matches_ground_truth_on_real_ocr_and_llm(world, identity_cases, bundle_id):
    bundle = next(b for b in _truth() if b["id"] == bundle_id)
    files = [((BUNDLES / bundle_id / d["file"]).name, (BUNDLES / bundle_id / d["file"]).read_bytes())
             for d in bundle["documents"]]
    case_id, seconds = world.run_case(bundle["case_type"], files)
    identity_cases[bundle_id] = case_id
    detail = world.detail(case_id)

    statuses = {d["original_filename"]: d["processing_status"] for d in detail["documents"]}
    observed = {f for f in _observed(detail) if f[0] != "photo"}
    expected = _expected(bundle)
    REPORT["identity"][bundle_id] = {
        "seconds": round(seconds, 1),
        "statuses": statuses,
        "expected": sorted(map(list, expected)),
        "observed": sorted(map(list, observed)),
        "missing": sorted(map(list, expected - observed)),
        "extra": sorted(map(list, observed - expected)),
        "extracted": {
            d["original_filename"]: {
                k: (v or {}).get("value") for k, v in (d["extracted_fields"] or {}).get("identity_fields", {}).items()
                if k in ("full_name", "date_of_birth", "gender", "annual_income", "id_number")
            }
            for d in detail["documents"]
        },
    }
    assert all(s == "complete" for s in statuses.values()), statuses
    assert expected - observed == set(), f"missed: {sorted(expected - observed)}"
    assert observed - expected == set(), f"unexpected: {sorted(observed - expected)}"


# ---------------------------------------------------------------------------
# 2. Photographs
# ---------------------------------------------------------------------------

def _photo_ids():
    if PHOTO_DIR is None or not (PHOTO_DIR / "ground_truth.json").is_file():
        return []
    return [b["id"] for b in json.loads((PHOTO_DIR / "ground_truth.json").read_text())["bundles"] if _wanted(b["id"])]


@pytest.mark.parametrize("bundle_id", _photo_ids())
def test_photograph_check_on_real_scanned_cards(world, bundle_id):
    if not face_service.models_installed():
        pytest.skip("face models not installed")
    bundle = next(b for b in json.loads((PHOTO_DIR / "ground_truth.json").read_text())["bundles"] if b["id"] == bundle_id)
    files = [(d["file"], (PHOTO_DIR / bundle_id / d["file"]).read_bytes()) for d in bundle["documents"]]
    case_id, seconds = world.run_case(bundle["case_type"], files)
    detail = world.detail(case_id)
    names = {d["id"]: d["original_filename"] for d in detail["documents"]}

    photo = {
        tuple(sorted(names[i] for i in f["document_ids"])): f for f in detail["cross_document_findings"]
        if f["field_name"] == "photo"
    }
    faces = {
        d["original_filename"]: (d["extracted_fields"] or {}).get("faces") for d in detail["documents"]
    }
    wanted = {tuple(sorted(e["documents"])): e["reason"].split("|") for e in bundle["expected_photo_findings"]}
    REPORT["photo"][bundle_id] = {
        "seconds": round(seconds, 1),
        "faces": {n: f"{(v or {}).get('status')}:{len((v or {}).get('items', []))}" for n, v in faces.items()},
        "observed": {"+".join(k): [v["reason"], v["severity"], (v.get("detail") or {}).get("similarity")] for k, v in photo.items()},
        "expected": {"+".join(k): v for k, v in wanted.items()},
    }
    assert set(photo) == set(wanted), f"pairs compared: {sorted(photo)} expected {sorted(wanted)}"
    for pair, reasons in wanted.items():
        assert photo[pair]["reason"] in reasons, (pair, photo[pair]["reason"], reasons)
    # the biometric description never reaches the client
    assert "embedding" not in json.dumps(detail)
    # every photo finding points at a place on both pages
    for finding in photo.values():
        assert all(e["bounding_box"] for e in finding["evidence"])
        assert len(finding["regions"]) == 2
        assert finding["message"]["text"]


# ---------------------------------------------------------------------------
# 3. Reviewer flow, profile, forms, report, languages on a real identity case
# ---------------------------------------------------------------------------

def test_reviewer_flow_on_a_real_conflict(world, identity_cases):
    case_id = identity_cases.get("B07-dob-year-conflict")
    if case_id is None:
        pytest.skip("B07 not run")
    detail = world.detail(case_id)
    conflict = next(f for f in detail["cross_document_findings"] if f["classification"] == "conflict")
    assert conflict["severity"] == "high" and conflict["message"]["action"]
    assert conflict["review_status"] == "pending"

    hindi = world.detail(case_id, lang="hi")
    hindi_conflict = next(f for f in hindi["cross_document_findings"] if f["classification"] == "conflict")
    assert re.search(r"[\u0900-\u097F]", hindi_conflict["message"]["text"])

    # an undecided high conflict blocks approval ...
    blocked = world.client.post(f"/cases/{case_id}/approve", json={}, headers=world.reviewer)
    REPORT["features"]["approve_with_open_conflict"] = [blocked.status_code, blocked.json().get("detail")]
    assert blocked.status_code == 409 and "still need a decision" in blocked.json()["detail"]

    # ... a decision unblocks it
    response = world.client.patch(
        f"/cases/{case_id}/findings/{conflict['id']}",
        json={"decision": "accepted", "note": "Confirmed on the original documents."},
        headers=world.reviewer,
    )
    assert response.status_code == 200, response.text
    assert response.json()["finding"]["review_status"] == "accepted"

    profile = world.client.get(f"/cases/{case_id}/profile", headers=world.reviewer)
    assert profile.status_code == 200, profile.text
    fields = {f["field"]: f for f in profile.json()["fields"]}
    REPORT["features"]["profile_date_of_birth"] = fields["date_of_birth"]["status"]
    assert fields["date_of_birth"]["status"] in {"conflict", "chosen", "agreed"}

    audit = world.client.get(f"/cases/{case_id}/audit-log", headers=world.reviewer)
    assert audit.status_code == 200
    body = audit.json()
    events = {e["event_type"] for e in (body["items"] if isinstance(body, dict) else body)}
    assert {"finding_reviewed", "cross_document_check_completed"} <= events

    reject = world.client.post(f"/cases/{case_id}/reject", json={"reason": "Date of birth does not match."}, headers=world.reviewer)
    REPORT["features"]["reject_with_conflict"] = reject.status_code
    assert reject.status_code == 200, reject.text


def test_clean_bundle_profile_and_prefilled_form(world, identity_cases):
    case_id = identity_cases.get("B01-clean")
    if case_id is None:
        pytest.skip("B01 not run")
    forms = world.client.get("/forms", headers=world.reviewer)
    assert forms.status_code == 200, forms.text
    form_id = forms.json()[0]["id"]
    form = world.client.get(f"/cases/{case_id}/forms/{form_id}", headers=world.reviewer)
    assert form.status_code == 200, form.text
    fields = form.json()["fields"]
    REPORT["features"]["form_fields"] = {f["key"]: f["status"] for f in fields}
    assert any(f["status"] == "filled" for f in fields)


def test_case_report_pdf_for_a_real_case(world, identity_cases):
    out = Path(os.environ["E2E_REPORT"]).parent if os.environ.get("E2E_REPORT") else None
    made = {}
    for bundle_id in ("B03-initials-and-order", "B09-similar-but-different-name"):
        case_id = identity_cases.get(bundle_id)
        if case_id is None:
            continue
        pdf = world.report_pdf(case_id)
        assert pdf[:5] == b"%PDF-" and len(pdf) > 2000
        made[bundle_id] = len(pdf)
        if out:
            (out / f"report_{bundle_id}.pdf").write_bytes(pdf)
    if not made:
        pytest.skip("no identity case run")
    REPORT["features"]["case_report_pdf_bytes"] = made


def test_languages_and_catalog(world):
    languages = world.client.get("/i18n/languages", headers=world.reviewer)
    assert languages.status_code == 200
    codes = {x["code"] for x in languages.json()}
    REPORT["features"]["languages"] = sorted(codes)
    assert {"en", "hi"} <= codes
    catalog = world.client.get("/i18n/catalog", params={"lang": "hi"}, headers=world.reviewer)
    assert catalog.status_code == 200
    assert "Photograph" in json.dumps(catalog.json()) or "फ़ोटो" in json.dumps(catalog.json(), ensure_ascii=False)


# ---------------------------------------------------------------------------
# 4. Upload validation on the real "bad file" samples
# ---------------------------------------------------------------------------

UPLOAD_TESTS = SAMPLES / "upload-tests"


@pytest.mark.parametrize(
    "name, accepted",
    [
        ("valid.pdf", True),
        ("empty.pdf", False),
        ("truncated.pdf", False),
        ("locked.pdf", False),
        ("notes.pdf", False),
        ("photo-renamed.pdf", False),
        ("photo.jpg", False),  # an invoice case takes PDFs only
    ],
)
def test_upload_validation_on_real_bad_files(world, name, accepted):
    path = UPLOAD_TESTS / name
    if not path.is_file():
        pytest.skip(f"{name} missing")
    case_id = world.create_case("vendor_invoice")
    response = world.upload(case_id, name, path.read_bytes())
    REPORT["uploads"][name] = response.status_code
    assert (response.status_code == 201) == accepted, f"{name}: {response.status_code} {response.text[:200]}"
    world.queue.clear()  # the accepted one is not processed here


# ---------------------------------------------------------------------------
# 5. Invoice cases: the original fraud-detection pipeline on real invoices
# ---------------------------------------------------------------------------

def _invoice_cases() -> dict[str, list[Path]]:
    cases: dict[str, list[Path]] = {}
    for folder in (SAMPLES, SAMPLES / "tampered_test_samples"):
        for invoice in sorted(folder.glob("Sample*_Invoice.pdf")):
            cases[invoice.stem.replace("_Invoice", "")] = [invoice, *folder.glob(invoice.name.replace("_Invoice", "_Evidence"))]
    return {k: v for k, v in cases.items() if _wanted(k)}


INVOICE_CASES = _invoice_cases()
INVOICE_RUNS: dict[str, tuple[str, dict]] = {}


@pytest.mark.parametrize("case_name", sorted(INVOICE_CASES))
def test_invoice_case_runs_every_check_on_real_pdfs(world, case_name):
    files = [(p.name, p.read_bytes()) for p in INVOICE_CASES[case_name]]
    case_id, seconds = world.run_case("vendor_invoice", files)
    detail = world.detail(case_id)

    checks: dict[str, dict] = {}
    for document in detail["documents"]:
        for check in document["checks"]:
            checks.setdefault(check["check_type"], {})[document["original_filename"]] = check["status"]
    assessment = detail["assessment"] or {}
    INVOICE_RUNS[case_name] = (case_id, detail)
    REPORT["invoice"][case_name] = {
        "issuers": {d["original_filename"]: ((d["extracted_fields"] or {}).get("core_fields") or {}).get("issuer", {}).get("value") for d in detail["documents"]},
        "issuer_verification": {
            d["original_filename"]: next((c["result"]["result"] for c in d["checks"] if c["check_type"] == "issuer_verification" and c["result"]), None)
            for d in detail["documents"]
        },
        "check_errors": {
            f"{d['original_filename']}:{c['check_type']}": (c.get("error_message") or "")[:140]
            for d in detail["documents"] for c in d["checks"] if c["status"] == "failed"
        },
        "seconds": round(seconds, 1),
        "documents": {d["original_filename"]: [d["processing_status"], d["document_type"], d.get("processing_error")] for d in detail["documents"]},
        "checks": checks,
        "forensic_findings": [f.get("check_type") or f.get("finding") for f in detail["forensic_findings"]][:20],
        "cross_document": [(f["field_name"], f["severity"]) for f in detail["cross_document_findings"]],
        "risk": [assessment.get("score"), assessment.get("tier")],
        "pipeline": detail["pipeline"],
        "case_status": detail["status"],
    }
    if LIVE_LLM:
        assert all(d["processing_status"] == "complete" for d in detail["documents"]), REPORT["invoice"][case_name]["documents"]
    else:  # no model: extraction is refused cleanly, the forensic checks still run on the real PDFs
        assert all(d["processing_status"] == "failed" and "oracle mode" in (d["processing_error"] or "") for d in detail["documents"])
    assert assessment, "no risk assessment was produced"
    required = ["metadata_forensics", "error_level_analysis", "copy_move_detection", "duplicate_detection"]
    if LIVE_LLM:
        required += ["field_validation", "issuer_verification"]
    for name in required:
        assert name in checks, f"{name} did not run: {sorted(checks)}"
        assert all(v == "completed" for v in checks[name].values()), f"{name}: {checks[name]}"


# ---------------------------------------------------------------------------
# 6. Issuer registry and duplicate detection, across two real submissions
# ---------------------------------------------------------------------------

def test_issuer_registry_match_and_duplicate_submission(world):
    if not INVOICE_RUNS:
        pytest.skip("no invoice case was run")
    name = sorted(INVOICE_RUNS)[0]
    case_id, detail = INVOICE_RUNS[name]
    invoice = next(d for d in detail["documents"] if d["original_filename"].endswith("_Invoice.pdf"))
    issuer = ((invoice["extracted_fields"] or {}).get("core_fields") or {}).get("issuer", {}).get("value")

    if issuer:
        created = world.client.post("/settings/issuers", json={"name": issuer, "type": "vendor"}, headers=world.reviewer)
        assert created.status_code == 201, created.text
        listed = world.client.get("/settings/issuers", headers=world.reviewer)
        assert any(i["name"] == issuer for i in listed.json())

    path = next(p for p in INVOICE_CASES[name] if p.name.endswith("_Invoice.pdf"))
    second_case, _ = world.run_case("vendor_invoice", [(path.name, path.read_bytes())])
    second = world.detail(second_case)
    checks = {c["check_type"]: c for c in second["documents"][0]["checks"]}
    REPORT["features"]["registry_and_duplicate"] = {
        "issuer": issuer,
        "issuer_verification": ((checks.get("issuer_verification") or {}).get("result") or {}).get("result"),
        "duplicate_detection": (checks.get("duplicate_detection") or {}).get("result", {}).get("result"),
    }
    if issuer:
        assert checks["issuer_verification"]["result"]["result"] == "pass"
    assert checks["duplicate_detection"]["result"]["result"] == "flag", "re-submitting the same file must be flagged"


# ---------------------------------------------------------------------------
# 7. Sign-in, settings, bulk upload
# ---------------------------------------------------------------------------

def test_sign_in_and_settings(world):
    login = world.client.post("/auth/login", json={"email": "e2e.reviewer@example.com", "password": "TestPassword123!"})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    me = world.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["email"] == "e2e.reviewer@example.com"
    wrong = world.client.post("/auth/login", json={"email": "e2e.reviewer@example.com", "password": "nope"})
    assert wrong.status_code == 401
    rules = world.client.get("/settings/risk-rules", headers=world.reviewer)
    assert rules.status_code == 200 and len(rules.json()) > 20
    REPORT["features"]["risk_rules"] = len(rules.json())
    # a submitter may not open the settings
    assert world.client.get("/settings/risk-rules", headers=world.submitter).status_code == 403


def test_bulk_upload_of_identity_bundles(world):
    wanted = [b for b in ("B01-clean", "B07-dob-year-conflict") if _wanted(b)]
    if not wanted:
        pytest.skip("not selected")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for bundle in wanted:
            for path in sorted((BUNDLES / bundle).iterdir()):
                archive.writestr(f"{bundle}/{path.name}", path.read_bytes())
    response = world.client.post(
        "/bulk-uploads", params={"case_type": "identity_verification", "filename": "bundles.zip"},
        content=buffer.getvalue(), headers={**world.submitter, "Content-Type": "application/zip"},
    )
    assert response.status_code == 202, response.text
    bulk_id = response.json()["id"]
    world.drain()
    detail = world.client.get(f"/bulk-uploads/{bulk_id}", headers=world.submitter).json()
    cases = detail["cases"]
    REPORT["features"]["bulk_upload"] = {"status": detail["status"], "cases": [(c["folder"], c["status"], c["live_status"]) for c in cases]}
    assert [c["status"] for c in cases] == ["created"] * len(wanted)
    by_folder = {c["folder"]: world.detail(c["case_id"]) for c in cases}
    if "B07-dob-year-conflict" in by_folder:
        assert any(f["field_name"] == "date_of_birth" and f["classification"] == "conflict"
                   for f in by_folder["B07-dob-year-conflict"]["cross_document_findings"])
