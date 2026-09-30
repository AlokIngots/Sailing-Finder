"""The login gate.

Covers exactly what the feature has to guarantee:
  - a correct username and password signs you in
  - a wrong password does not, and says nothing about which half was wrong
  - a protected endpoint is 401 signed out and 200 signed in
  - signing out kills the session server-side, not just in the browser
  - the cookie carries HttpOnly / SameSite=Lax, and Secure in production
"""

from __future__ import annotations

import pytest

from app.services import security

GOOD_PASSWORD = "correct-horse-battery"
WRONG_PASSWORD = "not-the-password"


@pytest.fixture
def alok(fake_db):
    return fake_db.add_user(
        "alok", security.hash_password(GOOD_PASSWORD), name="Alok", role="admin"
    )


@pytest.fixture
def priya(fake_db):
    return fake_db.add_user(
        "priya", security.hash_password(GOOD_PASSWORD), name="Priya", role="user"
    )


def sign_in(client, username, password=GOOD_PASSWORD):
    return client.post("/api/login", json={"username": username, "password": password})


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
def test_hash_is_not_the_password():
    hashed = security.hash_password(GOOD_PASSWORD)
    assert GOOD_PASSWORD not in hashed
    assert hashed.startswith("$2")


def test_verify_accepts_the_right_password_only():
    hashed = security.hash_password(GOOD_PASSWORD)
    assert security.verify_password(GOOD_PASSWORD, hashed)
    assert not security.verify_password(WRONG_PASSWORD, hashed)


def test_same_password_hashes_differently_each_time():
    """Per-hash salt: two accounts with the same password must not look alike."""
    assert security.hash_password(GOOD_PASSWORD) != security.hash_password(GOOD_PASSWORD)


@pytest.mark.parametrize("bad", ["", "short", "a" * 7])
def test_short_passwords_are_refused(bad):
    with pytest.raises(ValueError):
        security.hash_password(bad)


def test_over_long_passwords_are_refused():
    """bcrypt stops at 72 bytes. Truncating silently would let two different
    long passwords with the same prefix open the same account."""
    with pytest.raises(ValueError):
        security.hash_password("a" * 73)


# ---------------------------------------------------------------------------
# Signing in
# ---------------------------------------------------------------------------
def test_correct_login_succeeds_and_sets_the_cookie(client, alok):
    response = sign_in(client, "alok")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["data"] == {"username": "alok", "name": "Alok", "role": "admin"}

    # Attribute names and values are case-insensitive per RFC 6265; Starlette
    # writes 'SameSite=lax', so compare lowercased rather than pinning its
    # spelling.
    cookie = response.headers["set-cookie"].lower()
    assert "sf_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie


def test_login_never_returns_the_hash(client, alok):
    assert "password" not in sign_in(client, "alok").text.lower()


def test_username_is_case_insensitive(client, alok):
    assert sign_in(client, "ALOK").status_code == 200


def test_wrong_password_is_rejected(client, alok):
    response = sign_in(client, "alok", WRONG_PASSWORD)

    assert response.status_code == 401
    assert response.json()["message"] == "Username or password is incorrect."
    assert "set-cookie" not in response.headers


def test_unknown_user_and_wrong_password_are_indistinguishable(client, alok):
    """Otherwise the endpoint becomes a way to discover who has an account."""
    unknown = sign_in(client, "nobody")
    wrong = sign_in(client, "alok", WRONG_PASSWORD)

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["message"] == wrong.json()["message"]


def test_deactivated_user_cannot_sign_in(client, fake_db):
    fake_db.add_user("gone", security.hash_password(GOOD_PASSWORD), is_active=False)
    assert sign_in(client, "gone").status_code == 401


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------
def test_me_is_401_when_signed_out(client):
    response = client.get("/api/me")
    assert response.status_code == 401
    assert response.json()["status"] == "error"


def test_me_is_200_when_signed_in(client, alok):
    sign_in(client, "alok")
    response = client.get("/api/me")

    assert response.status_code == 200
    assert response.json()["data"] == {"username": "alok", "name": "Alok", "role": "admin"}


def test_other_endpoints_are_gated_too(client, alok):
    """The gate is mounted per-router, so check one that is not /api/me.

    /api/schedule is still a stub, so signed in it answers 501 — which is the
    point: the request got past require_auth and died in the handler instead.
    """
    assert client.get("/api/schedule").status_code == 401

    sign_in(client, "alok")
    assert client.get("/api/schedule").status_code == 501


def test_a_forged_cookie_is_rejected(client, alok):
    sign_in(client, "alok")
    client.cookies.set("sf_session", "not-a-signed-value")
    assert client.get("/api/me").status_code == 401


def test_a_session_deleted_server_side_stops_working(client, alok, fake_db):
    """Revoking access must not depend on the browser cooperating."""
    sign_in(client, "alok")
    assert client.get("/api/me").status_code == 200

    fake_db.sessions.clear()
    assert client.get("/api/me").status_code == 401


def test_sessions_are_per_user(client, alok, priya):
    sign_in(client, "alok")
    assert client.get("/api/me").json()["data"]["username"] == "alok"

    sign_in(client, "priya")
    me = client.get("/api/me").json()["data"]
    assert me["username"] == "priya"
    assert me["role"] == "user"


# ---------------------------------------------------------------------------
# Signing out
# ---------------------------------------------------------------------------
def test_logout_removes_the_session_row(client, alok, fake_db):
    sign_in(client, "alok")
    assert len(fake_db.sessions) == 1

    assert client.post("/api/logout").status_code == 200
    assert fake_db.sessions == {}
    assert client.get("/api/me").status_code == 401


def test_logout_requires_a_session(client):
    assert client.post("/api/logout").status_code == 401


def test_signing_in_twice_issues_a_new_session_id(client, alok, fake_db):
    sign_in(client, "alok")
    first = set(fake_db.sessions)
    sign_in(client, "alok")
    assert set(fake_db.sessions) != first


# ---------------------------------------------------------------------------
# Cookie flags
# ---------------------------------------------------------------------------
def test_cookie_is_not_secure_outside_production():
    """Locally there is no TLS, so a Secure cookie would never come back."""
    assert security.cookie_kwargs()["secure"] is False


def test_cookie_is_secure_in_production(monkeypatch):
    import dataclasses

    production = dataclasses.replace(security.settings, env="production")
    monkeypatch.setattr(security, "settings", production)

    flags = security.cookie_kwargs()
    assert flags["secure"] is True
    assert flags["httponly"] is True
    assert flags["samesite"] == "lax"


def test_cookie_carries_no_user_information():
    """The cookie is an opaque signed id. Everything else lives in the table."""
    sid = "some-session-id"
    signed = security.sign_session_id(sid)
    assert security.unsign_session_id(signed) == sid
    assert security.unsign_session_id("tampered") is None
