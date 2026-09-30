'use strict';
/**
 * Sign in / sign out / current session.
 *
 * The only routes reachable without a session.
 *
 * SCAFFOLD: handlers are stubs. Built on feature/login, together with
 * services/security.js and the login screen in frontend/index.html.
 */

const router = require('express').Router();

const notBuilt = (name) => (_req, res) =>
  res.status(501).json({ status: 'error', data: null, message: `${name} is not built yet.` });

// POST /api/login   { username, password } -> sets the session cookie
router.post('/login', notBuilt('Login'));

// POST /api/logout  -> destroys the session
router.post('/logout', notBuilt('Logout'));

// GET /api/session  -> who am I (used by the frontend to decide login vs app)
router.get('/session', (req, res) => {
  const user = req.session && req.session.user;
  res.json({
    status: 'ok',
    data: user ? { username: user.username, name: user.name, role: user.role } : null,
    message: '',
  });
});

module.exports = router;
