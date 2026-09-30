# Contributing — Sailing Finder

These are the rules for this repo. They are not suggestions, and they are not
overridden by time pressure.

---

## The never-do list

- Never edit `main` or `dev` directly.
- Never go live by hand. `./deploy.sh` is the only way.
- Never commit `.env`, a password, an API key, or a service-account key.
- Never paste a live key, secret, or database password into chat.
- Never commit customer files, uploads, PO PDFs, or `.xlsx`/`.csv` exports.
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
cp backend/src/routes/schedule.js ~/sailing_backups/schedule.js.bak.$(date +%Y%m%d_%H%M%S)

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

- installing any package or dependency
- any schema change (`CREATE` / `ALTER` / `DROP`)
- deleting any file or block of code
- changing authentication or session logic
- changing `.env.example`, `docker-compose.yml`, or the proxy config
- deploying to production

While waiting for APPROVED: do not find a workaround, do not "just do the other
bit", do not touch adjacent files.

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

It refuses to run on a dirty tree or off `main`, dumps the database first,
fails the deploy if the build is broken, tags a rollback point, applies
migrations, and rolls back automatically if `/healthz` does not come up.

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

After deploying, verify the file **on the server**, not the local copy, and
check the endpoint actually answers.

---

## Before you call anything done

- [ ] `npm test` passes
- [ ] the build is clean (`docker compose build app`)
- [ ] checked in a browser at **desktop width and ~400px phone width** — this is
      mandatory, not a nice-to-have
- [ ] **isolation check**: signed in as two different users, each sees only
      their own bookings
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
  weights and remarks stay free text. If a value looks wrong, raise it in
  conversation — never bake it into the software as a block.
- Files: `snake_case.js`. Functions: `camelCase`. API paths: `kebab-case`.
  Tables: `snake_case`, plural. Constants: `ALL_CAPS`. Booleans: `is_`/`has_`/`can_`.
- Raw parameterised SQL (`$1`, `$2`) — never string concatenation.
- Response envelope everywhere: `{ "status": ..., "data": ..., "message": ... }`.
- Never return a raw exception to the frontend. Log it internally, return a
  sanitised message.
- Log errors as `console.error('[route-name]', err)`. No `print`-style debugging
  left in production code.
- Specific routes register **before** parameterised ones (`/bookings/export`
  before `/bookings/:ref`).
- Every query on `schedule` or `bookings` is bounded — pagination or `LIMIT`.

---

## Secrets

If a secret ever lands in chat, a log, or a commit: treat it as compromised.
Rotate it **before** doing anything else.

`.gitignore` must keep covering: `.env`, `*.bak`, `uploads/`, `*.key`, `*.pem`.
