'use strict';
/**
 * Builds the sailing-schedule PDF attached to the Email and WhatsApp shares.
 *
 * Server-side replacement for the Apps Script PDF export. Light theme, navy
 * headings — same brand colours as the app.
 *
 * SCAFFOLD: not implemented yet. Built on feature/share.
 */

/** Brand colours — keep in step with frontend/css/styles.css. */
const BRAND = {
  navy: '#000C2E',
  red: '#BC0300',
  orange: '#E5531A',
  paper: '#FFFFFF',
};

async function buildSchedulePdf(/* rows, meta */) {
  throw new Error('pdf is not built yet.');
}

module.exports = { buildSchedulePdf, BRAND };
