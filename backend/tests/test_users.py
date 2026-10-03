"""The admin Users screen's API.

What it has to guarantee:
  - only an admin reaches it: a normal user gets 403, signed out gets 401
  - an admin can add as many users as they like, list them, and remove them
  - passwords are stored hashed, and no response carries a hash or a password
  - a removed user is signed out at once and cannot sign back in
  - an admin cannot remove themselves, and cannot overwrite an existing user
"""

from __future__ import annotations

import pytest

from app.services import security

GOOD_PASSWORD = "correct-horse-battery"
NEW_PASSWORD = "brand-new-password"


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
    response = client.post("/api/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response


def new_user(username="ravi", role="user", password=NEW_PASSWORD, name="Ravi Kumar"):
    return {"username": username, "name": name, "role": role, "password": password}


# ---------------------------------------------------------------------------
# Who may reach it
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "method, path, body",
    [
        ("get", "/api/users", None),
        ("post", "/api/users", new_user()),
        ("delete", "/api/users/alok", None),
    ],
)
def test_a_normal_user_is_forbidden(client, alok, priya, fake_db, method, path, body):
    sign_in(client, "priya")
    kwargs = {"json": body} if body else {}

    response = getattr(client, method)(path, **kwargs)

    assert response.status_code == 403
    assert response.json()["status"] == "error"
    # And nothing changed behind the 403.
    assert "ravi" not in fake_db.users
    assert fake_db.users["alok"]["is_active"]


@pytest.mark.parametrize(
    "method, path", [("get", "/api/users"), ("post", "/api/users"), ("delete", "/api/users/alok")]
)
def test_signed_out_is_unauthorised(client, alok, method, path):
    kwargs = {"json": new_user()} if method == "post" else {}
    assert getattr(client, method)(path, **kwargs).status_code == 401


def test_an_admin_can_list_users(client, alok, priya):
    sign_in(client, "alok")

    response = client.get("/api/users")

    assert response.status_code == 200
    rows = response.json()["data"]
    assert [r["username"] for r in rows] == ["alok", "priya"]
    assert rows[0]["is_self"] is True
    assert rows[1]["is_self"] is False
    for row in rows:
        assert set(row) == {"username", "name", "role", "created_at", "is_self"}


# ---------------------------------------------------------------------------
# Adding
# ---------------------------------------------------------------------------
def test_an_admin_can_add_many_users(client, alok, fake_db):
    sign_in(client, "alok")

    for n in range(5):
        response = client.post("/api/users", json=new_user(f"user{n}"))
        assert response.status_code == 201
        assert response.json()["data"]["username"] == f"user{n}"

    listed = [r["username"] for r in client.get("/api/users").json()["data"]]
    assert listed == ["alok", "user0", "user1", "user2", "user3", "user4"]


def test_an_added_admin_is_an_admin(client, alok):
    sign_in(client, "alok")
    client.post("/api/users", json=new_user("meera", role="admin"))

    client.cookies.clear()
    sign_in(client, "meera", NEW_PASSWORD)
    assert client.get("/api/users").status_code == 200


def test_an_added_user_can_sign_in_but_not_reach_users(client, alok):
    sign_in(client, "alok")
    client.post("/api/users", json=new_user("ravi"))

    client.cookies.clear()
    sign_in(client, "ravi", NEW_PASSWORD)
    assert client.get("/api/me").json()["data"]["role"] == "user"
    assert client.get("/api/users").status_code == 403


def test_the_password_is_stored_hashed(client, alok, fake_db):
    sign_in(client, "alok")
    response = client.post("/api/users", json=new_user())

    stored = fake_db.users["ravi"]["password_hash"]
    assert NEW_PASSWORD not in stored
    assert stored.startswith("$2")
    assert security.verify_password(NEW_PASSWORD, stored)
    assert NEW_PASSWORD not in response.text
    assert "$2" not in response.text


def test_the_username_is_normalised(client, alok, fake_db):
    sign_in(client, "alok")
    client.post("/api/users", json=new_user("  Ravi.K  "))
    assert "ravi.k" in fake_db.users


@pytest.mark.parametrize("bad", ["ra vi", "ravi@x", "r", "ravi/../x"])
def test_bad_usernames_are_refused(client, alok, fake_db, bad):
    sign_in(client, "alok")
    response = client.post("/api/users", json=new_user(bad))
    assert response.status_code == 422
    assert len(fake_db.users) == 1


def test_a_weak_password_is_refused_without_echoing_it(client, alok, fake_db):
    sign_in(client, "alok")
    response = client.post("/api/users", json=new_user(password="short1"))

    assert response.status_code == 422
    assert "short1" not in response.text
    assert "ravi" not in fake_db.users


def test_an_unknown_role_is_refused(client, alok, fake_db):
    sign_in(client, "alok")
    response = client.post("/api/users", json=new_user(role="superuser"))
    assert response.status_code == 422
    assert "ravi" not in fake_db.users


def test_an_existing_user_is_not_overwritten(client, alok, priya, fake_db):
    sign_in(client, "alok")
    before = fake_db.users["priya"]["password_hash"]

    response = client.post("/api/users", json=new_user("priya", role="admin"))

    assert response.status_code == 409
    assert fake_db.users["priya"]["password_hash"] == before
    assert fake_db.users["priya"]["role"] == "user"


# ---------------------------------------------------------------------------
# Removing
# ---------------------------------------------------------------------------
def test_removing_a_user_signs_them_out_and_blocks_sign_in(client, alok, priya, fake_db):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as priya_client:
        sign_in(priya_client, "priya")
        assert priya_client.get("/api/me").status_code == 200

        sign_in(client, "alok")
        response = client.delete("/api/users/priya")
        assert response.status_code == 200

        # Her open session is dead...
        assert priya_client.get("/api/me").status_code == 401
        # ...and she cannot start a new one.
        bad = priya_client.post(
            "/api/login", json={"username": "priya", "password": GOOD_PASSWORD}
        )
        assert bad.status_code == 401

    listed = [r["username"] for r in client.get("/api/users").json()["data"]]
    assert listed == ["alok"]


def test_a_removed_username_can_be_added_again(client, alok, priya, fake_db):
    sign_in(client, "alok")
    client.delete("/api/users/priya")

    response = client.post("/api/users", json=new_user("priya", name="Priya S"))

    assert response.status_code == 201
    assert fake_db.users["priya"]["is_active"]
    assert security.verify_password(NEW_PASSWORD, fake_db.users["priya"]["password_hash"])


def test_an_admin_cannot_remove_themselves(client, alok, fake_db):
    sign_in(client, "alok")
    response = client.delete("/api/users/alok")
    assert response.status_code == 409
    assert fake_db.users["alok"]["is_active"]


def test_removing_an_unknown_user_is_404(client, alok):
    sign_in(client, "alok")
    assert client.delete("/api/users/nobody").status_code == 404
