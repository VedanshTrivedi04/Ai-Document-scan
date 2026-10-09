"""A family head creating a sign-in for a member (app/api/families.py). All
people and addresses are made up."""
import uuid

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.user import User, UserRole
from tests.conftest import _headers_for, _make_user


@pytest.fixture()
def family(client, plain_headers):
    return client.post("/family", headers=plain_headers, json={"name": "Agrawal family"}).json()


def _login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def _member(view, name):
    return next(m for m in view["members"] if m["full_name"] == name)


def _add_with_login(client, headers, name="Sarla Agrawal", email="sarla@example.com", **login):
    return client.post(
        "/family/members",
        headers=headers,
        json={"full_name": name, "relation": "spouse", "login": {"email": email, **login}},
    )


def test_adding_a_member_with_a_login_creates_the_account_with_a_temporary_password(
    client, plain_headers, plain_user, family, db_session
):
    response = _add_with_login(client, plain_headers)
    assert response.status_code == 201, response.text
    body = response.json()

    credentials = body["credentials"]
    assert credentials["email"] == "sarla@example.com"
    password = credentials["temporary_password"]
    assert password and len(password) >= 12

    sarla = _member(body, "Sarla Agrawal")
    assert sarla["has_login"] is True
    assert sarla["login"] == {"email": "sarla@example.com", "is_active": True, "must_change_password": True}
    assert credentials["member_id"] == sarla["id"]

    user = db_session.execute(select(User).where(User.email == "sarla@example.com")).scalar_one()
    assert user.role == UserRole.user and user.company_id == plain_user.company_id
    assert user.full_name == "Sarla Agrawal" and user.must_change_password is True
    assert password not in (user.hashed_password or "")

    signed_in = _login(client, "sarla@example.com", password)
    assert signed_in.status_code == 200, signed_in.text
    assert signed_in.json()["must_change_password"] is True


def test_the_password_is_never_written_to_the_audit_log(client, plain_headers, family, db_session):
    password = _add_with_login(client, plain_headers, password="Chosen-Pass-77").json()
    assert password["credentials"]["temporary_password"] is None  # the head chose it; it is not echoed
    events = db_session.execute(
        select(AuditLog).where(AuditLog.event_type == "family_member_login_created")
    ).scalars().all()
    assert len(events) == 1
    assert "Chosen-Pass-77" not in str(events[0].event_data)
    assert events[0].event_data["email"] == "sarla@example.com"


def test_the_member_must_change_the_password_and_can_then_carry_on(client, plain_headers, family):
    password = _add_with_login(client, plain_headers).json()["credentials"]["temporary_password"]
    token = _login(client, "sarla@example.com", password).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/auth/me", headers=headers).json()["must_change_password"] is True

    changed = client.post(
        "/auth/me/password", headers=headers, json={"current_password": password, "new_password": "My-Own-Pass-1"}
    )
    assert changed.status_code == 204, changed.text
    assert client.get("/auth/me", headers=headers).json()["must_change_password"] is False
    assert _login(client, "sarla@example.com", "My-Own-Pass-1").json()["must_change_password"] is False


def test_a_login_can_be_added_to_an_existing_member(client, plain_headers, family):
    client.post("/family/members", headers=plain_headers, json={"full_name": "Tanvi Agrawal", "relation": "daughter"})
    tanvi = _member(client.get("/family", headers=plain_headers).json(), "Tanvi Agrawal")
    assert tanvi["has_login"] is False and tanvi["login"] is None

    created = client.post(
        f"/family/members/{tanvi['id']}/login", headers=plain_headers, json={"email": "tanvi@example.com"}
    )
    assert created.status_code == 201, created.text
    assert _member(created.json(), "Tanvi Agrawal")["has_login"] is True
    assert created.json()["credentials"]["temporary_password"]

    again = client.post(
        f"/family/members/{tanvi['id']}/login", headers=plain_headers, json={"email": "tanvi2@example.com"}
    )
    assert again.status_code == 409


def test_an_email_that_is_already_used_is_refused_and_leaves_no_member_behind(client, plain_headers, family):
    first = _add_with_login(client, plain_headers)
    assert first.status_code == 201
    second = _add_with_login(client, plain_headers, name="Other Person", email="SARLA@example.com")
    assert second.status_code == 409
    names = [m["full_name"] for m in client.get("/family", headers=plain_headers).json()["members"]]
    assert "Other Person" not in names


def test_the_head_cannot_get_a_login_made_for_themselves(client, plain_headers, family):
    head = next(m for m in family["members"] if m["is_head"])
    response = client.post(
        f"/family/members/{head['id']}/login", headers=plain_headers, json={"email": "me2@example.com"}
    )
    assert response.status_code == 409


