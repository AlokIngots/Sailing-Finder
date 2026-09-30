/**
 * Display helpers, ported from reference/Index.html.
 *
 * Direct / Indirect is NOT decided here. The server sends `ship_type`, worked
 * out from the same rule the routing filter uses in SQL, so the tag on a row
 * and the filter that selected it can never disagree.
 */

/** ETD within this many days earns the "Leaving soon" badge. */
export const LEAVING_SOON_DAYS = 3;

const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/**
 * The reference's parseDate: a local date, never UTC.
 *
 * `new Date('2026-09-29')` is parsed as UTC midnight, which in a negative-offset
 * timezone prints as the 28th. A sailing date has no time and no zone — the 29th
 * is the 29th wherever you read it.
 */
export function parseDate(value) {
  if (!value) return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;

  const text = String(value).trim().split(/[ T]/)[0];
  let m;
  if ((m = text.match(/^(\d{4})-(\d{2})-(\d{2})$/))) return new Date(+m[1], +m[2] - 1, +m[3]);
  if ((m = text.match(/^(\d{2})-(\d{2})-(\d{4})$/))) return new Date(+m[3], +m[2] - 1, +m[1]);
  if ((m = text.match(/^(\d{2})\.(\d{2})\.(\d{4})$/))) return new Date(+m[3], +m[2] - 1, +m[1]);

  const parsed = new Date(text);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/** "5 Oct 2026" — used in the copied list, the CSV and the enquiry summary. */
export function fmt(value) {
  const d = parseDate(value);
  return d ? `${d.getDate()} ${MON[d.getMonth()]} ${d.getFullYear()}` : '—';
}

/** "5 Oct" — used on the sailing rows, where the year would be noise. */
export function fmtShort(value) {
  const d = parseDate(value);
  return d ? `${d.getDate()} ${MON[d.getMonth()]}` : '—';
}

/** Midnight today, local time. The reference's TODAY. */
export function today() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

/** Departing within the next LEAVING_SOON_DAYS days (today counts). */
export function isLeavingSoon(etd) {
  const d = parseDate(etd);
  if (!d) return false;
  const t = today();
  return d >= t && d - t <= LEAVING_SOON_DAYS * 86_400_000;
}

/**
 * Split a scraped vessel string into a clean name and a voyage number.
 *
 * The scrapers sometimes bundle the voyage into the vessel field —
 * "MSC ORION (231W)" — and sometimes leave voyage_no empty. This pulls the
 * voyage out of the brackets when it is missing, then strips any bracketed
 * remainder from the name. Straight port of the reference's tidy().
 */
export function tidy(row) {
  let vessel = row.vessel_name || '';
  let voyage = row.voyage_no || '';

  const inBrackets = vessel.match(/\((\d{2,}[A-Z])\)/);
  if (!voyage && inBrackets) voyage = inBrackets[1];

  vessel = vessel.replace(/\s*\([^)]*\)/g, '').trim();
  return { vessel: vessel || row.vessel_name, voyage };
}

/** 'Direct' / 'Indirect' / '' for display, from the server's ship_type. */
export function shipTypeLabel(shipType) {
  if (shipType === 'direct') return 'Direct';
  if (shipType === 'indirect') return 'Indirect';
  return '';
}

/**
 * Where this list is going, for the email subject and the copied header.
 * Port beats country beats the default. The reference's whereLabel().
 */
export function whereLabel({ podCode, country, rows }) {
  if (podCode) {
    const match = (rows || []).find((r) => r.pod_code === podCode);
    return match ? `${match.pod_name || match.pod_code}, ${match.country}` : 'Europe & Mediterranean';
  }
  if (country) return country;
  return 'Europe & Mediterranean';
}
