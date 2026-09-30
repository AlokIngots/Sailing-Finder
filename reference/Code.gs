/*** =======================================================================
 *   SAILING FINDER — COMPLETE Code.gs  (with Booking flow: request → quotes → documents)
 *   This is the WHOLE file. Select all in your Code.gs, delete, paste this.
 *   Then fill: the 4 Interakt values, and the 3 FORWARDERS + BOOKING_REPLY_TO.
 *   ======================================================================= */

var SHEET_ID = '18qW38SIfCma1zRye0W-6mcuQRwl7-2iEa-78-xjaBoM';
var TAB_NAME = 'all_schedule';


/* ---------- WEB APP: serves the page (NO data here — data loads only after login) ---------- */
function doGet() {
  var t = HtmlService.createTemplateFromFile('Index');
  return t.evaluate()
    .setTitle('Sailing Finder')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/* Login-gated: the page calls this AFTER a valid login to get the schedule rows */
function getScheduleRows(token) {
  requireAuth_(token);
  return getRows();
}

/* Read every sailing row from the sheet as objects keyed by the header row */
function getRows() {
  var ss = SpreadsheetApp.openById(SHEET_ID);
  var sh = ss.getSheetByName(TAB_NAME);
  if (!sh) return [];
  var vals = sh.getDataRange().getDisplayValues();
  if (vals.length < 2) return [];
  var head = vals[0].map(function (h) { return String(h).trim(); });
  var out = [];
  for (var i = 1; i < vals.length; i++) {
    var o = {};
    for (var j = 0; j < head.length; j++) { o[head[j]] = vals[i][j]; }
    out.push(o);
  }
  return out;
}


/* ---------- EMAIL: one-click send of the sailing list from the page ---------- */
function sendMail(token, to, subject, body, tableHtml, brief) {
  requireAuth_(token);
  if (!to) { throw new Error('No recipient address'); }
  var opts = { name: 'Alok Ingots - Export Team' };
  if (tableHtml) {
    var when = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'dd-MMM-yyyy HH:mm');
    var html =
      '<html><body style="font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#000C2E;">' +
        '<h2 style="color:#000C2E;margin:0 0 2px;">Alok Ingots — Sailing Schedule</h2>' +
        '<div style="font-size:11px;color:#555;margin:0 0 10px;">' +
          (brief && brief.line ? brief.line : '') + ' &nbsp;|&nbsp; Generated ' + when +
        '</div>' + tableHtml +
        '<div style="font-size:10px;color:#777;margin-top:12px;">Carrier estimates — please confirm cut-offs before booking.</div>' +
      '</body></html>';
    var stamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'ddMMyyyy_HHmm');
    var pdf = Utilities.newBlob(html, 'text/html', 'sailing_schedule.pdf').getAs('application/pdf').setName('Sailing_Schedule_' + stamp + '.pdf');
    opts.attachments = [pdf];
  }
  MailApp.sendEmail(to, subject, body, opts);
  return true;
}

/* ---------- DAILY CLEANUP: remove sailings that already departed ---------- */
function cleanupOldSailings() {
  var ss = SpreadsheetApp.openById(SHEET_ID);
  var sh = ss.getSheetByName(TAB_NAME);
  var range = sh.getDataRange();
  var display = range.getDisplayValues();
  var raw = range.getValues();
  if (display.length < 2) { return; }
  var head = display[0].map(String);
  var etdCol = head.indexOf('etd');
  if (etdCol < 0) { return; }
  var today = new Date(); today.setHours(0, 0, 0, 0);
  var keep = [raw[0]];
  for (var i = 1; i < display.length; i++) {
    var d = parseEtd_(display[i][etdCol]);
    if (!(d && d < today)) { keep.push(raw[i]); }
  }
  sh.clearContents();
  sh.getRange(1, 1, keep.length, keep[0].length).setValues(keep);
}

function parseEtd_(s) {
  if (!s) return null;
  s = String(s).trim().split(/[ T]/)[0];
  var m;
  if ((m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/))) return new Date(+m[1], +m[2] - 1, +m[3]);
  if ((m = s.match(/^(\d{2})-(\d{2})-(\d{4})$/))) return new Date(+m[3], +m[2] - 1, +m[1]);
  if ((m = s.match(/^(\d{2})\.(\d{2})\.(\d{4})$/))) return new Date(+m[3], +m[2] - 1, +m[1]);
  var d = new Date(s); return isNaN(d) ? null : d;
}


