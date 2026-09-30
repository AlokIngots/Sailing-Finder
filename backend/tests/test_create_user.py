"""scripts/create_user.py — the only way an account comes into existence.

The password path is what matters here: it must never be accepted as an
argument, must be hashed before it reaches the database, and changing it must
invalidate any session still running under the old one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import create_user  # noqa: E402

PASSWORD = "first-password-1"
NEW_PASSWORD = "second-password-2"


@pytest.fixture
def run(fake_db, monkeypatch):
    """Invoke the script the way the command line would."""

    def _run(*args, password=PASSWORD):
        monkeypatch.setattr(sys, "argv", ["create_user", *args])
        if password is None:
            monkeypatch.delenv("SF_NEW_PASSWORD", raising=False)
        else:
            monkeypatch.setenv("SF_NEW_PASSWORD", password)
        return create_user.main()

    return _run


def test_creates_a_user(run, fake_db, capsys):
    assert run("alok", "Alok", "admin") == 0

    user = fake_db.users["alok"]
    assert user["name"] == "Alok"
    assert user["role"] == "admin"
    assert "Created" in capsys.readouterr().out


def test_password_is_hashed_not_stored(run, fake_db):
    run("alok", "Alok", "admin")

    stored = fake_db.users["alok"]["password_hash"]
    assert stored != PASSWORD
    assert PASSWORD not in stored
    assert stored.startswith("$2")


def test_password_never_appears_in_the_output(run, capsys):
    run("alok", "Alok", "admin")
    assert PASSWORD not in capsys.readouterr().out


def test_two_users_are_independent(run, fake_db):
    from app.services import security

    assert run("alok", "Alok", "admin") == 0
    assert run("priya", "Priya", "user", password="priya-password-9") == 0

    assert set(fake_db.users) == {"alok", "priya"}
    assert fake_db.users["alok"]["role"] == "admin"
    assert fake_db.users["priya"]["role"] == "user"

    # Each password opens only its own account.
    assert security.verify_password(PASSWORD, fake_db.users["alok"]["password_hash"])
    assert not security.verify_password(PASSWORD, fake_db.users["priya"]["password_hash"])


def test_username_is_normalised(run, fake_db):
    run("  ALOK  ", "Alok")
    assert "alok" in fake_db.users


def test_defaults_to_the_user_role(run, fake_db):
    run("priya", "Priya")
    assert fake_db.users["priya"]["role"] == "user"


@pytest.mark.parametrize("bad_role", ["owner", "Admin ", "superuser"])
def test_unknown_roles_are_refused(run, fake_db, bad_role):
    if bad_role.strip().lower() in create_user.ROLES:
        pytest.skip("that one is valid after normalising")
    assert run("alok", "Alok", bad_role) == 1
    assert fake_db.users == {}


def test_too_few_arguments_is_refused(run, fake_db):
    assert run("alok") == 1
    assert fake_db.users == {}


def test_a_weak_password_is_refused(run, fake_db):
    assert run("alok", "Alok", password="short") == 1
    assert fake_db.users == {}


def test_updating_a_user_signs_their_old_sessions_out(run, fake_db, capsys):
    from app.services import security

    run("alok", "Alok", "admin")
    user_id = fake_db.users["alok"]["id"]
    security.create_session(user_id)
    assert len(fake_db.sessions) == 1

    assert run("alok", "Alok Ingots", "admin", password=NEW_PASSWORD) == 0

    assert fake_db.sessions == {}, "a password change must not leave a session alive"
    assert fake_db.users["alok"]["name"] == "Alok Ingots"
    assert security.verify_password(NEW_PASSWORD, fake_db.users["alok"]["password_hash"])
    assert not security.verify_password(PASSWORD, fake_db.users["alok"]["password_hash"])
    assert "Updated" in capsys.readouterr().out
