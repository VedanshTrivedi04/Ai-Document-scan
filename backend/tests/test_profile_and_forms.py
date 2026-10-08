"""The verified profile of an identity case and forms pre-filled from it
(app/services/person_profile.py, form_templates.py, app/api/profiles.py).
All people and documents are made up."""
import json
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select

import app.services.translation_service as translation_service
from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.case import Case, CaseStatus, CaseType
from app.models.cross_document_finding import CrossDocumentFinding
from app.models.document import Document
from app.services import form_templates
from app.services.identity_comparison import BundleDocument, find_identity_contradictions
from app.services.person_profile import FindingState, ProfileDocument, build_profile
from scripts.generate_identity_bundles import generate
from tests.test_finding_review_and_i18n import _seed_findings
from tests.test_identity_comparison import _bundle

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


def _profile_of(bundle, *, resolution="open", overrides=None):
    """The profile of a ground-truth bundle, with every finding the
    contradiction check produces in the given state (harmless ones are
    always `no_issue`)."""
    documents = [
        ProfileDocument(d["file"], d["file"], d["document_type"], d["identity_fields"]) for d in bundle["documents"]
    ]
    found = find_identity_contradictions(
        [BundleDocument(d.id, d.filename, d.document_type, d.identity_fields) for d in documents]
    )
    states = [
        FindingState(
            f["field_name"], tuple(f["document_ids"]),
            "no_issue" if f["classification"] == "harmless_variant" else resolution,
        )
        for f in found
    ]
    return build_profile(documents, states, overrides)


def _by_field(profile):
    return {f["field"]: f for f in profile["fields"]}


# --- the profile ----------------------------------------------------------

def test_clean_bundle_gives_a_complete_profile_with_its_sources(ground_truth):
    profile = _profile_of(_bundle(ground_truth, "B01-clean"))
    fields = _by_field(profile)
    assert profile["ready"] is True
    assert profile["counts"] == {"agreed": 6, "chosen": 0, "conflict": 0, "missing": 0}
    assert fields["full_name"]["value"] == "Kavita Rao Deshmukh"
    assert fields["full_name"]["document_type"] == "national_id_card"
    assert fields["date_of_birth"]["value"] == "1990-03-12"
    assert fields["date_of_birth"]["display_value"] == "12 March 1990"
    assert fields["annual_income"]["value"] == 120000.0
    assert fields["annual_income"]["document_type"] == "income_certificate"
    assert fields["gender"]["display_value"] == "Female"
    assert profile["postal_code"] == "452001"
    assert {k: v["value"] for k, v in profile["id_numbers"].items()} == {
        "national_id_card": "XXXX XXXX 1107", "tax_id_card": "QWKPD4417L",
    }


def test_harmless_variants_do_not_block_and_the_fullest_name_is_used(ground_truth):
    fields = _by_field(_profile_of(_bundle(ground_truth, "B03-initials-and-order")))
    # "A. P. Sharma" and "Shri Sharma Ajay Prakash" are the same person; the
    # identity card's full wording is the one a form should carry.
    assert fields["full_name"]["status"] == "agreed"
    assert fields["full_name"]["value"] == "Ajay Prakash Sharma"
    assert fields["parent_or_spouse_name"]["value"] == "Om Prakash Sharma"
    assert len(fields["full_name"]["candidates"]) == 1
    assert len(fields["full_name"]["candidates"][0]["document_ids"]) == 3


def test_address_prefers_the_address_proof_wording(ground_truth):
    fields = _by_field(_profile_of(_bundle(ground_truth, "B02-spelling-variants")))
    assert fields["address"]["status"] == "agreed"
    assert fields["address"]["document_type"] == "address_proof"


