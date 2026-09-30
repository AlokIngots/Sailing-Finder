'use strict';
/**
 * Sharing the filtered sailing list: email (PDF attached) and WhatsApp
 * (Interakt template with a PDF link/attachment).
 *
 * Copy-list and CSV download are done in the browser from data it already has,
 * so they need no endpoint. The PDF is built server-side by services/pdf.js.
 *
 * SCAFFOLD: handlers are stubs. Built on feature/share.
 */

const router = require('express').Router();

const notBuilt = (name) => (_req, res) =>
  res.status(501).json({ status: 'error', data: null, message: `${name} is not built yet.` });

// POST /api/share/email     { to, subject, filters } — list as email + PDF
router.post('/share/email', notBuilt('Email these'));

// POST /api/share/whatsapp  { number, save, filters } — Interakt template + PDF
router.post('/share/whatsapp', notBuilt('WhatsApp share'));

module.exports = router;
