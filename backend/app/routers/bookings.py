"""Enquiry -> quotes -> booked -> documents.

Every query is scoped in SQL: `WHERE created_by = %s` for a normal user, no
such clause for role = 'admin'. That scoping is what the isolation check in the
test pass exercises, and it lives here — never in the React app.

SCAFFOLD: handlers are stubs. Built on feature/enquiry and feature/shipment.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.deps import CurrentUser, require_auth

router = APIRouter()


def _not_built(name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"{name} is not built yet.",
    )


class EnquiryIn(BaseModel):
    """The enquiry modal.

    stuffing, target_rate_remarks, net_wt and gross_wt are operator-judgement
    fields: free text, deliberately unvalidated beyond a length cap. If a value
    looks wrong that is raised in conversation, not blocked by the software.
    """

    row_key: str = Field(min_length=1, max_length=256)
    stuffing: str = Field(default="", max_length=200)
    container: str = Field(default="", max_length=200)
    net_wt: str = Field(default="", max_length=100)
    gross_wt: str = Field(default="", max_length=100)
    commodity: str = Field(default="", max_length=200)
    remarks: str = Field(default="", max_length=2000)


class QuoteIn(BaseModel):
    forwarder_id: str = Field(min_length=1, max_length=32)
    rate: str = Field(default="", max_length=100)  # operator judgement, free
    note: str = Field(default="", max_length=1000)


class QuotesIn(BaseModel):
    quotes: list[QuoteIn]


class ChooseIn(BaseModel):
    forwarder_id: str = Field(min_length=1, max_length=32)


@router.get("/bookings")
def list_bookings(user: CurrentUser = Depends(require_auth), limit: int = 200):
    """This user's bookings, newest first. Admin sees everyone's. Bounded."""
    raise _not_built("Bookings list")


@router.post("/enquiry")
def create_enquiry(body: EnquiryIn, user: CurrentUser = Depends(require_auth)):
    """Email all three forwarders SEPARATELY, then log the booking at stage=sent.

    Separate messages, never one email with all three addresses on it, and never
    CC/BCC between them.
    """
    raise _not_built("Enquiry")


@router.post("/bookings/{ref}/quotes")
def save_quotes(ref: str, body: QuotesIn, user: CurrentUser = Depends(require_auth)):
    """Save each forwarder's rate and note. Moves the booking to stage=quotes."""
    raise _not_built("Quotes")


@router.post("/bookings/{ref}/choose")
def choose_forwarder(ref: str, body: ChooseIn, user: CurrentUser = Depends(require_auth)):
    """Mark the winner. Moves the booking to stage=booked."""
    raise _not_built("Choose forwarder")


@router.post("/bookings/{ref}/documents")
def send_documents(
    ref: str,
    pl: UploadFile = File(..., description="Packing List"),
    ci: UploadFile = File(..., description="Commercial Invoice"),
    vgm: UploadFile = File(..., description="Verified Gross Mass"),
    user: CurrentUser = Depends(require_auth),
):
    """Store the three documents and email them to the chosen forwarder.

    Uploads go to UPLOAD_DIR, which is a gitignored volume outside the image.
    Moves the booking to stage=docs.
    """
    raise _not_built("Send documents")
