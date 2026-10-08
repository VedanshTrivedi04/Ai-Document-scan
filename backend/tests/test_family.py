"""Families (app/api/families.py) and the checks across their members
(app/services/family_checks.py). All people and documents are made up."""
import json
import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select

import app.services.translation_service as translation_service
from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.document import Document, DocumentProcessingStatus
from app.models.family import Family, FamilyMember
from app.models.user import UserRole
from app.services import family_checks
from app.services.family_checks import MemberDetails, run_family_checks
from app.services.identity_documents import IDENTITY_SCHEMA
from app.services.person_profile import ProfileDocument, build_profile
from scripts.generate_identity_bundles import generate
from tests.conftest import _headers_for, _make_user
from tests.test_identity_comparison import _bundle
from tests.test_profile_and_forms import _profile_of

GROUND_TRUTH = Path(__file__).resolve().parents[2] / "sample-documents" / "identity-bundles" / "ground_truth.json"


@pytest.fixture(scope="module")
def ground_truth(tmp_path_factory):
    if GROUND_TRUTH.exists():
        return json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    return generate(tmp_path_factory.mktemp("identity-bundles"))


@pytest.fixture(autouse=True)
def no_translation_service(monkeypatch):
    monkeypatch.setattr(settings, "google_translate_api_key", None)
    translation_service.clear_memory_cache()


def _with_documents(profile):
    return {**profile, "document_count": 2}


def _f01(ground_truth, *, child_overrides=None, child_name="Tanvi Agrawal"):
    """The synthetic family F01 as the head would have entered it."""
    child_bundle = _bundle(ground_truth, "F01-child")
    return [
        MemberDetails("head", "Mahesh Chand Agrawal", "self", date(1975, 2, 8),
                      _with_documents(_profile_of(_bundle(ground_truth, "F01-head")))),
        MemberDetails("spouse", "Sarla Agrawal", "spouse", date(1978, 6, 19),
                      _with_documents(_profile_of(_bundle(ground_truth, "F01-spouse")))),
        MemberDetails("child", child_name, "daughter", date(2004, 9, 27),
                      _with_documents(_profile_of(child_bundle, overrides=child_overrides))),
    ]


def _results(checks):
    return {(c["member_id"], c["check"]): c for c in checks}


# --- the checks -----------------------------------------------------------

def test_a_consistent_family_passes_every_check_that_can_be_made(ground_truth):
    results = _results(run_family_checks(_f01(ground_truth)))
    assert {key: c["result"] for key, c in results.items()} == {
        ("head", "member_identity"): "match",
        ("spouse", "member_identity"): "match",
        ("spouse", "shared_address"): "match",
        ("child", "member_identity"): "match",
        ("child", "shared_address"): "match",
        # The child's own documents disagree on the father's name, so this
        # is not judged until that conflict is settled.
        ("child", "parent_name"): "not_checked",
        ("child", "birth_order"): "match",
    }
    assert results[("spouse", "shared_address")]["summary"] == (
        "Sarla Agrawal has the same address as the head of the family."
    )
    assert all(c["severity"] == "info" for c in results.values())


def test_parent_name_is_judged_once_the_childs_own_conflict_is_settled(ground_truth):
    # The reviewer decides the marksheet is right: it names Mukesh, not the head Mahesh.
    wrong = _results(run_family_checks(
        _f01(ground_truth, child_overrides={"parent_or_spouse_name": {"document_id": "02-marksheet.pdf"}})
    ))[("child", "parent_name")]
    assert (wrong["result"], wrong["severity"]) == ("conflict", "critical")
    assert wrong["summary"] == (
        "Tanvi Agrawal: the documents name Mukesh Chand Agrawal as the parent. This does not match the "
        "parents entered in this family (Mahesh Chand Agrawal / Sarla Agrawal)."
    )
    # The identity card is right: it names the head.
    right = _results(run_family_checks(
        _f01(ground_truth, child_overrides={"parent_or_spouse_name": {"document_id": "01-national-id-card.pdf"}})
    ))[("child", "parent_name")]
    assert right["result"] == "match"
    assert "Mahesh Chand Agrawal" in right["summary"]


def _member(member_id, name, relation, born=None, **fields):
    """A member whose single document states `fields`."""
    document = ProfileDocument(f"{member_id}-doc", "id.pdf", "national_id_card", {
        name_: (value if isinstance(value, dict) else {"value": value, "latin": value})
        for name_, value in fields.items()
    })
    profile = {**build_profile([document], []), "document_count": 1} if fields else None
    return MemberDetails(member_id, name, relation, born, profile)


HOME = {"value": "12 Sarafa Bazar, Ratlam - 457001", "latin": "12 Sarafa Bazar, Ratlam - 457001", "postal_code": "457001"}


