# Sailing Finder

Login-protected web app for **Alok Ingots (Mumbai) Pvt. Ltd.** It replaces the
Google Apps Script version and runs on our own Hostinger VPS (KVM 8), alongside
n8n.

Two jobs:

1. **Find a sailing** — filter the schedule our scrapers collect (country, port,
   carrier, departure and arrival windows, direct vs indirect), then copy,
   download, email or WhatsApp the list to a customer.
2. **Run the enquiry** — send the request to our three forwarders, collect their
   quotes, pick one, and send the documents. Four stages:
   *request sent → quotes in → booked → docs sent*.

---

## Status

**Login gate and finder built.** Sign in, sign out, `GET /api/me`, server-side
sessions, the account script, the schedule sync and the finder screen all work
and are covered by tests. Enquiry, bookings, shipment and the two share
endpoints still answer `501` until their own branches.

Blocked on three things:

- **`reference/Index.html` and `reference/Code.gs` are still missing.** They are
  meant to be the source of truth for look and behaviour. The finder has
  therefore been built to the **written** specification, not ported from the
  reference — every control it asks for is present and behaves as described, but
  the layout and styling are not a copy of the Apps Script screen, because
  there is nothing to copy. Expect to reconcile the visuals when the files turn
  up. See `reference/README.md`.
- **VPS details.** Which reverse proxy is in front (Nginx / Caddy / Traefik) and
  its Docker network name. Marked `TODO(vps)` in `docker-compose.yml`.
- **Nothing has run against a real Postgres.** There is no database on a
  developer machine here, so the SQL is unverified even though the logic that
  builds it is tested.

---

## How it fits together

```
scrapers  ──►  Google Sheet (all_schedule)  ──►  sheet_sync  ──►  Postgres `schedule`  ──►  /api/schedule  ──►  React app
   (unchanged, not touched by this app)          daily job                  ▲
                                                                       cleanup
                                                          DELETE WHERE etd < CURRENT_DATE
```

The scrapers and the sheet are **not** modified. This app only reads the sheet,
through a read-only Google service account. The browser never reads the sheet —
it only ever calls `/api/*`.

### The auto-delete logic

The sheet self-cleans: only today and future sailings stay in it. The database
copies that behaviour so the app can never show a ship that has already left.

1. **Sync** (`app/services/sheet_sync.py`, daily late morning, after the
   scrapers) — read `all_schedule` and upsert every row:
   `INSERT ... ON CONFLICT (row_key) DO UPDATE`. New sailings are inserted,
   changed ones update in place, nothing duplicates.
2. **Cleanup** (`app/services/cleanup.py`, at the end of each sync and again
   daily) — `DELETE FROM schedule WHERE etd < CURRENT_DATE;`
3. **Safety** — the rows about to go are copied into a timestamped
   `bk_schedule_<stamp>` table first, and only genuinely past rows are deleted.
   There is no wipe-and-reload anywhere, so a failed sync cannot lose upcoming
   sailings. Backup tables older than 7 days are pruned.

Both are scheduled by APScheduler in `backend/jobs/daily.py`, which runs as its
own `jobs` container off the same image as the app — so the jobs can never drift
from the app's code.

Rollback for a bad cleanup:

```sql
INSERT INTO schedule SELECT * FROM bk_schedule_<stamp> ON CONFLICT (row_key) DO NOTHING;
```

---

## Stack

| Part       | Choice                                                         |
|------------|----------------------------------------------------------------|
| Frontend   | React + Vite, React Router, plain CSS ported from the reference |
| Backend    | FastAPI (Python 3.12) on uvicorn                               |
| Database   | PostgreSQL 16                                                  |
| Packaging  | Docker + docker compose — app, db, jobs                        |
| Front door | The VPS reverse proxy → `sailing.alokindia.com` over HTTPS     |
| Email      | SMTP (aiosmtplib) from `exports@alokindia.com`                 |
| WhatsApp   | Interakt HTTP API                                              |
| PDF        | reportlab, server-side                                         |

One image holds both halves: a Node stage builds the Vite bundle, and the Python
stage serves it. Same origin for app and API, so the session cookie works
without CORS and only one port exists. That port is **not** published to the
internet — the proxy reaches it over the shared Docker network.

---

## Layout

```
sailing_finder/
├─ backend/
│  ├─ app/
│  │  ├─ main.py             FastAPI app, envelope + error handling, serves the build
│  │  ├─ config.py           reads and validates .env
│  │  ├─ db.py               psycopg connection pool
│  │  ├─ deps.py             require_auth / require_admin
│  │  ├─ routers/            auth, schedule, bookings, share, wa_contacts
│  │  └─ services/           sheet_sync, cleanup, mailer, whatsapp, pdf, security
│  ├─ db/                    schema.sql, migrate.py
│  ├─ jobs/daily.py          APScheduler: sync then cleanup
│  ├─ scripts/create_user.py add a sign-in account
│  ├─ requirements.txt
│  ├─ Dockerfile
│  └─ .env.example
├─ frontend/
│  ├─ index.html             Vite entry — no data is ever baked into it
│  ├─ vite.config.js
│  └─ src/
│     ├─ main.jsx, App.jsx, api.js
│     ├─ styles/app.css
│     ├─ components/         Login, Finder, SailingRow, EnquiryModal, Bookings, Shipment
│     └─ lib/format.js       shipType, leaving-soon, date helpers
├─ reference/                Index.html + Code.gs — source of truth (pending)
├─ docker-compose.yml
├─ deploy.sh                 the only way to go live
├─ CONTRIBUTING.md           the rules — read before your first commit
└─ README.md
```

