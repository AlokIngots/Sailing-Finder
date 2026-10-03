"""Builds the sailing-schedule PDF attached to the Email and WhatsApp shares.

Server-side replacement for the Apps Script export in reference/Code.gs
(sendMail / sendWhatsAppPdf), which rendered an HTML table to PDF. Same
content, same order:

    Alok Ingots — Sailing Schedule
    <summary line> | Generated dd-MMM-yyyy HH:mm
    <the table>
    Carrier estimates — please confirm cut-offs before booking.

Light theme in the app's palette: navy for headings and the table header,
orange only in the logo mark, red nowhere (it is a signal colour). Landscape A4
so the eight columns read without squeezing; the header row repeats on every
page.

Only the built-in Helvetica is used, so nothing has to be installed on the
server. It covers Latin-1 — every carrier, vessel and port name the scrapers
produce today.
"""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services import share_text

#: Brand colours — keep in step with frontend/src/styles/app.css.
NAVY = "#000C2E"
RED = "#BC0300"  # signal only — not used in the PDF
ORANGE = "#E5531A"  # logo mark only
PAPER = "#FFFFFF"

GROUND = "#F4F6F9"  # zebra stripe, the app's page ground
BORDER = "#E7EAF0"
MUTED = "#5B6473"
MUTED_2 = "#8A93A3"
OK = "#0F7A4D"  # "Direct", as tagged in the app
INDIRECT = "#4B3B8F"  # "Indirect", as tagged in the app

TITLE = "Alok Ingots — Sailing Schedule"
FOOTNOTE = "Carrier estimates — please confirm cut-offs before booking."
COMPANY = "Alok Ingots (Mumbai) Pvt. Ltd."

#: (heading, width in mm, alignment). Widths fill landscape A4 inside 12 mm margins.
COLUMNS = (
    ("Carrier", 30, TA_LEFT),
    ("Vessel", 52, TA_LEFT),
    ("Voyage", 22, TA_LEFT),
    ("Destination", 66, TA_LEFT),
    ("ETD", 26, TA_LEFT),
    ("ETA", 26, TA_LEFT),
    ("Transit (days)", 26, TA_CENTER),
    ("Type", 25, TA_LEFT),
)

PAGE = landscape(A4)
MARGIN = 12 * mm

_CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=8.5, leading=10.5, textColor=colors.HexColor(NAVY))
_CELL_BOLD = ParagraphStyle("cellb", parent=_CELL, fontName="Helvetica-Bold")
_HEAD = ParagraphStyle("head", parent=_CELL, fontName="Helvetica-Bold", fontSize=8, textColor=colors.white)
_TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=colors.HexColor(NAVY))
_SUB = ParagraphStyle("sub", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.HexColor(MUTED))
_EMPTY = ParagraphStyle("empty", parent=_CELL, alignment=TA_CENTER, textColor=colors.HexColor(MUTED))


def _p(text: str, style: ParagraphStyle, align=None) -> Paragraph:
    if align is not None and align != style.alignment:
        style = ParagraphStyle(f"{style.name}-{align}", parent=style, alignment=align)
    return Paragraph(escape(str(text or "")), style)


def _type_cell(ship_type: str) -> Paragraph:
    label = share_text.type_label(ship_type)
    if not label:
        return _p("", _CELL)
    colour = OK if ship_type == "direct" else INDIRECT
    style = ParagraphStyle(f"type-{ship_type}", parent=_CELL_BOLD, textColor=colors.HexColor(colour))
    return _p(label, style)


def table_rows(rows: list[dict]) -> list[list[str]]:
    """The table as plain strings, in column order. Shared with the tests so
    what is asserted is exactly what is drawn."""
    out = []
    for r in rows:
        vessel, voyage = share_text.tidy_vessel(r)
        out.append(
            [
                r.get("carrier") or "",
                vessel,
                voyage,
                share_text.destination(r),
                share_text.fmt_date(r.get("etd")),
                share_text.fmt_date(r.get("eta")),
                "" if r.get("transit_days") is None else str(r["transit_days"]),
                share_text.type_label(r.get("ship_type")),
            ]
        )
    return out


def _draw_first_page(canvas, doc) -> None:
    """Page 1: the logo mark beside the title, then the usual footer."""
    canvas.saveState()
    # A navy rounded square with the orange block, as in the app header.
    x, top = MARGIN, PAGE[1] - MARGIN
    size = 9 * mm
    canvas.setFillColor(colors.HexColor(NAVY))
    canvas.roundRect(x, top - size, size, size, 1.6 * mm, stroke=0, fill=1)
    inner = 3.5 * mm
    canvas.setFillColor(colors.HexColor(ORANGE))
    canvas.roundRect(x + (size - inner) / 2, top - size + (size - inner) / 2, inner, inner, 0.9 * mm, stroke=0, fill=1)
    canvas.restoreState()
    _draw_page(canvas, doc)


def _draw_page(canvas, doc) -> None:
    """The footer, on every page."""
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor(BORDER))
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN, 9 * mm, PAGE[0] - MARGIN, 9 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor(MUTED_2))
    canvas.drawString(MARGIN, 5.5 * mm, FOOTNOTE)
    canvas.drawRightString(PAGE[0] - MARGIN, 5.5 * mm, f"{COMPANY}  ·  Page {doc.page}")

    canvas.restoreState()


def build_schedule_pdf(rows: list[dict], meta: dict | None = None, *, compress: bool = True) -> bytes:
    """Return the PDF as bytes, ready to attach.

    `rows` are shaped sailings (routers/schedule.shape). `meta` carries the
    summary `line` and the `generated` stamp; both are optional so a preview
    can be drawn from rows alone. `compress=False` leaves the page streams
    readable, which is what the tests search.
    """
    meta = meta or {}
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=PAGE,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=14 * mm,
        title=TITLE,
        author=COMPANY,
        subject=meta.get("line") or "Sailing schedule",
        pageCompression=1 if compress else 0,
        invariant=not compress,
    )

    indent = 12 * mm  # clear of the logo mark drawn by _draw_page
    title = ParagraphStyle("title-in", parent=_TITLE, leftIndent=indent)
    sub = ParagraphStyle("sub-in", parent=_SUB, leftIndent=indent)
    summary = " | ".join(
        part for part in (meta.get("line"), f"Generated {meta['generated']}" if meta.get("generated") else "") if part
    )

    story = [_p(TITLE, title), _p(summary, sub), Spacer(1, 6 * mm)]

    header = [_p(name, _HEAD, align) for name, _, align in COLUMNS]
    body = []
    for cells, row in zip(table_rows(rows), rows):
        line = [_p(text, _CELL_BOLD if i == 0 else _CELL, COLUMNS[i][2]) for i, text in enumerate(cells[:-1])]
        line.append(_type_cell(row.get("ship_type")))
        body.append(line)

    if not body:
        body = [[_p("No sailings match these filters.", _EMPTY)] + [""] * (len(COLUMNS) - 1)]

    table = Table([header] + body, colWidths=[w * mm for _, w, _ in COLUMNS], repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor(BORDER)),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(BORDER)),
    ]
    for i in range(2, len(body) + 1, 2):  # zebra, counting the header as row 0
        style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor(GROUND)))
    if not rows:
        style.append(("SPAN", (0, 1), (-1, 1)))
    table.setStyle(TableStyle(style))
    story.append(table)

    doc.build(story, onFirstPage=_draw_first_page, onLaterPages=_draw_page)
    return buffer.getvalue()
