-- Sailing Finder — database schema
-- Safe to re-run: every statement is IF NOT EXISTS / idempotent.
-- Applied by: python backend/db/migrate.py
--
-- Rollback for a fresh install (DESTRUCTIVE — never run against live data):
--   DROP TABLE IF EXISTS enquiry_rate_history, enquiry_quotes, enquiries,
--     bookings, saved_contacts, wa_contacts, schedule, sessions, users CASCADE;
--   DROP SEQUENCE IF EXISTS enquiry_ref_seq;

-- ---------------------------------------------------------------------------
-- users — who can sign in. Passwords are hashed (passlib/bcrypt), never stored
-- in plain text. role is 'user' (sees only their own bookings) or 'admin'
-- (sees all). There is no public sign-up — accounts are made by an admin.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
  id            BIGSERIAL PRIMARY KEY,
  username      TEXT        NOT NULL UNIQUE,
  password_hash TEXT        NOT NULL,
  name          TEXT,
  role          TEXT        NOT NULL DEFAULT 'user',
  is_active     BOOLEAN     NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- sessions — server-side session store.
--
-- The browser only ever holds the signed session id in an HTTP-only cookie;
-- everything about the session lives here. A container restart therefore does
-- not sign everyone out, and revoking a session is a single DELETE.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
  sid         TEXT        PRIMARY KEY,
  user_id     BIGINT      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at  TIMESTAMPTZ NOT NULL,
  user_agent  TEXT,
  ip          TEXT
);

CREATE INDEX IF NOT EXISTS sessions_user_id_idx    ON sessions (user_id);
CREATE INDEX IF NOT EXISTS sessions_expires_at_idx ON sessions (expires_at);

