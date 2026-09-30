-- Sailing Finder — database schema
-- Safe to re-run: every statement is IF NOT EXISTS / idempotent.
-- Applied by: python backend/db/migrate.py
--
-- Rollback for a fresh install (DESTRUCTIVE — never run against live data):
--   DROP TABLE IF EXISTS bookings, wa_contacts, schedule, sessions, users CASCADE;

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
-- wa_contacts — saved WhatsApp numbers for the share dropdown.
-- `number` is digits including country code, no +, no spaces.
-- Currently shared across all users (matches the Apps Script behaviour).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wa_contacts (
  id         BIGSERIAL PRIMARY KEY,
  name       TEXT,
  number     TEXT        NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
