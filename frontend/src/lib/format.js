/**
 * Small helpers shared by the finder and the bookings views.
 *
 * These implement the rules stated in the build spec. Anything that depends on
 * the exact wording or markup of reference/Index.html is NOT here yet — that
 * file has not been supplied, so nothing has been guessed.
 */

/** ETD within this many days earns the "Leaving soon" badge. */
export const LEAVING_SOON_DAYS = 3;

/**
 * Direct / Indirect, from the sheet's `transshipment` column.
 *   '0'      -> direct
 *   '1', '2' -> indirect
 *   blank    -> unlabelled; shown only under the "All" toggle, never tagged
 */
export function shipType(transshipment) {
  const raw = String(transshipment ?? '').trim();
  if (raw === '') return 'unlabelled';
  const n = Number.parseInt(raw, 10);
  if (Number.isNaN(n)) return 'unlabelled';
  return n === 0 ? 'direct' : 'indirect';
}

/** Does a sailing belong in the current All / Direct / Indirect toggle? */
export function matchesRouting(transshipment, routing) {
  if (routing === 'all') return true;
  return shipType(transshipment) === routing;
}

/** Midnight today, local time — the reference point for "leaving soon". */
function startOfToday() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

/** Whole days from today to `date`. Negative means it has already gone. */
export function daysUntil(date) {
  if (!date) return null;
  const then = new Date(date);
  if (Number.isNaN(then.getTime())) return null;
  then.setHours(0, 0, 0, 0);
  return Math.round((then - startOfToday()) / 86_400_000);
}

/** "Leaving soon" — departing within the next LEAVING_SOON_DAYS days. */
export function isLeavingSoon(etd) {
  const days = daysUntil(etd);
  return days !== null && days >= 0 && days <= LEAVING_SOON_DAYS;
}

/** Dates read the way the team writes them: 29 Sep 2026. */
export function formatDate(value) {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}
