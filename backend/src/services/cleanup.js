'use strict';
/**
 * Freshness / auto-delete for the `schedule` table.
 *
 * The scrapers' Google Sheet self-cleans: only today + future sailings stay in
 * it. This reproduces that in our own database, so the app never shows a ship
 * that has already left.
 *
 *   DELETE FROM schedule WHERE etd < CURRENT_DATE;
 *
 * Safety, in this order, every time:
 *   1. copy the rows about to go into a timestamped backup table
 *      (bk_schedule_YYYYMMDD_HHMMSS) — the golden-rules bk_ pattern
 *   2. delete ONLY rows whose etd is genuinely in the past
 *   3. never a wipe-and-reload, so a bad sync cannot lose upcoming sailings
 *
 * Rollback after a bad run:
 *   INSERT INTO schedule SELECT * FROM bk_schedule_<stamp>
 *   ON CONFLICT (row_key) DO NOTHING;
 *
 * Runs at the end of every sync, and again as a daily cron (jobs/daily.js).
 */

const { withTransaction, query } = require('../db/pool');

/** Backup tables older than this are dropped, so they don't pile up forever. */
const KEEP_BACKUP_DAYS = 7;

function stamp(date) {
  const p = (n) => String(n).padStart(2, '0');
  return (
    `${date.getFullYear()}${p(date.getMonth() + 1)}${p(date.getDate())}_` +
    `${p(date.getHours())}${p(date.getMinutes())}${p(date.getSeconds())}`
  );
}

/**
 * Back up then delete departed sailings.
 * @returns {Promise<{deleted:number, backupTable:string|null}>}
 */
async function cleanupDepartedSailings(now = new Date()) {
  return withTransaction(async (client) => {
    const { rows } = await client.query(
      'SELECT count(*)::int AS n FROM schedule WHERE etd < CURRENT_DATE'
    );
    const doomed = rows[0].n;

    if (doomed === 0) {
      console.log('[cleanup] nothing to remove — no sailings with etd before today');
      return { deleted: 0, backupTable: null };
    }

    // 1. backup first — identifier is built from a timestamp we generate, never
    //    from user input, so it is safe to interpolate.
    const backupTable = `bk_schedule_${stamp(now)}`;
    await client.query(
      `CREATE TABLE "${backupTable}" AS SELECT * FROM schedule WHERE etd < CURRENT_DATE`
    );

    // 2. delete only the past rows
    const del = await client.query('DELETE FROM schedule WHERE etd < CURRENT_DATE');

    console.log(
      `[cleanup] removed ${del.rowCount} departed sailing(s); backup in ${backupTable}. ` +
        `Rollback: INSERT INTO schedule SELECT * FROM ${backupTable} ON CONFLICT (row_key) DO NOTHING;`
    );
    return { deleted: del.rowCount, backupTable };
  });
}

/** Drop bk_schedule_* tables older than KEEP_BACKUP_DAYS. */
async function pruneOldBackups(now = new Date()) {
  const cutoff = new Date(now.getTime() - KEEP_BACKUP_DAYS * 24 * 60 * 60 * 1000);
  const cutoffKey = stamp(cutoff).slice(0, 8); // YYYYMMDD

  const { rows } = await query(
    `SELECT tablename FROM pg_tables
      WHERE schemaname = 'public' AND tablename LIKE 'bk\\_schedule\\_%'`
  );

  let dropped = 0;
  for (const { tablename } of rows) {
    const key = tablename.slice('bk_schedule_'.length, 'bk_schedule_'.length + 8);
    if (/^\d{8}$/.test(key) && key < cutoffKey) {
      await query(`DROP TABLE IF EXISTS "${tablename}"`);
      dropped += 1;
    }
  }
  if (dropped) console.log(`[cleanup] pruned ${dropped} backup table(s) older than ${KEEP_BACKUP_DAYS} days`);
  return dropped;
}

module.exports = { cleanupDepartedSailings, pruneOldBackups };
