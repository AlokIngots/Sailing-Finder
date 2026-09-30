'use strict';
/**
 * Add a sign-in account. There is no public sign-up.
 *
 *   docker compose exec app node scripts/create-user.js <username> "<Full Name>" [role]
 *
 * The password is NOT passed as an argument (it would land in shell history and
 * in `ps`). It is read from the SF_NEW_PASSWORD environment variable for one
 * command only, hashed, and discarded — the plain value is never stored, never
 * logged, never echoed.
 *
 *   docker compose exec -e SF_NEW_PASSWORD='...' app node scripts/create-user.js alok "Alok" admin
 *
 * Re-running for an existing username updates that user's password.
 *
 * Rollback:  DELETE FROM users WHERE username = '<username>';
 */

const { query, pool } = require('../src/db/pool');
const { hashPassword } = require('../src/services/security');

async function main() {
  const [username, name, role = 'user'] = process.argv.slice(2);
  const password = process.env.SF_NEW_PASSWORD;

  if (!username || !name) {
    console.error('Usage: SF_NEW_PASSWORD=... node scripts/create-user.js <username> "<Full Name>" [role]');
    process.exitCode = 1;
    return;
  }
  if (!password) {
    console.error('SF_NEW_PASSWORD is not set. Pass it as an environment variable, not an argument.');
    process.exitCode = 1;
    return;
  }

  const hash = await hashPassword(password);

  await query(
    `INSERT INTO users (username, password_hash, name, role)
          VALUES ($1, $2, $3, $4)
     ON CONFLICT (username)
     DO UPDATE SET password_hash = EXCLUDED.password_hash,
                   name          = EXCLUDED.name,
                   role          = EXCLUDED.role`,
    [username.trim().toLowerCase(), hash, name.trim(), role.trim()]
  );

  console.log(`User "${username}" saved (role: ${role}).`);
  await pool.end();
}

main().catch(async (err) => {
  console.error('Failed:', err.message);
  process.exitCode = 1;
  await pool.end();
});
