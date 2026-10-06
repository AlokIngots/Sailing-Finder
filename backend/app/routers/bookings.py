"""Enquiry -> quotes -> booked -> documents.

Every query is scoped in SQL: `WHERE created_by = %s` for a normal user, no
such clause for role = 'admin'. That scoping is what the isolation check in the
test pass exercises, and it lives here — never in the React app.

SCAFFOLD: handlers are stubs. Built on feature/enquiry and feature/shipment.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app import db
from app.config import MAX_FORWARDERS, settings
from app.deps import CurrentUser, require_auth
from app.routers.schedule import COLUMNS, shape
from app.services import enquiries, enquiry_email, mailer

log = logging.getLogger(__name__)

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
    #: The forwarders ticked in the modal (ids from GET /api/forwarders). Only
    #: these are emailed.
    forwarder_ids: list[Annotated[str, Field(min_length=1, max_length=32)]] = Field(
        min_length=1, max_length=MAX_FORWARDERS
    )


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


@router.get("/enquiry-origin")
def get_enquiry_origin(user: CurrentUser = Depends(require_auth)) -> dict:
    """The port of loading the modal shows — the same label the email uses."""
    return {
        "status": "ok",
        "data": {
            "port": settings.enquiry_origin_port,
            "code": settings.enquiry_origin_code,
            "label": enquiry_email.origin_label(),
        },
        "message": "",
    }


@router.post("/enquiry")
async def create_enquiry(body: EnquiryIn, user: CurrentUser = Depends(require_auth)) -> dict:
    """Email the forwarders ticked in the modal SEPARATELY, from lk.exports@.

    One message per forwarder: To its main address, CC its own colleagues only.
    Never one email with several forwarders on it, and never CC/BCC between them.

    Each enquiry gets a new number (ENQ-0001, ...) that goes in every subject,
    and is saved — with the forwarders it reached — for the rate summary
    (routers/enquiries.py).
    """
    if not settings.forwarders:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "No forwarders are set up yet.")
    chosen = set(body.forwarder_ids)
    unknown = chosen - {f.id for f in settings.forwarders}
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "One of the chosen forwarders is no longer set up. Close the form and open it again.",
        )
    forwarders = [f for f in settings.forwarders if f.id in chosen]  # config order
    if not mailer.is_enquiry_configured():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Enquiry email is not set up yet — the ENQUIRY_SMTP settings are missing.",
        )

    row = db.fetch_one(
        f"SELECT {', '.join(COLUMNS)} FROM schedule WHERE row_key = %s LIMIT 1",
        (body.row_key,),
    )
    if not row:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "That sailing is no longer in the schedule. Refresh the list and pick it again.",
        )

    sailing = shape(row)
    ref = enquiries.next_ref()
    subject, text = enquiry_email.build(sailing, body, ref)
    results = await mailer.send_to_forwarders_separately(forwarders, subject, lambda _f: text)

    reached = [f for f, error in results if error is None]
    sent = [f.name for f in reached]
    failed = [(f.name, error) for f, error in results if error is not None]
    log.info("enquiry %s by %r for %s: %d sent, %d failed", ref, user.username, body.row_key, len(sent), len(failed))
    if not sent:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, failed[0][1])

    message = f"{ref} sent to {', '.join(sent)}"
    if failed:
        message += f" — not sent to {', '.join(name for name, _ in failed)}"

    # The emails have gone. If saving fails now, say so rather than answer an
    # error — an operator who sees an error would send them all again.
    saved = True
    try:
        enquiries.record(ref, sailing, body, user.username, reached)
    except Exception:  # noqa: BLE001 - logged, and the operator is told
        log.exception("enquiry %s was emailed but could not be saved", ref)
        saved = False
        message += f". It could not be saved to the rate summary — note the number {ref}."

    return {
        "status": "ok",
        "data": {"ref": ref, "sent": sent, "failed": [name for name, _ in failed], "saved": saved},
        "message": message,
    }


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
