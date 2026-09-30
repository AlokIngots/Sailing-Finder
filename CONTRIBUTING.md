# Contributing — Sailing Finder

React (Vite) + FastAPI + PostgreSQL, on our own VPS.

These are the rules for this repo. They are not suggestions, and they are not
overridden by time pressure.

---

## The never-do list

- Never edit `main` or `dev` directly.
- Never go live by hand. `./deploy.sh` is the only way.
- Never commit `.env`, a password, an API key, or a service-account key.
- Never paste a live key, secret, or database password into chat.
- Never commit customer files, uploads, PO PDFs, `.xlsx`/`.csv` exports,
  `node_modules/`, `.venv/`, or `dist/`.
- Never print, log, or echo a secret — not even temporarily, for debugging.
- Never delete code you do not fully understand.
- Never assume a migration ran. Check it.
- Never `git push --force` to a shared branch.
- Never install a package without an explicit **APPROVED** from the project owner.
- Never put AI-attribution lines in a commit message — no `Co-Authored-By`,
  no "Generated with…".

---

## Branches and pull requests

```
main        always deployed, always stable, protected
dev         integration branch, no direct commits
feature/*   one branch per task
hotfix/*    emergency only — PR to main, then back-merge to dev
```

Every task:

```
git checkout dev
git pull origin dev
git checkout -b feature/short-description
# ...work, commit often...
git push -u origin feature/short-description
# open a Pull Request into dev
```

One person reviews, merges, and deploys. Branch names look like
`feature/finder-filters`, `feature/whatsapp-share`.

Commit messages: `type(scope): what changed — why`

```
feat(finder): add Next-per-port toggle — customers only need the soonest sailing
fix(sync): keep existing rows when the sheet read fails — a bad pull emptied the list
```

Commit as you go. Never leave a session with uncommitted work — run
`git status` before switching branches.

---

## Back up before you change anything

State the rollback **at the same time** as the change, before making it. If you
cannot state the rollback, you cannot make the change.

```bash
# file
cp backend/app/routers/schedule.py ~/sailing_backups/schedule.py.bak.$(date +%Y%m%d_%H%M%S)

# commit
git tag backup/task-name-$(date +%Y%m%d)

# database table — before ANY schema change or bulk delete
CREATE TABLE bk_bookings_20260930 AS SELECT * FROM bookings;
```

`.bak` files live **outside** the repo (`~/sailing_backups/`) and are gitignored
anyway. They are never committed.

---

## APPROVED required

The word **APPROVED**, in capitals, from the project owner, before:

- installing any package — Python or npm
- any schema change (`CREATE` / `ALTER` / `DROP`)
- deleting any file or block of code
- changing authentication or session logic
- changing `.env.example`, `docker-compose.yml`, or the proxy config
- deploying to production

While waiting for APPROVED: do not find a workaround, do not "just do the other
bit", do not touch adjacent files.

Once approved, the install and its lockfile go in **one commit**:
`requirements.lock.txt` for Python, `package-lock.json` for the frontend.

---

## Scope

One objective per session. If you spot something else wrong:

1. finish the task you were given,
2. write `⚠️ NOTICED (not touching): <what>`,
3. ask whether to do it next, as a separate task.

"While I'm in here I'll also fix…" is never acceptable.

---

## Deploying

```bash
./deploy.sh
```

It refuses a dirty tree or the wrong branch, dumps the database first, builds
the React bundle and the FastAPI image, import-checks the built image, fails the
deploy if any of that breaks, tags a rollback point, applies migrations, and
rolls back automatically if `/healthz` does not come up.

Roll back:

```bash
git checkout <the deploy/ tag printed by the last good deploy>
./deploy.sh
```

Restore the database:

```bash
gunzip -c ~/sailing_finder_backups/sailing_<stamp>.sql.gz | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

If a deploy causes a 502 or a silent failure within 15 minutes, roll back
immediately. Tell the project owner; do not wait to be told.

After deploying, verify **on the server** — not the local copy — and check the
endpoint actually answers.

---

## Before you call anything done

- [ ] tests pass (`pytest` in `backend/`)
- [ ] the build is clean (`docker compose build app`)
- [ ] checked in a browser at **desktop width and ~400px phone width** — this is
      mandatory, not a nice-to-have
- [ ] **isolation check**: signed in as two different users; each sees only
      their own bookings, and an admin sees all
- [ ] error states show visibly — "found 0" and "failed to load" look different
- [ ] nothing adjacent broke
- [ ] no new ERROR or WARNING lines in `docker compose logs app`
- [ ] the rollback path is written down

"It works on my machine" is not done. "I've written the code" is not done.
Done means written → committed → reviewed → deployed → verified live.

---

## House style

- **Light theme only.** Navy `#000C2E`, red `#BC0300` (signal only), orange
  `#E5531A` (logo mark only), white paper. No dark mode.
- **Mobile-responsive is mandatory.** Usable on a phone, not just desktop.
- **Do not validate operator-judgement fields.** Stuffing date, target rate,
  weights, rates and remarks stay free text. If a value looks wrong, raise it in
  conversation — never bake it into the software as a block.

**Python**

- Files and functions `snake_case`; classes `PascalCase`; constants `ALL_CAPS`.
- One router module per feature/screen, under `app/routers/`.
- Shared logic lives in `app/services/` and is written once.
- Raw parameterised SQL with `%s` — never f-strings or concatenation.
- Response envelope everywhere: `{"status": ..., "data": ..., "message": ...}`.
- Never return a raw exception to the frontend. Log it, return a sanitised
  message. Use `logging`, never `print`, in application code.
- Every query on `schedule` or `bookings` is bounded — pagination or `LIMIT`.
- Booleans read as `is_`/`has_`/`can_`.

**React**

- One component per file, `PascalCase.jsx`, under `src/components/`.
- All API calls go through `src/api.js`. No bare `fetch` in a component.
- Reuse the existing shared components. No one-off restyled button or modal.
- Status labels and action names match what is already on screen — no renaming
  for aesthetics.
- Never treat a client-side check as security. `require_auth` on the server is
  the boundary.

**API**

- Paths are `kebab-case` (`/api/wa-contacts`).
- Specific routes register **before** parameterised ones.
- Every endpoint has auth, a role scope, and a defined response shape before it
  is called done.
- 201 is a success. Do not treat it as an error.

---

## Secrets

If a secret ever lands in chat, a log, or a commit: treat it as compromised.
Rotate it **before** doing anything else.

`.gitignore` must keep covering: `.env`, `*.bak`, `uploads/`, `*.key`, `*.pem`,
`node_modules/`, `.venv/`, `dist/`.
