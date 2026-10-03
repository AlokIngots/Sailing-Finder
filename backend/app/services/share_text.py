"""Wording for the Email and WhatsApp shares, and the PDF built for both.

Ported from the browser half of reference/Index.html (whereLabel, buildText,
the `brief` passed to Code.gs) so the server now says exactly what the Apps
Script version said. Kept in one place so the email, the WhatsApp message and
the PDF describe a sailing the same way.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from app.config import settings

ORIGIN = "Nhava Sheva"
DEFAULT_WHERE = "Europe & Mediterranean"
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def now_local() -> datetime:
    """Now, in the app's timezone (Asia/Kolkata unless TZ says otherwise)."""
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(settings.timezone))
    except Exception:  # noqa: BLE001 - no tz database: IST is the only zone we run in
        return datetime.now(timezone(timedelta(hours=5, minutes=30)))


def _as_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def fmt_date(value) -> str:
    """'3 Oct 2026', the reference's fmt(). Em dash when missing."""
    d = _as_date(value)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}" if d else "—"


def generated_stamp(when: datetime | None = None) -> str:
    """'03-Oct-2026 15:30' — Code.gs: dd-MMM-yyyy HH:mm."""
    when = when or now_local()
    return f"{when.day:02d}-{MONTHS[when.month - 1]}-{when.year} {when:%H:%M}"


def pdf_filename(when: datetime | None = None) -> str:
    """'Sailing_Schedule_03102026_1530.pdf' — Code.gs: ddMMyyyy_HHmm."""
    when = when or now_local()
    return f"Sailing_Schedule_{when:%d%m%Y_%H%M}.pdf"


def tidy_vessel(row: dict) -> tuple[str, str]:
    """Vessel without its bracketed suffix; a bracketed voyage like "(270E)"
    fills a missing voyage number. Same as tidy() in the reference."""
    raw = row.get("vessel_name") or ""
    voyage = row.get("voyage_no") or ""
    match = re.search(r"\((\d{2,}[A-Z])\)", raw)
    if not voyage and match:
        voyage = match.group(1)
    vessel = re.sub(r"\s*\([^)]*\)", "", raw).strip()
    return (vessel or raw), voyage


def destination(row: dict) -> str:
    """'Rotterdam, Netherlands'."""
    port = row.get("pod_name") or row.get("pod_code") or ""
    country = row.get("country") or ""
    return f"{port}, {country}" if country else port


def type_label(ship_type: str | None) -> str:
    return {"direct": "Direct", "indirect": "Indirect"}.get(ship_type or "", "")


def where_label(filters, rows: list[dict]) -> str:
    """Where the list is going, for the subject and summary — whereLabel()."""
    pod = (getattr(filters, "pod_code", None) or "").strip().upper()
    if pod:
        hit = next((r for r in rows if (r.get("pod_code") or "").upper() == pod), None)
        return destination(hit) if hit else DEFAULT_WHERE
    country = (getattr(filters, "country", None) or "").strip()
    return country or DEFAULT_WHERE


def plural(n: int) -> str:
    return f"{n} sailing{'' if n == 1 else 's'}"


def summary_line(where: str, count: int) -> str:
    """The PDF's summary and the brief.line — 'Sailing schedule — Nhava Sheva
    to Italy · 12 sailings'."""
    return f"Sailing schedule — {ORIGIN} to {where} · {plural(count)}"


def email_subject(where: str) -> str:
    return f"Sailing schedule — {ORIGIN} to {where}"


def email_body(where: str, rows: list[dict], today: date | None = None, note: str = "") -> str:
    """buildText() from the reference, with an optional note on top."""
    today = today or now_local().date()
    lines = []
    for r in rows:
        vessel, voyage = tidy_vessel(r)
        transit = r.get("transit_days")
        lines.append(
            f"• {vessel}{f' ({voyage})' if voyage else ''} — {r.get('carrier') or ''}"
            f" — to {destination(r)} — Departs {fmt_date(r.get('etd'))},"
            f" Arrives {fmt_date(r.get('eta'))}{f' ({transit} days)' if transit is not None else ''}"
        )
    parts = []
    if note.strip():
        parts += [note.strip(), ""]
    parts += [
        f"Sailing schedule from {ORIGIN} to {where}",
        f"{len(rows)} sailing(s), as of {fmt_date(today)}",
        "",
        *lines,
        "",
        "Carrier estimates — please confirm cut-offs before booking.",
        "",
        "Export Team",
    ]
    return "\n".join(parts)


def whatsapp_body_values(where: str, count: int, today: date | None = None) -> list[str]:
    """The sailing_schedule template's body variables, in the reference's order."""
    today = today or now_local().date()
    return [where, fmt_date(today), str(count)]
