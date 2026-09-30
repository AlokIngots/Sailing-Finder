'use strict';
/**
 * Password hashing and session helpers.
 *
 * Plain passwords are never stored, never logged, and never returned by any
 * endpoint. Only the hash goes in the database.
 *
 * SCAFFOLD: hashing is wired to bcrypt but the login flow that uses it is built
 * on feature/login.
 */

const BCRYPT_ROUNDS = 12;

async function hashPassword(plain) {
  if (!plain || String(plain).length < 8) {
    throw new Error('Password must be at least 8 characters.');
  }
  const bcrypt = require('bcrypt');
  return bcrypt.hash(String(plain), BCRYPT_ROUNDS);
}

async function verifyPassword(plain, hash) {
  if (!plain || !hash) return false;
  const bcrypt = require('bcrypt');
  return bcrypt.compare(String(plain), hash);
}

/** What goes into the session cookie — never the hash, never the password. */
function sessionUser(row) {
  return { id: row.id, username: row.username, name: row.name, role: row.role };
}

module.exports = { hashPassword, verifyPassword, sessionUser, BCRYPT_ROUNDS };
