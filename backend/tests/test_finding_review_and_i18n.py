"""Per-finding review (app/api/findings.py) and messages in several languages
(app/services/identity_messages.py, translation_service.py, app/api/i18n.py).
Google Translation is never called for real: a fake stands in for it. All
people and documents are made up."""
import json
import re
from pathlib import Path

import pytest
from sqlalchemy import select

import app.services.translation_service as translation_service
from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.case import CaseStatus, CaseTier
from app.models.cross_document_finding import CrossDocumentFinding, finding_resolution
from app.models.document import Document
from app.services import identity_messages as messages
from app.services.identity_comparison import BundleDocument, find_identity_contradictions
from app.tasks.document_checks import run_cross_document_checks
from scripts.generate_identity_bundles import generate
from tests.test_identity_comparison import _bundle, _seed_bundle, task_session_factory  # noqa: F401

GROUND_TRUTH = Path(__file__).resolve().parents[2] / "sample-documents" / "identity-bundles" / "ground_truth.json"
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")


@pytest.fixture(scope="module")
def ground_truth(tmp_path_factory):
    if GROUND_TRUTH.exists():
        return json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    return generate(tmp_path_factory.mktemp("identity-bundles"))


@pytest.fixture(autouse=True)
def isolated_translation(monkeypatch):
    """No Google key, no Redis, an empty in-process cache."""
    monkeypatch.setattr(settings, "google_translate_api_key", None)
    monkeypatch.setattr(translation_service, "_from_redis", lambda language, texts: {})
    monkeypatch.setattr(translation_service, "_to_redis", lambda language, translated: None)
    translation_service.clear_memory_cache()
    yield
    translation_service.clear_memory_cache()


class FakeGoogle:
    """Stands in for the Cloud Translation endpoint: wraps each string in
    [lang] ... and records what it was sent."""

    def __init__(self, monkeypatch, *, mangle: str | None = None, fail: bool = False):
        self.requests: list[dict] = []
        self.mangle, self.fail = mangle, fail
        monkeypatch.setattr(settings, "google_translate_api_key", "test-key")
        monkeypatch.setattr(translation_service.httpx, "post", self._post)

    def _post(self, url, *, params, json, timeout):  # noqa: A002 - httpx's own name
        self.requests.append({"url": url, "params": params, **json})
        if self.fail:
            raise RuntimeError("network down")
        fake = self

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                out = []
                for q in json["q"]:
                    text = f"[{json['target']}] {q}"
                    if fake.mangle and fake.mangle in q:
                        text = text.replace("{", "(").replace("}", ")")
                    out.append({"translatedText": text})
                return {"data": {"translations": out}}

        return Response()

    @property
    def sent(self) -> list[str]:
        return [q for request in self.requests for q in request["q"]]


def _seed_findings(db_session, ground_truth, bundle_id):
    case = _seed_bundle(db_session, _bundle(ground_truth, bundle_id))
    documents = db_session.execute(select(Document).where(Document.case_id == case.id)).scalars().all()
    bundle_documents = [
        BundleDocument(str(d.id), d.original_filename, d.document_type, d.extracted_fields["identity_fields"])
        for d in sorted(documents, key=lambda d: d.original_filename)
    ]
    for finding in find_identity_contradictions(bundle_documents):
        db_session.add(CrossDocumentFinding(case_id=case.id, **finding))
    db_session.commit()
    findings = db_session.execute(
        select(CrossDocumentFinding).where(CrossDocumentFinding.case_id == case.id)
    ).scalars().all()
    return case, findings


# --- messages -------------------------------------------------------------

def test_hindi_catalog_covers_every_message_string_and_keeps_placeholders():
    hindi = translation_service.BUILT_IN_CATALOGS["hi"]
    for text in messages.catalog_strings():
        assert text in hindi, text
        assert sorted(PLACEHOLDER.findall(hindi[text])) == sorted(PLACEHOLDER.findall(text)), text
        assert hindi[text] != text


