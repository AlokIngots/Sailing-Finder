'use strict';
/**
 * Outgoing email over SMTP (nodemailer), from exports@alokindia.com.
 *
 * Rule carried over from the Apps Script version: an enquiry goes to each
 * forwarder in a SEPARATE email. Never one message with all three addresses on
 * it, and never CC/BCC between them.
 *
 * SCAFFOLD: not implemented yet. Built on feature/enquiry.
 */

async function sendMail(/* { to, subject, html, text, attachments } */) {
  throw new Error('mailer is not built yet.');
}

/** One email per forwarder — deliberately not a single multi-recipient send. */
async function sendToForwardersSeparately(/* forwarders, message */) {
  throw new Error('mailer is not built yet.');
}

module.exports = { sendMail, sendToForwardersSeparately };