def test_an_open_conflict_gives_no_value_and_lists_the_candidates(ground_truth):
    profile = _profile_of(_bundle(ground_truth, "B07-dob-year-conflict"))
    dob = _by_field(profile)["date_of_birth"]
    assert profile["ready"] is False
    assert dob["status"] == "conflict"
    assert dob["value"] is None and dob["document_id"] is None
    assert [c["display_value"] for c in dob["candidates"]] == ["12 March 1982", "12 March 1997"]
    # One document against one: nothing to suggest.
    assert dob["suggested_document_id"] is None and dob["documents_to_correct"] == []
    # The details nobody disputes are still available.
    assert _by_field(profile)["full_name"]["status"] == "agreed"


def test_when_most_documents_agree_the_odd_one_is_named_for_correction(ground_truth):
    dob = _by_field(_profile_of(_bundle(ground_truth, "H01-hiring-candidate")))["date_of_birth"]
    assert dob["status"] == "conflict"
    assert dob["candidates"][0]["display_value"] == "17 May 1998"
    assert len(dob["candidates"][0]["document_ids"]) == 2
    assert dob["suggested_document_id"] == "01-national-id-card.pdf"
    assert dob["documents_to_correct"] == ["03-degree-certificate.pdf"]


def test_a_confirmed_conflict_still_blocks_and_a_cleared_one_does_not(ground_truth):
    bundle = _bundle(ground_truth, "B07-dob-year-conflict")
    assert _by_field(_profile_of(bundle, resolution="conflict_confirmed"))["date_of_birth"]["status"] == "conflict"
    cleared = _by_field(_profile_of(bundle, resolution="no_issue"))["date_of_birth"]
    assert cleared["status"] == "agreed"
    assert cleared["document_type"] == "national_id_card"


def test_a_reviewers_choice_settles_a_disputed_detail(ground_truth):
    bundle = _bundle(ground_truth, "B07-dob-year-conflict")
    profile = _profile_of(bundle, overrides={"date_of_birth": {"document_id": "03-voter-id-card.pdf"}})
    dob = _by_field(profile)["date_of_birth"]
    assert (dob["status"], dob["value"], dob["document_type"]) == ("chosen", "1997-03-12", "voter_id_card")
    assert profile["ready"] is True
    # A choice pointing at a document that is no longer there is ignored.
    stale = _profile_of(bundle, overrides={"date_of_birth": {"document_id": "gone.pdf"}})
    assert _by_field(stale)["date_of_birth"]["status"] == "conflict"


def _doc(doc_id, document_type, **fields):
    return ProfileDocument(doc_id, f"{doc_id}.pdf", document_type, fields)


def test_income_is_taken_from_the_most_recent_certificate():
    documents = [
        _doc("old", "income_certificate", annual_income={"value": 120000.0, "currency": "INR"},
             issue_date={"value": "2024-02-01"}),
        _doc("new", "income_certificate", annual_income={"value": 120000.0, "currency": "INR"},
             issue_date={"value": "2026-02-01"}),
    ]
    assert _by_field(build_profile(documents, []))["annual_income"]["document_id"] == "new"


def test_a_disputed_identity_number_is_left_out():
    documents = [
        _doc("a", "national_id_card", id_number={"value": "1111 2222 3333"}),
        _doc("b", "national_id_card", id_number={"value": "1111 2222 9999"}),
        _doc("c", "tax_id_card", id_number={"value": "ABCDE1234F"}),
    ]
    disputed = [FindingState("id_number", ("a", "b"), "open")]
    assert set(build_profile(documents, disputed)["id_numbers"]) == {"tax_id_card"}
    assert set(build_profile(documents, [])["id_numbers"]) == {"national_id_card", "tax_id_card"}


def test_no_documents_gives_an_empty_profile():
    profile = build_profile([], [])
    assert profile["counts"] == {"agreed": 0, "chosen": 0, "conflict": 0, "missing": 6}
    assert profile["id_numbers"] == {} and profile["postal_code"] is None


# --- forms ----------------------------------------------------------------

def _filled(result):
    return {f["key"]: f for f in result["fields"]}


