"""Saved WhatsApp numbers for the share dropdown.

`number` is stored as digits including country code — no +, no spaces.
Shared across all users, as in the Apps Script version.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.deps import CurrentUser, require_auth
from app.services import wa_contacts

router = APIRouter()


class ContactIn(BaseModel):
    name: str = Field(default="", max_length=120)
    number: str = Field(min_length=6, max_length=20)


@router.get("/wa-contacts")
def list_contacts(user: CurrentUser = Depends(require_auth)) -> dict:
    return {"status": "ok", "data": wa_contacts.list_all(), "message": ""}


@router.post("/wa-contacts")
def save_contact(body: ContactIn, user: CurrentUser = Depends(require_auth)) -> dict:
    """Remember a number. Upsert on `number`, so saving twice is harmless."""
    try:
        digits = wa_contacts.save(body.name, body.number)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    return {"status": "ok", "data": {"name": body.name.strip(), "number": digits}, "message": "Saved."}
