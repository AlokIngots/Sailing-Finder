"""Sign in / sign out / current session.

The only routes reachable without a session.

SCAFFOLD: login and logout are stubs. Built on feature/login, together with
services/security.py and the React Login screen.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.deps import CurrentUser, require_auth

router = APIRouter()


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


def _not_built(name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"{name} is not built yet.",
    )


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response):
    """Check the password, create a `sessions` row, set the signed cookie.

    A wrong username and a wrong password must fail identically — never tell
    the caller which half was wrong.
    """
    raise _not_built("Login")


@router.post("/logout")
def logout(response: Response, user: CurrentUser = Depends(require_auth)):
    """Delete the `sessions` row and clear the cookie."""
    raise _not_built("Logout")


@router.get("/session")
def whoami(request: Request):
    """Who am I — the React app calls this on boot to decide login vs app.

    Open by design: it answers `null` when signed out rather than 401, so the
    first paint does not look like an error. It returns no schedule data.
    """
    try:
        user = require_auth(request)
    except HTTPException:
        return {"status": "ok", "data": None, "message": ""}

    return {
        "status": "ok",
        "data": {"username": user.username, "name": user.name, "role": user.role},
        "message": "",
    }