def test_form_is_filled_from_an_agreed_profile(ground_truth):
    profile = _profile_of(_bundle(ground_truth, "B01-clean"))
    result = form_templates.prefill(
        form_templates.get_form("scholarship_application"), profile, today=date(2026, 10, 9)
    )
    fields = _filled(result)
    assert result["ready"] is True
    assert result["counts"] == {"filled": 9, "needs_attention": 0, "to_fill": 3}
    assert fields["applicant_name"]["value"] == "Kavita Rao Deshmukh"
    assert fields["applicant_name"]["source_document_type"] == "national_id_card"
    assert fields["date_of_birth"]["value"] == "1990-03-12"
    assert fields["age"]["value"] == 36
    assert fields["gender"]["value"] == "female" and fields["gender"]["display_value"] == "Female"
    assert [o["value"] for o in fields["gender"]["options"]] == ["male", "female", "other"]
    assert fields["postal_code"]["value"] == "452001"
    assert fields["identity_number"]["value"] == "XXXX XXXX 1107"
    assert fields["annual_income"]["value"] == 120000.0
    assert fields["annual_income"]["display_value"] == "Rs. 1,20,000"
    # What the documents cannot know is left for the applicant.
    assert fields["bank_account"]["status"] == "to_fill" and fields["bank_account"]["note"] is None
    assert fields["bank_account"]["prefilled"] is False


def test_age_counts_whole_years_only():
    profile = build_profile([_doc("a", "national_id_card", date_of_birth={"value": "2000-10-10"})], [])
    form = form_templates.get_form("scholarship_application")
    assert _filled(form_templates.prefill(form, profile, today=date(2026, 10, 9)))["age"]["value"] == 25
    assert _filled(form_templates.prefill(form, profile, today=date(2026, 10, 10)))["age"]["value"] == 26


def test_a_disputed_detail_is_left_empty_with_a_reason(ground_truth):
    profile = _profile_of(_bundle(ground_truth, "B07-dob-year-conflict"))
    result = form_templates.prefill(form_templates.get_form("scholarship_application"), profile)
    fields = _filled(result)
    assert result["ready"] is False
    for key in ("date_of_birth", "age"):
        assert fields[key]["status"] == "needs_attention"
        assert fields[key]["value"] is None
        assert "do not agree" in fields[key]["note"]
    assert fields["applicant_name"]["status"] == "filled"


def test_a_detail_no_document_states_is_left_for_the_applicant(ground_truth):
    # No income certificate in this bundle.
    profile = _profile_of(_bundle(ground_truth, "B06-dob-minor-typo"), resolution="no_issue")
    income = _filled(form_templates.prefill(form_templates.get_form("income_certificate_application"), profile))[
        "annual_income"
    ]
    assert income["status"] == "to_fill"
    assert income["note"] == "Not found on your documents. Please enter it."


def test_forms_are_available_in_hindi_without_a_translation_service(ground_truth):
    for text in form_templates.form_strings():
        assert text in translation_service.BUILT_IN_CATALOGS["hi"], text
    profile = _profile_of(_bundle(ground_truth, "B07-dob-year-conflict"))
    result = form_templates.prefill(form_templates.get_form("income_certificate_application"), profile, language="hi")
    fields = _filled(result)
    assert result["form"]["title"] == "आय प्रमाण पत्र के लिए आवेदन"
    assert fields["applicant_name"]["label"] == "पूरा नाम"
    assert fields["gender"]["display_value"] == "पुरुष"
    assert fields["date_of_birth"]["note"].startswith("आपके दस्तावेज़ों में")
    # The person's own details are not translated.
    assert fields["applicant_name"]["value"] == "Vikram Singh Rathore"


def test_every_form_field_source_resolves(ground_truth):
    profile = _profile_of(_bundle(ground_truth, "B01-clean"))
    for form in form_templates.FORMS:
        result = form_templates.prefill(form, profile)
        assert len(result["fields"]) == len(form.fields)
        assert sum(result["counts"].values()) == len(form.fields)


# --- API ------------------------------------------------------------------

