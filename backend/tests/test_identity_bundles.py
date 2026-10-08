"""The synthetic identity bundles (scripts/generate_identity_bundles.py): the
files are valid uploads, each document really prints what the ground truth
says, and the ground truth is internally consistent. All data is made up."""
import json
import zipfile

import pymupdf
import pytest

from app.services.field_locator_service import attach_field_locations
from app.services.identity_documents import (
    IDENTITY_DOCUMENT_TYPE_LABELS,
    IDENTITY_FIELD_NAMES,
    identity_extracted_fields,
)
from app.services.llm_service import IdentityAnalysis
from app.services.ocr_service import OCRPage, OCRWord
from app.services.upload_validation import validate_upload
from scripts.generate_identity_bundles import build_bundles, generate

LIMIT = 10 * 1024 * 1024
SEVERITIES = {"info", "low", "medium", "high", "critical"}


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    out = tmp_path_factory.mktemp("identity-bundles")
    return out, generate(out)


def _documents(generated):
    out, truth = generated
    for bundle in truth["bundles"]:
        for document in bundle["documents"]:
            yield bundle, document, out / bundle["id"] / document["file"]


def test_every_kind_of_bundle_is_generated(generated):
    _, truth = generated
    kinds = {b["kind"] for b in truth["bundles"]}
    assert kinds == {"clean", "harmless", "conflict"}
    assert {b["case_type"] for b in truth["bundles"]} == {"identity_verification", "hiring_verification"}
    skipped = {s["bundle"] for s in truth["skipped"]}
    assert {b["id"] for b in truth["bundles"]} | skipped == {b.id for b in build_bundles()}
    formats = {d["file"].rsplit(".", 1)[1] for b in truth["bundles"] for d in b["documents"]}
    assert {"pdf", "jpg", "png", "tiff"} <= formats


def test_every_file_is_an_acceptable_upload(generated):
    for _, document, path in _documents(generated):
        validated = validate_upload(path.read_bytes(), path.name, max_bytes=LIMIT, allow_images=True)
        assert validated.page_count == 1
        assert document["document_type"] in IDENTITY_DOCUMENT_TYPE_LABELS


def test_ground_truth_matches_the_extraction_model(generated):
    """Each document's ground truth is a valid extraction result, so later
    phases can feed it straight into the comparison."""
    for _, document, _path in _documents(generated):
        fields = document["identity_fields"]
        assert tuple(fields) == IDENTITY_FIELD_NAMES
        analysis = IdentityAnalysis(
            document_type=document["document_type"], document_type_confidence=1.0, **fields
        )
        assert identity_extracted_fields(analysis)["identity_fields"] == fields


def test_english_pdfs_print_exactly_what_the_ground_truth_says(generated):
    for _, document, path in _documents(generated):
        if path.suffix != ".pdf" or document["language"] != "en":
            continue
        with pymupdf.open(path) as pdf:
            text = " ".join(pdf[0].get_text().split())
        fields = document["identity_fields"]
        for name in ("full_name", "parent_or_spouse_name", "address", "id_number"):
            if fields[name]["value"]:
                assert fields[name]["value"] in text, (path.name, name)
        for name in ("date_of_birth", "issue_date", "annual_income", "gender"):
            if fields[name]["raw_text"]:
                assert fields[name]["raw_text"] in text, (path.name, name)
        assert "SPECIMEN" in text


def test_expected_findings_are_consistent(generated):
    _, truth = generated
    for bundle in truth["bundles"]:
        files = {d["file"]: d["identity_fields"] for d in bundle["documents"]}
        classes = [e["classification"] for e in bundle["expected_findings"]]
        if bundle["kind"] == "clean":
            assert classes == []
        elif bundle["kind"] == "harmless":
            assert classes and set(classes) == {"harmless_variant"}
        else:
            assert "conflict" in classes
        for expected in bundle["expected_findings"]:
            first, second = expected["documents"]
            assert first != second
            assert expected["field"] in IDENTITY_FIELD_NAMES
            assert expected["severity"] in SEVERITIES
            assert (expected["severity"] == "info") == (expected["classification"] == "harmless_variant")
            # A finding needs a value on both sides, and the two must differ as printed.
            a, b = files[first][expected["field"]], files[second][expected["field"]]
            assert a["value"] is not None and b["value"] is not None
            assert a["value"] != b["value"]