def _evidence(a, b, type_a="national_id_card", type_b="voter_id_card"):
    return [
        {"document_type": type_a, "document_filename": "a.pdf", "value": a, "distinguish_by_filename": type_a == type_b},
        {"document_type": type_b, "document_filename": "b.pdf", "value": b, "distinguish_by_filename": type_a == type_b},
    ]


def test_conflict_message_in_english_says_what_why_and_what_to_do():
    message = messages.build_message(
        "date_of_birth", "conflict", "date_year_difference", "high",
        _evidence("12 March 1982", "12 March 1997"), {"years_apart": 15},
    )
    assert message == {
        "language": "en",
        "field_label": "Date of birth",
        "severity_label": "Serious mismatch",
        "summary": "Date of birth does not match: 12 March 1982 on the identity card and 12 March 1997 "
                   "on the voter identity card.",
        "explanation": "The years are 15 years apart.",
        "action": "Check which document is correct and have the other one corrected.",
        "text": "Date of birth does not match: 12 March 1982 on the identity card and 12 March 1997 on the "
                "voter identity card. The years are 15 years apart. Check which document is correct and "
                "have the other one corrected.",
    }


def test_the_same_message_in_hindi_without_any_translation_service():
    message = messages.build_message(
        "date_of_birth", "conflict", "date_year_difference", "high",
        _evidence("12 March 1982", "12 March 1997"), {"years_apart": 15}, "hi",
    )
    assert message["language"] == "hi"
    assert message["field_label"] == "जन्म तिथि"
    assert message["severity_label"] == "गंभीर अंतर"
    assert message["summary"] == (
        "जन्म तिथि में अंतर है: पहचान पत्र पर 12 March 1982 और मतदाता पहचान पत्र पर 12 March 1997।"
    )
    assert message["explanation"] == "वर्षों में 15 साल का अंतर है।"
    assert message["action"] == "देखें कि कौन-सा दस्तावेज़ सही है और दूसरे को ठीक करवाएँ।"


def test_harmless_message_says_nothing_needs_doing():
    message = messages.build_message(
        "full_name", "harmless_variant", "initials", "info",
        _evidence("A. P. Sharma", "Ajay Prakash Sharma", "tax_id_card", "national_id_card"), None, "hi",
    )
    assert message["severity_label"] == "कोई समस्या नहीं"
    assert message["action"] == "कुछ करने की ज़रूरत नहीं है।"
    assert "A. P. Sharma" in message["summary"] and "Ajay Prakash Sharma" in message["summary"]


def test_two_documents_of_one_kind_are_named_by_file_and_numbers_are_filled_in():
    message = messages.build_message(
        "annual_income", "conflict", "income_difference", "critical",
        _evidence("Rs. 60,000", "Rs. 4,80,000", "income_certificate", "income_certificate"), {"ratio": 8.0}, "hi",
    )
    assert "आय प्रमाण पत्र (a.pdf)" in message["summary"]
    assert message["explanation"] == "बड़ी राशि छोटी राशि की 8 गुना है।"
    assert message["severity_label"] == "सुधार ज़रूरी है"


def test_every_reason_has_text_in_both_shipped_languages():
    for reason in {**messages.HARMLESS_REASONS, **messages.CONFLICT_REASONS}:
        classification = "harmless_variant" if reason in messages.HARMLESS_REASONS else "conflict"
        for language in ("en", "hi"):
            message = messages.build_message(
                "full_name", classification, reason, "medium", _evidence("A", "B"), None, language
            )
            assert all(message[key] for key in ("summary", "explanation", "action")), (reason, language)
            assert "{" not in message["text"], (reason, language)


# --- translation service --------------------------------------------------

def test_english_and_unknown_languages_pass_through():
    assert translation_service.translate(["Name"], "en") == ["Name"]
    assert translation_service.normalize_language("xx") == "en"
    assert translation_service.normalize_language("HI-in") == "hi"
    assert translation_service.translate(["Name"], "xx") == ["Name"]


