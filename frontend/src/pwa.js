/**
 * The service worker (frontend/sw/sw.js, built to /sw.js) — production builds
 * only, so `vite dev` never caches anything.
 *
 * Staying current after a deploy:
 *   - the browser re-checks /sw.js on every page load, bypassing its HTTP
 *     cache (updateViaCache: 'none'), and we also ask whenever the app comes
 *     back to the screen — an installed app can sit open for days;
 *   - a new worker takes over at once and deletes the old caches;
 *   - the page already open then reloads the next time it is in the
 *     background, so the user returns to the new version rather than staying
 *     on the old one until they happen to close it.
 */

const API_CACHE_PREFIX = 'sf-api-';

export function registerServiceWorker() {
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return;

  // No controller yet means this is the first install: its takeover must not
  // trigger a reload.
  const hadController = Boolean(navigator.serviceWorker.controller);
  let updated = false;

  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (!hadController || updated) return;
    updated = true;
    if (document.visibilityState === 'hidden') window.location.reload();
  });

  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js', { scope: '/', updateViaCache: 'none' })
      .then((registration) => {
        document.addEventListener('visibilitychange', () => {
          if (document.visibilityState === 'hidden' && updated) {
            window.location.reload();
          } else if (document.visibilityState === 'visible') {
            registration.update().catch(() => {});
          }
        });
      })
      .catch(() => {
        // No service worker (private mode, plain http on a LAN address): the
        // app works exactly as before, just not offline.
      });
  });
}

/**
 * Forget the offline copies of API answers — called on sign-out so the next
 * person on this device never sees the last user's data offline.
 */
export function clearApiCache() {
  if (typeof caches === 'undefined') return Promise.resolve();
  return caches
    .keys()
    .then((keys) => Promise.all(keys.filter((k) => k.startsWith(API_CACHE_PREFIX)).map((k) => caches.delete(k))))
    .catch(() => {});
}