def test_fields_without_an_expected_finding_agree_once_normalized(generated):
    """Dates, gender and income are stored normalized: wherever the ground
    truth lists no finding, every document that has the field has the same
    value. (Names and addresses need the comparison engine.)"""
    _, truth = generated
    for bundle in truth["bundles"]:
        flagged = {e["field"] for e in bundle["expected_findings"]}
        for name in ("date_of_birth", "gender", "annual_income"):
            if name in flagged:
                continue
            values = {
                d["identity_fields"][name]["value"]
                for d in bundle["documents"]
                if d["identity_fields"][name]["value"] is not None
            }
            assert len(values) <= 1, (bundle["id"], name, values)


def test_families_reference_their_member_bundles(generated):
    _, truth = generated
    bundles = {b["id"]: b for b in truth["bundles"]}
    for family in truth["families"]:
        assert bundles[family["head"]]["relation"] == "head"
        for member in family["members"]:
            assert bundles[member["bundle"]]["family"] == family["id"]
            assert bundles[member["bundle"]]["relation"] == member["relation"]


def test_zips_hold_one_folder_per_bundle(generated):
    out, truth = generated
    for case_type in ("identity_verification", "hiring_verification"):
        expected = {
            f"{b['id']}/{d['file']}" for b in truth["bundles"] if b["case_type"] == case_type for d in b["documents"]
        }
        with zipfile.ZipFile(out / f"{case_type.replace('_', '-')}-bundles.zip") as zf:
            assert set(zf.namelist()) == expected


def test_generation_is_repeatable(generated, tmp_path):
    out, truth = generated
    again = generate(tmp_path)
    assert again == truth
    assert json.loads((out / "ground_truth.json").read_text(encoding="utf-8")) == truth


def _ocr_page(path) -> OCRPage:
    """The PDF's own words as an OCR page (positions as page fractions)."""
    with pymupdf.open(path) as pdf:
        page = pdf[0]
        width, height = page.rect.width, page.rect.height
        words = [
            OCRWord(text=w[4], x=w[0] / width, y=w[1] / height, width=(w[2] - w[0]) / width,
                    height=(w[3] - w[1]) / height)
            for w in page.get_text("words")
        ]
    return OCRPage(page_number=1, words=words, lines=[])


def test_values_are_located_on_the_generated_pages(generated):
    """The page-position step finds the printed values on these documents."""
    for _, document, path in _documents(generated):
        if path.suffix != ".pdf" or document["language"] != "en":
            continue
        stored = {"identity_fields": json.loads(json.dumps(document["identity_fields"]))}
        attach_field_locations([_ocr_page(path)], stored)
        fields = stored["identity_fields"]
        for name in ("full_name", "date_of_birth", "id_number", "annual_income", "issue_date"):
            if fields[name]["value"] is not None:
                assert "bounding_box" in fields[name], (path.name, name)
        # The value column starts to the right of the label column.
        assert fields["full_name"]["bounding_box"]["x"] > 0.35


def test_the_terminal_demo_reports_every_bundle_as_expected(generated, capsys):
    from scripts.demo_identity_bundles import detail, summary

    _, truth = generated
    assert summary(truth) is True
    out = capsys.readouterr().out
    assert "11 conflicts flagged, 24 harmless differences ignored" in out
    assert "DIFFERS" not in out

    detail(next(b for b in truth["bundles"] if b["id"] == "B07-dob-year-conflict"), "en", "scholarship_application")
    shown = capsys.readouterr().out
    assert "The years are 15 years apart." in shown
    assert "DISPUTED: 12 March 1982 | 12 March 1997" in shown
    assert "<left empty: documents disagree>" in shown
