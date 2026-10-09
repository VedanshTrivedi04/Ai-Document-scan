"""The head managing the family's cases, and family comparison cases
(app/api/case_access.py, app/api/family_comparisons.py). All people and
documents are made up."""
import uuid

import pytest
from sqlalchemy import select

from app.models.case import Case, CaseStatus
from app.models.cross_document_finding import CrossDocumentFinding
from app.models.user import UserRole
from tests.conftest import _headers_for, _make_user
from tests.test_family import (  # noqa: F401 - fixtures and helpers shared with the family tests
    _add,
    _attach_bundle,
    ground_truth,
    no_translation_service,
)
from tests.test_identity_comparison import _bundle


def _login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def _member_by_name(view, name):
    return next(m for m in view["members"] if m["full_name"] == name)


@pytest.fixture()
def household(client, plain_headers, db_session, ground_truth):
    """The synthetic family F01: head, spouse and child, each with a bundle.
    The spouse has her own sign-in; the head submitted the others."""
    created = client.post("/family", headers=plain_headers, json={"head_date_of_birth": "1975-02-08"}).json()
    head = created["members"][0]
    client.patch(f"/family/members/{head['id']}", headers=plain_headers, json={"full_name": "Mahesh Chand Agrawal"})
    spouse_reply = client.post(
        "/family/members",
        headers=plain_headers,
        json={
            "full_name": "Sarla Agrawal", "relation": "spouse", "date_of_birth": "1978-06-19",
            "login": {"email": "sarla@example.com"},
        },
    ).json()
    spouse = _member_by_name(spouse_reply, "Sarla Agrawal")
    spouse_headers = {
        "Authorization": "Bearer "
        + _login(client, "sarla@example.com", spouse_reply["credentials"]["temporary_password"]).json()["access_token"]
    }
    child = _add(client, plain_headers, "Tanvi Agrawal", "daughter", "2004-09-27")

    cases = {}
    for key, member, bundle_id, headers in (
        ("head", head, "F01-head", plain_headers),
        ("spouse", spouse, "F01-spouse", spouse_headers),
        ("child", child, "F01-child", plain_headers),
    ):
        body = {"case_type": "identity_verification", "family_member_id": member["id"]}
        case = client.post("/cases", headers=headers, json=body).json()
        _attach_bundle(db_session, case["id"], _bundle(ground_truth, bundle_id))
        cases[key] = case["id"]
    return {
        "family": created, "head": head, "spouse": spouse, "child": child, "cases": cases,
        "spouse_headers": spouse_headers,
    }


# --- Phase B: the head manages members' cases ------------------------------

def test_the_head_sees_and_manages_a_members_own_case_but_other_members_do_not(
    client, plain_headers, household, db_session
):
    cases = household["cases"]
    stranger = _headers_for(_make_user(db_session, "stranger@example.com", UserRole.user, "Some Stranger"))
    spouse_headers = household["spouse_headers"]

    spouses_case = client.get(f"/cases/{cases['spouse']}", headers=plain_headers)
    assert spouses_case.status_code == 200, spouses_case.text
    assert spouses_case.json()["can_manage"] is True
    assert client.get(f"/cases/{cases['spouse']}/profile", headers=plain_headers).status_code == 200

    # The spouse sees her own case, but she does not manage it: the head does.
    own = client.get(f"/cases/{cases['spouse']}", headers=spouse_headers).json()
    assert own["can_manage"] is False
    # She cannot see the head's or the child's case.
    assert client.get(f"/cases/{cases['head']}", headers=spouse_headers).status_code == 404
    assert client.get(f"/cases/{cases['child']}", headers=spouse_headers).status_code == 404
    # A stranger sees none.
    for case_id in cases.values():
        assert client.get(f"/cases/{case_id}", headers=stranger).status_code == 404


def test_case_lists_follow_the_same_visibility(client, plain_headers, household, db_session):
    cases = household["cases"]
    head_list = {c["id"] for c in client.get("/cases", headers=plain_headers).json()}
    assert set(cases.values()) <= head_list
    assert {c["id"] for c in client.get("/cases", headers=household["spouse_headers"]).json()} == {cases["spouse"]}
    stranger = _headers_for(_make_user(db_session, "stranger@example.com", UserRole.user, "Some Stranger"))
    assert client.get("/cases", headers=stranger).json() == []


def test_the_head_settles_a_members_conflict_and_the_member_cannot(client, plain_headers, db_session, ground_truth):
    client.post("/family", headers=plain_headers, json={})
    reply = client.post(
        "/family/members",
        headers=plain_headers,
        json={"full_name": "Asha Rao", "relation": "other", "login": {"email": "asha@example.com"}},
    ).json()
    asha = _member_by_name(reply, "Asha Rao")
    asha_headers = {
        "Authorization": "Bearer "
        + _login(client, "asha@example.com", reply["credentials"]["temporary_password"]).json()["access_token"]
    }
    case_id = client.post(
        "/cases", headers=asha_headers, json={"case_type": "identity_verification"}
    ).json()["id"]
    assert str(db_session.get(Case, uuid.UUID(case_id)).family_member_id) == asha["id"]
    _attach_bundle(db_session, case_id, _bundle(ground_truth, "B07-dob-year-conflict"))

    documents = client.get(f"/cases/{case_id}", headers=plain_headers).json()["documents"]
    first = next(d for d in documents if d["original_filename"].startswith("01-"))

    refused = client.put(
        f"/cases/{case_id}/profile/date_of_birth", headers=asha_headers, json={"document_id": first["id"]}
    )
    assert refused.status_code == 403
    chosen = client.put(
        f"/cases/{case_id}/profile/date_of_birth", headers=plain_headers, json={"document_id": first["id"]}
    )
    assert chosen.status_code == 200, chosen.text


