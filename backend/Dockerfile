# Sailing Finder — one image: the React build plus the FastAPI app that serves it.
#
# Build context is the REPO ROOT (see docker-compose.yml), so both frontend/ and
# backend/ are reachable.
#
# Stage 1 builds the Vite bundle. Stage 2 is the runtime — Node does not ship to
# production, only the static files it produced.

# ---------------------------------------------------------------------------
# Stage 1 — build the React app
# ---------------------------------------------------------------------------
FROM node:22-alpine AS frontend

WORKDIR /build

# Dependencies first so source edits don't bust the layer cache.
# npm ci fails loudly if package-lock.json drifts from package.json — exactly
# what we want on a deploy.
COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build          # -> /build/dist

# ---------------------------------------------------------------------------
# Stage 2 — FastAPI runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Kolkata \
    FRONTEND_DIST=/app/frontend_dist

# curl is used by the container health check. postgresql-client gives deploy.sh
# a pg_dump that matches the server version.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl postgresql-client tzdata \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app     ./app
COPY backend/db      ./db
COPY backend/jobs    ./jobs
COPY backend/scripts ./scripts

COPY --from=frontend /build/dist ./frontend_dist

# Customer documents live on a volume, never in the image.
RUN useradd --create-home --uid 10001 sailing \
 && mkdir -p /app/uploads \
 && chown -R sailing:sailing /app

USER sailing
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
