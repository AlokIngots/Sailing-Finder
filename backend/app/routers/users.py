"""Users — the admin-only account screen.

Every route here depends on require_admin, so a signed-in non-admin gets 403
and a signed-out caller gets 401. Hiding the screen in React is a convenience;
this is the boundary.

Passwords arrive once, are hashed by security.hash_password, and are never
stored, logged, or returned. No response carries an id or a hash.
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.deps import CurrentUser, require_admin
from app.services import users

log = logging.getLogger(__name__)

router = APIRouter()

#: Lowercase letters, digits, dot, dash, underscore. Usernames are stored
#: lowercased and login lowercases what is typed, so case never matters.
USERNAME_PATTERN = r"^[a-z0-9._-]+$"


class UserIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    role: Literal["user", "admin"] = "user"
    password: str = Field(min_length=1, max_length=256)


def _envelope(data=None, message: str = "") -> dict:
    return {"status": "ok", "data": data, "message": message}


def _public(row: dict, me: CurrentUser) -> dict:
    return {
        "username": row["username"],
        "name": row["name"] or row["username"],
        "role": row["role"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "is_self": row["username"] == me.username,
    }


@router.get("/users")
def list_users(admin: CurrentUser = Depends(require_admin)) -> dict:
    rows = users.list_active()
    return _envelope([_public(r, admin) for r in rows])


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(body: UserIn, admin: CurrentUser = Depends(require_admin)) -> dict:
    username = body.username.strip().lower()
    name = body.name.strip()
    if len(username) < 2 or not re.fullmatch(USERNAME_PATTERN, username):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Username may use only letters, digits, dot, dash and underscore.",
        )
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Full name is required.")

    try:
        row = users.create(username, name, body.role, body.password)
    except ValueError as exc:
        # The password policy message names the rule, never the value.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    except users.UsernameTaken:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f'There is already a user called "{username}".'
        ) from None

    log.info("user %r added (role %s) by %r", username, body.role, admin.username)
    return _envelope(_public(row, admin), f'Added "{username}".')


@router.delete("/users/{username}")
def remove_user(username: str, admin: CurrentUser = Depends(require_admin)) -> dict:
    username = username.strip().lower()
    if username == admin.username:
        # Also guarantees there is always at least one admin left: the caller
        # is an active admin, and they cannot remove themselves.
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot remove your own account.")

    if not users.deactivate(username):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f'No user called "{username}".')

    log.info("user %r removed by %r", username, admin.username)
    return _envelope(None, f'Removed "{username}".')
