"""Saved WhatsApp numbers for the share dropdown — getWaContacts() and
saveWaContact() in reference/Code.gs, on the wa_contacts table.

Numbers are stored normalised (digits, country code in front, no +), so the
same person typed two ways is one entry. Saving an existing number is a no-op,
as in Code.gs: the first label sticks.
"""

from __future__ import annotations

from app import db
from app.services import whatsapp

LIST_LIMIT = 500


def list_all() -> list[dict]:
    rows = db.fetch_all(
        """
        SELECT name, number
          FROM wa_contacts
         ORDER BY lower(coalesce(nullif(name, ''), number)), number
         LIMIT %s
        """,
        (LIST_LIMIT,),
    )
    return [{"name": r["name"] or "", "number": r["number"]} for r in rows]


def save(name: str, number: str) -> str:
    """Remember a number. Returns the normalised digits; ValueError if unusable."""
    digits = whatsapp.normalise_number(number)
    if not digits:
        raise ValueError("Please enter a valid WhatsApp number.")
    db.execute(
        """
        INSERT INTO wa_contacts (name, number)
             VALUES (%s, %s)
        ON CONFLICT (number) DO NOTHING
        """,
        ((name or "").strip()[:120], digits),
    )
    return digits
