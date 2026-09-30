"""Password hashing and session helpers.

Plain passwords are never stored, never logged, and never returned by any
endpoint. Only the bcrypt hash goes in the database.

The cookie holds a *signed* session id, nothing else — no user id, no role, no
expiry the browser could tamper with. The row in `sessions` is the truth.
"""

from __future__ import annotations

import secrets

from itsdangerous import BadSignature, URLSafeSerializer
from passlib.context import CryptContext

from app.config import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
_signer = URLSafeSerializer(settings.session_secret, salt="sailing-finder-session")

MIN_PASSWORD_LENGTH = 8


def hash_password(plain: str) -> str:
    if not plain or len(plain) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return _pwd.verify(plain, hashed)
    except ValueError:
        # Malformed hash in the database — treat as a failed sign-in, do not
        # leak the reason to the caller.
        return False


def new_session_id() -> str:
    return secrets.token_urlsafe(32)


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
    """Consistent cookie flags everywhere one is set."""
    return {
        "key": settings.session_cookie,
        "httponly": True,
        "secure": settings.is_production,  # HTTPS only in production
        "samesite": "lax",
        "path": "/",
        "max_age": settings.session_ttl_hours * 3600,
    }
