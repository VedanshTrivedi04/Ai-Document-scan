"""An organisation's subdomain (app/services/subdomains.py): who may sign in
where, which organisation a site belongs to, and how a platform admin sets
it. Isolation of data does not depend on any of this; tests/test_multi_tenancy.py
covers that."""
import pytest
from starlette.requests import Request

from app.core.config import settings
from app.db import tenancy
from app.models.user import UserRole
from app.services import subdomains
from tests.conftest import _headers_for, _make_user, make_company

PASSWORD = "TestPassword123!"


def _request(headers: dict[str, str]) -> Request:
    return Request({
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    })


def _set_subdomain(db_session, company, label):
    state = tenancy.snapshot(db_session)
    tenancy.bind_platform(db_session)
    try:
        company.subdomain = label
        db_session.commit()
    finally:
        tenancy.restore(db_session, state)


@pytest.fixture()
def two_organisations(db_session, company):
    """The default company at "indore" with one user, a second at "bhopal"."""
    _set_subdomain(db_session, company, "indore")
    other = make_company(db_session, "Bhopal Office")
    _set_subdomain(db_session, other, "bhopal")
    indore_user = _make_user(db_session, "asha@indore.example", UserRole.user, "Asha Verma")
    bhopal_user = _make_user(db_session, "ravi@bhopal.example", UserRole.user, "Ravi Jain", company_id=other.id)
    return {"indore": indore_user, "bhopal": bhopal_user, "other_company": other}


def _login(client, email, subdomain=None, password=PASSWORD):
    headers = {subdomains.HEADER: subdomain} if subdomain is not None else {}
    return client.post("/auth/login", json={"email": email, "password": password}, headers=headers)


# --- the label itself -----------------------------------------------------

@pytest.mark.parametrize("value, expected", [("indore", "indore"), (" Tehsil-Office-2 ", "tehsil-office-2"), ("abc", "abc")])
def test_usable_subdomains(value, expected):
    assert subdomains.normalize(value) == expected


@pytest.mark.parametrize(
    "value", ["ab", "-indore", "indore-", "ind ore", "ind_ore", "इंदौर", "a" * 64, "in--dore", "www", "admin", "api", ""]
)
def test_unusable_subdomains(value):
    with pytest.raises(subdomains.InvalidSubdomain):
        subdomains.normalize(value)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Tehsil Office, Indore", "tehsil-office-indore"),
        ("Acme Ltd.", "acme-ltd"),
        ("  Café   Société  ", "cafe-societe"),
        ("Admin", None),          # reserved
        ("इंदौर", None),           # nothing usable in Latin letters
        ("X", None),
    ],
)
def test_subdomain_suggested_from_a_name(name, expected):
    assert subdomains.suggest(name) == expected


def test_subdomain_of_a_request(monkeypatch):
    assert subdomains.from_request(_request({"X-Org-Subdomain": "Indore"})) == "indore"
    assert subdomains.from_request(_request({"X-Org-Subdomain": "www"})) is None
    assert subdomains.from_request(_request({"host": "indore.example.org"})) is None  # no base domain set

    monkeypatch.setattr(settings, "app_base_domain", "example.org")
    assert subdomains.from_request(_request({"host": "indore.example.org:8000"})) == "indore"
    assert subdomains.from_request(_request({"host": "example.org"})) is None
    assert subdomains.from_request(_request({"host": "www.example.org"})) is None
    assert subdomains.from_request(_request({"host": "a.b.example.org"})) is None
    assert subdomains.from_request(_request({"host": "indore.example.com"})) is None
    # The page's origin wins over the API's own host; the header over both.
    assert subdomains.from_request(
        _request({"origin": "https://bhopal.example.org", "host": "api.example.org"})
    ) == "bhopal"
    assert subdomains.from_request(
        _request({"X-Org-Subdomain": "indore", "origin": "https://bhopal.example.org"})
    ) == "indore"


# --- signing in -----------------------------------------------------------

def test_users_sign_in_only_on_their_own_organisations_site(client, two_organisations):
    own = _login(client, "asha@indore.example", "indore")
    assert own.status_code == 200, own.text
    assert own.json()["company_subdomain"] == "indore"

    elsewhere = _login(client, "asha@indore.example", "bhopal")
    assert elsewhere.status_code == 401
    # Indistinguishable from a wrong password.
    wrong_password = _login(client, "asha@indore.example", "indore", password="nope-nope-nope")
    assert elsewhere.json() == wrong_password.json() == {"detail": "Incorrect email or password"}

    assert _login(client, "asha@indore.example", "no-such-office").status_code == 401
    assert _login(client, "ravi@bhopal.example", "bhopal").status_code == 200


def test_without_a_subdomain_sign_in_works_as_before(client, two_organisations):
    response = _login(client, "ravi@bhopal.example")
    assert response.status_code == 200
    assert response.json()["company_subdomain"] == "bhopal"  # tells the page where this user belongs
    assert _login(client, "ravi@bhopal.example", "www").status_code == 200  # a platform label names nobody


def test_platform_admin_signs_in_on_the_platform_site_only(client, two_organisations, platform_admin_user):
    assert _login(client, platform_admin_user.email).status_code == 200
    assert _login(client, platform_admin_user.email).json()["company_subdomain"] is None
    assert _login(client, platform_admin_user.email, "indore").status_code == 401