---

## Database

| Table         | What it holds                                                      |
|---------------|--------------------------------------------------------------------|
| `schedule`    | Mirror of the sheet, 15 columns, unique on `row_key`, `etd`/`eta` as real dates |
| `bookings`    | One row per enquiry, `stage` = `sent`/`quotes`/`booked`/`docs`, quotes as JSONB |
| `users`       | Sign-in accounts, bcrypt hashes only, role `user` or `admin`        |
| `wa_contacts` | Saved WhatsApp numbers                                             |
| `sessions`    | Server-side session store, so a restart does not sign everyone out  |

`bookings.created_by` scopes a booking to the person who raised it: a `user`
sees only their own, an `admin` sees all. Enforced in SQL in
`app/routers/bookings.py`, never in the React app.

---

## Running it

### First time, on the VPS

```bash
git clone <repo> /opt/sailing_finder
cd /opt/sailing_finder
cp backend/.env.example backend/.env
nano backend/.env                     # fill in — never commit this file
mkdir -p /opt/sailing_finder/secrets  # put google-key.json here (gitignored)
./deploy.sh
```

### Accounts

There is **no sign-up page**. Accounts exist only because an admin ran
`scripts/create_user.py`:

```bash
docker compose exec -it app python -m scripts.create_user <username> "<Full Name>" [user|admin]
```

It prompts for the password twice, without echoing it. The role defaults to
`user`; `admin` sees every booking, `user` sees only their own.

```bash
# a normal logistics user
docker compose exec -it app python -m scripts.create_user priya "Priya Sharma"

# an admin
docker compose exec -it app python -m scripts.create_user alok "Alok" admin
```

For a setup script or anywhere without a TTY, pass the password through the
environment instead — **never** as an argument, which would land in shell
history and be visible in `ps`:

```bash
docker compose exec -e SF_NEW_PASSWORD='...' app python -m scripts.create_user alok "Alok" admin
```

Running it again for an existing username updates that person's name, role and
password, and signs them out everywhere — a password change should not leave an
old session alive.

Passwords are bcrypt-hashed before they reach the database; the plain value is
never stored, logged, or printed. Minimum 8 characters, maximum 72 bytes
(bcrypt ignores anything past that, so over-long passwords are refused rather
than silently truncated).

Rollback for an account added by mistake:

```sql
CREATE TABLE bk_users_20260930 AS SELECT * FROM users;   -- back up first
DELETE FROM users WHERE username = '<username>';
```

### Day to day

```bash
docker compose logs -f app                          # logs
docker compose exec app python -m db.migrate        # apply schema (safe to re-run)
docker compose exec app python -m jobs.daily        # sync + cleanup, now
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

### Sample data

`services/sheet_sync.py` needs a Google service-account key, which only exists
on the VPS. To get a usable schedule anywhere else:

```bash
python -m scripts.seed_sample              # ~180 made-up sailings over 8 weeks
python -m scripts.seed_sample --count 400
python -m scripts.seed_sample --clear      # remove them again
```

Everything it writes carries `source = 'sample-seed'`, and `--clear` only ever
deletes rows with that marker — so it cannot remove real sailings. The data is
generated from a fixed seed: plausible, repeatable, and entirely invented. No
customer, rate or booking data appears in it.

### Locally

Python 3.12, Node 22, and a Postgres to point at. Two terminals:

```bash
# backend
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m db.migrate
.venv/bin/uvicorn app.main:app --reload --port 8000
.venv/bin/pytest                    # tests need no database

# frontend
cd frontend
npm install
npm run dev        # http://localhost:5173, /api proxied to uvicorn
```

---

## Deploying and rolling back

**`./deploy.sh` is the only way to go live.** Never `docker compose build`/`up`
by hand against the live site.

It refuses a dirty tree or the wrong branch, dumps the database first, builds
both halves, import-checks the built image, fails if any of that breaks, tags a
rollback point, migrates, and rolls back by itself if the health check does not
pass.

```bash
./deploy.sh                                             # deploy
git checkout deploy/<stamp>-<commit> && ./deploy.sh     # roll back the code
gunzip -c ~/sailing_finder_backups/sailing_<stamp>.sql.gz \
  | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"   # roll back the data
```

Health: `GET /healthz` — it queries the database, so it reports real state
rather than just returning 200.

---

## Configuration

Everything lives in `backend/.env`, which is **never committed**. Copy
`backend/.env.example` and fill it in: database URL, Google key path + sheet ID +
tab, SMTP details, Interakt key and template, session secret, the three
forwarders and the booking reply-to, and `TZ=Asia/Kolkata`.

The Google service-account key file stays on the VPS and is mounted read-only
into the container.

---

## Conventions

Light theme only — navy `#000C2E`, red `#BC0300` for signal, orange `#E5531A`
for the logo mark, white paper. No dark mode. Mobile-responsive is mandatory.
Operator-judgement fields (stuffing date, target rate, weights, quoted rates)
are free text and are never validated.

The rest is in **`CONTRIBUTING.md`** — read it before your first commit.