@pytest.mark.parametrize(
    "entered, expected",
    [
        ("Tanvi Agrawal", ("match", "info")),
        ("T. Agrawal", ("match", "info")),            # initials are the same person
        ("Tanvee Agrawal", ("match", "info")),        # spelling of the same sound
        ("Tanvi Agarwal", ("conflict", "medium")),    # one-letter slip: a person decides
        ("Pooja Nair", ("conflict", "critical")),     # someone else's documents
    ],
)
def test_documents_are_checked_against_the_name_the_head_entered(entered, expected):
    member = _member("m", entered, "daughter", full_name="Tanvi Agrawal")
    check = _results(run_family_checks([member]))[("m", "member_identity")]
    assert (check["result"], check["severity"]) == expected


def test_entered_date_of_birth_is_checked_too():
    member = _member("m", "Tanvi Agrawal", "daughter", date(2005, 9, 27),
                     full_name="Tanvi Agrawal", date_of_birth={"value": "2004-09-27"})
    check = _results(run_family_checks([member]))[("m", "member_identity")]
    assert (check["result"], check["severity"]) == ("conflict", "high")
    assert check["summary"] == (
        "Tanvi Agrawal: the documents show the date of birth 27 September 2004, but 27 September 2005 "
        "was entered for this family member."
    )


def test_a_member_living_elsewhere_is_flagged_and_formatting_is_not():
    head = _member("h", "Mahesh Agrawal", "self", full_name="Mahesh Agrawal", address=HOME)
    same = _member("a", "Sarla Agrawal", "spouse", full_name="Sarla Agrawal",
                   address={"value": "12, Sarafa Bazaar, Ratlam", "latin": "12, Sarafa Bazaar, Ratlam", "postal_code": None})
    away = _member("b", "Rohan Agrawal", "son", full_name="Rohan Agrawal",
                   address={"value": "4 Hostel Road, Pune - 411001", "latin": "4 Hostel Road, Pune - 411001",
                            "postal_code": "411001"})
    results = _results(run_family_checks([head, same, away]))
    assert results[("a", "shared_address")]["result"] == "match"
    away_check = results[("b", "shared_address")]
    assert (away_check["result"], away_check["severity"]) == ("conflict", "medium")
    assert "4 Hostel Road, Pune - 411001" in away_check["summary"]


def test_dates_of_birth_must_be_in_order():
    head = _member("h", "Mahesh Agrawal", "self", full_name="Mahesh Agrawal", date_of_birth={"value": "1975-02-08"})
    child = _member("c", "Tanvi Agrawal", "daughter", full_name="Tanvi Agrawal", date_of_birth={"value": "1970-01-01"})
    father = _member("f", "Ratan Lal Agrawal", "father", full_name="Ratan Lal Agrawal",
                     date_of_birth={"value": "1980-05-05"})
    results = _results(run_family_checks([head, child, father]))
    born_first = results[("c", "birth_order")]
    assert (born_first["result"], born_first["severity"]) == ("conflict", "high")
    assert born_first["summary"] == (
        "Tanvi Agrawal (1 January 1970) is recorded as born before or on the same day as the parent "
        "Mahesh Agrawal (8 February 1975)."
    )
    assert results[("f", "birth_order")]["result"] == "conflict"
    assert "born after" in results[("f", "birth_order")]["summary"]


def test_the_heads_own_father_is_checked_against_the_member_entered_as_father():
    head = _member("h", "Mahesh Chand Agrawal", "self", full_name="Mahesh Chand Agrawal",
                   parent_or_spouse_name="R. L. Agrawal")
    father = _member("f", "Ratan Lal Agrawal", "father")
    assert _results(run_family_checks([head, father]))[("h", "parent_name")]["result"] == "match"
    stranger = _member("f", "Gopal Das Mittal", "father")
    assert _results(run_family_checks([head, stranger]))[("h", "parent_name")]["result"] == "conflict"


def test_a_member_without_documents_is_not_judged():
    checks = run_family_checks([_member("m", "Tanvi Agrawal", "daughter")])
    assert [(c["check"], c["result"]) for c in checks] == [("member_identity", "not_checked")]
    assert checks[0]["summary"] == "Tanvi Agrawal: no documents have been checked yet."
    assert family_checks.count_results(checks) == {"match": 0, "conflict": 0, "not_checked": 1}


def test_check_messages_are_available_in_hindi(ground_truth):
    for text in family_checks.check_strings():
        assert text in translation_service.BUILT_IN_CATALOGS["hi"]
    results = _results(run_family_checks(_f01(ground_truth), "hi"))
    spouse = results[("spouse", "shared_address")]
    assert spouse["label"] == "पता"
    assert spouse["summary"] == "Sarla Agrawal का पता परिवार के मुखिया के पते जैसा ही है।"


