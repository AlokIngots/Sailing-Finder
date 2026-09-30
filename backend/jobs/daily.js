'use strict';
/**
 * Daily job: pull the sheet into the schedule table, then drop departed sailings.
 *
 * Run once, by hand:      npm run sync
 * Run on a schedule:      node jobs/daily.js --cron    (SYNC_CRON / CLEANUP_CRON)
 *
 * Order matters. Sync first so today's new sailings are in, cleanup second so
 * anything that has already left goes out. Cleanup backs up before it deletes —
 * see services/cleanup.js for the rollback command.
 */

const config = require('../src/config');
const { pool } = require('../src/db/pool');
const { syncScheduleFromSheet } = require('../src/services/sheetSync');
const { cleanupDepartedSailings, pruneOldBackups } = require('../src/services/cleanup');

async function runOnce() {
  const started = Date.now();
  try {
    const synced = await syncScheduleFromSheet();
    console.log(`[daily] sync done: ${JSON.stringify(synced)}`);
  } catch (err) {
    // A failed sync must NOT stop the cleanup, and must never empty the table.
    console.error('[daily] sync FAILED — schedule table left as it was:', err.message);
  }

  try {
    await cleanupDepartedSailings();
    await pruneOldBackups();
  } catch (err) {
    console.error('[daily] cleanup FAILED:', err.message);
  }

  console.log(`[daily] finished in ${Math.round((Date.now() - started) / 1000)}s`);
}

async function main() {
  if (process.argv.includes('--cron')) {
    const cron = require('node-cron');
    const opts = { timezone: config.timezone };
    cron.schedule(config.cron.sync, () => void runOnce(), opts);
    console.log(`[daily] scheduled: sync ${config.cron.sync} (${config.timezone})`);
    return; // stay alive
  }

  await runOnce();
  await pool.end();
}

main();
