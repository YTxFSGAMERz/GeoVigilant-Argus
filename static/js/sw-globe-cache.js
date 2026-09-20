// public/sw-globe-cache.js
// GeoVigilant 3D Globe - High-Performance Tile & Static Asset Cache Service Worker
// Intercepts and caches map imagery and radar tiles in CacheStorage
// to eliminate repetitive tile downloads and CPU-intensive re-decoding.

const CACHE_NAME = 'geovigilant-globe-tiles-v1';
const MAX_TILES = 800; // ~40 MB maximum disk footprint

const TILE_DOMAINS = [
  'services.arcgisonline.com',
  'tilecache.rainviewer.com',
  'tile.openstreetmap.org'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((k) => {
          if (k !== CACHE_NAME) {
            console.log('[SW-Globe] Purging obsolete cache:', k);
            return caches.delete(k);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

async function trimCache(cache, maxItems) {
  const keys = await cache.keys();
  if (keys.length > maxItems) {
    // Delete the oldest 15% of tiles to prevent continuous churn
    const deleteCount = Math.max(1, Math.floor(keys.length * 0.15));
    for (let i = 0; i < deleteCount; i++) {
      await cache.delete(keys[i]);
    }
  }
}

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Only intercept GET requests for map tile providers
  const isTile = event.request.method === 'GET' &&
    TILE_DOMAINS.some(domain => url.hostname.includes(domain));

  if (!isTile) {
    return; // Pass through directly
  }

  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      // 1. Cache First
      const cached = await cache.match(event.request);
      if (cached) {
        return cached;
      }

      // 2. Network Fetch & Cache
      try {
        const response = await fetch(event.request, { mode: 'cors' });
        if (response && (response.status === 200 || response.type === 'opaque')) {
          cache.put(event.request, response.clone()).then(() => {
            trimCache(cache, MAX_TILES).catch(() => {});
          });
        }
        return response;
      } catch (err) {
        if (cached) return cached;
        throw err;
      }
    })
  );
});