/* =======================================================================
 *   WHATSAPP (INTERAKT)
 *   ======================================================================= */

// ---------- FILL THESE 4 WITH YOUR INTERAKT VALUES ----------
var INTERAKT_API_KEY  = 'PASTE_YOUR_INTERAKT_API_KEY_HERE';
var INTERAKT_TEMPLATE = 'sailing_schedule';
var INTERAKT_LANG     = 'en';
var DEFAULT_COUNTRY   = '91';
// ------------------------------------------------------------

var WA_CONTACTS_TAB = 'wa_contacts';

function getWaContacts(token) {
  requireAuth_(token);
  var ss = SpreadsheetApp.openById(SHEET_ID);
  var sh = ss.getSheetByName(WA_CONTACTS_TAB);
  if (!sh) { sh = ss.insertSheet(WA_CONTACTS_TAB); sh.getRange(1, 1, 1, 2).setValues([['name', 'number']]); return []; }
  var vals = sh.getDataRange().getDisplayValues();
  var out = [];
  for (var i = 1; i < vals.length; i++) { var num = String(vals[i][1] || '').trim(); if (num) out.push({ name: String(vals[i][0] || '').trim(), number: num }); }
  return out;
}

function saveWaContact(token, name, number) {
  requireAuth_(token);
  var digits = normalizeNumber_(number);
  if (!digits) throw new Error('Bad number');
  var ss = SpreadsheetApp.openById(SHEET_ID);
  var sh = ss.getSheetByName(WA_CONTACTS_TAB);
  if (!sh) { sh = ss.insertSheet(WA_CONTACTS_TAB); sh.getRange(1, 1, 1, 2).setValues([['name', 'number']]); }
  var existing = sh.getDataRange().getDisplayValues();
  for (var i = 1; i < existing.length; i++) { if (normalizeNumber_(existing[i][1]) === digits) return true; }
  sh.appendRow([name || '', digits]);
  return true;
}

function normalizeNumber_(raw) {
  var d = String(raw || '').replace(/[^0-9]/g, '');
  if (!d) return '';
  if (d.length === 10) d = DEFAULT_COUNTRY + d;
  return d;
}

function sendWhatsAppPdf(token, number, tableHtml, brief) {
  requireAuth_(token);
  var digits = normalizeNumber_(number);
  if (!digits) throw new Error('Please enter a valid WhatsApp number');
  var when = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'dd-MMM-yyyy HH:mm');
  var html =
    '<html><body style="font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#000C2E;">' +
      '<h2 style="color:#000C2E;margin:0 0 2px;">Alok Ingots — Sailing Schedule</h2>' +
      '<div style="font-size:11px;color:#555;margin:0 0 10px;">' + (brief && brief.line ? brief.line : '') + ' &nbsp;|&nbsp; Generated ' + when + '</div>' +
      (tableHtml || '') +
      '<div style="font-size:10px;color:#777;margin-top:12px;">Carrier estimates — please confirm cut-offs before booking.</div>' +
    '</body></html>';
  var stamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'ddMMyyyy_HHmm');
  var pdf = Utilities.newBlob(html, 'text/html', 'sailing_schedule.pdf').getAs('application/pdf').setName('Sailing_Schedule_' + stamp + '.pdf');
  var file = DriveApp.createFile(pdf);
  file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
  var pdfUrl = 'https://drive.google.com/uc?export=download&id=' + file.getId();
  var local = (digits.indexOf(DEFAULT_COUNTRY) === 0) ? digits.substring(DEFAULT_COUNTRY.length) : digits;
  var payload = {
    countryCode: '+' + DEFAULT_COUNTRY, phoneNumber: local, type: 'Template',
    template: { name: INTERAKT_TEMPLATE, languageCode: INTERAKT_LANG, headerValues: [pdfUrl], fileName: pdf.getName(), bodyValues: (brief && brief.bodyValues) ? brief.bodyValues : [] }
  };
  var res = UrlFetchApp.fetch('https://api.interakt.ai/v1/public/message/', {
    method: 'post', contentType: 'application/json',
    headers: { 'Authorization': 'Basic ' + INTERAKT_API_KEY },
    payload: JSON.stringify(payload), muteHttpExceptions: true
  });
  var code = res.getResponseCode(); var body = res.getContentText();
  if (code < 200 || code >= 300) { throw new Error('Interakt error ' + code + ': ' + body); }
  return 'sent';
}


