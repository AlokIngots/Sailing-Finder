'use strict';
/**
 * Enquiry -> quotes -> booked -> documents.
 *
 * Every handler scopes its query to the signed-in user (bookings.created_by),
 * so two users never see each other's bookings. That is the isolation check in
 * the test pass, and it is enforced here in SQL, not in the frontend.
 *
 * SCAFFOLD: handlers are stubs. Built on feature/enquiry and feature/shipment.
 */

const router = require('express').Router();

const notBuilt = (name) => (_req, res) =>
  res.status(501).json({ status: 'error', data: null, message: `${name} is not built yet.` });

// GET  /api/bookings                      — this user's bookings, newest first
router.get('/bookings', notBuilt('Bookings list'));

// POST /api/enquiry                       — email the 3 forwarders SEPARATELY,
//                                           log the booking at stage=sent
router.post('/enquiry', notBuilt('Enquiry'));

// POST /api/bookings/:ref/quotes          — save each forwarder's rate + note
router.post('/bookings/:ref/quotes', notBuilt('Quotes'));

// POST /api/bookings/:ref/choose          — mark the winner, stage=booked
router.post('/bookings/:ref/choose', notBuilt('Choose forwarder'));

// POST /api/bookings/:ref/documents       — multipart: PL, CI, VGM -> email to
//                                           the chosen forwarder, stage=docs
router.post('/bookings/:ref/documents', notBuilt('Send documents'));

module.exports = router;
