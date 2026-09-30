'use strict';
/**
 * Saved WhatsApp numbers for the share dropdown.
 * `number` is stored as digits including country code — no +, no spaces.
 *
 * SCAFFOLD: handlers are stubs. Built on feature/share.
 */

const router = require('express').Router();

const notBuilt = (name) => (_req, res) =>
  res.status(501).json({ status: 'error', data: null, message: `${name} is not built yet.` });

// GET  /api/wa-contacts        — saved numbers
router.get('/wa-contacts', notBuilt('WhatsApp contacts'));

// POST /api/wa-contacts        { name, number } — remember a number
router.post('/wa-contacts', notBuilt('Save WhatsApp contact'));

module.exports = router;
