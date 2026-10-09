"""Signature comparison across the documents of an identity bundle
(app/services/signature_local.py, identity_comparison.signature_findings,
PUT /cases/{id}/signature-reference). Signatures here are drawn by the test
(no real person's handwriting is stored)."""
import itertools
import uuid

import cv2
import numpy as np
import pytest

from app.models.case import CaseType
from app.models.cross_document_finding import FindingSeverity
from app.models.document import Document, DocumentProcessingStatus
from app.services import signature_local as sl
from app.services.identity_comparison import CONFLICT, HARMLESS, BundleDocument, find_identity_contradictions
from app.services.identity_messages import build_message
from tests.helpers_risk import make_case


def _drawn(name: str, seed: int = 0, font=cv2.FONT_HERSHEY_SCRIPT_SIMPLEX) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.full((160, 420, 3), 235, np.uint8)
    cv2.putText(img, name, (20, 100), font, 2.0 + 0.1 * (seed % 3), (60, 30, 20), 2 + seed % 2, cv2.LINE_AA)
    matrix = cv2.getRotationMatrix2D((210, 80), (seed % 5) - 2, 1 + 0.05 * (seed % 3))
    img = cv2.warpAffine(img, matrix, (420, 160), borderValue=(235, 235, 235))
    img = np.clip(cv2.GaussianBlur(img, (0, 0), 0.8) + rng.normal(0, 3, img.shape), 0, 255).astype(np.uint8)
    return img


def _template(image: np.ndarray) -> str:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return sl._pack(sl.describe(sl._clean_ink(sl._ink_mask(gray))))