def test_without_a_key_only_the_built_in_language_is_translated():
    assert translation_service.translate(["Name", "Open case"], "hi") == ["नाम", "Open case"]
    assert translation_service.translate(["Name"], "ta") == ["Name"]
    assert translation_service.language_source("hi") == "built_in"
    assert translation_service.language_source("ta") == "unavailable"
    assert translation_service.language_source("en") == "source"


def test_google_translates_what_the_catalog_lacks_and_each_string_only_once(monkeypatch):
    google = FakeGoogle(monkeypatch)
    assert translation_service.language_source("ta") == "google"

    assert translation_service.translate(["Open case", "Name"], "hi") == ["[hi] Open case", "नाम"]
    assert google.sent == ["Open case"]  # the built-in string was not sent

    translation_service.translate(["Open case"], "hi")
    assert len(google.requests) == 1  # cached

    request = google.requests[0]
    assert request["params"] == {"key": "test-key"}
    assert (request["source"], request["target"], request["format"]) == ("en", "hi", "html")


def test_placeholders_survive_translation_and_a_mangled_one_falls_back_to_english(monkeypatch):
    google = FakeGoogle(monkeypatch, mangle="{b}")
    kept, mangled = translation_service.translate(["Total: {a} items", "Compare {a} with {b}"], "ta")
    assert kept == "[ta] Total: {a} items"
    assert mangled == "Compare {a} with {b}"
    assert '<span translate="no">{a}</span>' in google.sent[0]


def test_a_failing_service_gives_english_and_is_not_cached(monkeypatch):
    google = FakeGoogle(monkeypatch, fail=True)
    assert translation_service.translate(["Open case"], "ta") == ["Open case"]
    google.fail = False
    # The service is left alone for a while after a failure...
    assert translation_service.translate(["Open case"], "ta") == ["Open case"]
    assert len(google.requests) == 1
    # ...and asked again once that pause is over.
    monkeypatch.setattr(translation_service, "_google_paused_until", 0.0)
    assert translation_service.translate(["Open case"], "ta") == ["[ta] Open case"]


def test_a_case_in_a_google_language_costs_one_translation_request(
    client, auth_headers, db_session, ground_truth, monkeypatch
):
    case, findings = _seed_findings(db_session, ground_truth, "H01-hiring-candidate")
    assert len(findings) == 7
    google = FakeGoogle(monkeypatch)
    body = client.get(f"/cases/{case.id}?lang=bn", headers=auth_headers).json()
    assert all(f["message"]["summary"].startswith("[bn] ") for f in body["cross_document_findings"])
    assert len(google.requests) == 1
    client.get(f"/cases/{case.id}?lang=bn", headers=auth_headers)
    assert len(google.requests) == 1
    assert "Nikhil" not in " ".join(google.sent)


def test_a_persons_details_are_never_sent_for_translation(monkeypatch):
    google = FakeGoogle(monkeypatch)
    message = messages.build_message(
        "full_name", "conflict", "different_name", "critical",
        _evidence("Rahul Verma", "Sanjay Singh", "national_id_card", "tax_id_card"), None, "ta",
    )
    assert "Rahul Verma" in message["summary"] and "Sanjay Singh" in message["summary"]
    assert message["summary"].startswith("[ta] ")
    sent = " ".join(google.sent)
    assert "Rahul" not in sent and "Sanjay" not in sent and "a.pdf" not in sent


# --- case detail in a language --------------------------------------------

def test_case_detail_returns_each_finding_in_the_requested_language(client, auth_headers, db_session, ground_truth):
    case, _ = _seed_findings(db_session, ground_truth, "B07-dob-year-conflict")

    hindi = client.get(f"/cases/{case.id}?lang=hi", headers=auth_headers).json()
    assert hindi["language"] == "hi"
    (finding,) = hindi["cross_document_findings"]
    assert finding["message"]["language"] == "hi"
    assert finding["message"]["explanation"] == "वर्षों में 15 साल का अंतर है।"
    assert "12 March 1982" in finding["message"]["summary"]
    # The stored description and the machine keys stay as they are.
    assert finding["description"].startswith("Date of birth does not match")
    assert finding["reason"] == "date_year_difference"

    english = client.get(f"/cases/{case.id}", headers=auth_headers).json()
    assert english["language"] == "en"
    assert english["cross_document_findings"][0]["message"]["severity_label"] == "Serious mismatch"
    assert client.get(f"/cases/{case.id}?lang=zz", headers=auth_headers).json()["language"] == "en"


