"""Account management for the admin Users screen.

Removing a user deactivates the row (is_active = FALSE) and deletes their
sessions; it does not DELETE the row. bookings.created_by points at users.id
with ON DELETE SET NULL, so a hard delete would silently strip the owner off
every booking that person raised. A deactivated user cannot sign in — login and
session_user() both require is_active — and is left out of the list.

Re-adding a removed username reactivates that row with the new name, role and
password, the same way scripts/create_user.py does.
"""

from __future__ import annotations

import logging

from app import db
from app.services import security

log = logging.getLogger(__name__)

ROLES = ("user", "admin")

#: The screen lists everyone at once; this only stops a runaway query.
LIST_LIMIT = 500


class UsernameTaken(Exception):
    """An active account already uses this username."""


def list_active() -> list[dict]:
    return db.fetch_all(
        """
        SELECT username, name, role, created_at
          FROM users
         WHERE is_active
         ORDER BY username
         LIMIT %s
        """,
        (LIST_LIMIT,),
    )


def create(username: str, name: str, role: str, password: str) -> dict:
    """Add an account, or bring back a removed one under the same username.

    Raises ValueError if the password breaks the policy (the message describes
    the rule, never the value) and UsernameTaken if an active account already
    has the username — an existing person is never overwritten from here.
    """
    hashed = security.hash_password(password)

    # The WHERE on DO UPDATE makes this one atomic statement: a fresh username
    # inserts, a removed one is reactivated, and an active one returns no row.
    row = db.fetch_one(
        """
        INSERT INTO users (username, password_hash, name, role)
             VALUES (%s, %s, %s, %s)
        ON CONFLICT (username) DO UPDATE
                SET password_hash = EXCLUDED.password_hash,
                    name          = EXCLUDED.name,
                    role          = EXCLUDED.role,
                    is_active     = TRUE
              WHERE users.is_active = FALSE
          RETURNING id, username, name, role, created_at, (xmax = 0) AS was_inserted
        """,
        (username, hashed, name, role),
    )
    if row is None:
        raise UsernameTaken(username)

    if not row["was_inserted"]:
        # Defensive: deactivation already ended them, but a reactivated
        # account must never inherit an old session.
        security.delete_sessions_for_user(row["id"])

    return {k: row[k] for k in ("username", "name", "role", "created_at")}


def deactivate(username: str) -> bool:
    """Remove an account from use. False if there is no active one by that name."""
    row = db.fetch_one(
        """
        UPDATE users
           SET is_active = FALSE
         WHERE username = %s
           AND is_active
     RETURNING id
        """,
        (username,),
    )
    if row is None:
        return False

    security.delete_sessions_for_user(row["id"])
    return True
