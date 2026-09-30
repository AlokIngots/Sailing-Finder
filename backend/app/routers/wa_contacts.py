"""Saved WhatsApp numbers for the share dropdown.

`number` is stored as digits including country code — no +, no spaces.

SCAFFOLD: handlers are stubs. Built on feature/share.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.deps import CurrentUser, require_auth

router = APIRouter()


def _not_built(name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"{name} is not built yet.",
    )


class ContactIn(BaseModel):
    name: str = Field(default="", max_length=120)
    number: str = Field(min_length=6, max_length=20)


@router.get("/wa-contacts")
def list_contacts(user: CurrentUser = Depends(require_auth)):
    raise _not_built("WhatsApp contacts")


@router.post("/wa-contacts")
def save_contact(body: ContactIn, user: CurrentUser = Depends(require_auth)):
    """Remember a number. Upsert on `number`, so saving twice is harmless."""
    raise _not_built("Save WhatsApp contact")
