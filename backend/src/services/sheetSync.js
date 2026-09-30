'use strict';
/**
 * Google Sheet (`all_schedule` tab) -> `schedule` table.
 *
 * Read-only, via a Google service account. The scrapers and the sheet are NOT
 * touched by this app — we only read what they produce.
 *
 * Every row is UPSERTed on `row_key`:
 *   - a new sailing is inserted
 *   - a sailing whose ETD/ETA/vessel changed updates its existing row
 *   - nothing is ever duplicated
 *
 * After the upsert, services/cleanup.js removes departed sailings. There is no
 * truncate-and-reload anywhere — a failed read must never empty the table.
 *
 * SCAFFOLD: not implemented yet. Built on feature/sheet-sync, once the exact
 * `all_schedule` column order is confirmed against the live sheet.
 */

const config = require('../config');

/** Columns of the schedule table, in sheet order. */
const COLUMNS = [
  'carrier',
  'pol_code',
  'pol_name',
  'pod_code',
  'pod_name',
  'vessel_name',
  'voyage_no',
  'etd',
  'eta',
  'transit_days',
  'transshipment',
  'service',
  'source',
  'pulled_on',
  'row_key',
];

async function syncScheduleFromSheet() {
  throw new Error(
    `sheetSync is not built yet (sheet ${config.sheet.id}, tab ${config.sheet.tab}).`
  );
}

module.exports = { syncScheduleFromSheet, COLUMNS };
