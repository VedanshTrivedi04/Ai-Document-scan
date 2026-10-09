"""The identity contradiction check (app/services/identity_comparison.py):
harmless variants are recognised by a named reason, real conflicts are
flagged with a severity, and the synthetic bundles come out exactly as their
ground truth says. Every name and address here is made up."""
import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.tasks.document_checks as document_checks_module
from app.models import Base
from app.models.audit_log import AuditLog
from app.models.case import Case, CaseStatus, CaseType
from app.models.cross_document_finding import CrossDocumentFinding, FindingSeverity
from app.models.document import Document, DocumentProcessingStatus
from app.models.user import User, UserRole
from app.services.identity_comparison import (
    BundleDocument,
    compare_addresses,
    compare_dates,
    compare_gender,
    compare_id_numbers,
    compare_income,
    compare_names,
    find_identity_contradictions,
    sound_key,
)
from app.services.identity_documents import IDENTITY_SCHEMA
from app.tasks.document_checks import run_cross_document_checks
from scripts.generate_identity_bundles import generate
from tests.conftest import tenant_task_factory

GROUND_TRUTH = Path(__file__).resolve().parents[2] / "sample-documents" / "identity-bundles" / "ground_truth.json"


def _name(text: str, latin: str | None = "same") -> dict:
    return {"value": text, "latin": text if latin == "same" else latin}


def _verdict(v) -> tuple[str, str, str]:
    return (v.classification, v.reason, v.severity.value)


# --- names ----------------------------------------------------------------

HARMLESS_NAMES = [
    ("Lakshmi Narayanan", "Laxmi Narayanan", "spelling_variant"),
    ("Sunita Choudhary", "Suneeta Chowdhary", "spelling_variant"),
    ("Vijay Kumar", "Vijai Kumar", "spelling_variant"),
    ("Pooja Nair", "Puja Nair", "spelling_variant"),
    ("Sunitha Rao", "Sunita Rao", "spelling_variant"),
    ("Shweta Tiwari", "Sweta Tiwary", "spelling_variant"),
    ("K. Suresh", "Kavitha Suresh", "initials"),
    ("A. P. Sharma", "Ajay Prakash Sharma", "initials"),
    ("A. P. Sharma", "Shri Sharma Ajay Prakash", "initials"),
    ("Mohd. Asif Khan", "Mohammad Asif Khan", "abbreviation"),
    ("Md Asif Khan", "Mohd. Asif Khan", "abbreviation"),
    ("Mohammed Asif", "Mohd Asif", "abbreviation"),
    ("Ram Kr Singh", "Ram Kumar Singh", "abbreviation"),
    ("Dr. Anil Gupta", "Anil Gupta", "honorific_or_word_order"),
    ("Verma Rahul", "Rahul Verma", "honorific_or_word_order"),
    ("Smt. Sarla Agrawal", "Agrawal Sarla", "honorific_or_word_order"),
    ("Nikhil Joshi", "Nikhil Madhav Joshi", "extra_middle_name"),
    ("Nikhil Joshi", "Nikhil M. Joshi", "extra_middle_name"),
]


@pytest.mark.parametrize("a, b, reason", HARMLESS_NAMES)
def test_harmless_name_variants_are_recognised_by_reason(a, b, reason):
    assert _verdict(compare_names(_name(a), _name(b))) == ("harmless_variant", reason, "info")
    assert _verdict(compare_names(_name(b), _name(a))) == ("harmless_variant", reason, "info")


@pytest.mark.parametrize(
    "a, b",
    [("RAHUL VERMA", "Rahul Verma"), ("Rahul  Verma", "Rahul Verma"), ("Rahul Verma.", "rahul verma")],
)
def test_case_spacing_and_punctuation_are_not_differences(a, b):
    assert compare_names(_name(a), _name(b)).classification == "match"


