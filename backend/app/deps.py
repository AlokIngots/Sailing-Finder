"""Shared FastAPI dependencies.

`require_auth` is the real gate. The React app hiding a view proves nothing —
every /api/* call is checked here, server-side, against the sessions table.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

from app.config import settings
from app.services import security


@dataclass(frozen=True)
class CurrentUser:
    id: int
    username: str
    name: str
    role: str
    sid: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def public(self) -> dict:
        """What may be sent to the browser. No id, no session id, no hash."""
        return {"username": self.username, "name": self.name, "role": self.role}


def _unauthorised() -> HTTPException:
    # One message for every failure mode — expired, forged, revoked, absent.
    # Which one it was is server-side knowledge.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Please sign in.",
    )


def require_auth(request: Request) -> CurrentUser:
    """Resolve the signed session cookie to a live user, or reject the call."""
    raw = request.cookies.get(settings.session_cookie)
    if not raw:
        raise _unauthorised()

    sid = security.unsign_session_id(raw)
    if not sid:
        raise _unauthorised()

    row = security.session_user(sid)
    if not row:
        raise _unauthorised()

    security.touch_session(sid)

    return CurrentUser(
        id=row["id"],
        username=row["username"],
        name=row["name"] or row["username"],
        role=row["role"],
        sid=sid,
    )


def require_admin(user: CurrentUser = Depends(require_auth)) -> CurrentUser:
    """For routes only an admin may call."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this.",
        )
    return user
