"""Each user's saved WhatsApp numbers and email addresses for the share boxes —
the saved_contacts table.

Who sees what is decided HERE, in SQL: a normal user's list carries
`AND username = %s`, an admin's does not (one entry per value, the most
recently used). Same rule as enquiries and My bookings.

Values are stored normalised, so the same recipient typed two ways is one
entry: WhatsApp numbers as digits with the country code (whatsapp.normalise_number),
emails trimmed and lower-cased. Sending to a saved value again only moves it
to the top and, if a name came with it, updates the name.
"""

from __future__ import annotations

from app import db
from app.deps import CurrentUser
from app.services import whatsapp

WA = "wa"
EMAIL = "email"

LIST_LIMIT = 500
MAX_NAME = 120


def normalise(kind: str, raw: str) -> str:
    """The stored form of a number or address; '' when there is nothing usable."""
    if kind == WA:
        return whatsapp.normalise_number(raw)
    return (raw or "").strip().lower()


def list_for(user: CurrentUser, kind: str) -> list[dict]:
    """[{name, value}], most recently used first."""
    if user.is_admin:
        rows = db.fetch_all(
            """
            SELECT name, value FROM (
              SELECT DISTINCT ON (value) name, value, last_used_at
                FROM saved_contacts
               WHERE kind = %s
               ORDER BY value, last_used_at DESC
            ) latest
            ORDER BY last_used_at DESC
            LIMIT %s
            """,
            (kind, LIST_LIMIT),
        )
    else:
        rows = db.fetch_all(
            """
            SELECT name, value
              FROM saved_contacts
             WHERE kind = %s AND username = %s
             ORDER BY last_used_at DESC, id DESC
             LIMIT %s
            """,
            (kind, user.username, LIST_LIMIT),
        )
    return [{"name": r["name"] or "", "value": r["value"]} for r in rows]


def remember(username: str, kind: str, raw: str, name: str = "") -> str:
    """Save a number/address for this user, or bump it to the top if already
    saved. Returns the stored value; ValueError if there is nothing usable."""
    value = normalise(kind, raw)
    if not value:
        raise ValueError("Please enter a valid WhatsApp number." if kind == WA else "Please enter an email address.")
    db.execute(
        """
        INSERT INTO saved_contacts (username, kind, value, name)
             VALUES (%s, %s, %s, %s)
        ON CONFLICT (username, kind, value) DO UPDATE
              SET last_used_at = now(),
                  name = COALESCE(NULLIF(EXCLUDED.name, ''), saved_contacts.name)
        """,
        (username, kind, value, (name or "").strip()[:MAX_NAME]),
    )
    return value
