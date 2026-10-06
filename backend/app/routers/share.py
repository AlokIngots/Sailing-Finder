"""Sharing the filtered sailing list: email and WhatsApp, both carrying the
schedule PDF — sendMail() and sendWhatsAppPdf() in reference/Code.gs.

The browser sends its filter state, never rows: the server rebuilds exactly
the list on screen with the same query the finder uses (routers/schedule.py),
so what is sent cannot be edited on the way.

Copy list and CSV download happen in the browser from data it already has, so
they need no endpoint.

GET /api/share/pdf draws the same PDF without sending it — a preview that works
before any SMTP or Interakt key exists.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, EmailStr, Field, field_validator

from app import db
from app.deps import CurrentUser, require_auth
from app.routers.schedule import build_schedule_query, shape
from app.services import mailer, pdf, saved_contacts, share_text, shared_pdfs, whatsapp

log = logging.getLogger(__name__)

router = APIRouter()

#: Served outside /api, with no session: the link Interakt downloads the PDF
#: from. See services/shared_pdfs.py.
public_router = APIRouter()

MAX_RECIPIENTS = 20  # bulk sends are bounded

NOTHING_TO_SEND = "No sailings to send — adjust the filters."


class Filters(BaseModel):
    """The finder's current filter state, so the server rebuilds exactly the
    list the user is looking at rather than trusting rows posted by the browser."""

    country: str | None = None
    pod_code: str | None = None
    carrier: str | None = None
    etd_from: date | None = None
    etd_to: date | None = None
    eta_from: date | None = None
    eta_to: date | None = None
    routing: Literal["all", "direct", "indirect"] = "all"
    mode: Literal["all", "next_per_port"] = "all"
    sort: Literal["etd", "transit", "eta"] = "etd"

    @field_validator("etd_from", "etd_to", "eta_from", "eta_to", mode="before")
    @classmethod
    def _blank_date(cls, value):
        # The finder sends '' for an empty date box.
        return None if value in ("", None) else value


class EmailIn(BaseModel):
    to: list[EmailStr] = Field(min_length=1, max_length=MAX_RECIPIENTS)
    subject: str = Field(default="", max_length=300)
    note: str = Field(default="", max_length=2000)
    #: Optional contact name, saved with the address when there is one recipient.
    name: str = Field(default="", max_length=120)
    filters: Filters


class WhatsAppIn(BaseModel):
    number: str = Field(min_length=6, max_length=20)
    #: Optional contact name, saved with the number.
    name: str = Field(default="", max_length=120)
    filters: Filters


def _remember(user: CurrentUser, kind: str, value: str, name: str) -> None:
    """Save a recipient to this user's list after a successful send. The
    message has already gone, so a failure here is logged, never reported as
    a failed send."""
    try:
        saved_contacts.remember(user.username, kind, value, name)
    except Exception:  # noqa: BLE001 - logged; the send itself succeeded
        log.exception("could not save %s contact for %r", kind, user.username)


def _rows(filters: Filters) -> list[dict]:
    sql, params = build_schedule_query(**filters.model_dump())
    return [shape(r) for r in db.fetch_all(sql, params)]


def _render(filters: Filters) -> tuple[list[dict], str, bytes, str]:
    """(rows, where, pdf bytes, file name) for the current filters."""
    rows = _rows(filters)
    where = share_text.where_label(filters, rows)
    when = share_text.now_local()
    meta = {
        "line": share_text.summary_line(where, len(rows)),
        "generated": share_text.generated_stamp(when),
    }
    return rows, where, pdf.build_schedule_pdf(rows, meta), share_text.pdf_filename(when)


@router.get("/share/pdf")
def preview_pdf(filters: Annotated[Filters, Query()], user: CurrentUser = Depends(require_auth)) -> Response:
    """The PDF for the current filters, shown in the browser. Sends nothing."""
    _, _, data, filename = _render(filters)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/share/email")
async def share_email(body: EmailIn, user: CurrentUser = Depends(require_auth)) -> dict:
    """The filtered list as an email, with the schedule PDF attached.

    Each address gets its own message, so customers on one send never see
    each other's addresses.
    """
    if not mailer.is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Email is not set up yet — the SMTP settings are missing.")

    rows, where, data, filename = _render(body.filters)
    if not rows:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, NOTHING_TO_SEND)

    subject = body.subject.strip() or share_text.email_subject(where)
    text = share_text.email_body(where, rows, note=body.note)
    attachment = [(filename, data, "application/pdf")]

    sent, failed = [], []
    for address in dict.fromkeys(str(a) for a in body.to):  # de-duplicated, order kept
        try:
            await mailer.send_mail(address, subject, text, attachment)
            sent.append(address)
        except mailer.MailSendFailed as exc:
            failed.append((address, str(exc)))

    for address in sent:
        _remember(user, saved_contacts.EMAIL, address, body.name if len(sent) == 1 else "")

    log.info("share/email by %r: %d sent, %d failed, %d sailings", user.username, len(sent), len(failed), len(rows))
    if failed and not sent:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, failed[0][1])

    message = f"Email sent to {', '.join(sent)}"
    if failed:
        message += f" — not sent to {', '.join(a for a, _ in failed)}"
    return {"status": "ok", "data": {"sent": sent, "failed": [a for a, _ in failed], "count": len(rows)}, "message": message}


@router.post("/share/whatsapp")
async def share_whatsapp(body: WhatsAppIn, user: CurrentUser = Depends(require_auth)) -> dict:
    """Interakt template message carrying the schedule PDF. The number is saved
    to this user's list once the send has gone through."""
    digits = whatsapp.normalise_number(body.number)
    if not digits:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please enter a valid WhatsApp number.")
    if not whatsapp.is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "WhatsApp is not set up yet — the Interakt settings are missing.")

    rows, where, data, filename = _render(body.filters)
    if not rows:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, NOTHING_TO_SEND)

    token = shared_pdfs.save(data)
    try:
        await whatsapp.send_template(
            digits,
            shared_pdfs.public_url(token),
            filename,
            share_text.whatsapp_body_values(where, len(rows)),
        )
    except whatsapp.WhatsAppSendFailed as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None

    _remember(user, saved_contacts.WA, digits, body.name)

    log.info("share/whatsapp by %r to +%s, %d sailings", user.username, digits, len(rows))
    return {"status": "ok", "data": {"to": f"+{digits}", "count": len(rows)}, "message": f"Sent to +{digits}"}


@public_router.get("/shared/{name}", include_in_schema=False)
def shared_pdf(name: str, request: Request):
    """The PDF behind a WhatsApp message, for Interakt to download. No session;
    the unguessable token in the name is the only key, and it expires."""
    token = name[:-4] if name.endswith(".pdf") else ""
    path = shared_pdfs.path_for(token)
    if path is None:
        # A plain response, not HTTPException: main.py's handler re-raises
        # HTTP errors outside /api, which would surface as a 500.
        return Response(status_code=status.HTTP_404_NOT_FOUND, content="Not found", media_type="text/plain")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename="Sailing_Schedule.pdf",
        content_disposition_type="inline",
        headers={"X-Robots-Tag": "noindex", "Cache-Control": "private, max-age=86400"},
    )