# --- reviewing a finding --------------------------------------------------

def test_resolution_follows_the_decision():
    assert finding_resolution("conflict", "pending") == "open"
    assert finding_resolution("conflict", "accepted") == "conflict_confirmed"
    assert finding_resolution("conflict", "dismissed") == "no_issue"
    assert finding_resolution("harmless_variant", "pending") == "no_issue"
    assert finding_resolution("harmless_variant", "accepted") == "no_issue"
    assert finding_resolution("harmless_variant", "dismissed") == "conflict_confirmed"
    assert finding_resolution(None, "pending") == "open"  # an invoice finding


def test_reviewer_accepts_and_dismisses_findings(client, reviewer_headers, reviewer_user, db_session, ground_truth):
    case, findings = _seed_findings(db_session, ground_truth, "B11-gender-and-address")
    gender = next(f for f in findings if f.field_name == "gender")
    address = next(f for f in findings if f.field_name == "address")

    before = client.get(f"/cases/{case.id}", headers=reviewer_headers).json()
    assert before["finding_counts"] == {"open": 2, "conflict_confirmed": 0, "no_issue": 0, "ignored_as_harmless": 0}

    accepted = client.patch(
        f"/cases/{case.id}/findings/{gender.id}", headers=reviewer_headers,
        json={"decision": "accepted", "note": "  Card clearly says Female.  "},
    )
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["finding"]["review_status"] == "accepted"
    assert body["finding"]["resolution"] == "conflict_confirmed"
    assert body["finding"]["review_note"] == "Card clearly says Female."
    assert body["finding"]["reviewed_by_name"] == "Rita Reviewer"
    assert body["finding"]["reviewed_at"] is not None
    assert body["finding_counts"] == {"open": 1, "conflict_confirmed": 1, "no_issue": 0, "ignored_as_harmless": 0}

    dismissed = client.patch(
        f"/cases/{case.id}/findings/{address.id}?lang=hi", headers=reviewer_headers, json={"decision": "dismissed"}
    ).json()
    assert dismissed["finding"]["resolution"] == "no_issue"
    assert dismissed["finding"]["message"]["language"] == "hi"
    assert dismissed["finding_counts"] == {"open": 0, "conflict_confirmed": 1, "no_issue": 1, "ignored_as_harmless": 0}

    after = client.get(f"/cases/{case.id}", headers=reviewer_headers).json()
    assert {f["field_name"]: f["review_status"] for f in after["cross_document_findings"]} == {
        "gender": "accepted", "address": "dismissed",
    }

    events = db_session.execute(
        select(AuditLog).where(AuditLog.case_id == case.id, AuditLog.event_type == "finding_reviewed")
        .order_by(AuditLog.created_at)
    ).scalars().all()
    assert [e.event_data["decision"] for e in events] == ["accepted", "dismissed"]
    assert events[0].actor_user_id == reviewer_user.id
    assert events[0].event_data["previous_decision"] == "pending"
    assert events[0].event_data["note"] == "Card clearly says Female."
    assert events[0].event_data["actor_role"] == "Reviewer L1"
    assert events[0].event_data["field_name"] == "gender"


def test_a_decision_can_be_undone(client, reviewer_headers, db_session, ground_truth):
    case, (finding,) = _seed_findings(db_session, ground_truth, "B07-dob-year-conflict")
    url = f"/cases/{case.id}/findings/{finding.id}"
    client.patch(url, headers=reviewer_headers, json={"decision": "accepted", "note": "Confirmed."})
    undone = client.patch(url, headers=reviewer_headers, json={"decision": "pending"}).json()["finding"]
    assert (undone["review_status"], undone["resolution"]) == ("pending", "open")
    assert undone["review_note"] is None and undone["reviewed_by_name"] is None and undone["reviewed_at"] is None