# Similar spellings that are different people. A similarity score would pass
# most of these; none has a naming convention that explains the difference.
DIFFERENT_PEOPLE = [
    ("Rahul Verma", "Sanjay Singh"),
    ("Rahul Verma", "Rohit Verma"),
    ("Mahesh Chand Agrawal", "Mukesh Chand Agrawal"),
    ("Rina Shah", "Rani Shah"),
    ("Seema Jain", "Reema Jain"),
    ("Ramesh Gupta", "Rajesh Gupta"),
    ("Amit Kumar", "Sumit Kumar"),
    ("Priya Singh", "Priya Sinha"),
    ("Anil Kumar Gupta", "Anil Prasad Gupta"),
]


@pytest.mark.parametrize("a, b", DIFFERENT_PEOPLE)
def test_different_names_are_critical_however_similar_they_look(a, b):
    assert _verdict(compare_names(_name(a), _name(b))) == ("conflict", "different_name", "critical")


@pytest.mark.parametrize(
    "a, b", [("Sunil Agrawal", "Sunil Agarwal"), ("Rahul Verma", "Rahul Varma"), ("Kiran Patel", "Karan Patel")]
)
def test_a_one_letter_slip_is_flagged_for_a_person_to_decide(a, b):
    assert _verdict(compare_names(_name(a), _name(b))) == ("conflict", "possible_spelling_error", "medium")


@pytest.mark.parametrize("a, b", [("Kiran", "Kiran Patel"), ("Patel", "Kiran Patel")])
def test_a_single_shared_part_is_not_enough_to_call_two_names_the_same(a, b):
    assert _verdict(compare_names(_name(a), _name(b))) == ("conflict", "partial_name", "low")


def test_sound_key_does_not_merge_different_names():
    assert sound_key("choudhary") == sound_key("chowdhary") == sound_key("chaudhari")
    assert sound_key("lakshmi") == sound_key("laxmi")
    assert sound_key("mahesh") != sound_key("mukesh")
    assert sound_key("rina") != sound_key("rani")
    assert sound_key("agrawal") != sound_key("agroal")


def test_hindi_name_matches_its_english_form_through_the_latin_reading():
    hindi = {"value": "रमेश कुमार शर्मा", "latin": "Ramesh Kumar Sharma"}
    assert _verdict(compare_names(hindi, _name("Ramesh Kumar Sharma"))) == (
        "harmless_variant", "transliteration", "info"
    )
    # A transliteration is approximate: a trailing vowel does not make a new name.
    loose = {"value": "रमेश कुमार शर्मा", "latin": "Ramesha Kumar Sharma"}
    assert compare_names(loose, _name("Ramesh Kumar Sharma")).reason == "transliteration"
    # ...but a different person is still a different person.
    assert _verdict(compare_names(hindi, _name("Suresh Kumar Sharma"))) == (
        "conflict", "different_name", "critical"
    )


def test_two_hindi_documents_agree_without_a_finding():
    hindi = {"value": "रमेश कुमार शर्मा", "latin": "Ramesh Kumar Sharma"}
    assert compare_names(hindi, dict(hindi)).classification == "match"


def test_name_in_another_script_without_a_latin_reading_is_not_judged():
    assert compare_names({"value": "रमेश कुमार", "latin": None}, _name("Ramesh Kumar")) is None
    assert compare_names({"value": None, "latin": None}, _name("Ramesh Kumar")) is None


# --- dates, gender, income, identity number -------------------------------

def _date(value):
    return {"value": value, "raw_text": value}


@pytest.mark.parametrize(
    "a, b, expected",
    [
        ("1995-08-15", "1995-08-15", ("match", "same", "info")),
        ("1995-08-15", "1995-08-16", ("conflict", "date_minor_difference", "medium")),
        ("1995-08-15", "1995-09-15", ("conflict", "date_minor_difference", "medium")),
        ("1995-07-05", "1995-05-07", ("conflict", "date_day_month_swapped", "low")),
        ("1995-08-15", "1995-11-23", ("conflict", "date_difference", "high")),
        ("1982-03-12", "1997-03-12", ("conflict", "date_year_difference", "high")),
        ("1998-05-17", "1999-05-17", ("conflict", "date_year_difference", "high")),
    ],
)
def test_dates(a, b, expected):
    assert _verdict(compare_dates(_date(a), _date(b))) == expected


def test_a_missing_or_unreadable_date_is_not_compared():
    assert compare_dates(_date(None), _date("1995-08-15")) is None
    assert compare_dates(_date("15/08/1995"), _date("1995-08-15")) is None