def test_resetting_a_password_replaces_it_and_forces_a_change(client, plain_headers, family):
    first = _add_with_login(client, plain_headers).json()
    member_id = first["credentials"]["member_id"]
    old = first["credentials"]["temporary_password"]
    token = _login(client, "sarla@example.com", old).json()["access_token"]
    client.post(
        "/auth/me/password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": old, "new_password": "Her-Own-Pass-9"},
    )

    reset = client.post(f"/family/members/{member_id}/login/reset-password", headers=plain_headers, json={})
    assert reset.status_code == 200, reset.text
    fresh = reset.json()["credentials"]["temporary_password"]
    assert fresh and fresh != old

    assert _login(client, "sarla@example.com", "Her-Own-Pass-9").status_code == 401
    assert _login(client, "sarla@example.com", fresh).json()["must_change_password"] is True


def test_the_head_can_switch_a_login_off_and_on_and_remove_it(client, plain_headers, family):
    created = _add_with_login(client, plain_headers).json()
    member_id, password = created["credentials"]["member_id"], created["credentials"]["temporary_password"]

    off = client.patch(f"/family/members/{member_id}/login", headers=plain_headers, json={"is_active": False})
    assert _member(off.json(), "Sarla Agrawal")["login"]["is_active"] is False
    assert _login(client, "sarla@example.com", password).status_code == 401

    on = client.patch(f"/family/members/{member_id}/login", headers=plain_headers, json={"is_active": True})
    assert _member(on.json(), "Sarla Agrawal")["login"]["is_active"] is True
    assert _login(client, "sarla@example.com", password).status_code == 200

    removed = client.delete(f"/family/members/{member_id}/login", headers=plain_headers)
    assert removed.status_code == 200
    sarla = _member(removed.json(), "Sarla Agrawal")
    assert sarla["has_login"] is False  # the member stays
    assert _login(client, "sarla@example.com", password).status_code == 401
    assert client.delete(f"/family/members/{member_id}/login", headers=plain_headers).status_code == 404


def test_removing_a_member_switches_their_login_off(client, plain_headers, family):
    created = _add_with_login(client, plain_headers).json()
    client.delete(f"/family/members/{created['credentials']['member_id']}", headers=plain_headers)
    assert _login(client, "sarla@example.com", created["credentials"]["temporary_password"]).status_code == 401


def test_only_the_head_manages_logins(client, plain_headers, family, reviewer_headers, db_session):
    member_id = _add_with_login(client, plain_headers).json()["credentials"]["member_id"]
    other = _headers_for(_make_user(db_session, "neighbour@example.com", UserRole.user, "Nosy Neighbour"))
    for headers in (other, reviewer_headers):
        assert client.post(
            f"/family/members/{member_id}/login/reset-password", headers=headers, json={}
        ).status_code == 404
        assert client.patch(
            f"/family/members/{member_id}/login", headers=headers, json={"is_active": False}
        ).status_code == 404
        assert client.delete(f"/family/members/{member_id}/login", headers=headers).status_code == 404
    assert client.post(
        f"/family/members/{member_id}/login/reset-password", json={}
    ).status_code == 401


def test_a_member_with_a_login_cannot_start_a_family_of_their_own(client, plain_headers, family):
    password = _add_with_login(client, plain_headers).json()["credentials"]["temporary_password"]
    token = _login(client, "sarla@example.com", password).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/family", headers=headers, json={}).status_code == 409
    assert client.get("/family", headers=headers).json() is None


def test_a_members_case_is_linked_to_them_automatically(client, plain_headers, family, db_session):
    created = _add_with_login(client, plain_headers).json()
    member_id = created["credentials"]["member_id"]
    token = _login(client, "sarla@example.com", created["credentials"]["temporary_password"]).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    made = client.post("/cases", headers=headers, json={"case_type": "identity_verification"})
    assert made.status_code == 201, made.text
    case = db_session.get(Case, uuid.UUID(made.json()["id"]))
    assert str(case.family_member_id) == member_id

    # They cannot submit for anyone else.
    head = next(m for m in family["members"] if m["is_head"])
    refused = client.post(
        "/cases", headers=headers, json={"case_type": "identity_verification", "family_member_id": head["id"]}
    )
    assert refused.status_code == 422

    # The head sees that case under the member.
    sarla = _member(client.get("/family", headers=plain_headers).json(), "Sarla Agrawal")
    assert [c["id"] for c in sarla["cases"]] == [str(case.id)]


def test_a_member_cannot_read_the_family(client, plain_headers, family):
    created = _add_with_login(client, plain_headers).json()
    token = _login(client, "sarla@example.com", created["credentials"]["temporary_password"]).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/families/{family['id']}", headers=headers).status_code == 404
    assert client.patch(
        f"/family/members/{created['credentials']['member_id']}", headers=headers, json={"full_name": "X"}
    ).status_code == 404