def test_the_head_reviews_findings_of_a_members_case_and_a_member_cannot(
    client, plain_headers, household, db_session
):
    case_id = uuid.UUID(household["cases"]["child"])
    finding = CrossDocumentFinding(
        company_id=db_session.get(Case, case_id).company_id, case_id=case_id, field_name="address",
        finding_type="identity_consistency", description="x", document_ids=[], classification="conflict",
        reason="address_difference",
    )
    finding.severity = "low"
    db_session.add(finding)
    db_session.commit()
    url = f"/cases/{case_id}/findings/{finding.id}"

    assert client.patch(url, headers=plain_headers, json={"decision": "dismissed"}).status_code == 200
    assert client.patch(url, headers=household["spouse_headers"], json={"decision": "accepted"}).status_code == 403
    stranger = _headers_for(_make_user(db_session, "stranger@example.com", UserRole.user, "Some Stranger"))
    assert client.patch(url, headers=stranger, json={"decision": "accepted"}).status_code == 403


def test_the_family_view_lists_each_cases_documents(client, plain_headers, household):
    view = client.get("/family", headers=plain_headers).json()
    (case,) = _member_by_name(view, "Tanvi Agrawal")["cases"]
    assert [d["filename"] for d in case["documents"]]
    assert {"id", "filename", "document_type", "processing_status"} <= set(case["documents"][0])


# --- Phase C: family comparison cases --------------------------------------

def _compare(client, headers, member_ids, lang="en"):
    return client.post(f"/family/comparisons?lang={lang}", headers=headers, json={"member_ids": member_ids})


def test_a_consistent_family_compares_clean(client, plain_headers, household):
    response = _compare(client, plain_headers, [household["spouse"]["id"], household["child"]["id"]])
    assert response.status_code == 201, response.text
    view = response.json()
    assert view["case_number"].startswith("CASE-")
    assert [m["full_name"] for m in view["members"]][0] == "Mahesh Chand Agrawal"  # the head is always in
    assert {m["full_name"] for m in view["members"]} == {"Mahesh Chand Agrawal", "Sarla Agrawal", "Tanvi Agrawal"}
    assert view["check_counts"]["conflict"] == 0
    assert view["finding_counts"] == {"open": 0, "conflict_confirmed": 0, "no_issue": 0}
    shared = next(c for c in view["checks"] if c["member_name"] == "Sarla Agrawal" and c["check"] == "shared_address")
    assert shared["result"] == "match" and shared["finding_id"] is None


def test_a_conflict_becomes_a_finding_the_head_can_dismiss_and_it_survives_a_refresh(
    client, plain_headers, household, db_session, reviewer_headers
):
    # The head entered a wrong date of birth for the child.
    client.patch(
        f"/family/members/{household['child']['id']}", headers=plain_headers, json={"date_of_birth": "1990-01-01"}
    )
    view = _compare(client, plain_headers, [household["child"]["id"]]).json()
    case_id = view["id"]
    assert view["finding_counts"]["open"] == 1
    conflict = next(c for c in view["checks"] if c["result"] == "conflict")
    assert conflict["check"] == "member_identity" and conflict["member_name"] == "Tanvi Agrawal"
    assert conflict["resolution"] == "open" and conflict["finding_id"]

    # A stored finding, like any other.
    stored = db_session.execute(
        select(CrossDocumentFinding).where(CrossDocumentFinding.case_id == uuid.UUID(case_id))
    ).scalars().all()
    assert [(f.finding_type, f.classification) for f in stored] == [("family_check", "conflict")]

    url = f"/cases/{case_id}/findings/{conflict['finding_id']}"
    reviewed = client.patch(url, headers=plain_headers, json={"decision": "dismissed", "note": "Typing mistake."})
    assert reviewed.status_code == 200, reviewed.text

    after = client.get(f"/family/comparisons/{case_id}", headers=plain_headers).json()
    decided = next(c for c in after["checks"] if c["result"] == "conflict")
    assert decided["review_status"] == "dismissed" and decided["resolution"] == "no_issue"
    assert decided["review_note"] == "Typing mistake."
    assert after["finding_counts"]["no_issue"] == 1

    # Running it again keeps the decision.
    again = client.post(f"/family/comparisons/{case_id}/refresh", headers=plain_headers).json()
    assert next(c for c in again["checks"] if c["result"] == "conflict")["review_status"] == "dismissed"

    # A company reviewer reads it.
    assert client.get(f"/family/comparisons/{case_id}", headers=reviewer_headers).status_code == 200

    # Correcting the entry clears the conflict, and its finding with it.
    client.patch(
        f"/family/members/{household['child']['id']}", headers=plain_headers, json={"date_of_birth": "2004-09-27"}
    )
    cleared = client.post(f"/family/comparisons/{case_id}/refresh", headers=plain_headers).json()
    assert cleared["check_counts"]["conflict"] == 0
    assert cleared["finding_counts"] == {"open": 0, "conflict_confirmed": 0, "no_issue": 0}
    assert db_session.execute(
        select(CrossDocumentFinding).where(CrossDocumentFinding.case_id == uuid.UUID(case_id))
    ).scalars().all() == []


