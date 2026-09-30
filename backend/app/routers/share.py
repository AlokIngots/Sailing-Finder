"""Sharing the filtered sailing list: email and WhatsApp.

Copy-list and CSV download happen in the browser from data it already has, so
they need no endpoint. The PDF is built server-side by services/pdf.py.

SCAFFOLD: handlers are stubs. Built on feature/share.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.deps import CurrentUser, require_auth

router = APIRouter()

MAX_RECIPIENTS = 20  # bulk sends are bounded


def _not_built(name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"{name} is not built yet.",
    )


class Filters(BaseModel):
    """The finder's current filter state, so the server rebuilds exactly the
    list the user is looking at rather than trusting rows posted by the browser."""

    country: str | None = None
    pod_code: str | None = None
    carrier: str | None = None
    etd_from: str | None = None
    etd_to: str | None = None
    eta_from: str | None = None
    eta_to: str | None = None
    routing: str = "all"
    mode: str = "all"
    sort: str = "etd"


class EmailIn(BaseModel):
    to: list[EmailStr] = Field(min_length=1, max_length=MAX_RECIPIENTS)
    subject: str = Field(default="", max_length=300)
    note: str = Field(default="", max_length=2000)
    filters: Filters


class WhatsAppIn(BaseModel):
    number: str = Field(min_length=6, max_length=20)
    save: bool = False
    name: str = Field(default="", max_length=120)
    filters: Filters


@router.post("/share/email")
def share_email(body: EmailIn, user: CurrentUser = Depends(require_auth)):
    """The filtered list as an email, with the schedule PDF attached."""
    raise _not_built("Email these")


@router.post("/share/whatsapp")
def share_whatsapp(body: WhatsAppIn, user: CurrentUser = Depends(require_auth)):
    """Interakt template message carrying the schedule PDF."""
    raise _not_built("WhatsApp share")
