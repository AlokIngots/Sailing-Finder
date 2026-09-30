# Sailing Finder — backend image.
# Serves the Express API and the static frontend from one container.
#
# Build context is the REPO ROOT (see docker-compose.yml), so that the
# frontend/ folder can be copied in alongside the backend.

FROM node:22-alpine

ENV NODE_ENV=production
ENV TZ=Asia/Kolkata

WORKDIR /app

# Install dependencies first so code edits don't bust the layer cache.
# package-lock.json is committed; `npm ci` fails loudly if it drifts from
# package.json, which is what we want on a deploy.
COPY backend/package*.json ./
RUN npm ci --omit=dev

# Application code
COPY backend/src     ./src
COPY backend/jobs    ./jobs
COPY backend/scripts ./scripts

# Static frontend (split out of reference/Index.html — see README)
COPY frontend ./frontend

# Customer documents live on a volume, never in the image
RUN mkdir -p /app/uploads && chown -R node:node /app/uploads

USER node
EXPOSE 8080

CMD ["node", "src/index.js"]
