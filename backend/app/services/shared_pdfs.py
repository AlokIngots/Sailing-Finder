"""Schedule PDFs kept for Interakt to fetch.

An Interakt document template takes the document as a URL and downloads it
itself, so the PDF has to be reachable without a session. Code.gs did this by
sharing a Drive file "anyone with the link"; this is the same idea on our own
server:

  - each PDF is stored under UPLOAD_DIR/shared_pdfs/<token>.pdf, where the
    token is 32 random bytes (secrets.token_urlsafe), so the link cannot be
    guessed or enumerated
  - it is served read-only at /shared/<token>.pdf (routers/share.py), and the
    token is checked against a strict pattern before it touches the disk
  - links expire: files older than KEEP_DAYS are deleted whenever a new one is
    written

What is in these files is the public carrier schedule — no customer, rate or
booking data — the same content Code.gs left on Drive.
"""

from __future__ import annotations

import logging
import re
import secrets
import time
from pathlib import Path

from app.config import settings

log = logging.getLogger(__name__)

KEEP_DAYS = 7
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{40,64}$")


def _dir() -> Path:
    path = Path(settings.upload_dir) / "shared_pdfs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def purge_old(now: float | None = None) -> int:
    cutoff = (now or time.time()) - KEEP_DAYS * 86400
    removed = 0
    for f in _dir().glob("*.pdf"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def save(data: bytes) -> str:
    """Store a PDF and return its token."""
    purge_old()
    token = secrets.token_urlsafe(32)
    (_dir() / f"{token}.pdf").write_bytes(data)
    return token


def path_for(token: str) -> Path | None:
    """The file for a token, or None if the token is malformed, unknown or expired."""
    if not TOKEN_RE.fullmatch(token or ""):
        return None
    path = _dir() / f"{token}.pdf"
    if not path.is_file():
        return None
    if path.stat().st_mtime < time.time() - KEEP_DAYS * 86400:
        return None
    return path


def public_url(token: str) -> str:
    return f"{settings.public_url.rstrip('/')}/shared/{token}.pdf"
