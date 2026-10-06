/*
 * Sailing Finder service worker — the app opens without internet.
 *
 * NOT served as-is. `vite build` (the swPlugin in vite.config.js) fills in
 * VERSION (a hash of the whole build) and PRECACHE (every built file) below,
 * and writes the result to dist/sw.js, served from the site root so its scope
 * is the whole app.
 *
 * Updates: every deploy that changes anything changes the version, so the
 * browser sees a new sw.js, installs it, and it takes over at once
 * (skipWaiting + clients.claim). Activation deletes every older cache. Pages
 * themselves are always fetched network-first, so a fresh deploy is what
 * opens whenever the server can be reached.
 *
 * Strategies:
 *   page loads (navigations)  network-first, fallback to the cached app shell
 *   /api/* GETs               network-first, fallback to the last answer (offline only)
 *   /assets/*, icons, manifest cache-first (file names change when content does)
 *   everything else           straight to the network, untouched
 * POST/PATCH/DELETE never touch a cache.
 */

const VERSION = '__SW_VERSION__';
const PRECACHE = __PRECACHE__;

const SHELL_CACHE = `sf-shell-${VERSION}`;
const API_CACHE = `sf-api-${VERSION}`;
const SHELL_PAGE = '/index.html';

// Never cached: the PDF preview (large, and only useful online) and the
// public WhatsApp PDF links.
const API_SKIP = ['/api/share/pdf'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      // cache: 'reload' — straight from the server, not the HTTP cache.
      .then((cache) => cache.addAll(PRECACHE.map((url) => new Request(url, { cache: 'reload' }))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith('sf-') && key !== SHELL_CACHE && key !== API_CACHE)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // fonts etc.: the browser's own handling

  if (request.mode === 'navigate') {
    event.respondWith(pageNetworkFirst(request));
    return;
  }
  if (url.pathname.startsWith('/api/')) {
    if (API_SKIP.some((prefix) => url.pathname.startsWith(prefix))) return;
    event.respondWith(apiNetworkFirst(request));
    return;
  }
  if (url.pathname.startsWith('/assets/') || PRECACHE.includes(url.pathname)) {
    event.respondWith(staticCacheFirst(request));
  }
});

/** A page: the server's latest, and a copy of it kept as the offline shell.
 *  React Router draws every route from the same index.html. */
async function pageNetworkFirst(request) {
  try {
    const response = await fetch(request);
    const type = response.headers.get('content-type') || '';
    if (response.ok && type.includes('text/html')) {
      const cache = await caches.open(SHELL_CACHE);
      await cache.put(SHELL_PAGE, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(SHELL_PAGE);
    return cached || offlineText();
  }
}

/** Live data: always the network when there is one. Only a successful answer
 *  is kept, and only handed back when the network is unreachable. */
async function apiNetworkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(API_CACHE);
      await cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request, { cacheName: API_CACHE });
    if (cached) return cached;
    // The app's own error envelope, so the screen says why.
    return new Response(
      JSON.stringify({
        status: 'error',
        data: null,
        message: "You're offline. Connect to the internet and try again.",
      }),
      { status: 503, headers: { 'Content-Type': 'application/json' } },
    );
  }
}

/** Built files are named by their content, so a cached copy is never stale. */
async function staticCacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) {
    const cache = await caches.open(SHELL_CACHE);
    await cache.put(request, response.clone());
  }
  return response;
}

function offlineText() {
  return new Response("You're offline, and Sailing Finder hasn't been opened on this device yet.", {
    status: 503,
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
}
