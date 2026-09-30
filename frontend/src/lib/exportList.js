/**
 * Copy list and Download — ported from reference/Index.html.
 *
 * Both act on exactly what is on screen: the filtered, sorted list the user is
 * looking at, so what a customer receives matches what was read out to them.
 *
 * The wording, the bullet layout, the CSV columns and the filename are all the
 * reference's. They are what customers already receive from us, so they are not
 * ours to improve.
 */

import { fmt, tidy, today } from './format.js';

/** CSV columns, exactly as the reference writes them. */
export const CSV_HEADER = [
  'Carrier',
  'Vessel',
  'Voyage',
  'Port',
  'Country',
  'Departs',
  'Arrives',
  'Transit (days)',
];

/**
 * Every field is quoted, not just the awkward ones: a vessel name like
 * "MSC PEGASUS VII / IP639A" carries a slash today and could carry a comma
 * tomorrow. Embedded quotes are doubled, per RFC 4180.
 */
function esc(value) {
  return `"${String(value ?? '').replace(/"/g, '""')}"`;
}

/** The filtered list as CSV, with a header row. */
export function buildCsv(sailings) {
  const lines = [CSV_HEADER.map(esc).join(',')];

  for (const sailing of sailings) {
    const { vessel, voyage } = tidy(sailing);
    lines.push(
      [
        sailing.carrier,
        vessel,
        voyage,
        sailing.pod_name || sailing.pod_code,
        sailing.country,
        fmt(sailing.etd),
        fmt(sailing.eta),
        sailing.transit_days == null ? '' : sailing.transit_days,
      ]
        .map(esc)
        .join(','),
    );
  }

  // CRLF: Excel on Windows is what opens these.
  return lines.join('\r\n');
}

/** Subject and body for the copied list and the email. */
export function buildText(sailings, where) {
  const lines = sailings.map((sailing) => {
    const { vessel, voyage } = tidy(sailing);
    return (
      `• ${vessel}${voyage ? ` (${voyage})` : ''}` +
      ` — ${sailing.carrier}` +
      ` — to ${sailing.pod_name || sailing.pod_code}, ${sailing.country}` +
      ` — Departs ${fmt(sailing.etd)}, Arrives ${fmt(sailing.eta)}` +
      (sailing.transit_days == null ? '' : ` (${sailing.transit_days} days)`)
    );
  });

  return {
    subject: `Sailing schedule — Nhava Sheva to ${where}`,
    body:
      `Sailing schedule from Nhava Sheva to ${where}\n` +
      `${sailings.length} sailing(s), as of ${fmt(today())}\n\n` +
      `${lines.join('\n')}\n\n` +
      'Carrier estimates — please confirm cut-offs before booking.\n\n' +
      'Export Team',
  };
}

/** sailings_YYYY-MM-DD.csv, as the reference names it. */
export function csvFilename() {
  return `sailings_${new Date().toISOString().slice(0, 10)}.csv`;
}

/**
 * Hand the CSV to the browser as a download.
 * Returns false if the browser would not take it, so the caller can fall back
 * to copying — which is what the reference does.
 */
export function downloadCsv(csv, filename = csvFilename()) {
  try {
    // The BOM is what makes Excel read the file as UTF-8 rather than the local
    // codepage, which otherwise mangles any non-ASCII port name.
    const blob = new Blob([`﻿${csv}`], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return true;
  } catch {
    return false;
  }
}

/** Copy text to the clipboard, falling back where the API is unavailable. */
export async function copyText(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Not a secure context, or permission refused. Fall through.
    }
  }

  const area = document.createElement('textarea');
  area.value = text;
  area.setAttribute('readonly', '');
  area.style.position = 'fixed';
  area.style.opacity = '0';
  document.body.appendChild(area);
  area.select();
  let ok = false;
  try {
    ok = document.execCommand('copy');
  } catch {
    ok = false;
  }
  area.remove();
  return ok;
}
