"""WhatsApp via the Interakt HTTP API — same template flow as the Apps Script
version. The API key comes from .env and is never logged.

SCAFFOLD: not implemented. Built on feature/share.
"""

from __future__ import annotations

import logging

from app.config import settings

log = logging.getLogger(__name__)

API_URL = "https://api.interakt.ai/v1/public/message/"


def normalise_number(raw: str, country_code: str | None = None) -> str:
    """Digits only, country code prefixed, no + and no spaces."""
    country_code = country_code or settings.interakt_country
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if not digits:
        return ""
    return f"{country_code}{digits}" if len(digits) <= 10 else digits


async def send_template(number: str, params: list[str], pdf_url: str = "") -> dict:
    raise NotImplementedError("whatsapp is not built yet.")
