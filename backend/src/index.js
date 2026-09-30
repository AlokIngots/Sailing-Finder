'use strict';
/**
 * Sailing Finder — server entry point.
 *
 * Starts Express, mounts the API routes, serves the static frontend.
 *
 * SCAFFOLD STATE: the routes are mounted but their handlers are stubs (501)
 * until each feature is built on its own branch. The wiring, the session gate
 * and the static serving are real.
 */

const fs = require('node:fs');
const path = require('node:path');
const express = require('express');
const helmet = require('helmet');
const session = require('express-session');
const PgSession = require('connect-pg-simple')(session);

const config = require('./config');
const { pool } = require('./db/pool');
const requireAuth = require('./middleware/requireAuth');

config.validate();

const app = express();
app.set('trust proxy', 1); // behind the VPS reverse proxy

app.use(helmet({ contentSecurityPolicy: false }));
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: false }));

// --- sessions: secure, HTTP-only cookies, stored in Postgres ---------------
app.use(
  session({
    store: new PgSession({ pool, tableName: 'session' }),
    name: 'sf.sid',
    secret: config.session.secret,
    resave: false,
    saveUninitialized: false,
    rolling: true,
    cookie: {
      httpOnly: true,
      secure: config.isProduction, // HTTPS only in production
      sameSite: 'lax',
      maxAge: config.session.ttlHours * 60 * 60 * 1000,
    },
  })
);

// --- health check ----------------------------------------------------------
// Reflects actual service state: the app is only healthy if the DB answers.
app.get('/healthz', async (_req, res) => {
  try {
    await pool.query('SELECT 1');
    res.json({ status: 'ok', data: { db: 'up' }, message: '' });
  } catch (err) {
    console.error('[healthz]', err.message);
    res.status(503).json({ status: 'error', data: { db: 'down' }, message: 'database unavailable' });
  }
});

// --- API -------------------------------------------------------------------
// Only /api/login and /api/logout are open. Everything else needs a session.
app.use('/api', require('./routes/auth'));
app.use('/api', requireAuth);
app.use('/api', require('./routes/schedule'));
app.use('/api', require('./routes/bookings'));
app.use('/api', require('./routes/share'));
app.use('/api', require('./routes/waContacts'));

// Unknown API path — never fall through to the SPA, or the frontend gets HTML
// where it expected JSON.
app.use('/api', (_req, res) => {
  res.status(404).json({ status: 'error', data: null, message: 'Not found' });
});

// --- static frontend -------------------------------------------------------
// index.html contains ONLY the login screen markup plus the empty app shell.
// No schedule data is ever embedded in the page — it is fetched after login.
// In the image the frontend sits at /app/frontend; in a local checkout it is a
// sibling of backend/. Pick whichever exists.
const frontendDir = [
  process.env.FRONTEND_DIR,
  path.join(__dirname, '..', 'frontend'),
  path.join(__dirname, '..', '..', 'frontend'),
].find((dir) => dir && fs.existsSync(path.join(dir, 'index.html')));

if (!frontendDir) throw new Error('frontend/index.html not found — cannot serve the app.');
app.use(express.static(frontendDir, { index: false, maxAge: '1h' }));
app.get('*', (_req, res) => res.sendFile(path.join(frontendDir, 'index.html')));

// --- error handler ---------------------------------------------------------
// Log the real error internally; return a sanitised message to the frontend.
// eslint-disable-next-line no-unused-vars
app.use((err, req, res, _next) => {
  console.error(`[${req.method} ${req.path}] ${err.message}`, err.stack);
  res.status(err.status || 500).json({
    status: 'error',
    data: null,
    message: err.expose ? err.message : 'Something went wrong. Please try again.',
  });
});

const server = app.listen(config.port, () => {
  console.log(`[sailing-finder] listening on ${config.port} (${config.env}, ${config.timezone})`);
});

function shutdown(signal) {
  console.log(`[sailing-finder] ${signal} — shutting down`);
  server.close(() => pool.end().finally(() => process.exit(0)));
  setTimeout(() => process.exit(1), 10_000).unref();
}
process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

module.exports = app;
