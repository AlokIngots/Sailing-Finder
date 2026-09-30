"""Password hashing and server-side sessions.

Plain passwords are never stored, never logged, and never returned by any
endpoint. Only the bcrypt hash goes in the database.

The cookie holds a *signed session id* and nothing else — no user id, no role,
no expiry the browser could tamper with. The row in `sessions` is the truth, so
a container restart does not sign anyone out and revoking access is one DELETE.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from itsdangerous import BadSignature, URLSafeSerializer
from passlib.context import CryptContext

from app import db
from app.config import settings

log = logging.getLogger(__name__)

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
_signer = URLSafeSerializer(settings.session_secret, salt="sailing-finder-session")

MIN_PASSWORD_LENGTH = 8

#: bcrypt only ever looks at the first 72 bytes. Silently ignoring the rest
#: would mean two different long passwords sharing a prefix both open the same
#: account, so an over-long password is rejected outright instead.
MAX_PASSWORD_BYTES = 72

#: Hash of nothing in particular, used to keep the timing of "no such user" and
#: "wrong password" roughly equal. Built once, lazily.
_DUMMY_HASH: str | None = None


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
def check_password_policy(plain: str) -> None:
    """Raise ValueError if the password cannot be used. Never echoes the value."""
    if not plain or len(plain) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(plain.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes "
            "(bcrypt ignores anything past that)."
        )


def hash_password(plain: str) -> str:
    check_password_policy(plain)
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return _pwd.verify(plain, hashed)
    except ValueError:
        # Malformed hash in the database, or an over-long password. Treat as a
        # failed sign-in; never leak the reason to the caller.
        return False


def dummy_verify() -> None:
    """Burn roughly one bcrypt verification.

    Called when the username does not exist, so that "no such user" and "wrong
    password" take about the same time and cannot be told apart from outside.
    """
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = _pwd.hash("sailing-finder-timing-equaliser")
    _pwd.verify("not-the-password", _DUMMY_HASH)


# ---------------------------------------------------------------------------
# Cookie
# ---------------------------------------------------------------------------
def sign_session_id(sid: str) -> str:
    """What goes in the cookie."""
    return _signer.dumps(sid)


def unsign_session_id(raw: str) -> str | None:
    """Reverse of sign_session_id. None if the value was tampered with."""
    try:
        return _signer.loads(raw)
    except BadSignature:
        return None


def cookie_kwargs() -> dict:
    """Cookie flags, in one place so every set_cookie call matches.

    httponly  — JavaScript cannot read it, so an XSS cannot steal the session
    secure    — HTTPS only in production (off locally, where there is no TLS)
    samesite  — 'lax' blocks cross-site POSTs while keeping normal navigation
    """
    return {
        "key": settings.session_cookie,
        "httponly": True,
        "secure": settings.is_production,
        "samesite": "lax",
        "path": "/",
        "max_age": settings.session_ttl_hours * 3600,
    }


# ---------------------------------------------------------------------------
# Sessions (server-side, in the `sessions` table)
# ---------------------------------------------------------------------------
def create_session(user_id: int, user_agent: str = "", ip: str = "") -> str:
    """Start a session and return its raw id (sign it before it goes in a cookie).

    A fresh id every time, so signing in never reuses the previous session.
    """
    sid = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours)

    db.execute(
        """
        INSERT INTO sessions (sid, user_id, expires_at, user_agent, ip)
             VALUES (%s, %s, %s, %s, %s)
        """,
        (sid, user_id, expires_at, user_agent[:400], ip[:64]),
    )
    return sid


def session_user(sid: str) -> dict | None:
    """The live user behind a session id, or None if it is gone or expired."""
    return db.fetch_one(
        """
        SELECT u.id, u.username, u.name, u.role
          FROM sessions s
          JOIN users u ON u.id = s.user_id
         WHERE s.sid = %s
           AND s.expires_at > now()
           AND u.is_active
        """,
        (sid,),
    )


def touch_session(sid: str) -> None:
    """Sliding expiry — an active user is not signed out mid-task."""
    db.execute(
        """
        UPDATE sessions
           SET last_seen  = now(),
               expires_at = now() + make_interval(hours => %s)
         WHERE sid = %s
        """,
        (settings.session_ttl_hours, sid),
    )


def delete_session(sid: str) -> None:
    db.execute("DELETE FROM sessions WHERE sid = %s", (sid,))


def delete_sessions_for_user(user_id: int) -> int:
    """Sign a user out everywhere. Used when their password changes."""
    return db.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))


def purge_expired_sessions() -> int:
    """Housekeeping. Expired rows are already ignored by session_user()."""
    return db.execute("DELETE FROM sessions WHERE expires_at < now()")


def find_user_by_username(username: str) -> dict | None:
    return db.fetch_one(
        """
        SELECT id, username, name, role, password_hash, is_active
          FROM users
         WHERE username = %s
        """,
        (username.strip().lower(),),
    )
