"""Outgoing email over SMTP, from exports@alokindia.com.

Settings come from .env (SMTP_HOST, SMTP_PORT, SMTP_STARTTLS, SMTP_USER,
SMTP_PASS, MAIL_FROM, MAIL_FROM_NAME). The password is never logged.

Rule carried over from the Apps Script version: an enquiry goes to each
forwarder in a SEPARATE message. Never one email with all three addresses on
it, and never CC/BCC between them — a forwarder must not see who else was asked.
The share-by-email endpoint follows the same rule for its recipients.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import aiosmtplib

from app.config import settings

log = logging.getLogger(__name__)

#: Values a template .env may still hold. Treated as "not set".
_PLACEHOLDERS = {"", "changeme", "unused", "unused-in-tests", "preview-not-used"}


class MailNotConfigured(Exception):
    """SMTP settings are missing — set at deploy."""


class MailSendFailed(Exception):
    """The server was reached (or not) and the message did not go. The message
    text is safe to show: it never carries the password."""


def is_configured() -> bool:
    return bool(settings.smtp_host) and settings.smtp_pass.strip().lower() not in _PLACEHOLDERS


def build_message(to: str, subject: str, text: str, attachments=None, reply_to: str = "") -> EmailMessage:
    """One message to one address. `attachments` is [(filename, bytes, mime)]."""
    msg = EmailMessage()
    msg["From"] = formataddr((settings.mail_from_name, settings.mail_from))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=settings.mail_from.split("@")[-1] or None)
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text)
    for filename, data, mime in attachments or []:
        maintype, _, subtype = mime.partition("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return msg


async def send_mail(to, subject, text, attachments=None, reply_to="") -> None:
    """Send one message to one address."""
    if not is_configured():
        raise MailNotConfigured("Email is not set up yet — the SMTP settings are missing.")

    msg = build_message(to, subject, text, attachments, reply_to)
    implicit_tls = settings.smtp_port == 465
    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_pass or None,
            use_tls=implicit_tls,
            start_tls=settings.smtp_starttls and not implicit_tls,
            timeout=30,
        )
    except aiosmtplib.SMTPAuthenticationError as exc:
        log.error("SMTP sign-in refused for %s (code %s)", settings.smtp_user, exc.code)
        raise MailSendFailed("The mail server refused the sign-in. Check the SMTP settings.") from None
    except aiosmtplib.SMTPRecipientsRefused:
        raise MailSendFailed(f"The mail server refused the address {to}.") from None
    except (aiosmtplib.SMTPException, OSError) as exc:
        log.error("SMTP send to %s failed: %s", to, type(exc).__name__)
        raise MailSendFailed("Could not reach the mail server. Please try again.") from None

    log.info("mail sent to %s: %s", to, subject)


async def send_to_forwarders_separately(forwarders, subject, body_for):
    """One email per forwarder — deliberately not a single multi-recipient send.

    `body_for(forwarder)` builds that forwarder's copy, so nothing about the
    others can leak into it.
    """
    raise NotImplementedError("mailer is not built yet.")