/* =======================================================================
 *   BOOKING FLOW  (Stage 1 request → Stage 2 quotes → Stage 3 documents)
 *   ======================================================================= */

// ---------- FILL THESE ----------
var FORWARDERS = [
  { name: 'Forwarder 1', email: '' },   // e.g. { name: 'Seabird Logistics', email: 'ops@seabird.com' }
  { name: 'Forwarder 2', email: '' },
  { name: 'Forwarder 3', email: '' }
];
var BOOKING_FROM_NAME = 'Alok Ingots - Export Team';
var BOOKING_REPLY_TO  = '';               // where forwarder replies should land, e.g. exports@alokindia.com
// --------------------------------

var BOOKINGS_TAB = 'bookings';
var BK_HEAD = ['ref','created_at','stage','carrier','vessel','voyage','pol_code','pod_code','pod_name','country',
               'etd','eta','transit_days','stuffing','container','commodity','net_wt','gross_wt','remarks',
               'sent_to','quotes_json','won','docs_sent_at'];

/* forwarder names for the page (only ones with an email filled) */
function getForwarders(token) {
  requireAuth_(token);
  return FORWARDERS.filter(function (f) { return f && f.email; }).map(function (f) { return { name: f.name || f.email, email: f.email }; });
}

function bkSheet_() {
  var ss = SpreadsheetApp.openById(SHEET_ID);
  var sh = ss.getSheetByName(BOOKINGS_TAB);
  if (!sh) { sh = ss.insertSheet(BOOKINGS_TAB); sh.getRange(1, 1, 1, BK_HEAD.length).setValues([BK_HEAD]); }
  return sh;
}
function bkAll_() {
  var sh = bkSheet_();
  var vals = sh.getDataRange().getDisplayValues();
  var rows = [];
  for (var i = 1; i < vals.length; i++) {
    var o = {}; for (var j = 0; j < BK_HEAD.length; j++) { o[BK_HEAD[j]] = vals[i][j]; }
    o._row = i + 1; rows.push(o);
  }
  return rows;
}
function bkFind_(ref) {
  var all = bkAll_();
  for (var i = 0; i < all.length; i++) { if (all[i].ref === ref) return all[i]; }
  return null;
}
function bkSet_(rowNum, key, value) {
  var sh = bkSheet_();
  var col = BK_HEAD.indexOf(key) + 1;
  if (col > 0) sh.getRange(rowNum, col).setValue(value);
}

/* Return all bookings for "My bookings" (newest first) */
function getBookings(token) {
  requireAuth_(token);
  var all = bkAll_();
  return all.map(function (o) {
    var quotes = [];
    try { quotes = o.quotes_json ? JSON.parse(o.quotes_json) : []; } catch (e) { quotes = []; }
    return {
      ref: o.ref, stage: o.stage || 'sent', carrier: o.carrier, vessel: o.vessel, voyage: o.voyage,
      pod_code: o.pod_code, pod: o.pod_name, country: o.country, etd: o.etd, eta: o.eta, transit: o.transit_days,
      stuffing: o.stuffing, container: o.container, commodity: o.commodity, net: o.net_wt, gross: o.gross_wt,
      remarks: o.remarks, quotes: quotes, won: o.won || '', sent_to: o.sent_to
    };
  }).reverse();
}

