'use strict';
/**
 * The sailing schedule, read from the `schedule` table only — never from the
 * Google Sheet directly. The sheet reaches the table through services/sheetSync.
 *
 * SCAFFOLD: handlers are stubs. Built on feature/finder.
 */

const router = require('express').Router();

const notBuilt = (name) => (_req, res) =>
  res.status(501).json({ status: 'error', data: null, message: `${name} is not built yet.` });

// GET /api/schedule
// Filters (all optional): country, pod_code, carrier, etd_from, etd_to,
// eta_from, eta_to, routing (all|direct|indirect), mode (all|next_per_port),
// sort (etd|transit|eta)
router.get('/schedule', notBuilt('Schedule'));

// GET /api/forwarders — the three configured forwarders (names only; the
// addresses stay server-side and are never sent to the browser).
router.get('/forwarders', notBuilt('Forwarders'));

module.exports = router;