def test_a_sign_in_is_not_accepted_on_another_organisations_site(client, two_organisations):
    token = _headers_for(two_organisations["indore"])
    assert client.get("/auth/me", headers=token).status_code == 200
    assert client.get("/auth/me", headers={**token, subdomains.HEADER: "indore"}).status_code == 200

    refused = client.get("/cases", headers={**token, subdomains.HEADER: "bhopal"})
    assert refused.status_code == 401
    assert "different organisation" in refused.json()["detail"]


def test_host_under_the_base_domain_names_the_organisation(client, two_organisations, monkeypatch):
    monkeypatch.setattr(settings, "app_base_domain", "example.org")
    payload = {"email": "asha@indore.example", "password": PASSWORD}
    assert client.post("/auth/login", json=payload, headers={"host": "indore.example.org"}).status_code == 200
    assert client.post("/auth/login", json=payload, headers={"host": "bhopal.example.org"}).status_code == 401
    assert client.post("/auth/login", json=payload, headers={"host": "example.org"}).status_code == 200


def test_me_reports_the_organisations_subdomain(client, two_organisations, platform_admin_headers):
    me = client.get("/auth/me", headers=_headers_for(two_organisations["bhopal"])).json()
    assert (me["company_name"], me["company_subdomain"]) == ("Bhopal Office", "bhopal")
    assert client.get("/auth/me", headers=platform_admin_headers).json()["company_subdomain"] is None


# --- which organisation a site is for -------------------------------------

def test_organisation_of_a_site(client, two_organisations, db_session, monkeypatch):
    by_header = client.get("/organisation", headers={subdomains.HEADER: "bhopal"})
    assert by_header.status_code == 200
    assert by_header.json() == {"subdomain": "bhopal", "name": "Bhopal Office", "base_domain": None}
    assert client.get("/organisation?subdomain=Bhopal").json()["name"] == "Bhopal Office"

    # The platform's own site names nobody.
    assert client.get("/organisation").json() == {"subdomain": None, "name": None, "base_domain": None}
    assert client.get("/organisation?subdomain=www").json()["name"] is None

    assert client.get("/organisation?subdomain=nobody-here").status_code == 404

    monkeypatch.setattr(settings, "app_base_domain", "example.org")
    by_host = client.get("/organisation", headers={"host": "indore.example.org"}).json()
    assert (by_host["subdomain"], by_host["base_domain"]) == ("indore", "example.org")


def test_a_suspended_organisation_is_not_found(client, two_organisations, platform_admin_headers):
    other = two_organisations["other_company"]
    client.patch(f"/platform/companies/{other.id}", headers=platform_admin_headers, json={"is_active": False})
    assert client.get("/organisation?subdomain=bhopal").status_code == 404
    assert _login(client, "ravi@bhopal.example", "bhopal").status_code == 401


# --- platform admin sets it -----------------------------------------------

def _create(client, headers, **body):
    return client.post("/platform/companies", headers=headers, json=body)


def test_a_new_company_gets_a_subdomain_from_its_name(client, platform_admin_headers):
    first = _create(client, platform_admin_headers, name="Tehsil Office, Indore")
    assert first.status_code == 201, first.text
    assert first.json()["subdomain"] == "tehsil-office-indore"
    # A second name that makes the same label gets the next free one.
    assert _create(client, platform_admin_headers, name="Tehsil Office Indore").json()["subdomain"] == (
        "tehsil-office-indore-2"
    )
    # A name nothing can be made from leaves it unset.
    assert _create(client, platform_admin_headers, name="इंदौर कार्यालय").json()["subdomain"] is None

    listed = {c["name"]: c["subdomain"] for c in client.get("/platform/companies", headers=platform_admin_headers).json()}
    assert listed["Tehsil Office, Indore"] == "tehsil-office-indore"


def test_subdomain_can_be_chosen_and_must_be_usable_and_free(client, platform_admin_headers):
    chosen = _create(client, platform_admin_headers, name="Acme Hiring", subdomain="Acme")
    assert chosen.status_code == 201 and chosen.json()["subdomain"] == "acme"

    assert _create(client, platform_admin_headers, name="Acme Two", subdomain="acme").status_code == 409
    for bad in ("ab", "admin", "has space", "-lead"):
        assert _create(client, platform_admin_headers, name=f"Bad {bad}", subdomain=bad).status_code == 422


def test_subdomain_can_be_changed_and_removed(client, platform_admin_headers, two_organisations):
    other = two_organisations["other_company"]
    url = f"/platform/companies/{other.id}"

    assert client.patch(url, headers=platform_admin_headers, json={"subdomain": "indore"}).status_code == 409
    assert client.patch(url, headers=platform_admin_headers, json={"subdomain": "api"}).status_code == 422

    moved = client.patch(url, headers=platform_admin_headers, json={"subdomain": "bhopal-city"})
    assert moved.status_code == 200 and moved.json()["subdomain"] == "bhopal-city"
    # The old address stops working at once, the new one works.
    assert _login(client, "ravi@bhopal.example", "bhopal").status_code == 401
    assert _login(client, "ravi@bhopal.example", "bhopal-city").status_code == 200

    # Renaming alone leaves the subdomain as it is.
    renamed = client.patch(url, headers=platform_admin_headers, json={"name": "Bhopal City Office"}).json()
    assert renamed["subdomain"] == "bhopal-city"

    removed = client.patch(url, headers=platform_admin_headers, json={"subdomain": ""}).json()
    assert removed["subdomain"] is None
    assert _login(client, "ravi@bhopal.example").status_code == 200
    assert _login(client, "ravi@bhopal.example", "bhopal-city").status_code == 401