/* STAGE 1 — email each forwarder separately, log the booking, return ref + count */
function sendBookingRequest(token, subject, body, booking) {
  requireAuth_(token);
  var list = FORWARDERS.filter(function (f) { return f && f.email; }).map(function (f) { return { name: f.name || f.email, email: f.email }; });
  if (!list.length) { throw new Error('No forwarder emails set — fill FORWARDERS at the top of the booking section in Code.gs.'); }
  if (!subject) subject = 'Booking request';
  var ref = (booking && booking.ref) ? booking.ref : ('BR-' + Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyyMMdd-HHmm'));
  var sentTo = [];
  for (var i = 0; i < list.length; i++) {
    var greet = list[i].name ? list[i].name.split(' ')[0] : 'Team';
    var opts = { name: BOOKING_FROM_NAME };
    if (BOOKING_REPLY_TO) opts.replyTo = BOOKING_REPLY_TO;
    MailApp.sendEmail(list[i].email, subject, 'Dear ' + greet + ',\n\n' + body, opts);
    sentTo.push(list[i].email);
  }
  var b = booking || {};
  var when = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'dd-MMM-yyyy HH:mm');
  var sh = bkSheet_();
  var rowVals = [ref, when, 'sent', b.carrier || '', b.vessel || '', b.voyage || '', b.pol_code || 'INNSA',
    b.pod_code || '', b.pod || '', b.country || '', b.etd || '', b.eta || '', b.transit || '',
    b.stuffing || '', b.container || '', b.commodity || '', b.net_wt || '', b.gross_wt || '', b.remarks || '',
    sentTo.join(', '), '[]', '', ''];
  sh.appendRow(rowVals);
  return { ref: ref, count: sentTo.length };
}

/* STAGE 2 — save the 3 forwarder quotes typed in on the page. quotes = [{fwd, price, note}] */
function saveQuotes(token, ref, quotes) {
  requireAuth_(token);
  var b = bkFind_(ref);
  if (!b) throw new Error('Booking ' + ref + ' not found');
  bkSet_(b._row, 'quotes_json', JSON.stringify(quotes || []));
  bkSet_(b._row, 'stage', 'quotes');
  return true;
}

/* STAGE 2 — mark the chosen forwarder (the winner) */
function chooseForwarder(token, ref, forwarderName) {
  requireAuth_(token);
  var b = bkFind_(ref);
  if (!b) throw new Error('Booking ' + ref + ' not found');
  bkSet_(b._row, 'won', forwarderName);
  bkSet_(b._row, 'stage', 'booked');
  return true;
}

/* STAGE 3 — email PL + CI + VGM to the chosen forwarder.
   files = [{ name, mimeType, dataBase64 }]  (uploaded from the page) */
function sendDocuments(token, ref, files) {
  requireAuth_(token);
  var b = bkFind_(ref);
  if (!b) throw new Error('Booking ' + ref + ' not found');
  var won = b.won;
  if (!won) throw new Error('No forwarder chosen yet for ' + ref);
  var f = null;
  for (var i = 0; i < FORWARDERS.length; i++) { if ((FORWARDERS[i].name || '') === won) { f = FORWARDERS[i]; break; } }
  if (!f || !f.email) throw new Error('No email on file for chosen forwarder "' + won + '"');

  var atts = (files || []).map(function (x) {
    var bytes = Utilities.base64Decode(x.dataBase64);
    return Utilities.newBlob(bytes, x.mimeType || 'application/octet-stream', x.name || 'document');
  });

  var subject = 'Shipping documents — ' + ref + ' — ' + b.vessel + ' to ' + b.pod_name;
  var greet = f.name ? f.name.split(' ')[0] : 'Team';
  var body = 'Dear ' + greet + ',\n\n' +
    'Please find attached the shipping documents for the booking below.\n\n' +
    'Booking ref: ' + ref + '\n' +
    'Carrier: ' + b.carrier + '\n' +
    'Vessel / voyage: ' + b.vessel + (b.voyage ? ' / ' + b.voyage : '') + '\n' +
    'From: Nhava Sheva (INNSA)\n' +
    'To: ' + b.pod_name + ', ' + b.country + '\n' +
    (b.stuffing ? 'Stuffing date: ' + b.stuffing + '\n' : '') +
    (b.container ? 'Containers: ' + b.container + '\n' : '') +
    '\nAttached: Packing List, Commercial Invoice and VGM (Verified Gross Mass).\n\n' +
    'Warm regards,\nExport Team\nAlok Ingots (Mumbai) Pvt. Ltd.';

  var opts = { name: BOOKING_FROM_NAME, attachments: atts };
  if (BOOKING_REPLY_TO) opts.replyTo = BOOKING_REPLY_TO;
  MailApp.sendEmail(f.email, subject, body, opts);

  var when = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'dd-MMM-yyyy HH:mm');
  bkSet_(b._row, 'docs_sent_at', when);
  bkSet_(b._row, 'stage', 'docs');
  return { to: f.email, count: atts.length };
}