def test_gender():
    assert compare_gender({"value": "female"}, {"value": "female"}).classification == "match"
    assert _verdict(compare_gender({"value": "female"}, {"value": "male"})) == (
        "conflict", "gender_difference", "high"
    )
    assert compare_gender({"value": None}, {"value": "male"}) is None


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (120000, 120000, ("match", "same", "info")),
        (120000, 120500, ("match", "same", "info")),
        (100000, 115000, ("conflict", "income_difference", "medium")),
        (100000, 150000, ("conflict", "income_difference", "high")),
        (60000, 480000, ("conflict", "income_difference", "critical")),
    ],
)
def test_income(a, b, expected):
    first, second = {"value": a, "currency": "INR"}, {"value": b, "currency": "INR"}
    assert _verdict(compare_income(first, second)) == expected
    assert _verdict(compare_income(second, first)) == expected


def test_income_in_two_currencies_is_not_compared():
    assert compare_income({"value": 1000, "currency": "USD"}, {"value": 80000, "currency": "INR"}) is None


def test_identity_numbers_respect_masking():
    assert compare_id_numbers({"value": "XXXX XXXX 4321"}, {"value": "5567 8812 4321"}).classification == "match"
    assert compare_id_numbers({"value": "5567-8812-4321"}, {"value": "5567 8812 4321"}).classification == "match"
    assert _verdict(compare_id_numbers({"value": "XXXX XXXX 4321"}, {"value": "5567 8812 9999"})) == (
        "conflict", "id_number_difference", "high"
    )


def _doc(doc_id, document_type, **fields) -> BundleDocument:
    return BundleDocument(
        id=doc_id, filename=f"{doc_id}.pdf", document_type=document_type,
        identity_fields={name: (value if isinstance(value, dict) else {"value": value}) for name, value in fields.items()},
    )


def test_identity_numbers_are_compared_only_between_cards_of_the_same_kind():
    card_a = _doc("a", "national_id_card", id_number="1111 2222 3333")
    card_b = _doc("b", "national_id_card", id_number="1111 2222 9999")
    tax = _doc("c", "tax_id_card", id_number="ABCDE1234F")
    cert_a = _doc("d", "income_certificate", id_number="IC/2026/1")
    cert_b = _doc("e", "income_certificate", id_number="IC/2025/2")
    assert [f["reason"] for f in find_identity_contradictions([card_a, card_b])] == ["id_number_difference"]
    assert find_identity_contradictions([card_a, tax]) == []
    assert find_identity_contradictions([cert_a, cert_b]) == []


# --- addresses ------------------------------------------------------------

def _address(text, postal_code=None, latin="same"):
    return {"value": text, "latin": text if latin == "same" else latin, "postal_code": postal_code}


@pytest.mark.parametrize(
    "a, b",
    [
        ("45 Mahatma Gandhi Road, Near Bus Stand, Ujjain, Madhya Pradesh", "45 M.G. Rd, Nr Bus Stand, Ujjain, MP"),
        ("5 Narmada Colony, Khargone", "House No. 5, Narmada Colony, Near Temple, Khargone, MP"),
        ("12 Sarafa Bazar, Ratlam", "12 Sarafa Bazaar, Ratlam"),
        ("Flat 201, MG Road, Indore", "Flat 201, M.G. Road, Indore"),
    ],
)
def test_address_written_differently_is_harmless(a, b):
    assert _verdict(compare_addresses(_address(a), _address(b))) == (
        "harmless_variant", "address_formatting", "info"
    )


@pytest.mark.parametrize(
    "a, b, postal_a, postal_b, expected",
    [
        ("5 Narmada Colony, Khargone", "5 Narmada Colony, Khandwa", None, None,
         ("conflict", "address_locality_difference", "medium")),
        ("5 Narmada Colony, Khargone", "5 Narmada Colony, Khargone", "451001", "450001",
         ("conflict", "address_locality_difference", "medium")),
        ("Flat 201, MG Road, Indore", "Flat 201, Nehru Road, Indore", None, None,
         ("conflict", "address_locality_difference", "medium")),
        ("5 Narmada Colony, Khargone", "7 Narmada Colony, Khargone", None, None,
         ("conflict", "address_difference", "low")),
    ],
)
def test_address_conflicts(a, b, postal_a, postal_b, expected):
    assert _verdict(compare_addresses(_address(a, postal_a), _address(b, postal_b))) == expected