# --- API ------------------------------------------------------------------

def _attach_bundle(db_session, case_id, bundle):
    """Give a case the processed documents of a ground-truth bundle."""
    case = db_session.get(Case, uuid.UUID(case_id))
    for document in bundle["documents"]:
        db_session.add(Document(
            case_id=case.id, uploaded_by_user_id=case.submitted_by_user_id, original_filename=document["file"],
            blob_storage_path=f"https://fake.blob.core.windows.net/documents/{uuid.uuid4().hex}",
            file_hash=uuid.uuid4().hex * 2, content_type="application/pdf", file_size_bytes=100,
            document_type=document["document_type"], processing_status=DocumentProcessingStatus.complete,
            extracted_fields={"schema": IDENTITY_SCHEMA, "identity_fields": document["identity_fields"],
                              "core_fields": {}},
        ))
    db_session.commit()


def _add(client, headers, name, relation, born=None):
    response = client.post(
        "/family/members", headers=headers, json={"full_name": name, "relation": relation, "date_of_birth": born}
    )
    assert response.status_code == 201, response.text
    return next(m for m in response.json()["members"] if m["full_name"] == " ".join(name.split()))


def test_a_user_sets_up_a_family_and_becomes_its_head(client, plain_headers, plain_user, db_session):
    assert client.get("/family", headers=plain_headers).json() is None

    created = client.post("/family", headers=plain_headers, json={"head_date_of_birth": "1975-02-08"})
    assert created.status_code == 201, created.text
    family = created.json()
    assert family["head_user_id"] == str(plain_user.id)
    assert family["name"].endswith(" family")
    (head,) = family["members"]
    assert head["is_head"] and head["relation"] == "self" and head["relation_label"] == "Head of family"
    assert head["date_of_birth"] == "1975-02-08"
    assert head["cases"] == [] and head["profile_ready"] is None

    assert client.post("/family", headers=plain_headers, json={}).status_code == 409
    assert client.get("/family", headers=plain_headers).json()["id"] == family["id"]
    assert db_session.execute(
        select(AuditLog.event_type).where(AuditLog.event_type == "family_created")
    ).scalar_one() == "family_created"


def test_the_head_adds_corrects_and_removes_members(client, plain_headers):
    assert client.post(
        "/family/members", headers=plain_headers, json={"full_name": "Sarla Agrawal", "relation": "spouse"}
    ).status_code == 404  # no family yet
    client.post("/family", headers=plain_headers, json={"name": "Agrawal family"})

    spouse = _add(client, plain_headers, "  Sarla   Agrawal ", "spouse", "1978-06-19")
    assert spouse["full_name"] == "Sarla Agrawal" and spouse["relation_label"] == "Spouse"
    child = _add(client, plain_headers, "Tanvi Agrawal", "daughter")

    for bad in ({"full_name": "   ", "relation": "son"}, {"full_name": "X", "relation": "self"},
                {"full_name": "X", "relation": "cousin"}):
        assert client.post("/family/members", headers=plain_headers, json=bad).status_code == 422

    updated = client.patch(
        f"/family/members/{child['id']}", headers=plain_headers, json={"date_of_birth": "2004-09-27"}
    ).json()
    patched = next(m for m in updated["members"] if m["id"] == child["id"])
    assert (patched["full_name"], patched["relation"], patched["date_of_birth"]) == (
        "Tanvi Agrawal", "daughter", "2004-09-27"
    )

    head = next(m for m in updated["members"] if m["is_head"])
    assert client.patch(
        f"/family/members/{head['id']}", headers=plain_headers, json={"relation": "son"}
    ).status_code == 409
    assert client.delete(f"/family/members/{head['id']}", headers=plain_headers).status_code == 409
    assert client.delete(f"/family/members/{uuid.uuid4()}", headers=plain_headers).status_code == 404

    after = client.delete(f"/family/members/{spouse['id']}", headers=plain_headers).json()
    assert [m["full_name"] for m in after["members"] if not m["is_head"]] == ["Tanvi Agrawal"]