def test_profile_endpoint_for_a_reviewer_and_for_others(client, reviewer_headers, plain_headers, db_session, ground_truth):
    case, _ = _seed_findings(db_session, ground_truth, "B07-dob-year-conflict")
    body = client.get(f"/cases/{case.id}/profile", headers=reviewer_headers).json()
    assert body["case_number"] == case.case_number
    assert body["document_count"] == 3
    assert body["ready"] is False
    assert _by_field(body)["date_of_birth"]["status"] == "conflict"
    assert _by_field(body)["full_name"]["value"] == "Vikram Singh Rathore"

    # Someone else's case does not exist for an applicant.
    assert client.get(f"/cases/{case.id}/profile", headers=plain_headers).status_code == 404
    assert client.get(f"/cases/{case.id}/profile").status_code == 401


def test_the_applicant_sees_the_profile_of_their_own_case(client, plain_headers, plain_user, db_session, ground_truth):
    case, _ = _seed_findings(db_session, ground_truth, "B01-clean")
    case.submitted_by_user_id = plain_user.id
    db_session.commit()
    body = client.get(f"/cases/{case.id}/profile", headers=plain_headers).json()
    assert body["ready"] is True


def test_an_invoice_case_has_no_profile(client, auth_headers):
    case_id = client.post("/cases", json={"case_type": "vendor_invoice"}, headers=auth_headers).json()["id"]
    response = client.get(f"/cases/{case_id}/profile", headers=auth_headers)
    assert response.status_code == 409
    assert "not a person's document bundle" in response.json()["detail"]
    assert client.get(f"/cases/{case_id}/forms/scholarship_application", headers=auth_headers).status_code == 409


def test_reviewer_chooses_the_right_document_and_can_take_it_back(
    client, reviewer_headers, reviewer_user, db_session, ground_truth
):
    case, _ = _seed_findings(db_session, ground_truth, "B07-dob-year-conflict")
    voter = db_session.execute(
        select(Document).where(Document.case_id == case.id, Document.document_type == "voter_id_card")
    ).scalar_one()
    url = f"/cases/{case.id}/profile/date_of_birth"

    chosen = client.put(url, headers=reviewer_headers, json={"document_id": str(voter.id)})
    assert chosen.status_code == 200, chosen.text
    dob = _by_field(chosen.json())["date_of_birth"]
    assert (dob["status"], dob["value"], dob["document_id"]) == ("chosen", "1997-03-12", str(voter.id))
    assert chosen.json()["ready"] is True

    # It is stored: a later read shows the same.
    again = client.get(f"/cases/{case.id}/profile", headers=reviewer_headers).json()
    assert _by_field(again)["date_of_birth"]["status"] == "chosen"

    event = db_session.execute(
        select(AuditLog).where(AuditLog.case_id == case.id, AuditLog.event_type == "profile_value_chosen")
    ).scalar_one()
    assert event.actor_user_id == reviewer_user.id
    assert event.event_data == {
        "field_name": "date_of_birth", "document_id": str(voter.id), "document_type": "voter_id_card",
        "actor_role": "Reviewer L1",
    }

    removed = client.put(url, headers=reviewer_headers, json={"document_id": None}).json()
    assert _by_field(removed)["date_of_birth"]["status"] == "conflict"


def test_choice_is_validated_and_restricted(client, reviewer_headers, plain_headers, db_session, ground_truth):
    case, _ = _seed_findings(db_session, ground_truth, "B07-dob-year-conflict")
    documents = db_session.execute(select(Document).where(Document.case_id == case.id)).scalars().all()
    income = next(d for d in documents if d.document_type == "income_certificate")
    card = next(d for d in documents if d.document_type == "national_id_card")
    url = f"/cases/{case.id}/profile/date_of_birth"

    assert client.put(url, headers=plain_headers, json={"document_id": str(card.id)}).status_code == 403
    # The income certificate states no date of birth.
    assert client.put(url, headers=reviewer_headers, json={"document_id": str(income.id)}).status_code == 422
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.put(url, headers=reviewer_headers, json={"document_id": missing}).status_code == 422
    assert client.put(
        f"/cases/{case.id}/profile/shoe_size", headers=reviewer_headers, json={"document_id": str(card.id)}
    ).status_code == 404
    assert client.put(
        f"/cases/{missing}/profile/date_of_birth", headers=reviewer_headers, json={"document_id": str(card.id)}
    ).status_code == 404

    case.status = CaseStatus.approved
    db_session.commit()
    assert client.put(url, headers=reviewer_headers, json={"document_id": str(card.id)}).status_code == 409
    db_session.expire_all()
    assert not db_session.get(Case, case.id).profile_overrides


