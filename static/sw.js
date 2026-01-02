const STATIC_CACHE = "fa-static-v1";
const API_CACHE = "fa-api-v1";

const STATIC_ASSETS = [
  "/",
  "/static/styles.css",
  "/static/app.js",
  "/static/manifest.json"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys
        .filter(k => ![STATIC_CACHE, API_CACHE].includes(k))
        .map(k => caches.delete(k))
    );
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  if (url.origin !== self.location.origin) return;

  if (req.method !== "GET") {
    event.respondWith(fetch(req));
    return;
  }

  if (url.pathname.startsWith("/api/")) {
    event.respondWith((async () => {
      try {
        const fresh = await fetch(req);
        const cache = await caches.open(API_CACHE);
        cache.put(req, fresh.clone());
        return fresh;
      } catch {
        const cached = await caches.match(req);
        return cached || new Response(JSON.stringify({ error: "Offline and no cached API data." }), {
          status: 503,
          headers: { "Content-Type": "application/json" }
        });
      }
    })());
    return;
  }

  event.respondWith((async () => {
    const cached = await caches.match(req);
    if (cached) return cached;
    const fresh = await fetch(req);
    const cache = await caches.open(STATIC_CACHE);
    cache.put(req, fresh.clone());
    return fresh;
  })());
});