def _card(signature: np.ndarray | None, label: bool = True):
    """A card page (BGR) with a signature above its printed label, and the OCR
    words the pipeline would hand over."""
    page = np.full((600, 900, 3), 245, np.uint8)
    words = [{"text": "NAME", "x": 0.05, "y": 0.1, "width": 0.1, "height": 0.04}]
    cv2.putText(page, "NAME", (45, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (30, 30, 30), 2)
    if signature is not None:
        small = cv2.resize(signature, (270, 100))
        page[330:430, 300:570] = small
    if label:
        cv2.putText(page, "Signature", (340, 480), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (90, 40, 20), 2)
        words.append({"text": "Signature", "x": 340 / 900, "y": 450 / 600, "width": 0.17, "height": 0.06})
    return page, words


# ---- finding and describing -------------------------------------------------

def test_a_signature_above_its_label_is_found_with_its_place():
    page, words = _card(_drawn("Gupta"))
    (item,) = sl.find_on_page(page, words, 1)
    box = item["bounding_box"]
    assert box["page"] == 1 and 0.3 < box["x"] < 0.7 and 0.5 < box["y"] < 0.8
    assert item["ink"] > 200 and item["template"]


def test_a_page_without_a_signature_label_has_none_found():
    page, words = _card(_drawn("Gupta"), label=False)
    assert sl.find_on_page(page, [w for w in words if w["text"] != "Signature"], 1) == []


def test_a_label_with_nothing_written_above_it_finds_nothing():
    page, words = _card(None)
    assert sl.find_on_page(page, words, 1) == []


def test_the_label_in_hindi_is_recognised():
    assert sl._is_label("हस्ताक्षर") and sl._is_label("Signature:") and not sl._is_label("Name")


def test_analyse_document_never_raises():
    assert sl.analyse_document([(np.zeros((0, 0, 3), np.uint8), [])])["status"] in {sl.STATUS_OK, sl.STATUS_FAILED}


# ---- comparing --------------------------------------------------------------

def test_one_signature_resembles_itself_far_more_than_another_name():
    base = _template(_drawn("Gupta", 0))
    same = [sl.similarity(base, _template(_drawn("Gupta", s))) for s in range(1, 6)]
    other = [sl.similarity(base, _template(_drawn(n, 1))) for n in ("Sharma", "Rathore", "Verma", "Joshi")]
    assert min(same) > max(other)
    assert np.mean(same) > sl.MATCH_THRESHOLD > sl.DIFFERENT_THRESHOLD > np.mean(other) - 0.1


def test_the_same_signature_resized_or_recompressed_still_matches():
    page, words = _card(_drawn("Gupta"))
    a = sl.find_on_page(page, words, 1)[0]["template"]
    small = cv2.resize(page, None, fx=0.6, fy=0.6)
    b = sl.find_on_page(small, words, 1)[0]["template"]
    jpeg = cv2.imdecode(cv2.imencode(".jpg", page, [cv2.IMWRITE_JPEG_QUALITY, 35])[1], cv2.IMREAD_COLOR)
    c = sl.find_on_page(jpeg, words, 1)[0]["template"]
    assert sl.similarity(a, b) >= sl.MATCH_THRESHOLD and sl.similarity(a, c) >= sl.MATCH_THRESHOLD


# ---- inside the bundle ------------------------------------------------------

def _item(signature: np.ndarray, page: int = 1) -> dict:
    return {"bounding_box": {"page": page, "x": 0.3, "y": 0.5, "width": 0.3, "height": 0.15}, "ink": 500,
            "template": _template(signature)}


def _doc(doc_id, document_type, *signatures) -> BundleDocument:
    return BundleDocument(doc_id, f"{doc_id}.jpg", document_type, {}, (), tuple(signatures))


def _findings(reference_id, *documents):
    return [f for f in find_identity_contradictions(list(documents), reference_id) if f["field_name"] == "signature"]


def test_every_other_document_is_compared_with_the_reference_only():
    ref = _doc("pan", "tax_id_card", _item(_drawn("Gupta", 0)))
    same = _doc("licence", "driving_licence", _item(_drawn("Gupta", 3)))
    other = _doc("passport", "passport", _item(_drawn("Rathore", 1)))
    results = {tuple(f["document_ids"]): f for f in _findings("pan", ref, same, other)}
    assert set(results) == {("pan", "licence"), ("pan", "passport")}  # not licence-passport
    assert results[("pan", "licence")]["reason"] == "signature_match"
    assert results[("pan", "licence")]["classification"] == HARMLESS
    bad = results[("pan", "passport")]
    assert bad["classification"] == CONFLICT and bad["severity"] == FindingSeverity.high
    assert bad["reason"] == "signature_mismatch" and bad["detail"]["similarity"] < sl.DIFFERENT_THRESHOLD
    assert [e["bounding_box"]["page"] for e in bad["evidence"]] == [1, 1]
    assert "does not look like the reference signature" in bad["description"]


def test_a_document_with_no_signature_is_not_a_mismatch():
    ref = _doc("pan", "tax_id_card", _item(_drawn("Gupta")))
    (finding,) = _findings("pan", ref, _doc("aadhaar", "national_id_card"))
    assert finding["reason"] == "signature_absent" and finding["classification"] == HARMLESS
    assert finding["severity"] == FindingSeverity.info
    assert finding["evidence"][1]["bounding_box"] is None


def test_no_reference_or_a_reference_without_a_signature_gives_no_findings():
    a = _doc("a", "tax_id_card", _item(_drawn("Gupta")))
    b = _doc("b", "driving_licence", _item(_drawn("Gupta", 2)))
    assert _findings(None, a, b) == []
    assert _findings("missing", a, b) == []
    assert _findings("c", _doc("c", "national_id_card"), a) == []


def test_messages_in_english_and_hindi():
    ref = _doc("pan", "tax_id_card", _item(_drawn("Gupta", 0)))
    other = _doc("passport", "passport", _item(_drawn("Rathore", 1)))
    (f,) = _findings("pan", ref, other)
    en = build_message("signature", f["classification"], f["reason"], "high", f["evidence"], f["detail"])
    assert en["field_label"] == "Signature"
    assert en["summary"] == "The signature on the passport does not look like the reference signature on the tax identity card."
    hi = build_message("signature", f["classification"], f["reason"], "high", f["evidence"], f["detail"], "hi")
    assert hi["field_label"] == "हस्ताक्षर" and "संदर्भ हस्ताक्षर" in hi["summary"]


# ---- privacy ----------------------------------------------------------------

def test_the_stored_ink_picture_never_reaches_a_client():
    stored = {"signatures": {"status": "ok", "items": [_item(_drawn("Gupta"))]}}
    public = sl.public_signatures(stored)
    assert "template" not in public["signatures"]["items"][0]
    assert public["signatures"]["items"][0]["bounding_box"]["page"] == 1
    assert "template" in stored["signatures"]["items"][0]


# ---- the reference endpoint ---------------------------------------------------

@pytest.fixture()
def identity_case(db_session, plain_user):
    case = make_case(db_session, plain_user)
    case.case_type = CaseType.identity_verification

    def add(name, signed):
        fields = {"schema": "identity", "identity_fields": {},
                  "signatures": {"status": "ok", "items": [_item(_drawn("Gupta"))] if signed else []}}
        doc = Document(case_id=case.id, uploaded_by_user_id=plain_user.id, original_filename=name,
                       blob_storage_path=f"p/{name}", file_hash=uuid.uuid4().hex * 2, content_type="image/jpeg",
                       processing_status=DocumentProcessingStatus.complete, extracted_fields=fields)
        db_session.add(doc)
        return doc

    signed, unsigned = add("pan.jpg", True), add("aadhaar.jpg", False)
    db_session.commit()
    return case, signed, unsigned


def test_a_reviewer_picks_the_reference_document(client, reviewer_headers, identity_case, db_session):
    case, signed, unsigned = identity_case
    refused = client.put(f"/cases/{case.id}/signature-reference", json={"document_id": str(unsigned.id)},
                         headers=reviewer_headers)
    assert refused.status_code == 409 and "No signature was found" in refused.json()["detail"]
    ok = client.put(f"/cases/{case.id}/signature-reference", json={"document_id": str(signed.id)},
                    headers=reviewer_headers)
    assert ok.status_code == 200 and ok.json()["signature_reference_document_id"] == str(signed.id)
    detail = client.get(f"/cases/{case.id}", headers=reviewer_headers).json()
    assert detail["signature_reference_document_id"] == str(signed.id)
    assert "template" not in str(detail["documents"])
    cleared = client.delete(f"/cases/{case.id}/signature-reference", headers=reviewer_headers)
    assert cleared.json()["signature_reference_document_id"] is None


def test_a_submitter_cannot_and_a_foreign_document_is_refused(client, plain_headers, reviewer_headers, identity_case):
    case, signed, _ = identity_case
    assert client.put(f"/cases/{case.id}/signature-reference", json={"document_id": str(signed.id)},
                      headers=plain_headers).status_code == 403
    assert client.put(f"/cases/{case.id}/signature-reference", json={"document_id": str(uuid.uuid4())},
                      headers=reviewer_headers).status_code == 404


def test_an_invoice_case_has_no_signature_comparison(client, reviewer_headers, identity_case, db_session):
    case, signed, _ = identity_case
    case.case_type = CaseType.vendor_invoice
    db_session.commit()
    assert client.put(f"/cases/{case.id}/signature-reference", json={"document_id": str(signed.id)},
                      headers=reviewer_headers).status_code == 409
