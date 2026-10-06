"""Saved WhatsApp numbers and email addresses for the share dropdowns.

Per user: each user sees the numbers and addresses they have sent to, most
recently used first; an admin sees everyone's (services/saved_contacts.py).
Sends remember their recipient automatically (routers/share.py); the POSTs
here save one without sending.

A WhatsApp `number` is digits including country code — no +, no spaces.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.deps import CurrentUser, require_auth
from app.services import saved_contacts

router = APIRouter()


class ContactIn(BaseModel):
    name: str = Field(default="", max_length=120)
    number: str = Field(min_length=6, max_length=20)


class EmailContactIn(BaseModel):
    name: str = Field(default="", max_length=120)
    email: str = Field(min_length=3, max_length=254)


def _ok(data, message: str = "") -> dict:
    return {"status": "ok", "data": data, "message": message}


@router.get("/wa-contacts")
def list_contacts(user: CurrentUser = Depends(require_auth)) -> dict:
    rows = saved_contacts.list_for(user, saved_contacts.WA)
    return _ok([{"name": r["name"], "number": r["value"]} for r in rows])


@router.post("/wa-contacts")
def save_contact(body: ContactIn, user: CurrentUser = Depends(require_auth)) -> dict:
    """Remember a number for this user. Saving twice is harmless."""
    try:
        digits = saved_contacts.remember(user.username, saved_contacts.WA, body.number, body.name)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    return _ok({"name": body.name.strip(), "number": digits}, "Saved.")


@router.get("/email-contacts")
def list_email_contacts(user: CurrentUser = Depends(require_auth)) -> dict:
    rows = saved_contacts.list_for(user, saved_contacts.EMAIL)
    return _ok([{"name": r["name"], "email": r["value"]} for r in rows])


@router.post("/email-contacts")
def save_email_contact(body: EmailContactIn, user: CurrentUser = Depends(require_auth)) -> dict:
    """Remember an address for this user. Saving twice is harmless."""
    try:
        email = saved_contacts.remember(user.username, saved_contacts.EMAIL, body.email, body.name)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    return _ok({"name": body.name.strip(), "email": email}, "Saved.")