def test_same_address_is_a_match_and_postal_code_is_read_from_the_text():
    same = "22 Tilak Path, Sector 4, Indore - 452001"
    assert compare_addresses(_address(same), _address(same)).classification == "match"
    other = "22 Tilak Path, Sector 4, Indore - 452010"
    assert compare_addresses(_address(same), _address(other)).reason == "address_locality_difference"


def test_hindi_address_matches_its_english_form():
    hindi = _address("18 गांधी चौक, देवास, मध्य प्रदेश - 455001", "455001", latin="18 Gandhi Chauk, Dewas, Madhya Pradesh - 455001")
    english = _address("18 Gandhi Chowk, Dewas, Madhya Pradesh - 455001", "455001")
    assert _verdict(compare_addresses(hindi, english)) == ("harmless_variant", "transliteration", "info")


# --- the synthetic bundles ------------------------------------------------

@pytest.fixture(scope="module")
def ground_truth(tmp_path_factory):
    if GROUND_TRUTH.exists():
        return json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    return generate(tmp_path_factory.mktemp("identity-bundles"))


def _bundle_documents(bundle) -> list[BundleDocument]:
    return [
        BundleDocument(id=d["file"], filename=d["file"], document_type=d["document_type"],
                       identity_fields=d["identity_fields"])
        for d in bundle["documents"]
    ]


def test_every_bundle_gives_exactly_its_expected_findings(ground_truth):
    """Nothing missed and nothing extra, per bundle: the conflicts found and
    the harmless variants ignored, each for the stated reason."""
    assert len(ground_truth["bundles"]) >= 15
    for bundle in ground_truth["bundles"]:
        found = {
            (f["field_name"], tuple(f["document_ids"]), f["classification"], f["reason"], f["severity"].value)
            for f in find_identity_contradictions(_bundle_documents(bundle))
        }
        expected = {
            (e["field"], tuple(e["documents"]), e["classification"], e["reason"], e["severity"])
            for e in bundle["expected_findings"]
        }
        assert found == expected, bundle["id"]


def test_clean_bundles_produce_nothing_and_harmless_bundles_no_conflict(ground_truth):
    for bundle in ground_truth["bundles"]:
        findings = find_identity_contradictions(_bundle_documents(bundle))
        if bundle["kind"] == "clean":
            assert findings == [], bundle["id"]
        if bundle["kind"] == "harmless":
            assert {f["classification"] for f in findings} == {"harmless_variant"}, bundle["id"]
            assert {f["severity"] for f in findings} == {FindingSeverity.info}


def _bundle(ground_truth, bundle_id):
    return next(b for b in ground_truth["bundles"] if b["id"] == bundle_id)


def test_findings_read_as_plain_sentences(ground_truth):
    conflict = find_identity_contradictions(_bundle_documents(_bundle(ground_truth, "B07-dob-year-conflict")))[0]
    assert conflict["description"] == (
        "Date of birth does not match: 12 March 1982 on the identity card and 12 March 1997 on the "
        "voter identity card. The years are 15 years apart."
    )
    harmless = find_identity_contradictions(_bundle_documents(_bundle(ground_truth, "B04-name-abbreviation")))[0]
    assert harmless["description"] == (
        "Name is written differently: Mohammad Asif Khan on the identity card and Mohd. Asif Khan on the "
        "tax identity card. One document uses a common short form of the same name. No action is needed."
    )
    # Two documents of one kind are told apart by file name.
    income = find_identity_contradictions(_bundle_documents(_bundle(ground_truth, "B10-income-conflict")))[0]
    assert "income certificate (02-income-certificate.pdf)" in income["description"]
    assert "8 times" in income["description"]


