import { createHash } from 'node:crypto';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const here = fileURLToPath(new URL('.', import.meta.url));

/** Every file under public/, as site paths ('/icons/icon-192.png'). */
function publicFiles(dir = join(here, 'public')) {
  let found = [];
  let entries = [];
  try {
    entries = readdirSync(dir);
  } catch {
    return found;
  }
  for (const name of entries) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) found = found.concat(publicFiles(full));
    else found.push(`/${relative(join(here, 'public'), full).split(sep).join('/')}`);
  }
  return found;
}

/**
 * Writes dist/sw.js from sw/sw.js at build time (never in dev), filling in:
 *   __PRECACHE__  every built file plus everything in public/ (the app shell)
 *   __SW_VERSION__ a hash of all of them, so any change to the build — and only
 *                  a change — gives a new service worker and new cache names.
 */
function swPlugin() {
  return {
    name: 'sailing-finder-sw',
    apply: 'build',
    enforce: 'post',
    generateBundle(_options, bundle) {
      const hash = createHash('sha256');
      const urls = [];

      for (const file of Object.values(bundle).sort((a, b) => a.fileName.localeCompare(b.fileName))) {
        if (file.fileName.endsWith('.map')) continue;
        urls.push(`/${file.fileName}`);
        hash.update(file.fileName);
        hash.update(file.type === 'chunk' ? file.code : file.source);
      }
      for (const url of publicFiles().sort()) {
        urls.push(url);
        hash.update(url);
        hash.update(readFileSync(join(here, 'public', url)));
      }

      const template = readFileSync(join(here, 'sw', 'sw.js'), 'utf8');
      hash.update(template);
      const version = hash.digest('hex').slice(0, 12);

      // Each placeholder must appear exactly once, or the worker would ship
      // unversioned — fail the build instead.
      for (const token of ['__SW_VERSION__', '__PRECACHE__']) {
        if (template.split(token).length !== 2) this.error(`sw/sw.js must contain ${token} exactly once`);
      }

      this.emitFile({
        type: 'asset',
        fileName: 'sw.js',
        source: template
          .replace('__SW_VERSION__', version)
          .replace('__PRECACHE__', JSON.stringify(urls)),
      });
    },
  };
}

// The bundle is built to frontend/dist and copied into the image, where FastAPI
// serves it. One origin for app and API, so the session cookie works without
// CORS and without a second public port. Files in public/ (manifest, icons)
// land at the site root; sw.js is generated there by swPlugin.
export default defineConfig({
  plugins: [react(), swPlugin()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 5173,
    // Local development only: forward /api to uvicorn so the cookie is
    // same-origin here too. Not used in production.
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/healthz': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
});
