'use strict';
/**
 * WhatsApp via the Interakt HTTP API — same template flow as the Apps Script
 * version. The API key comes from .env and is never logged.
 *
 * SCAFFOLD: not implemented yet. Built on feature/share.
 */

async function sendTemplate(/* { number, params, pdfUrl } */) {
  throw new Error('whatsapp is not built yet.');
}

/** Digits only, country code prefixed, no + and no spaces. */
function normaliseNumber(raw, countryCode) {
  const digits = String(raw || '').replace(/\D/g, '');
  if (!digits) return '';
  return digits.length <= 10 ? `${countryCode}${digits}` : digits;
}

module.exports = { sendTemplate, normaliseNumber };
