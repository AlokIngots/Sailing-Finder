"""The enquiry email a forwarder receives.

This is the server's copy of buildEmail() in
frontend/src/components/EnquiryModal.jsx, which shows the operator the email in
the "Review & send" pane. The two must produce the same text — what the
operator reviewed is what the forwarders get. Change both together.

The sailing comes from the database (by row_key), never from the browser; only
the operator-judgement fields come from the form, as free text.

The port of loading is NOT read from the sailing: we always load at
ENQUIRY_ORIGIN_PORT / ENQUIRY_ORIGIN_CODE, and origin_label() is the only
place that turns those into text. The modal gets the same label from
GET /api/enquiry-origin.
"""

from __future__ import annotations

import re
from datetime import date

from app.config import settings

#: Fixed English month names — strftime('%b') follows the server locale.
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def origin_label() -> str:
    """'Nhava Sheva (INNSA)', from the config — never from a sailing row."""
    port, code = settings.enquiry_origin_port, settings.enquiry_origin_code
    return f"{port} ({code})" if code else port


def format_date(value) -> str:
    """'2026-10-05' -> '5 Oct 2026', as formatDate() in lib/format.js. '' if empty."""
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            return ""
    return f"{value.day} {_MONTHS[value.month - 1]} {value.year}"


def tidy_vessel(sailing: dict) -> tuple[str, str]:
    """(vessel, voyage), as tidyVessel() in lib/format.js: bracketed text comes
    off the vessel name, and a bracketed voyage like '(270E)' fills a missing one."""
    raw = sailing.get("vessel_name") or ""
    voyage = sailing.get("voyage_no") or ""
    in_brackets = re.search(r"\((\d{2,}[A-Z])\)", raw)
    if not voyage and in_brackets:
        voyage = in_brackets.group(1)
    vessel = re.sub(r"\s*\([^)]*\)", "", raw).strip()
    return vessel or raw, voyage


def destination(sailing: dict) -> str:
    """'Genoa, Italy' — the port of discharge, with its country when known."""
    port = sailing.get("pod_name") or sailing.get("pod_code") or ""
    return f"{port}, {sailing['country']}" if sailing.get("country") else port


def subject(ref: str, sailing: dict) -> str:
    """'Rate Enquiry ENQ-0001 — Nhava Sheva to Genoa, Italy'. The ref is how a
    forwarder's reply is matched back to its enquiry, so it is always here."""
    return f"Rate Enquiry {ref} — {settings.enquiry_origin_port} to {destination(sailing)}"


def build(sailing: dict, fields, ref: str) -> tuple[str, str]:
    """(subject, body) for a shaped sailing (routers.schedule.shape), the
    enquiry form (routers.bookings.EnquiryIn) and the enquiry's ref."""
    vessel, voyage = tidy_vessel(sailing)
    where = destination(sailing)
    origin = origin_label()
    transit = sailing.get("transit_days")
    carrier = sailing.get("carrier") or ""

    lines = [
        "We would like to book the shipment below. Please send your best all-in rate "
        "and the latest booking cut-off for this vessel.",
        "",
        f"Carrier: {carrier}",
        f"Vessel / voyage: {vessel}{f' / {voyage}' if voyage else ''}",
        f"From: {origin}",
        f"To: {where}{f' ({sailing['pod_code']})' if sailing.get('pod_code') else ''}",
        f"ETD: {format_date(sailing.get('etd')) or '—'}   ETA: {format_date(sailing.get('eta')) or '—'}"
        + (f"   Transit: {transit} days" if isinstance(transit, int) else ""),
    ]
    if fields.stuffing:
        lines.append(f"Stuffing date: {fields.stuffing}")
    if fields.container:
        lines.append(f"Containers: {fields.container}")
    if fields.commodity:
        lines.append(f"Commodity: {fields.commodity}")
    if fields.net_wt or fields.gross_wt:
        gross = f" / {fields.gross_wt} gross" if fields.gross_wt else ""
        lines.append(f"Weight: {fields.net_wt or '—'} net{gross}")
    if fields.remarks:
        lines.append(f"Remarks: {fields.remarks}")
    lines += [
        "",
        "Please confirm space and quote by return.",
        "",
        "Warm regards,",
        "Export Team",
        "Alok Ingots (Mumbai) Pvt. Ltd.",
    ]
    return subject(ref, sailing), "\n".join(lines)
