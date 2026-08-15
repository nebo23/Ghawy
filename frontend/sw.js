// Kill-switch service worker.
//
// A service worker was registered against this origin at some point and never
// removed. Nothing in the site registers one today, so /sw.js answered 404 —
// and a 404 does NOT retire a service worker. The browser keeps the last
// working copy it has and goes on serving every navigation and every asset out
// of that worker's cache, so an affected visitor sees a frozen, partial build
// of the site: no JS behaviour, no i18n, none of the Arabic that i18n.js fills
// in. The server is serving a perfectly good site the whole time and can't
// tell, because the requests never leave the browser.
//
// This file is the only thing that ends that state. It claims the registration,
// deletes every cache the old worker left behind, unregisters itself, and
// reloads open tabs so they come back over the network. It has no fetch
// handler, so from the moment it activates nothing is intercepted.
//
// Keep serving it. Deleting it puts the 404 back, and any browser still holding
// the old worker would stay stuck with no way out.

self.addEventListener('install', () => {
    // Don't wait for existing tabs to close — the point is to take over now.
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil((async () => {
        await self.clients.claim();

        const names = await caches.keys();
        await Promise.all(names.map((name) => caches.delete(name)));

        await self.registration.unregister();

        // Reload open tabs so they re-fetch from the network instead of sitting
        // on whatever the dead worker last handed them.
        const clients = await self.clients.matchAll({ type: 'window' });
        for (const client of clients) {
            client.navigate(client.url);
        }
    })());
});
