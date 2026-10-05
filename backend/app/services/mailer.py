"""Outgoing email over SMTP, from two mailboxes.

- Share emails go from exports@alokindia.com (SMTP_HOST, SMTP_PORT,
  SMTP_STARTTLS, SMTP_USER, SMTP_PASS, MAIL_FROM, MAIL_FROM_NAME).
- Enquiries go from lk.exports@alokindia.com (ENQUIRY_SMTP_USER,
  ENQUIRY_SMTP_PASS, ENQUIRY_MAIL_FROM, ENQUIRY_MAIL_FROM_NAME; host, port and
  STARTTLS fall back to the SMTP_* values unless ENQUIRY_SMTP_* override them).

Passwords are never logged.

Rule carried over from the Apps Script version: an enquiry goes to each
forwarder in a SEPARATE message. Never one email with several forwarders on it,
and never CC/BCC between them — a forwarder must not see who else was asked. A
forwarder's own colleagues (FORWARDER_n_CC) are CC'd on that forwarder's copy
only. The share-by-email endpoint follows the same one-message-per-recipient
rule for its recipients.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import aiosmtplib

from app.config import settings

log = logging.getLogger(__name__)

#: Values a template .env may still hold. Treated as "not set".
_PLACEHOLDERS = {"", "changeme", "unused", "unused-in-tests", "preview-not-used", "preview-not-configured"}


class MailNotConfigured(Exception):
    """SMTP settings are missing — set at deploy."""


class MailSendFailed(Exception):
    """The server was reached (or not) and the message did not go. The message
    text is safe to show: it never carries the password."""


@dataclass(frozen=True)
class Account:
    """One sending mailbox. repr=False keeps the password out of any repr."""

    host: str
    port: int
    starttls: bool
    user: str
    password: str = field(repr=False)
    from_addr: str
    from_name: str

    @property
    def is_configured(self) -> bool:
        return bool(self.host) and self.password.strip().lower() not in _PLACEHOLDERS


def share_account() -> Account:
    """exports@alokindia.com — the share-by-email sender."""
    return Account(
        host=settings.smtp_host,
        port=settings.smtp_port,
        starttls=settings.smtp_starttls,
        user=settings.smtp_user,
        password=settings.smtp_pass,
        from_addr=settings.mail_from,
        from_name=settings.mail_from_name,
    )


def enquiry_account() -> Account:
    """lk.exports@alokindia.com — the enquiry sender. The sign-in defaults to
    the From address, which is what Google Workspace expects."""
    return Account(
        host=settings.enquiry_smtp_host,
        port=settings.enquiry_smtp_port,
        starttls=settings.enquiry_smtp_starttls,
        user=settings.enquiry_smtp_user or settings.enquiry_mail_from,
        password=settings.enquiry_smtp_pass,
        from_addr=settings.enquiry_mail_from,
        from_name=settings.enquiry_mail_from_name,
    )


def is_configured() -> bool:
    return share_account().is_configured


def is_enquiry_configured() -> bool:
    return enquiry_account().is_configured


def build_message(
    to: str,
    subject: str,
    text: str,
    attachments=None,
    reply_to: str = "",
    cc=(),
    account: Account | None = None,
) -> EmailMessage:
    """One message to one recipient (plus their CCs). `attachments` is
    [(filename, bytes, mime)]. The sender defaults to the share mailbox."""
    account = account or share_account()
    msg = EmailMessage()
    msg["From"] = formataddr((account.from_name, account.from_addr))
    msg["To"] = to
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=account.from_addr.split("@")[-1] or None)
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text)
    for filename, data, mime in attachments or []:
        maintype, _, subtype = mime.partition("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return msg


async def _deliver(account: Account, msg: EmailMessage) -> None:
    """Hand one built message to the account's SMTP server. aiosmtplib sends
    to every To and Cc address on the message."""
    to = msg["To"]
    implicit_tls = account.port == 465
    try:
        await aiosmtplib.send(
            msg,
            hostname=account.host,
            port=account.port,
            username=account.user or None,
            password=account.password or None,
            use_tls=implicit_tls,
            start_tls=account.starttls and not implicit_tls,
            timeout=30,
        )
    except aiosmtplib.SMTPAuthenticationError as exc:
        log.error("SMTP sign-in refused for %s (code %s)", account.user, exc.code)
        raise MailSendFailed("The mail server refused the sign-in. Check the SMTP settings.") from None
    except aiosmtplib.SMTPRecipientsRefused:
        raise MailSendFailed(f"The mail server refused the address {to}.") from None
    except (aiosmtplib.SMTPException, OSError) as exc:
        log.error("SMTP send to %s failed: %s", to, type(exc).__name__)
        raise MailSendFailed("Could not reach the mail server. Please try again.") from None

    log.info("mail sent from %s to %s: %s", account.from_addr, to, msg["Subject"])


async def send_mail(to, subject, text, attachments=None, reply_to="") -> None:
    """Send one share message to one address, from exports@."""
    account = share_account()
    if not account.is_configured:
        raise MailNotConfigured("Email is not set up yet — the SMTP settings are missing.")
    await _deliver(account, build_message(to, subject, text, attachments, reply_to, account=account))


async def send_to_forwarders_separately(forwarders, subject, body_for):
    """One email per forwarder — deliberately not a single multi-recipient send.

    Each copy goes To the forwarder's main address with CC to that forwarder's
    own colleagues only. `body_for(forwarder)` builds that forwarder's copy, so
    nothing about the others can leak into it.

    Returns [(forwarder, error_message_or_None)] in the order given. One failed
    forwarder never stops the others.
    """
    account = enquiry_account()
    if not account.is_configured:
        raise MailNotConfigured(
            "Enquiry email is not set up yet — the ENQUIRY_SMTP settings are missing."
        )

    async def one(forwarder):
        msg = build_message(
            forwarder.email, subject, body_for(forwarder), cc=forwarder.cc, account=account
        )
        try:
            await _deliver(account, msg)
            return forwarder, None
        except MailSendFailed as exc:
            return forwarder, str(exc)

    return list(await asyncio.gather(*(one(f) for f in forwarders)))
