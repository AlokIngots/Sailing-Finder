/**
 * Copy list and Download (CSV).
 *
 * Both act on exactly what is on screen — the filtered, sorted list the user is
 * looking at — so what a customer receives matches what was read out to them.
 *
 * Kept out of the component so the formatting can be reasoned about (and later
 * tested) on its own.
 */

import { destination, formatDate, shipTypeLabel } from './format.js';

/** Column order, shared by the CSV and the plain-text list. */
export const COLUMNS = [
  { key: 'carrier', label: 'Carrier', value: (s) => s.carrier },
  { key: 'vessel', label: 'Vessel', value: (s) => s.vessel_name },
  { key: 'voyage', label: 'Voyage', value: (s) => s.voyage_no },
  { key: 'port', label: 'Port', value: (s) => s.pod_name || s.pod_code },
  { key: 'country', label: 'Country', value: (s) => s.country },
  { key: 'departs', label: 'Departs', value: (s) => formatDate(s.etd) },
  { key: 'arrives', label: 'Arrives', value: (s) => formatDate(s.eta) },
  { key: 'transit', label: 'Transit (days)', value: (s) => (s.transit_days ?? '') },
  { key: 'routing', label: 'Routing', value: (s) => shipTypeLabel(s.ship_type) },
];

/**
 * One CSV field.
 *
 * Every field is quoted, not just the awkward ones: a vessel name like
 * "MSC PEGASUS VII / IP639A" carries a slash today and could carry a comma
 * tomorrow. Embedded quotes are doubled, per RFC 4180.
 */
function csvField(value) {
  return `"${String(value ?? '').replace(/"/g, '""')}"`;
}

/** The filtered list as CSV, with a header row. */
export function toCsv(sailings) {
  const header = COLUMNS.map((c) => csvField(c.label)).join(',');
  const rows = sailings.map((s) => COLUMNS.map((c) => csvField(c.value(s))).join(','));
  // CRLF and a trailing newline: Excel on Windows is what opens these.
  return [header, ...rows].join('\r\n') + '\r\n';
}

/**
 * The filtered list as plain text, for pasting into WhatsApp or an email.
 *
 * One sailing per line, readable without a monospace font — a table of aligned
 * columns falls apart the moment it lands in a chat window.
 */
export function toPlainText(sailings) {
  return sailings
    .map((s) => {
      const routing = shipTypeLabel(s.ship_type);
      const transit = Number.isFinite(s.transit_days) ? `${s.transit_days} days` : '';
      const bits = [
        `${s.carrier}${s.voyage_no ? ` ${s.voyage_no}` : ''}`,
        destination(s),
        `ETD ${formatDate(s.etd)}`,
        `ETA ${formatDate(s.eta)}`,
        transit,
        routing,
      ].filter(Boolean);
      return bits.join(' · ');
    })
    .join('\n');
}

/** Filename that sorts correctly and says when it was taken. */
export function csvFilename(today = new Date()) {
  const pad = (n) => String(n).padStart(2, '0');
  const stamp = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
  return `sailings_${stamp}.csv`;
}

/** Hand the CSV to the browser as a download. */
export function downloadCsv(sailings, filename = csvFilename()) {
  // The BOM is what makes Excel read the file as UTF-8 rather than the local
  // codepage, which otherwise mangles any non-ASCII port name.
  const blob = new Blob(['﻿', toCsv(sailings)], {
    type: 'text/csv;charset=utf-8;',
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** Copy text to the clipboard, falling back where the API is unavailable. */
export async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }

  // http://<vps-ip> during testing is not a secure context, so the Clipboard
  // API is missing. This still works there.
  const area = document.createElement('textarea');
  area.value = text;
  area.setAttribute('readonly', '');
  area.style.position = 'fixed';
  area.style.opacity = '0';
  document.body.appendChild(area);
  area.select();
  const ok = document.execCommand('copy');
  area.remove();
  if (!ok) throw new Error('Could not copy. Select the list and copy manually.');
}