-- ---------------------------------------------------------------------------
-- schedule — mirror of the `all_schedule` tab of the scrapers' Google Sheet.
--
-- Filled by app/services/sheet_sync.py (INSERT ... ON CONFLICT (row_key) DO
-- UPDATE, so a re-sync updates a changed sailing instead of duplicating it).
-- Cleaned by app/services/cleanup.py: DELETE FROM schedule WHERE etd < CURRENT_DATE;
-- so the table only ever holds today + future sailings, same as the sheet.
--
-- etd/eta are real DATEs (not text) so the cleanup and the date-range filters
-- work correctly.
-- `transshipment` is kept as TEXT to preserve exactly what the sheet holds:
-- '0' = Direct, '1'+ = Indirect, '' / NULL = unlabelled (shown only under All).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schedule (
  id            BIGSERIAL PRIMARY KEY,
  carrier       TEXT,
  pol_code      TEXT,
  pol_name      TEXT,
  pod_code      TEXT,
  pod_name      TEXT,
  vessel_name   TEXT,
  voyage_no     TEXT,
  etd           DATE,
  eta           DATE,
  transit_days  INTEGER,
  transshipment TEXT,
  service       TEXT,
  source        TEXT,
  pulled_on     TIMESTAMPTZ,
  row_key       TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS schedule_row_key_uidx ON schedule (row_key);
CREATE INDEX IF NOT EXISTS schedule_etd_idx      ON schedule (etd);
CREATE INDEX IF NOT EXISTS schedule_pod_code_idx ON schedule (pod_code);
CREATE INDEX IF NOT EXISTS schedule_carrier_idx  ON schedule (carrier);

-- ---------------------------------------------------------------------------
-- bookings — one row per enquiry, moving through the 4 stages.
--
-- stage: sent -> quotes -> booked -> docs
--
-- `created_by` scopes a booking to the person who raised it: a logistics user
-- sees only their own, role = 'admin' sees all. Same rule as our other tools.
-- Confirmed by the project owner — this is the intended behaviour, not a guess.
-- Every query in routers/bookings.py enforces it in SQL, never in the frontend.
--
-- `stuffing`, `remarks` (target rate) and the weights are deliberately TEXT
-- with no CHECK constraints — these are operator-judgement fields and must
-- stay free per the golden rules.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bookings (
  id           BIGSERIAL PRIMARY KEY,
  ref          TEXT        NOT NULL UNIQUE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by   BIGINT      REFERENCES users (id) ON DELETE SET NULL,
  stage        TEXT        NOT NULL DEFAULT 'sent'
                 CHECK (stage IN ('sent', 'quotes', 'booked', 'docs')),
  carrier      TEXT,
  vessel       TEXT,
  voyage       TEXT,
  pol_code     TEXT,
  pod_code     TEXT,
  pod_name     TEXT,
  country      TEXT,
  etd          DATE,
  eta          DATE,
  transit_days INTEGER,
  stuffing     TEXT,
  container    TEXT,
  commodity    TEXT,
  net_wt       TEXT,
  gross_wt     TEXT,
  remarks      TEXT,
  sent_to      TEXT,
  quotes_json  JSONB       NOT NULL DEFAULT '[]'::jsonb,
  won          TEXT,
  docs_sent_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS bookings_created_by_idx ON bookings (created_by);
CREATE INDEX IF NOT EXISTS bookings_created_at_idx ON bookings (created_at DESC);
CREATE INDEX IF NOT EXISTS bookings_stage_idx      ON bookings (stage);

-- ---------------------------------------------------------------------------
-- enquiries — one row per enquiry emailed from the Finder's Enquire modal,
-- written by POST /api/enquiry once at least one forwarder was sent it.
-- Separate from `bookings` above (My bookings), which it does not touch.
--
-- `ref` (ENQ-0001, from enquiry_ref_seq) is in the email subject, so a
-- forwarder's reply can be matched back to its enquiry.
--
-- `created_by` is the username. A normal user sees only their own rows,
-- role = 'admin' sees all — enforced in SQL in services/enquiries.py.
--
-- status: sent -> quoting (a rate entered) -> confirmed (winner marked)
--         -> booked (not set by the app yet)
--
-- The form fields are TEXT with no CHECKs: operator-judgement fields, free.
--
-- `winner_quote_id` has no FK: enquiry_quotes references enquiries, and a
-- second FK back would make the two tables depend on each other. The code
-- only ever sets it to a quote of the same enquiry.
--
-- Rollback (new tables only — nothing above is touched):
--   DROP TABLE IF EXISTS enquiry_rate_history, enquiry_quotes, enquiries;
--   DROP SEQUENCE IF EXISTS enquiry_ref_seq;
-- ---------------------------------------------------------------------------
CREATE SEQUENCE IF NOT EXISTS enquiry_ref_seq;

CREATE TABLE IF NOT EXISTS enquiries (
  id              BIGSERIAL PRIMARY KEY,
  ref             TEXT        NOT NULL UNIQUE,
  vessel          TEXT,
  voyage          TEXT,
  carrier         TEXT,
  pod_name        TEXT,
  country         TEXT,
  etd             DATE,
  eta             DATE,
  transit_days    INTEGER,
  stuffing_date   TEXT,
  containers      TEXT,
  net_weight      TEXT,
  gross_weight    TEXT,
  commodity       TEXT,
  remarks         TEXT,
  created_by      TEXT        NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  status          TEXT        NOT NULL DEFAULT 'sent'
                    CHECK (status IN ('sent', 'quoting', 'confirmed', 'booked')),
  winner_quote_id BIGINT
);

CREATE INDEX IF NOT EXISTS enquiries_created_by_idx ON enquiries (created_by);
CREATE INDEX IF NOT EXISTS enquiries_created_at_idx ON enquiries (created_at DESC);

-- One row per forwarder the enquiry was emailed to. replied_at / reply_text
-- are for matching replies by ref (stage 2); quoted_rate and notes are typed
-- in on the Enquiries screen — free text.
CREATE TABLE IF NOT EXISTS enquiry_quotes (
  id              BIGSERIAL PRIMARY KEY,
  enquiry_id      BIGINT      NOT NULL REFERENCES enquiries (id) ON DELETE CASCADE,
  forwarder_name  TEXT        NOT NULL,
  forwarder_email TEXT        NOT NULL,
  replied_at      TIMESTAMPTZ,
  reply_text      TEXT,
  quoted_rate     TEXT,
  notes           TEXT,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS enquiry_quotes_enquiry_id_idx ON enquiry_quotes (enquiry_id);

-- The rate a quote had before each change (NULL = it was empty).
CREATE TABLE IF NOT EXISTS enquiry_rate_history (
  id         BIGSERIAL PRIMARY KEY,
  quote_id   BIGINT      NOT NULL REFERENCES enquiry_quotes (id) ON DELETE CASCADE,
  old_rate   TEXT,
  changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS enquiry_rate_history_quote_id_idx ON enquiry_rate_history (quote_id);

-- ---------------------------------------------------------------------------
-- wa_contacts — saved WhatsApp numbers for the share dropdown.
-- `number` is digits including country code, no +, no spaces.
-- Shared across all users (the Apps Script behaviour). No longer read since
-- per-user saved_contacts replaced it; kept so no saved number is lost.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wa_contacts (
  id         BIGSERIAL PRIMARY KEY,
  name       TEXT,
  number     TEXT        NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- saved_contacts — each user's own saved WhatsApp numbers and email addresses
-- for the share boxes, remembered automatically after a successful send.
-- kind 'wa': `value` is digits with country code, no +, no spaces.
-- kind 'email': `value` is the address, trimmed and lower-cased.
-- One row per (user, kind, value); sending again bumps last_used_at, which
-- orders the dropdown most-recently-used first. role = 'admin' sees everyone's
-- — enforced in SQL in services/saved_contacts.py.
--
-- Rollback (DESTRUCTIVE): DROP TABLE IF EXISTS saved_contacts;
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS saved_contacts (
  id           BIGSERIAL PRIMARY KEY,
  username     TEXT        NOT NULL,
  kind         TEXT        NOT NULL CHECK (kind IN ('wa', 'email')),
  value        TEXT        NOT NULL,
  name         TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (username, kind, value)
);

CREATE INDEX IF NOT EXISTS saved_contacts_recent_idx
  ON saved_contacts (username, kind, last_used_at DESC);
