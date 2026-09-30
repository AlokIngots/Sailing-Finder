"""Outgoing email over SMTP, from exports@alokindia.com.

Rule carried over from the Apps Script version: an enquiry goes to each
forwarder in a SEPARATE message. Never one email with all three addresses on
it, and never CC/BCC between them — a forwarder must not see who else was asked.

SCAFFOLD: not implemented. Built on feature/enquiry.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


async def send_mail(to, subject, html, text="", attachments=None, reply_to=""):
    """Send one message."""
    raise NotImplementedError("mailer is not built yet.")


async def send_to_forwarders_separately(forwarders, subject, body_for):
    """One email per forwarder — deliberately not a single multi-recipient send.

    `body_for(forwarder)` builds that forwarder's copy, so nothing about the
    others can leak into it.
    """
    raise NotImplementedError("mailer is not built yet.")
