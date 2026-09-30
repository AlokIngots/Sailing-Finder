'use strict';
/**
 * Postgres connection pool. One pool for the whole process.
 *
 * Queries elsewhere use raw SQL via parameterised text — never string
 * concatenation, so there is no injection surface.
 */

const { Pool } = require('pg');
const config = require('../config');

const pool = new Pool({
  connectionString: config.databaseUrl,
  max: 10,
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 10_000,
});

pool.on('error', (err) => {
  // An idle client blew up. Log it; do not crash the process.
  console.error('[db] idle client error:', err.message);
});

/**
 * Run a parameterised query.
 * @param {string} text  SQL with $1, $2 … placeholders
 * @param {Array}  params
 */
function query(text, params = []) {
  return pool.query(text, params);
}

/** Run several statements in one transaction. */
async function withTransaction(fn) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const result = await fn(client);
    await client.query('COMMIT');
    return result;
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

module.exports = { pool, query, withTransaction };
