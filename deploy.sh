#!/usr/bin/env bash
#
# Sailing Finder — THE only way to go live.
#
#   ./deploy.sh
#
# What it does, in order:
#   1. refuses to run on a dirty working tree or off the deploy branch
#   2. dumps the database to a timestamped file OUTSIDE the repo
#   3. builds the new image  -- if the build fails, nothing is touched
#   4. tags the current commit so there is always a rollback point
#   5. restarts the app, runs migrations, waits for /healthz
#   6. rolls back automatically if the health check does not pass
#
# Rollback by hand:
#   git checkout <tag printed at the end of the last good deploy> && ./deploy.sh
# Restore the database:
#   gunzip -c <dump>.sql.gz | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"

set -Eeuo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/sailing_finder_backups}"
STAMP="$(date +%Y%m%d_%H%M%S)"
HEALTH_URL="http://127.0.0.1:${APP_PORT:-8080}/healthz"
HEALTH_RETRIES=30

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
grn()  { printf '\033[32m%s\033[0m\n' "$*"; }
info() { printf '\033[36m==> %s\033[0m\n' "$*"; }
die()  { red "DEPLOY ABORTED: $*"; exit 1; }

# ---------------------------------------------------------------------------
# 0. Pre-flight
# ---------------------------------------------------------------------------
info "Pre-flight checks"

[ -f backend/.env ] || die "backend/.env is missing. Copy backend/.env.example and fill it in."

# shellcheck disable=SC1091
set -a; . ./backend/.env; set +a

: "${POSTGRES_USER:?POSTGRES_USER not set in backend/.env}"
: "${POSTGRES_DB:?POSTGRES_DB not set in backend/.env}"

command -v docker >/dev/null 2>&1 || die "docker not found"
docker compose version >/dev/null 2>&1 || die "docker compose v2 not found"

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
[ "$BRANCH" = "$DEPLOY_BRANCH" ] || die "on branch '$BRANCH'. Live only deploys from '$DEPLOY_BRANCH'."

if [ -n "$(git status --porcelain)" ]; then
  die "uncommitted changes present. Commit or stash first — what deploys must be what is committed."
fi

info "Fetching latest $DEPLOY_BRANCH"
git pull --ff-only origin "$DEPLOY_BRANCH" || die "git pull failed (not a fast-forward?)"

COMMIT="$(git rev-parse --short HEAD)"
ROLLBACK_TAG="deploy/${STAMP}-${COMMIT}"

# ---------------------------------------------------------------------------
# 1. Database backup — BEFORE anything else changes
# ---------------------------------------------------------------------------
info "Backing up the database"
mkdir -p "$BACKUP_DIR"
DUMP="$BACKUP_DIR/sailing_${STAMP}.sql.gz"

if docker compose ps --status running --services 2>/dev/null | grep -qx db; then
  docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    | gzip > "$DUMP" || die "pg_dump failed — refusing to deploy without a backup"
  [ -s "$DUMP" ] || die "backup file is empty — refusing to deploy"
  grn "    backup: $DUMP ($(du -h "$DUMP" | cut -f1))"
else
  echo "    db container not running (first deploy?) — nothing to back up"
  DUMP="(none — first deploy)"
fi

# ---------------------------------------------------------------------------
# 2. Build — a broken build stops here, live is untouched
# ---------------------------------------------------------------------------
info "Building the image"
docker compose build app || die "build failed — live site untouched"

info "Checking the built image actually starts (import check)"
docker compose run --rm --no-deps --entrypoint node app -e "require('./src/config.js'); console.log('imports OK')" \
  || die "the built image cannot load its own code — live site untouched"

# ---------------------------------------------------------------------------
# 3. Rollback point
# ---------------------------------------------------------------------------
git tag -f "$ROLLBACK_TAG" >/dev/null
info "Rollback point tagged: $ROLLBACK_TAG"

# ---------------------------------------------------------------------------
# 4. Roll out
# ---------------------------------------------------------------------------
PREV_IMAGE="$(docker compose images -q app 2>/dev/null || true)"

info "Starting database"
docker compose up -d db

info "Applying migrations"
docker compose run --rm --entrypoint node app src/db/migrate.js || die "migration failed — live site untouched"

info "Starting app"
docker compose up -d app

# ---------------------------------------------------------------------------
# 5. Health check
# ---------------------------------------------------------------------------
info "Waiting for $HEALTH_URL"
OK=0
for i in $(seq 1 "$HEALTH_RETRIES"); do
  if curl -fsS --max-time 3 "$HEALTH_URL" >/dev/null 2>&1; then OK=1; break; fi
  sleep 2
done

if [ "$OK" -ne 1 ]; then
  red "Health check FAILED after $((HEALTH_RETRIES * 2))s — rolling back"
  docker compose logs --tail=80 app || true
  if [ -n "$PREV_IMAGE" ]; then
    docker compose down app || true
    docker tag "$PREV_IMAGE" "$(docker compose config --images app | head -1)" || true
    docker compose up -d app || true
  fi
  die "deploy rolled back. Database backup is safe at: $DUMP"
fi

# ---------------------------------------------------------------------------
# 6. Done
# ---------------------------------------------------------------------------
grn ""
grn "DEPLOY OK"
grn "  commit:        $COMMIT ($DEPLOY_BRANCH)"
grn "  rollback tag:  $ROLLBACK_TAG"
grn "  db backup:     $DUMP"
grn ""
grn "To roll back:  git checkout $ROLLBACK_TAG && ./deploy.sh"
