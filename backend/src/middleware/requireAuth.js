'use strict';
/**
 * Rejects unauthenticated API calls.
 *
 * Mounted on /api after the auth routes, so login/logout stay reachable and
 * every other endpoint is gated. There is no client-side-only gate anywhere:
 * the browser hiding a view proves nothing, this check is the real one.
 */

module.exports = function requireAuth(req, res, next) {
  if (req.session && req.session.user && req.session.user.id) return next();

  res.status(401).json({
    status: 'error',
    data: null,
    message: 'Please sign in.',
  });
};