def test_dismissing_a_harmless_variant_marks_it_as_a_real_conflict(client, reviewer_headers, db_session, ground_truth):
    case, findings = _seed_findings(db_session, ground_truth, "B04-name-abbreviation")
    start = client.get(f"/cases/{case.id}", headers=reviewer_headers).json()["finding_counts"]
    assert start == {"open": 0, "conflict_confirmed": 0, "no_issue": 5, "ignored_as_harmless": 5}

    body = client.patch(
        f"/cases/{case.id}/findings/{findings[0].id}", headers=reviewer_headers, json={"decision": "dismissed"}
    ).json()
    assert body["finding"]["resolution"] == "conflict_confirmed"
    assert body["finding_counts"] == {"open": 0, "conflict_confirmed": 1, "no_issue": 4, "ignored_as_harmless": 4}


def test_only_reviewers_of_the_company_may_decide(
    client, plain_headers, reviewer_headers, platform_admin_headers, db_session, ground_truth
):
    case, (finding,) = _seed_findings(db_session, ground_truth, "B07-dob-year-conflict")
    url = f"/cases/{case.id}/findings/{finding.id}"
    assert client.patch(url, headers=plain_headers, json={"decision": "accepted"}).status_code == 403
    assert client.patch(url, headers=platform_admin_headers, json={"decision": "accepted"}).status_code == 403
    assert client.patch(url, json={"decision": "accepted"}).status_code == 401
    assert client.patch(url, headers=reviewer_headers, json={"decision": "maybe"}).status_code == 422
    db_session.expire_all()
    assert db_session.get(CrossDocumentFinding, finding.id).review_status == "pending"


def test_unknown_case_or_finding_is_a_404(client, reviewer_headers, db_session, ground_truth):
    case, (finding,) = _seed_findings(db_session, ground_truth, "B07-dob-year-conflict")
    other_case, _ = _seed_findings(db_session, ground_truth, "B06-dob-minor-typo")
    payload = {"decision": "accepted"}
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.patch(f"/cases/{missing}/findings/{finding.id}", headers=reviewer_headers, json=payload).status_code == 404
    assert client.patch(f"/cases/{case.id}/findings/{missing}", headers=reviewer_headers, json=payload).status_code == 404
    # A finding of another case is not reachable through this one.
    assert client.patch(
        f"/cases/{other_case.id}/findings/{finding.id}", headers=reviewer_headers, json=payload
    ).status_code == 404


def test_findings_of_a_decided_case_are_frozen(client, reviewer_headers, db_session, ground_truth):
    case, (finding,) = _seed_findings(db_session, ground_truth, "B07-dob-year-conflict")
    case.status = CaseStatus.rejected
    db_session.commit()
    response = client.patch(
        f"/cases/{case.id}/findings/{finding.id}", headers=reviewer_headers, json={"decision": "dismissed"}
    )
    assert response.status_code == 409
    assert "already rejected" in response.json()["detail"]


def test_l1_reviewer_cannot_decide_on_an_escalated_case(client, reviewer_headers, auth_headers, db_session, ground_truth):
    case, (finding,) = _seed_findings(db_session, ground_truth, "B07-dob-year-conflict")
    case.assigned_tier = CaseTier.l2
    db_session.commit()
    url = f"/cases/{case.id}/findings/{finding.id}"
    assert client.patch(url, headers=reviewer_headers, json={"decision": "accepted"}).status_code == 403
    assert client.patch(url, headers=auth_headers, json={"decision": "accepted"}).status_code == 200  # reviewer_l2