def test_each_finding_carries_what_both_documents_show(ground_truth):
    finding = find_identity_contradictions(_bundle_documents(_bundle(ground_truth, "B11-gender-and-address")))[0]
    assert finding["finding_type"] == "identity_consistency"
    first, second = finding["evidence"]
    assert (first["value"], second["value"]) == ("Female", "Male")
    assert (first["document_type"], second["document_type"]) == ("national_id_card", "voter_id_card")
    assert finding["document_ids"] == [first["document_id"], second["document_id"]]


# --- the case-level task and the API --------------------------------------

@pytest.fixture()
def task_session_factory(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    factory = tenant_task_factory(monkeypatch, engine)
    monkeypatch.setattr(document_checks_module, "SessionLocal", factory)
    return factory


def _box(y: float) -> dict:
    return {"page": 1, "x": 0.4, "y": y, "width": 0.3, "height": 0.03}


def _seed_bundle(session, bundle, case_type=CaseType.identity_verification) -> Case:
    user = User(
        email=f"applicant-{uuid.uuid4().hex[:6]}@example.com", hashed_password="not-a-real-hash",
        role=UserRole.user, is_active=True,
    )
    session.add(user)
    session.flush()
    case = Case(
        case_number=f"CASE-{uuid.uuid4().hex[:8].upper()}", case_type=case_type,
        submitted_by_user_id=user.id, status=CaseStatus.submitted,
    )
    session.add(case)
    session.flush()
    for document in bundle["documents"]:
        fields = json.loads(json.dumps(document["identity_fields"]))
        for index, field in enumerate(fields.values()):
            if field["value"] is not None:
                field["bounding_box"] = _box(0.2 + index * 0.06)
        session.add(Document(
            case_id=case.id, uploaded_by_user_id=user.id, original_filename=document["file"],
            blob_storage_path=f"https://fake.blob.core.windows.net/documents/{uuid.uuid4().hex}",
            file_hash=uuid.uuid4().hex * 2, content_type="application/pdf", file_size_bytes=100,
            document_type=document["document_type"], processing_status=DocumentProcessingStatus.complete,
            extracted_fields={"schema": IDENTITY_SCHEMA, "identity_fields": fields, "core_fields": {}},
        ))
    session.commit()
    return case


def test_task_stores_the_findings_of_an_identity_case(task_session_factory, ground_truth):
    session = task_session_factory()
    case = _seed_bundle(session, _bundle(ground_truth, "B11-gender-and-address"))
    case_id = case.id
    session.close()
    company = str(task_session_factory.company_id)

    run_cross_document_checks(str(case_id), company)
    run_cross_document_checks(str(case_id), company)  # a re-run replaces, never duplicates

    session = task_session_factory()
    try:
        rows = session.execute(
            select(CrossDocumentFinding).where(CrossDocumentFinding.case_id == case_id)
        ).scalars().all()
        assert {(r.field_name, r.classification, r.reason, r.severity) for r in rows} == {
            ("gender", "conflict", "gender_difference", FindingSeverity.high),
            ("address", "conflict", "address_locality_difference", FindingSeverity.medium),
        }
        gender = next(r for r in rows if r.field_name == "gender")
        assert gender.finding_type == "identity_consistency"
        assert [e["value"] for e in gender.evidence] == ["Female", "Male"]
        assert all(e["bounding_box"]["page"] == 1 for e in gender.evidence)
        assert sorted(gender.document_ids) == sorted(e["document_id"] for e in gender.evidence)

        event_data = session.execute(
            select(AuditLog.event_data)
            .where(AuditLog.case_id == case_id, AuditLog.event_type == "cross_document_check_completed")
            .limit(1)
        ).scalar_one()
        assert event_data == {"finding_count": 2, "conflict_count": 2}
    finally:
        session.close()


def test_task_keeps_harmless_variants_as_info(task_session_factory, ground_truth):
    session = task_session_factory()
    case_id = _seed_bundle(session, _bundle(ground_truth, "B04-name-abbreviation")).id
    session.close()

    run_cross_document_checks(str(case_id), str(task_session_factory.company_id))

    session = task_session_factory()
    try:
        rows = session.execute(
            select(CrossDocumentFinding).where(CrossDocumentFinding.case_id == case_id)
        ).scalars().all()
        assert len(rows) == 5
        assert {r.classification for r in rows} == {"harmless_variant"}
        assert {r.severity for r in rows} == {FindingSeverity.info}
    finally:
        session.close()


def test_case_detail_returns_findings_with_evidence_and_highlight_regions(
    client, auth_headers, db_session, seeded_user, ground_truth
):
    case = _seed_bundle(db_session, _bundle(ground_truth, "B07-dob-year-conflict"))
    documents = db_session.execute(select(Document).where(Document.case_id == case.id)).scalars().all()
    bundle_documents = [
        BundleDocument(str(d.id), d.original_filename, d.document_type, d.extracted_fields["identity_fields"])
        for d in sorted(documents, key=lambda d: d.original_filename)
    ]
    for finding in find_identity_contradictions(bundle_documents):
        db_session.add(CrossDocumentFinding(case_id=case.id, **finding))
    db_session.commit()

    response = client.get(f"/cases/{case.id}", headers=auth_headers)
    assert response.status_code == 200, response.text
    (finding,) = response.json()["cross_document_findings"]
    assert finding["field_name"] == "date_of_birth"
    assert finding["classification"] == "conflict"
    assert finding["reason"] == "date_year_difference"
    assert finding["severity"] == "high"
    assert [e["value"] for e in finding["evidence"]] == ["12 March 1982", "12 March 1997"]
    assert len(finding["regions"]) == 2
    region = finding["regions"][0]
    assert region["label"] == "Date of birth"
    assert region["bounding_box"]["page"] == 1
    assert region["other"][0]["value"] == "12 March 1997"
    assert region["caption"] == "Date of birth: 12 March 1982 (other document: 12 March 1997)"


# ---- a value the reader was unsure of is not "a different person" ----------------

def _idoc(doc_id, document_type, **fields):
    return BundleDocument(doc_id, f"{doc_id}.jpg", document_type, fields)


def _unsure(text, latin="same"):
    field = _name(text, latin)
    field["uncertain"] = True
    return field


def test_a_misread_name_is_raised_for_checking_not_as_a_different_person():
    """Real case: a photographed passbook read as "SAMRIDDH] GUPTS" against
    "SAMRIDDHI GUPTA" on the PAN card."""
    sure = _idoc("pan", "tax_id_card", full_name=_name("SAMRIDDHI GUPTA", None))
    unsure = _idoc("passbook", "address_proof", full_name=_unsure("MISS. SAMRIDDH] GUPTS", None))
    (finding,) = [f for f in find_identity_contradictions([unsure, sure]) if f["field_name"] == "full_name"]
    assert finding["classification"] == "conflict"
    assert finding["reason"] == "unclear_reading" and finding["severity"] == FindingSeverity.medium
    assert finding["detail"]["was"] == "different_name" and finding["detail"]["was_severity"] == "critical"
    assert "could not be read clearly" in finding["description"]


def test_the_same_difference_on_values_that_were_read_with_confidence_stays_critical():
    one = _idoc("a", "national_id_card", full_name=_name("Rahul Verma", None))
    two = _idoc("b", "voter_id_card", full_name=_name("Rohit Verma", None))
    (finding,) = find_identity_contradictions([one, two])
    assert finding["reason"] == "different_name" and finding["severity"] == FindingSeverity.critical


def test_doubt_does_not_touch_harmless_variants_or_minor_differences():
    one = _idoc("a", "national_id_card", full_name=_unsure("A. P. Sharma", None))
    two = _idoc("b", "voter_id_card", full_name=_name("Ajay Prakash Sharma", None))
    (finding,) = find_identity_contradictions([one, two])
    assert finding["classification"] == "harmless_variant" and finding["reason"] == "initials"


def test_an_unsure_date_of_birth_year_difference_is_medium():
    one = _idoc("a", "national_id_card", date_of_birth={"value": "1982-03-12", "uncertain": True})
    two = _idoc("b", "voter_id_card", date_of_birth={"value": "1997-03-12"})
    (finding,) = find_identity_contradictions([one, two])
    assert finding["reason"] == "unclear_reading" and finding["severity"] == FindingSeverity.medium
