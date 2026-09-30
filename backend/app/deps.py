"""Shared FastAPI dependencies.

`require_auth` is the real gate. The React app hiding a view proves nothing —
every /api/* call is checked here, server-side, against the sessions table.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

from app import db
from app.config import settings
from app.services import security


@dataclass(frozen=True)
class CurrentUser:
    id: int
    username: str
    name: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


UNAUTHORISED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Please sign in.",
)


def require_auth(request: Request) -> CurrentUser:
    """Resolve the signed session cookie to a live user, or reject the call."""
    raw = request.cookies.get(settings.session_cookie)
    if not raw:
        raise UNAUTHORISED

    sid = security.unsign_session_id(raw)
    if not sid:
        raise UNAUTHORISED

    row = db.fetch_one(
        """
        SELECT s.sid, u.id, u.username, u.name, u.role
          FROM sessions s
          JOIN users u ON u.id = s.user_id
         WHERE s.sid = %s
           AND s.expires_at > now()
           AND u.is_active
        """,
        (sid,),
    )
    if not row:
        raise UNAUTHORISED

    # Sliding expiry: touch the session so an active user is not signed out
    # mid-task. Cheap enough at our volume.
    db.execute("UPDATE sessions SET last_seen = now() WHERE sid = %s", (sid,))

    return CurrentUser(
        id=row["id"],
        username=row["username"],
        name=row["name"] or row["username"],
        role=row["role"],
    )


def require_admin(user: CurrentUser = Depends(require_auth)) -> CurrentUser:
    """For routes only an admin may call."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this.",
        )
    return user
