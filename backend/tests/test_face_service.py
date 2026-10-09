"""Photograph comparison across the documents of an identity bundle
(app/services/face_service.py, app/services/identity_comparison.py).

The comparison logic is tested on hand-made descriptions, so it needs no
model and no photograph. The detector itself is exercised by the last tests,
which need the model files and a folder of portraits supplied by the
developer (FACE_TEST_PHOTOS: person_a_1.jpg, person_a_2.jpg, person_b_1.jpg);
no photograph of a real person is stored in the repository. They are skipped
when either is missing.
"""
import os
from pathlib import Path

import numpy as np
import pytest

from app.models.cross_document_finding import FindingSeverity
from app.services import face_service
from app.services.identity_comparison import (
    CONFLICT,
    HARMLESS,
    BundleDocument,
    compare_photos,
    find_identity_contradictions,
)
from app.services.identity_messages import build_message


def _unit(*values: float) -> list[float]:
    vector = np.array((*values, 0, 0, 0)[:3] if len(values) < 3 else values, dtype=float)
    return (vector / np.linalg.norm(vector)).tolist()


def _face(embedding: list[float], page: int = 1) -> dict:
    return {
        "bounding_box": {"page": page, "x": 0.1, "y": 0.2, "width": 0.15, "height": 0.2},
        "score": 0.95,
        "pixels": 120,
        "embedding": embedding,
    }


def _doc(doc_id: str, document_type: str, *faces: dict, fields: dict | None = None) -> BundleDocument:
    return BundleDocument(
        id=doc_id,
        filename=f"{doc_id}.pdf",
        document_type=document_type,
        identity_fields=fields or {},
        faces=tuple(faces),
    )


def _with_similarity(target: float) -> tuple[list[float], list[float]]:
    """Two descriptions whose cosine similarity is `target`."""
    angle = np.arccos(target)
    return _unit(1, 0), _unit(np.cos(angle), np.sin(angle))


# ---- the comparison -------------------------------------------------------

def test_same_person_is_recorded_as_a_harmless_match():
    a, b = _with_similarity(0.8)
    verdict = compare_photos(_doc("a", "national_id_card", _face(a)), _doc("b", "voter_id_card", _face(b)))
    assert verdict.classification == HARMLESS and verdict.reason == "photo_match"
    assert verdict.severity == FindingSeverity.info
    assert verdict.detail["similarity"] == pytest.approx(0.8, abs=0.001)


def test_clearly_different_people_are_a_critical_conflict():
    a, b = _with_similarity(0.05)
    verdict = compare_photos(_doc("a", "national_id_card", _face(a)), _doc("b", "voter_id_card", _face(b)))
    assert verdict.classification == CONFLICT and verdict.reason == "photo_different_person"
    assert verdict.severity == FindingSeverity.critical


def test_a_score_in_between_is_left_to_a_person():
    a, b = _with_similarity(0.35)
    verdict = compare_photos(_doc("a", "national_id_card", _face(a)), _doc("b", "voter_id_card", _face(b)))
    assert verdict.classification == CONFLICT and verdict.reason == "photo_uncertain"
    assert verdict.severity == FindingSeverity.medium


@pytest.mark.parametrize(
    "similarity, reason",
    [
        (face_service.MATCH_THRESHOLD, "photo_match"),
        (face_service.MATCH_THRESHOLD - 0.01, "photo_uncertain"),
        (face_service.DIFFERENT_THRESHOLD, "photo_uncertain"),
        (face_service.DIFFERENT_THRESHOLD - 0.01, "photo_different_person"),
    ],
)
def test_the_thresholds_are_where_they_say(similarity, reason):
    a, b = _with_similarity(similarity)
    verdict = compare_photos(_doc("a", "x", _face(a)), _doc("b", "y", _face(b)))
    assert verdict.reason == reason


def test_a_document_without_a_photograph_is_not_compared():
    a, _ = _with_similarity(0.5)
    assert compare_photos(_doc("a", "national_id_card", _face(a)), _doc("b", "income_certificate")) is None
    assert compare_photos(_doc("a", "income_certificate"), _doc("b", "address_proof")) is None