/* =======================================================================
 *   LOGIN / SESSION  (username + password gate)
 *   FIRST-TIME SETUP:
 *     1) Put your real users in USERS_SETUP below (plain passwords, just this once).
 *     2) In the editor, pick setupUsers from the function list and Run it.
 *        It writes the users to a hidden "users" tab with the passwords SCRAMBLED (hashed).
 *     3) Then BLANK the passwords in USERS_SETUP back to '' and save, so no plain
 *        password is left in the code. Add/repeat anytime to add users.
 *   ======================================================================= */

var USERS_TAB    = 'users';
var SESSION_HOURS = 6;                       // how long a login stays valid (max 6)
var PW_SALT      = 'AlokIngots::SailingFinder::v1';   // change once; keep it constant after

// ---- edit for first-time setup, then blank the passwords out again ----
var USERS_SETUP = [
  { user: 'admin',     pass: '', name: 'Admin' },
  { user: 'logistics', pass: '', name: 'Logistics' }
];
// ----------------------------------------------------------------------

/* Run this ONCE from the editor after filling USERS_SETUP. Read-only to the schedule. */
function setupUsers() {
  var ss = SpreadsheetApp.openById(SHEET_ID);
  var sh = ss.getSheetByName(USERS_TAB);
  if (!sh) { sh = ss.insertSheet(USERS_TAB); }
  var rows = USERS_SETUP.filter(function (u) { return u.user && u.pass; })
    .map(function (u) { return [String(u.user).trim().toLowerCase(), hashPw_(u.pass), u.name || u.user]; });
  if (!rows.length) { return 'Nothing to write — fill USERS_SETUP with user + pass first.'; }
  // merge with existing users (update password if the username already exists)
  var existing = {};
  if (sh.getLastRow() > 1) {
    var cur = sh.getRange(2, 1, sh.getLastRow() - 1, 3).getValues();
    cur.forEach(function (r) { if (r[0]) existing[String(r[0]).trim().toLowerCase()] = [r[0], r[1], r[2]]; });
  }
  rows.forEach(function (r) { existing[r[0]] = r; });
  var out = Object.keys(existing).map(function (k) { return existing[k]; });
  sh.clear();
  sh.getRange(1, 1, 1, 3).setValues([['username', 'password_hash', 'name']]);
  if (out.length) sh.getRange(2, 1, out.length, 3).setValues(out);
  return out.length + ' user(s) saved. Now blank the passwords in USERS_SETUP.';
}

function hashPw_(pw) {
  var raw = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, String(pw) + '::' + PW_SALT, Utilities.Charset.UTF_8);
  return raw.map(function (b) { return ('0' + (b & 0xFF).toString(16)).slice(-2); }).join('');
}

/* Called by the login screen. Returns {ok:true, token, name} or {ok:false}. */
function login(user, pass) {
  user = String(user || '').trim().toLowerCase();
  if (!user || !pass) return { ok: false };
  var sh = SpreadsheetApp.openById(SHEET_ID).getSheetByName(USERS_TAB);
  if (!sh || sh.getLastRow() < 2) { throw new Error('No users set up yet — run setupUsers() once.'); }
  var vals = sh.getRange(2, 1, sh.getLastRow() - 1, 3).getValues();
  var want = hashPw_(pass);
  for (var i = 0; i < vals.length; i++) {
    if (String(vals[i][0]).trim().toLowerCase() === user && String(vals[i][1]).trim() === want) {
      var token = Utilities.getUuid().replace(/-/g, '');
      CacheService.getScriptCache().put('sess_' + token, user, SESSION_HOURS * 3600);
      return { ok: true, token: token, name: vals[i][2] || user };
    }
  }
  return { ok: false };
}

function logout(token) {
  if (token) CacheService.getScriptCache().remove('sess_' + String(token));
  return true;
}

/* Throws if the token isn't a valid live session. Every data function calls this. */
function requireAuth_(token) {
  var u = token ? CacheService.getScriptCache().get('sess_' + String(token)) : null;
  if (!u) { throw new Error('Please sign in again.'); }
  return u;
}
