"""Builds the sailing-schedule PDF attached to the Email and WhatsApp shares.

Server-side replacement for the Apps Script PDF export, using reportlab.
Light theme, navy headings — the same brand colours as the app.

SCAFFOLD: not implemented. Built on feature/share.
"""

from __future__ import annotations

#: Brand colours — keep in step with frontend/src/styles/app.css.
NAVY = "#000C2E"
RED = "#BC0300"  # signal only
ORANGE = "#E5531A"  # logo mark only
PAPER = "#FFFFFF"


def build_schedule_pdf(rows, meta=None) -> bytes:
    """Return the PDF as bytes, ready to attach."""
    raise NotImplementedError("pdf is not built yet.")