def test_the_best_pair_of_faces_decides():
    """A repeated small "ghost" photograph or a second person must not raise
    a conflict when the main photographs match."""
    same_a, same_b = _with_similarity(0.9)
    stranger = _unit(0, 0, 1)
    verdict = compare_photos(
        _doc("a", "national_id_card", _face(same_a), _face(stranger)),
        _doc("b", "voter_id_card", _face(stranger), _face(same_b)),
    )
    assert verdict.reason == "photo_match"


def test_a_face_without_a_description_is_ignored():
    assert face_service.best_match([{"bounding_box": {}}], [_face(_unit(1, 0))]) is None


# ---- inside the bundle ------------------------------------------------------

def test_a_bundle_gets_one_photo_finding_per_pair_with_both_places_on_the_pages():
    a, b = _with_similarity(0.02)
    documents = [
        _doc("a", "national_id_card", _face(a, page=1)),
        _doc("b", "voter_id_card", _face(b, page=2)),
        _doc("c", "income_certificate"),
    ]
    findings = [f for f in find_identity_contradictions(documents) if f["field_name"] == "photo"]
    assert len(findings) == 1
    finding = findings[0]
    assert finding["classification"] == CONFLICT and finding["severity"] == FindingSeverity.critical
    assert finding["document_ids"] == ["a", "b"]
    assert [e["bounding_box"]["page"] for e in finding["evidence"]] == [1, 2]
    assert finding["detail"]["similarity"] < 0.1
    assert "photograph on the identity card does not look like" in finding["description"]


def test_matching_photos_are_listed_as_ignored_not_raised():
    a, b = _with_similarity(0.9)
    findings = find_identity_contradictions(
        [_doc("a", "national_id_card", _face(a)), _doc("b", "driving_licence", _face(b))]
    )
    assert [(f["field_name"], f["classification"], f["severity"]) for f in findings] == [
        ("photo", HARMLESS, FindingSeverity.info)
    ]


def test_three_documents_are_compared_pairwise():
    a, b = _with_similarity(0.9)
    other = _unit(0, 0, 1)
    documents = [
        _doc("a", "national_id_card", _face(a)),
        _doc("b", "driving_licence", _face(b)),
        _doc("c", "voter_id_card", _face(other)),
    ]
    photo = {tuple(f["document_ids"]): f["reason"] for f in find_identity_contradictions(documents)}
    assert photo == {
        ("a", "b"): "photo_match",
        ("a", "c"): "photo_different_person",
        ("b", "c"): "photo_different_person",
    }


def test_bundles_without_photographs_are_unchanged():
    assert find_identity_contradictions([_doc("a", "national_id_card"), _doc("b", "voter_id_card")]) == []


def test_the_message_names_the_documents_in_english_and_hindi():
    a, b = _with_similarity(0.02)
    finding = [
        f
        for f in find_identity_contradictions(
            [_doc("a", "national_id_card", _face(a)), _doc("b", "voter_id_card", _face(b))]
        )
        if f["field_name"] == "photo"
    ][0]
    english = build_message(
        "photo", finding["classification"], finding["reason"], "critical", finding["evidence"], finding["detail"]
    )
    assert english["field_label"] == "Photograph"
    assert english["summary"] == (
        "The photograph on the identity card does not look like the photograph on the voter identity card."
    )
    assert "two different people" in english["explanation"]
    hindi = build_message(
        "photo", finding["classification"], finding["reason"], "critical", finding["evidence"], finding["detail"], "hi"
    )
    assert hindi["summary"] == "पहचान पत्र की फ़ोटो मतदाता पहचान पत्र की फ़ोटो से मेल नहीं खाती।"
    assert hindi["field_label"] == "फ़ोटो"


# ---- privacy ----------------------------------------------------------------

def test_face_descriptions_never_leave_the_server():
    stored = {
        "schema": "identity",
        "identity_fields": {},
        "faces": {"status": "ok", "items": [_face(_unit(1, 0))]},
    }
    public = face_service.public_extracted_fields(stored)
    assert "embedding" not in public["faces"]["items"][0]
    assert public["faces"]["items"][0]["bounding_box"]["page"] == 1
    assert "embedding" in stored["faces"]["items"][0]  # the stored value is untouched


