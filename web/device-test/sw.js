// Minimal service worker for the Phase 0 device test: offline shell + push display.
const CACHE = 'coach-device-test-v1';
const SHELL = ['./', 'index.html', 'manifest.webmanifest', 'icon-180.png', 'icon-192.png', 'icon-512.png'];

self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL))); self.skipWaiting(); });
self.addEventListener('activate', e => { e.waitUntil(self.clients.claim()); });
self.addEventListener('fetch', e => { e.respondWith(caches.match(e.request).then(r => r || fetch(e.request))); });

self.addEventListener('push', e => {
  let body = 'Web Push works.';
  try { body = e.data ? e.data.text() : body; } catch (_) {}
  const at = new Date().toISOString();
  e.waitUntil(Promise.all([
    self.registration.showNotification('Coach test push', { body, icon: 'icon-192.png' }),
    self.clients.matchAll({ includeUncontrolled: true }).then(cs => cs.forEach(c => c.postMessage({ type: 'push', at }))),
  ]));
});
self.addEventListener('notificationclick', e => { e.notification.close(); e.waitUntil(self.clients.openWindow('./')); });