def test_the_comparison_is_private_to_the_head_and_readable_by_reviewers(
    client, plain_headers, household, reviewer_headers, db_session
):
    case_id = _compare(client, plain_headers, [household["child"]["id"]]).json()["id"]
    stranger = _headers_for(_make_user(db_session, "stranger@example.com", UserRole.user, "Some Stranger"))
    for headers in (stranger, household["spouse_headers"]):
        assert client.get(f"/family/comparisons/{case_id}", headers=headers).status_code == 404
        assert client.get(f"/cases/{case_id}", headers=headers).status_code == 404
    assert client.get("/family/comparisons", headers=stranger).json() == []
    # Reviewers read, but do not refresh or close someone else's.
    assert client.post(f"/family/comparisons/{case_id}/refresh", headers=reviewer_headers).status_code == 404
    assert client.delete(f"/family/comparisons/{case_id}", headers=reviewer_headers).status_code == 404
    assert client.get(f"/family/comparisons/{case_id}").status_code == 401


def test_a_comparison_needs_a_member_besides_the_head_and_only_from_this_family(
    client, plain_headers, household
):
    assert _compare(client, plain_headers, [household["head"]["id"]]).status_code == 422
    assert _compare(client, plain_headers, [str(uuid.uuid4())]).status_code == 422
    assert client.post("/family/comparisons", headers=plain_headers, json={"member_ids": []}).status_code == 422


def test_comparisons_are_listed_and_can_be_closed(client, plain_headers, household, db_session):
    client.patch(
        f"/family/members/{household['child']['id']}", headers=plain_headers, json={"date_of_birth": "1990-01-01"}
    )
    case_id = _compare(client, plain_headers, [household["child"]["id"]]).json()["id"]
    (row,) = client.get("/family/comparisons", headers=plain_headers).json()
    assert row["id"] == case_id and row["conflicts"] == 1 and row["open_conflicts"] == 1
    assert row["members"] == ["Mahesh Chand Agrawal", "Tanvi Agrawal"]
    # It shows among the head's cases too.
    assert case_id in {c["id"] for c in client.get("/cases", headers=plain_headers).json()}

    assert client.delete(f"/family/comparisons/{case_id}", headers=plain_headers).status_code == 204
    assert client.get("/family/comparisons", headers=plain_headers).json() == []
    assert db_session.get(Case, uuid.UUID(case_id)).status == CaseStatus.closed
    assert client.post(f"/family/comparisons/{case_id}/refresh", headers=plain_headers).status_code == 409


def test_a_comparison_case_cannot_be_made_or_filled_the_ordinary_way(client, plain_headers, household):
    assert client.post("/cases", headers=plain_headers, json={"case_type": "family_comparison"}).status_code == 422
    case_id = _compare(client, plain_headers, [household["child"]["id"]]).json()["id"]
    refused = client.post(
        f"/cases/{case_id}/documents", headers=plain_headers, files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")}
    )
    assert refused.status_code == 409


def test_the_comparison_is_in_hindi_on_request(client, plain_headers, household):
    view = _compare(client, plain_headers, [household["spouse"]["id"]], lang="hi").json()
    assert view["language"] == "hi"
    shared = next(c for c in view["checks"] if c["member_name"] == "Sarla Agrawal" and c["check"] == "shared_address")
    assert shared["summary"].endswith("पते जैसा ही है।")


def test_a_member_sees_only_their_own_part_of_the_family(client, plain_headers, household):
    mine = client.get("/family/me", headers=household["spouse_headers"]).json()
    assert mine["full_name"] == "Sarla Agrawal" and mine["family_name"]
    assert [c["id"] for c in mine["cases"]] == [household["cases"]["spouse"]]
    assert mine["cases"][0]["documents"] and mine["latest_case_id"] == household["cases"]["spouse"]
    assert "members" not in mine
    # The head and people outside any family have no membership.
    assert client.get("/family/me", headers=plain_headers).json() is None


def test_the_comparison_says_who_may_review_it(client, plain_headers, household, reviewer_headers):
    case_id = _compare(client, plain_headers, [household["child"]["id"]]).json()["id"]
    mine = client.get(f"/family/comparisons/{case_id}", headers=plain_headers).json()
    assert mine["is_head"] is True and mine["can_review"] is True
    theirs = client.get(f"/family/comparisons/{case_id}", headers=reviewer_headers).json()
    assert theirs["is_head"] is False and theirs["can_review"] is True