def test_a_family_is_private_to_its_head_and_readable_by_reviewers(
    client, plain_headers, reviewer_headers, platform_admin_headers, db_session
):
    family = client.post("/family", headers=plain_headers, json={}).json()
    other = _headers_for(_make_user(db_session, "neighbour@example.com", UserRole.user, "Nosy Neighbour"))

    assert client.get(f"/families/{family['id']}", headers=plain_headers).status_code == 200
    assert client.get(f"/families/{family['id']}", headers=reviewer_headers).json()["id"] == family["id"]
    assert client.get(f"/families/{family['id']}", headers=other).status_code == 404
    # The neighbour has no family of their own to change, and cannot reach this one.
    assert client.get("/family", headers=other).json() is None
    member_id = family["members"][0]["id"]
    assert client.patch(f"/family/members/{member_id}", headers=other, json={"full_name": "X"}).status_code == 404
    # Reviewers read; they do not manage someone else's family.
    assert client.patch(
        f"/family/members/{member_id}", headers=reviewer_headers, json={"full_name": "X"}
    ).status_code == 404
    assert client.get("/family", headers=platform_admin_headers).status_code == 403
    assert client.get("/family").status_code == 401


def test_only_the_head_can_submit_a_bundle_for_a_member(client, plain_headers, reviewer_headers, db_session):
    family = client.post("/family", headers=plain_headers, json={}).json()
    child = _add(client, plain_headers, "Tanvi Agrawal", "daughter")
    payload = {"case_type": "identity_verification", "family_member_id": child["id"]}

    created = client.post("/cases", headers=plain_headers, json=payload)
    assert created.status_code == 201, created.text
    detail = client.get(f"/cases/{created.json()['id']}", headers=plain_headers).json()
    assert detail["family_member"] == {
        "id": child["id"], "family_id": family["id"], "full_name": "Tanvi Agrawal", "relation": "daughter",
    }

    assert client.post("/cases", headers=reviewer_headers, json=payload).status_code == 422
    assert client.post(
        "/cases", headers=plain_headers, json={"case_type": "vendor_invoice", "family_member_id": child["id"]}
    ).status_code == 422
    assert client.post(
        "/cases", headers=plain_headers,
        json={"case_type": "identity_verification", "family_member_id": str(uuid.uuid4())},
    ).status_code == 422
    # A case without a member still works as before.
    plain = client.post("/cases", headers=plain_headers, json={"case_type": "identity_verification"})
    assert plain.status_code == 201
    assert client.get(f"/cases/{plain.json()['id']}", headers=plain_headers).json()["family_member"] is None

    # A member with documents submitted can no longer be removed.
    assert client.delete(f"/family/members/{child['id']}", headers=plain_headers).status_code == 409
    assert db_session.get(FamilyMember, uuid.UUID(child["id"])) is not None


def test_family_view_brings_members_cases_and_checks_together(client, plain_headers, db_session, ground_truth):
    family = client.post("/family", headers=plain_headers, json={"head_date_of_birth": "1975-02-08"}).json()
    head = family["members"][0]
    client.patch(f"/family/members/{head['id']}", headers=plain_headers, json={"full_name": "Mahesh Chand Agrawal"})
    spouse = _add(client, plain_headers, "Sarla Agrawal", "spouse", "1978-06-19")
    child = _add(client, plain_headers, "Tanvi Agrawal", "daughter", "2004-09-27")
    grandfather = _add(client, plain_headers, "Ratan Lal Agrawal", "father")

    for member, bundle_id in ((head, "F01-head"), (spouse, "F01-spouse"), (child, "F01-child")):
        case = client.post(
            "/cases", headers=plain_headers,
            json={"case_type": "identity_verification", "family_member_id": member["id"]},
        ).json()
        _attach_bundle(db_session, case["id"], _bundle(ground_truth, bundle_id))

    view = client.get("/family?lang=hi", headers=plain_headers).json()
    assert view["language"] == "hi"
    members = {m["full_name"]: m for m in view["members"]}
    assert members["Mahesh Chand Agrawal"]["profile_ready"] is True
    assert members["Ratan Lal Agrawal"]["profile_ready"] is None
    (child_case,) = members["Tanvi Agrawal"]["cases"]
    assert child_case["document_count"] == 2 and child_case["case_number"].startswith("CASE-")
    assert members["Tanvi Agrawal"]["latest_case_id"] == child_case["id"]

    results = {(c["member_name"], c["check"]): c for c in view["checks"]}
    assert results[("Sarla Agrawal", "shared_address")]["result"] == "match"
    assert results[("Sarla Agrawal", "shared_address")]["summary"].endswith("पते जैसा ही है।")
    assert results[("Tanvi Agrawal", "birth_order")]["result"] == "match"
    # The head's identity card names Ratan Lal Agrawal as father; so does the family.
    assert results[("Mahesh Chand Agrawal", "parent_name")]["result"] == "match"
    assert results[("Ratan Lal Agrawal", "member_identity")]["result"] == "not_checked"
    assert view["check_counts"]["conflict"] == 0
    assert sum(view["check_counts"].values()) == len(view["checks"])
    assert db_session.execute(select(Family)).scalars().one().name == family["name"]
