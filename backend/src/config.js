'use strict';
/**
 * Reads and validates the environment.
 *
 * Deliberately has NO dependencies — deploy.sh loads this file inside the freshly
 * built image as its "does the code even load" check, before anything else runs.
 *
 * In Docker, values come from backend/.env via env_file.
 * Locally:  node --env-file=backend/.env backend/src/index.js
 *
 * Nothing in here is ever logged. Values are read, never printed.
 */

/** Required keys — missing ones abort startup with a clear message. */
const REQUIRED = [
  'DATABASE_URL',
  'SESSION_SECRET',
  'SHEET_ID',
  'GOOGLE_KEY_PATH',
  'SMTP_HOST',
  'SMTP_USER',
  'SMTP_PASS',
  'MAIL_FROM',
];

function required(key) {
  const value = process.env[key];
  if (!value || !String(value).trim()) {
    throw new Error(
      `Missing required environment variable: ${key}. ` +
        'Copy backend/.env.example to backend/.env and fill it in.'
    );
  }
  return String(value).trim();
}

function optional(key, fallback = '') {
  const value = process.env[key];
  return value === undefined || value === '' ? fallback : String(value).trim();
}

function int(key, fallback) {
  const value = optional(key, '');
  if (value === '') return fallback;
  const n = Number.parseInt(value, 10);
  if (Number.isNaN(n)) throw new Error(`Environment variable ${key} must be a whole number.`);
  return n;
}

function bool(key, fallback = false) {
  const value = optional(key, '').toLowerCase();
  if (value === '') return fallback;
  return value === 'true' || value === '1' || value === 'yes';
}

/**
 * The three forwarders. Each enquiry is emailed to each of them SEPARATELY —
 * never one email with all three addresses visible.
 */
function forwarders() {
  const list = [];
  for (const n of [1, 2, 3]) {
    const name = optional(`FORWARDER_${n}_NAME`);
    const email = optional(`FORWARDER_${n}_EMAIL`);
    if (name && email) list.push({ id: `f${n}`, name, email });
  }
  return list;
}

/** Only validate fully when actually starting the server. */
function validate() {
  const missing = REQUIRED.filter((k) => !process.env[k] || !String(process.env[k]).trim());
  if (missing.length) {
    throw new Error(
      `Missing required environment variables: ${missing.join(', ')}. ` +
        'Copy backend/.env.example to backend/.env and fill it in.'
    );
  }
  if (forwarders().length !== 3) {
    throw new Error('All three FORWARDER_n_NAME / FORWARDER_n_EMAIL pairs must be set.');
  }
  if (optional('SESSION_SECRET').length < 32) {
    throw new Error('SESSION_SECRET must be at least 32 characters. Generate: openssl rand -hex 32');
  }
}

const config = {
  env: optional('NODE_ENV', 'development'),
  isProduction: optional('NODE_ENV', 'development') === 'production',
  port: int('PORT', 8080),
  timezone: optional('TZ', 'Asia/Kolkata'),
  publicUrl: optional('PUBLIC_URL', 'https://sailing.alokindia.com'),

  databaseUrl: optional('DATABASE_URL'),

  session: {
    secret: optional('SESSION_SECRET'),
    ttlHours: int('SESSION_TTL_HOURS', 12),
  },

  sheet: {
    keyPath: optional('GOOGLE_KEY_PATH', '/run/secrets/google-key.json'),
    id: optional('SHEET_ID'),
    tab: optional('SHEET_TAB', 'all_schedule'),
  },

  cron: {
    sync: optional('SYNC_CRON', '0 11 * * *'),
    cleanup: optional('CLEANUP_CRON', '30 11 * * *'),
  },

  smtp: {
    host: optional('SMTP_HOST'),
    port: int('SMTP_PORT', 587),
    secure: bool('SMTP_SECURE', false),
    user: optional('SMTP_USER'),
    pass: optional('SMTP_PASS'),
    fromName: optional('MAIL_FROM_NAME', 'Alok Ingots (Mumbai) Pvt. Ltd.'),
    from: optional('MAIL_FROM'),
    bookingReplyTo: optional('BOOKING_REPLY_TO'),
  },

  forwarders: forwarders(),

  interakt: {
    apiKey: optional('INTERAKT_API_KEY'),
    templateName: optional('INTERAKT_TEMPLATE_NAME'),
    templateLang: optional('INTERAKT_TEMPLATE_LANG', 'en'),
    countryCode: optional('INTERAKT_COUNTRY_CODE', '91'),
  },

  uploads: {
    dir: optional('UPLOAD_DIR', '/app/uploads'),
    maxMb: int('MAX_UPLOAD_MB', 15),
  },

  required,
  validate,
};

module.exports = config;
