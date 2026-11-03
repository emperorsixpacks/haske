/* Haske service worker: app shell + fonts + last 20 results. */

const VERSION = "haske-v1";
const APP_SHELL_CACHE = `${VERSION}-shell`;
const FONT_CACHE = `${VERSION}-fonts`;
const RESULT_CACHE = `${VERSION}-results`;
const RESULT_LIMIT = 20;

const SHELL_URLS = ["/", "/manifest.webmanifest", "/icons/icon.svg", "/icons/icon-192.png", "/icons/icon-512.png"];
const FONT_URLS = ["/fonts/inter-var.woff2"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const shell = await caches.open(APP_SHELL_CACHE);
      await shell.addAll(SHELL_URLS);
      const fonts = await caches.open(FONT_CACHE);
      await fonts.addAll(FONT_URLS);
      await self.skipWaiting();
    })()
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.filter((k) => k.startsWith("haske-") && !k.startsWith(VERSION)).map((k) => caches.delete(k)));
      await self.clients.claim();
    })()
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  // Never cache registry lookups or checks.
  if (url.pathname.startsWith("/v1/")) return;

  // Fonts: cache-first.
  if (url.pathname.startsWith("/fonts/")) {
    event.respondWith(
      caches.match(request).then((hit) => hit || fetch(request).then((res) => {
        const copy = res.clone();
        caches.open(FONT_CACHE).then((c) => c.put(request, copy));
        return res;
      }))
    );
    return;
  }

  // Navigations: network-first, fall back to the shell so the app opens offline.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((res) => {
          const copy = res.clone();
          caches.open(APP_SHELL_CACHE).then((c) => c.put("/", copy));
          return res;
        })
        .catch(() => caches.match("/"))
    );
    return;
  }

  // Static assets: stale-while-revalidate.
  event.respondWith(
    caches.match(request).then((hit) => {
      const network = fetch(request)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(APP_SHELL_CACHE).then((c) => c.put(request, copy));
          }
          return res;
        })
        .catch(() => hit);
      return hit || network;
    })
  );
});

self.addEventListener("message", (event) => {
  const msg = event.data || {};
  if (msg.type === "SAVE_RESULT" && msg.result) {
    event.waitUntil(
      (async () => {
        const cache = await caches.open(RESULT_CACHE);
        const keys = await cache.keys();
        await cache.put(new Request(`/result/${msg.result.id}`), new Response(JSON.stringify(msg.result), {
          headers: { "Content-Type": "application/json" },
        }));
        // Enforce the last-20 cap.
        const excess = keys.length + 1 - RESULT_LIMIT;
        if (excess > 0) {
          const sorted = keys.sort((a, b) => (a.url < b.url ? -1 : 1));
          for (const key of sorted.slice(0, excess)) await cache.delete(key);
        }
      })()
    );
  }
  if (msg.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});
