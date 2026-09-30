"""Test setup.

The environment is filled in before anything from `app` is imported, because
config.py reads it at import time.

The database is faked. There is no Postgres in CI or on a developer laptop, and
these tests are about the auth logic — the session lifecycle, the cookie flags,
who gets a 401 — not about SQL. The fake below understands only the handful of
statements the auth code issues; it deliberately does not try to be a database.
Anything that needs real SQL semantics belongs in a test against a real
Postgres, run on the VPS.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("SESSION_SECRET", "t" * 48)
os.environ.setdefault("SESSION_TTL_HOURS", "12")
os.environ.setdefault("SHEET_ID", "test-sheet")
os.environ.setdefault("GOOGLE_KEY_PATH", "/tmp/none.json")
os.environ.setdefault("SMTP_HOST", "localhost")
os.environ.setdefault("SMTP_USER", "exports@alokindia.com")
os.environ.setdefault("SMTP_PASS", "unused-in-tests")
os.environ.setdefault("MAIL_FROM", "exports@alokindia.com")
for n in (1, 2, 3):
    os.environ.setdefault(f"FORWARDER_{n}_NAME", f"Forwarder {n}")
    os.environ.setdefault(f"FORWARDER_{n}_EMAIL", f"f{n}@example.com")


class FakeDb:
    """In-memory stand-in for app.db, covering only the auth statements."""

    def __init__(self) -> None:
        self.users: dict[str, dict] = {}
        self.sessions: dict[str, dict] = {}
        self._next_id = 1

    # --- helpers used by tests ---
    def add_user(self, username, password_hash, name="", role="user", is_active=True) -> dict:
        user = {
            "id": self._next_id,
            "username": username,
            "password_hash": password_hash,
            "name": name or username,
            "role": role,
            "is_active": is_active,
        }
        self._next_id += 1
        self.users[username] = user
        return user

    # --- the app.db surface ---
    def fetch_one(self, sql: str, params=()):
        if "INSERT INTO users" in sql:
            # scripts/create_user.py — upsert on username, RETURNING whether it
            # was an insert or an update.
            username, password_hash, name, role = params
            existing = self.users.get(username)
            if existing:
                existing.update(
                    password_hash=password_hash, name=name, role=role, is_active=True
                )
                return {"id": existing["id"], "was_inserted": False}
            created = self.add_user(username, password_hash, name=name, role=role)
            return {"id": created["id"], "was_inserted": True}

        if "FROM users" in sql and "WHERE username" in sql:
            user = self.users.get(params[0])
            return dict(user) if user else None

        if "FROM sessions s" in sql:
            session = self.sessions.get(params[0])
            if not session or session["expires_at"] <= datetime.now(timezone.utc):
                return None
            user = next((u for u in self.users.values() if u["id"] == session["user_id"]), None)
            if not user or not user["is_active"]:
                return None
            return {
                "id": user["id"],
                "username": user["username"],
                "name": user["name"],
                "role": user["role"],
            }

        raise AssertionError(f"FakeDb got an unexpected query: {sql.strip()[:80]}")

    def execute(self, sql: str, params=()) -> int:
        if "INSERT INTO sessions" in sql:
            sid, user_id, expires_at, user_agent, ip = params
            self.sessions[sid] = {
                "sid": sid,
                "user_id": user_id,
                "expires_at": expires_at,
                "user_agent": user_agent,
                "ip": ip,
            }
            return 1

        if "UPDATE sessions" in sql:
            hours, sid = params
            if sid in self.sessions:
                self.sessions[sid]["expires_at"] = datetime.now(timezone.utc) + timedelta(hours=hours)
                return 1
            return 0

        if "DELETE FROM sessions WHERE sid" in sql:
            return 1 if self.sessions.pop(params[0], None) else 0

        if "DELETE FROM sessions WHERE user_id" in sql:
            gone = [s for s, v in self.sessions.items() if v["user_id"] == params[0]]
            for sid in gone:
                del self.sessions[sid]
            return len(gone)

        raise AssertionError(f"FakeDb got an unexpected statement: {sql.strip()[:80]}")

    # No-ops: the pool is never opened in tests.
    def open_pool(self) -> None:
        pass

    def close_pool(self) -> None:
        pass


@pytest.fixture
def fake_db(monkeypatch) -> FakeDb:
    from app import db

    fake = FakeDb()
    for name in ("fetch_one", "execute", "open_pool", "close_pool"):
        monkeypatch.setattr(db, name, getattr(fake, name))
    return fake


@pytest.fixture
def client(fake_db):
    """TestClient with the fake database already in place."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
