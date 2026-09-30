'use strict';
/**
 * Applies db/schema.sql. Safe to re-run — every statement is idempotent.
 *
 * Run:      npm run migrate          (inside the container)
 * Deploy:   ./deploy.sh runs this automatically, before the app starts.
 *
 * This never drops or alters existing data. Any future change that DOES need to
 * touch existing data gets its own reviewed migration with a stated rollback,
 * and a table dump taken first — see CONTRIBUTING.md.
 */

const fs = require('node:fs');
const path = require('node:path');
const { pool } = require('./pool');

async function main() {
  const file = path.join(__dirname, 'schema.sql');
  const sql = fs.readFileSync(file, 'utf8');

  console.log(`[migrate] applying ${file}`);
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query(sql);
    await client.query('COMMIT');
    console.log('[migrate] OK');
  } catch (err) {
    await client.query('ROLLBACK');
    console.error('[migrate] FAILED — nothing was applied:', err.message);
    process.exitCode = 1;
  } finally {
    client.release();
    await pool.end();
  }
}

main();
