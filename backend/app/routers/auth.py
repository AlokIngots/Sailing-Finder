"""Sign in, sign out, and who-am-I.

/api/login is the only route reachable without a session. /api/logout and
/api/me both require one.

A wrong username and a wrong password fail identically — same status, same
message, and roughly the same time — so the endpoint cannot be used to find out
which usernames exist.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.deps import CurrentUser, require_auth
from app.services import security

log = logging.getLogger(__name__)

router = APIRouter()

BAD_CREDENTIALS = "Username or password is incorrect."


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


def _envelope(data=None, message: str = "") -> dict:
    return {"status": "ok", "data": data, "message": message}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response) -> dict:
    """Verify the credentials, create a session row, set the cookie."""
    username = body.username.strip().lower()
    row = security.find_user_by_username(username)

    if row is None or not row["is_active"]:
        # Burn a comparable amount of time so a missing user and a wrong
        # password are indistinguishable from outside.
        security.dummy_verify()
        log.info("failed sign-in for %r (no such active user)", username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, BAD_CREDENTIALS)

    if not security.verify_password(body.password, row["password_hash"]):
        log.info("failed sign-in for %r (wrong password)", username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, BAD_CREDENTIALS)

    sid = security.create_session(
        row["id"],
        user_agent=request.headers.get("user-agent", ""),
        ip=(request.client.host if request.client else ""),
    )
    response.set_cookie(value=security.sign_session_id(sid), **security.cookie_kwargs())

    log.info("signed in: %r", username)
    return _envelope(
        {"username": row["username"], "name": row["name"] or row["username"], "role": row["role"]}
    )


@router.post("/logout")
def logout(response: Response, user: CurrentUser = Depends(require_auth)) -> dict:
    """Delete the session row, then clear the cookie.

    The row goes first: if the response is lost in transit the session is still
    dead server-side, which is the safe way round.
    """
    security.delete_session(user.sid)

    flags = security.cookie_kwargs()
    response.delete_cookie(
        key=flags["key"],
        path=flags["path"],
        httponly=flags["httponly"],
        secure=flags["secure"],
        samesite=flags["samesite"],
    )

    log.info("signed out: %r", user.username)
    return _envelope(None, "Signed out.")


@router.get("/me")
def me(user: CurrentUser = Depends(require_auth)) -> dict:
    """The signed-in user's name and role. 401 when there is no live session."""
    return _envelope(user.public())
