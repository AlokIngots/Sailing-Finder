"""WhatsApp via the Interakt HTTP API — same template flow as sendWhatsAppPdf()
in reference/Code.gs. Settings come from .env (INTERAKT_API_KEY,
INTERAKT_TEMPLATE_NAME, INTERAKT_TEMPLATE_LANG, INTERAKT_COUNTRY_CODE); the API
key is never logged.

Interakt fetches the PDF itself from `headerValues[0]`, so the PDF has to be at
a public URL. Code.gs shared a Drive file "anyone with the link"; here it is
services/shared_pdfs.py behind an unguessable link.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

log = logging.getLogger(__name__)

API_URL = "https://api.interakt.ai/v1/public/message/"

#: Values a template .env may still hold. Treated as "not set".
_PLACEHOLDERS = {"", "paste_your_interakt_api_key_here", "changeme"}


class WhatsAppNotConfigured(Exception):
    """Interakt settings are missing — set at deploy."""


class WhatsAppSendFailed(Exception):
    """Interakt was reached (or not) and did not accept the message. Safe to
    show: it never carries the key."""


def is_configured() -> bool:
    return settings.interakt_api_key.strip().lower() not in _PLACEHOLDERS and bool(settings.interakt_template)


def normalise_number(raw: str, country_code: str | None = None) -> str:
    """Digits only; a 10-digit number gets the default country code in front.
    Exactly normalizeNumber_() in Code.gs."""
    country_code = country_code or settings.interakt_country
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if not digits:
        return ""
    return f"{country_code}{digits}" if len(digits) == 10 else digits


def build_payload(digits: str, pdf_url: str, file_name: str, body_values: list[str]) -> dict:
    """The request body Code.gs sends: the default country code, the number
    without it, and the template with the PDF as its document header."""
    country = settings.interakt_country
    local = digits[len(country):] if digits.startswith(country) else digits
    return {
        "countryCode": f"+{country}",
        "phoneNumber": local,
        "type": "Template",
        "template": {
            "name": settings.interakt_template,
            "languageCode": settings.interakt_lang,
            "headerValues": [pdf_url],
            "fileName": file_name,
            "bodyValues": body_values,
        },
    }


async def send_template(digits: str, pdf_url: str, file_name: str, body_values: list[str]) -> None:
    if not is_configured():
        raise WhatsAppNotConfigured("WhatsApp is not set up yet — the Interakt settings are missing.")

    payload = build_payload(digits, pdf_url, file_name, body_values)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                API_URL,
                json=payload,
                headers={"Authorization": f"Basic {settings.interakt_api_key}"},
            )
    except httpx.HTTPError as exc:
        log.error("Interakt unreachable: %s", type(exc).__name__)
        raise WhatsAppSendFailed("Could not reach WhatsApp (Interakt). Please try again.") from None

    if not 200 <= res.status_code < 300:
        # Interakt's own message is useful ("invalid phone number", "template
        # not approved") and contains no secret; keep it short.
        detail = res.text.strip().replace("\n", " ")[:300]
        log.error("Interakt error %s: %s", res.status_code, detail)
        raise WhatsAppSendFailed(f"Interakt error {res.status_code}: {detail}")

    log.info("whatsapp template %s sent to +%s", settings.interakt_template, digits)
