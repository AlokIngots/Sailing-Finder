/**
 * Display helpers for the finder and the bookings views.
 *
 * Direct / Indirect is NOT decided here. The server sends `ship_type` on every
 * sailing, worked out from the same rule the routing filter uses in SQL, so the
 * tag on a row and the filter that selected it can never disagree.
 */

/** ETD within this many days earns the "Leaving soon" badge. */
export const LEAVING_SOON_DAYS = 3;

/**
 * Parse a plain 'YYYY-MM-DD' as a LOCAL date.
 *
 * `new Date('2026-09-29')` is parsed as UTC midnight, which in a negative-offset
 * timezone prints as the 28th. Sailing dates have no time and no zone — a
 * departure on the 29th is the 29th wherever you read it.
 */
export function parseDate(value) {
  if (!value) return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;

  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value));
  if (iso) {
    return new Date(Number(iso[1]), Number(iso[2]) - 1, Number(iso[3]));
  }

  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/** Midnight today, local time — the reference point for "leaving soon". */
function startOfToday() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

/** Whole days from today to `value`. Negative means it has already gone. */
export function daysUntil(value) {
  const then = parseDate(value);
  if (!then) return null;
  then.setHours(0, 0, 0, 0);
  return Math.round((then - startOfToday()) / 86_400_000);
}

/** Departing within the next LEAVING_SOON_DAYS days (today counts). */
export function isLeavingSoon(etd) {
  const days = daysUntil(etd);
  return days !== null && days >= 0 && days <= LEAVING_SOON_DAYS;
}

/** Dates read the way the team writes them: 29 Sep 2026. */
export function formatDate(value) {
  const d = parseDate(value);
  if (!d) return '';
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

/** 'Direct' / 'Indirect' / '' for display, from the server's ship_type. */
export function shipTypeLabel(shipType) {
  if (shipType === 'direct') return 'Direct';
  if (shipType === 'indirect') return 'Indirect';
  return '';
}

/** "37 days", or an em dash when the carrier did not publish one. */
export function formatTransit(days) {
  return Number.isFinite(days) ? `${days} days` : '—';
}

/** Destination as the team says it: "Rotterdam, Netherlands". */
export function destination(sailing) {
  const port = sailing.pod_name || sailing.pod_code || '';
  return sailing.country ? `${port}, ${sailing.country}` : port;
}