def test_decisions_survive_a_rerun_of_the_check(task_session_factory, ground_truth):  # noqa: F811
    session = task_session_factory()
    case_id = _seed_bundle(session, _bundle(ground_truth, "B11-gender-and-address")).id
    session.close()
    company = str(task_session_factory.company_id)
    run_cross_document_checks(str(case_id), company)

    session = task_session_factory()
    gender = session.execute(
        select(CrossDocumentFinding).where(
            CrossDocumentFinding.case_id == case_id, CrossDocumentFinding.field_name == "gender"
        )
    ).scalar_one()
    gender.review_status, gender.review_note = "dismissed", "Clerical error on the voter card."
    session.commit()
    session.close()

    run_cross_document_checks(str(case_id), company)

    session = task_session_factory()
    try:
        rows = session.execute(
            select(CrossDocumentFinding).where(CrossDocumentFinding.case_id == case_id)
        ).scalars().all()
        assert {r.field_name: (r.review_status, r.review_note) for r in rows} == {
            "gender": ("dismissed", "Clerical error on the voter card."),
            "address": ("pending", None),
        }
    finally:
        session.close()


# --- i18n endpoints -------------------------------------------------------

def test_languages_are_listed_with_their_availability(client, monkeypatch):
    languages = {item["code"]: item for item in client.get("/i18n/languages").json()}
    assert len(languages) >= 12
    assert languages["en"]["source"] == "source" and languages["en"]["available"]
    assert languages["hi"] == {
        "code": "hi", "name": "Hindi", "native_name": "हिन्दी", "direction": "ltr",
        "source": "built_in", "available": True,
    }
    assert languages["ta"]["available"] is False
    assert languages["ur"]["direction"] == "rtl"

    FakeGoogle(monkeypatch)
    with_key = {item["code"]: item for item in client.get("/i18n/languages").json()}
    assert with_key["ta"]["source"] == "google" and with_key["ta"]["available"]


def test_catalog_gives_the_labels_keyed_by_machine_keys(client, auth_headers):
    assert client.get("/i18n/catalog?lang=hi").status_code == 401
    catalog = client.get("/i18n/catalog?lang=hi", headers=auth_headers).json()
    assert catalog["language"] == "hi" and catalog["direction"] == "ltr"
    assert catalog["fields"]["date_of_birth"] == "जन्म तिथि"
    assert catalog["documents"]["income_certificate"] == "आय प्रमाण पत्र"
    assert catalog["severities"]["critical"] == "सुधार ज़रूरी है"
    assert catalog["reasons"]["initials"] == "एक दस्तावेज़ में उसी नाम के केवल शुरुआती अक्षर लिखे हैं।"
    assert catalog["actions"]["partial_name"] == "ऐसा दस्तावेज़ अपलोड करें जिसमें पूरा नाम लिखा हो।"
    assert catalog["no_action"] == "कुछ करने की ज़रूरत नहीं है।"
    english = client.get("/i18n/catalog", headers=auth_headers).json()
    assert english["fields"]["date_of_birth"] == "Date of birth"


def test_interface_strings_are_translated_through_the_server(client, auth_headers, monkeypatch):
    payload = {"language": "mr", "texts": ["My cases", "Upload documents", "My cases"]}
    assert client.post("/i18n/translate", json=payload).status_code == 401

    without_key = client.post("/i18n/translate", headers=auth_headers, json=payload).json()
    assert without_key == {
        "language": "mr",
        "translations": {"My cases": "My cases", "Upload documents": "Upload documents"},
        "complete": False,
    }

    google = FakeGoogle(monkeypatch)
    with_key = client.post("/i18n/translate", headers=auth_headers, json=payload).json()
    assert with_key["translations"] == {"My cases": "[mr] My cases", "Upload documents": "[mr] Upload documents"}
    assert with_key["complete"] is True
    assert google.sent == ["My cases", "Upload documents"]


def test_translate_refuses_oversized_requests(client, auth_headers):
    too_many = {"language": "hi", "texts": [f"text {i}" for i in range(301)]}
    assert client.post("/i18n/translate", headers=auth_headers, json=too_many).status_code == 422
    too_long = {"language": "hi", "texts": ["x" * 501]}
    assert client.post("/i18n/translate", headers=auth_headers, json=too_long).status_code == 422