def test_forms_are_listed_and_filtered_by_kind_of_case(client, auth_headers):
    assert client.get("/forms").status_code == 401
    everything = client.get("/forms", headers=auth_headers).json()
    assert [f["id"] for f in everything] == [
        "income_certificate_application", "scholarship_application", "domicile_certificate_application",
        "employee_joining_form",
    ]
    hiring = client.get("/forms?case_type=hiring_verification&lang=hi", headers=auth_headers).json()
    assert [f["id"] for f in hiring] == ["employee_joining_form"]
    assert hiring[0]["title"] == "कर्मचारी कार्यभार ग्रहण प्रपत्र"
    assert hiring[0]["field_count"] == 11 and hiring[0]["prefilled_field_count"] == 8
    assert hiring[0]["fields"][0] == {
        "key": "applicant_name", "label": "पूरा नाम", "type": "text", "required": True, "prefilled": True,
    }


def test_prefilled_form_endpoint_follows_the_profile(client, reviewer_headers, db_session, ground_truth):
    case, _ = _seed_findings(db_session, ground_truth, "B07-dob-year-conflict")
    url = f"/cases/{case.id}/forms/income_certificate_application"

    before = client.get(url, headers=reviewer_headers).json()
    assert before["case_number"] == case.case_number
    assert before["ready"] is False
    assert _filled(before)["date_of_birth"]["status"] == "needs_attention"
    assert _filled(before)["annual_income"]["value"] == 84000.0

    card = db_session.execute(
        select(Document).where(Document.case_id == case.id, Document.document_type == "national_id_card")
    ).scalar_one()
    client.put(f"/cases/{case.id}/profile/date_of_birth", headers=reviewer_headers, json={"document_id": str(card.id)})

    after = client.get(f"{url}?lang=hi", headers=reviewer_headers).json()
    assert after["ready"] is True and after["language"] == "hi"
    dob = _filled(after)["date_of_birth"]
    assert (dob["status"], dob["value"], dob["source_document_type"]) == ("filled", "1982-03-12", "national_id_card")
    assert dob["label"] == "जन्म तिथि"


def test_a_form_for_another_kind_of_case_is_not_found(client, reviewer_headers, db_session, ground_truth):
    case, _ = _seed_findings(db_session, ground_truth, "B01-clean")
    assert client.get(f"/cases/{case.id}/forms/employee_joining_form", headers=reviewer_headers).status_code == 404
    assert client.get(f"/cases/{case.id}/forms/no_such_form", headers=reviewer_headers).status_code == 404
    assert case.case_type == CaseType.identity_verification


def test_clearing_a_finding_fills_the_form(client, reviewer_headers, db_session, ground_truth):
    """Dismissing the conflict (the reviewer says it is not a problem) is
    enough for the detail to be used."""
    case, (finding,) = _seed_findings(db_session, ground_truth, "B06-dob-minor-typo")
    url = f"/cases/{case.id}/forms/domicile_certificate_application"
    assert _filled(client.get(url, headers=reviewer_headers).json())["date_of_birth"]["status"] == "needs_attention"
    client.patch(f"/cases/{case.id}/findings/{finding.id}", headers=reviewer_headers, json={"decision": "dismissed"})
    dob = _filled(client.get(url, headers=reviewer_headers).json())["date_of_birth"]
    assert (dob["status"], dob["value"]) == ("filled", "1995-08-15")
    assert db_session.get(CrossDocumentFinding, finding.id) is not None