def test_public_fields_pass_through_when_there_are_no_faces():
    assert face_service.public_extracted_fields(None) is None
    plain = {"core_fields": {}}
    assert face_service.public_extracted_fields(plain) is plain


def test_a_document_response_carries_no_description(tmp_path):
    from app.schemas.document import CaseDocumentSummary

    class _Doc:
        id = "00000000-0000-0000-0000-000000000001"
        original_filename = "id.pdf"
        document_type = "national_id_card"
        processing_status = type("S", (), {"value": "complete"})()
        extracted_fields = {"faces": {"status": "ok", "items": [_face(_unit(1, 0))]}}
        processing_error = None
        content_type = "application/pdf"
        file_size_bytes = 1
        file_hash = "x"
        created_at = __import__("datetime").datetime(2026, 1, 1)
        checks: list = []

    summary = CaseDocumentSummary.from_document(_Doc(), "http://example/file")
    assert "embedding" not in summary.extracted_fields["faces"]["items"][0]


# ---- the detector (needs models and portraits) -------------------------------

def _photos():
    folder = os.environ.get("FACE_TEST_PHOTOS")
    if not folder or not Path(folder).is_dir():
        pytest.skip("FACE_TEST_PHOTOS not set")
    if not face_service.models_installed():
        pytest.skip("face models not installed (python -m app.services.face_models)")
    return Path(folder)


def test_a_page_with_no_face_reports_none():
    if not face_service.models_installed():
        pytest.skip("face models not installed")
    import cv2

    blank = cv2.imencode(".png", np.full((800, 1200, 3), 255, np.uint8))[1].tobytes()
    assert face_service.analyse_document(blank) == {"status": "ok", "items": []}


def test_without_models_the_check_reports_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(face_service.settings, "face_model_dir", str(tmp_path))
    monkeypatch.setattr(face_service, "_models", None)
    result = face_service.analyse_document(b"%PDF-1.4")
    assert result["status"] == "unavailable" and result["items"] == []


def test_a_garbled_file_never_raises():
    if not face_service.models_installed():
        pytest.skip("face models not installed")
    assert face_service.analyse_document(b"not an image")["items"] == []


def test_the_same_person_matches_and_another_does_not():
    folder = _photos()
    person_a = face_service.analyse_document((folder / "person_a_1.jpg").read_bytes())["items"]
    person_a2 = face_service.analyse_document((folder / "person_a_2.jpg").read_bytes())["items"]
    person_b = face_service.analyse_document((folder / "person_b_1.jpg").read_bytes())["items"]
    assert person_a and person_a2 and person_b
    same = face_service.best_match(person_a, person_a2)[0]
    different = face_service.best_match(person_a, person_b)[0]
    assert same >= face_service.MATCH_THRESHOLD
    assert different < face_service.MATCH_THRESHOLD


# ---- hardening: geometry, odd files, threads ---------------------------------

@pytest.mark.parametrize("rotation", ["cw", "ccw", "half"])
def test_a_box_found_on_a_turned_page_is_placed_back_on_the_page(rotation):
    """_unrotate must be the inverse of turning the page."""
    import cv2

    codes = {"cw": cv2.ROTATE_90_CLOCKWISE, "ccw": cv2.ROTATE_90_COUNTERCLOCKWISE, "half": cv2.ROTATE_180}
    page = np.zeros((300, 500), dtype=np.uint8)
    page[60:120, 340:400] = 255  # the "face": x 0.68-0.80, y 0.20-0.40
    turned = cv2.rotate(page, codes[rotation])
    ys, xs = np.where(turned > 0)
    height, width = turned.shape
    found = face_service.Face(
        1, xs.min() / width, ys.min() / height, (xs.max() - xs.min() + 1) / width,
        (ys.max() - ys.min() + 1) / height, 0.9, 50, (1.0,),
    )
    back = face_service._unrotate(found, codes[rotation])
    assert (back.x, back.y, back.width, back.height) == pytest.approx((0.68, 0.20, 0.12, 0.20), abs=0.01)


def _portrait_card(folder: Path, name: str) -> np.ndarray:
    import cv2

    image = cv2.imread(str(folder / f"{name}.jpg"))
    detector, _ = face_service._load_models()
    detector.setInputSize((image.shape[1], image.shape[0]))
    _, found = detector.detect(image)
    x, y, w, h = (int(v) for v in found[0][:4])
    margin = int(0.35 * w)
    face = cv2.resize(image[max(0, y - margin): y + h + margin, max(0, x - margin): x + w + margin], (130, 162))
    page = np.full((900, 1400, 3), 245, np.uint8)
    page[150:312, 90:220] = face
    cv2.putText(page, "SPECIMEN CARD", (320, 230), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (30, 30, 30), 3)
    return page


@pytest.mark.parametrize("turn", [None, "cw", "half", "ccw"])
def test_a_card_photographed_sideways_or_upside_down_is_still_read(turn):
    import cv2

    folder = _photos()
    page = _portrait_card(folder, "person_a_1")
    if turn:
        page = cv2.rotate(page, {"cw": cv2.ROTATE_90_CLOCKWISE, "half": cv2.ROTATE_180, "ccw": cv2.ROTATE_90_COUNTERCLOCKWISE}[turn])
    faces = face_service.analyse_document(cv2.imencode(".jpg", page)[1].tobytes())["items"]
    assert len(faces) == 1
    box = faces[0]["bounding_box"]
    # the box sits on the face: the face is in the printed card's top-left corner
    # of the unturned page, wherever the page was turned to
    inside = page[int(box["y"] * page.shape[0]): int((box["y"] + box["height"]) * page.shape[0]),
                  int(box["x"] * page.shape[1]): int((box["x"] + box["width"]) * page.shape[1])]
    assert inside.shape[0] > 20 and inside.std() > 25  # a face, not blank paper


def test_a_face_on_a_later_page_of_a_pdf_or_tiff_is_found_with_its_page_number():
    import io

    import cv2
    import pymupdf
    from PIL import Image

    page = _portrait_card(_photos(), "person_a_1")
    jpeg = cv2.imencode(".jpg", page)[1].tobytes()
    pdf = pymupdf.open()
    pdf.new_page()
    second = pdf.new_page()
    second.insert_image(second.rect, stream=jpeg)
    assert face_service.analyse_document(pdf.tobytes())["items"][0]["bounding_box"]["page"] == 2

    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(
        buffer, format="TIFF", save_all=True, append_images=[Image.fromarray(cv2.cvtColor(page, cv2.COLOR_BGR2RGB))]
    )
    assert face_service.analyse_document(buffer.getvalue())["items"][0]["bounding_box"]["page"] == 2


def test_a_phone_photo_turned_by_its_exif_tag_is_read_upright():
    import io

    import cv2
    from PIL import Image

    page = _portrait_card(_photos(), "person_a_1")
    sideways = Image.fromarray(cv2.cvtColor(cv2.rotate(page, cv2.ROTATE_90_CLOCKWISE), cv2.COLOR_BGR2RGB))
    exif = Image.Exif()
    exif[0x0112] = 6  # "rotate 90 clockwise to display": stored sideways, shown upright
    buffer = io.BytesIO()
    sideways.save(buffer, format="JPEG", exif=exif)
    faces = face_service.analyse_document(buffer.getvalue())["items"]
    assert len(faces) == 1


def test_several_documents_at_once_give_the_same_answer():
    """Workers may run documents in threads; the models are shared."""
    import cv2
    from concurrent.futures import ThreadPoolExecutor

    folder = _photos()
    contents = [cv2.imencode(".jpg", _portrait_card(folder, n))[1].tobytes() for n in ("person_a_1", "person_a_2", "person_b_1")]
    alone = [face_service.analyse_document(c)["items"][0]["embedding"] for c in contents]
    with ThreadPoolExecutor(max_workers=4) as pool:
        together = list(pool.map(lambda c: face_service.analyse_document(c)["items"][0]["embedding"], contents * 4))
    for index, embedding in enumerate(together):
        assert face_service.similarity(embedding, alone[index % 3]) > 0.999
