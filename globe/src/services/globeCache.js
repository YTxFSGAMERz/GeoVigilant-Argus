// globe/src/services/globeCache.js
// High-Performance Multi-Tier Caching System for GeoVigilant 3D Globe
// Resolves high RAM & CPU usage without ANY visual quality, resolution or FPS degradation.
// Features: L1 Memory LRU + L2 IndexedDB persistence, in-flight request coalescing,
// and content-fingerprinted change detection to eliminate redundant Cesium render loops.

export const DEFAULT_TTLS = {
  flights: 14,          // ADS-B poll is 15s
  vessels: 18,          // AIS poll is 20s
  squawks: 18,          // Emergency squawks poll is 20s
  satellites: 50,       // Satellites poll is 60s
  cctv: 180,            // CCTV cameras poll is 60s (cameras rarely move)
  earthquakes: 300,     // USGS feed poll is 300s
  weather: 300,         // Weather radar/stations poll is 300s
  weatherAlerts: 300,   // NWS alerts poll is 300s
  naturalEvents: 600,   // NASA EONET poll is 600s
  wildfires: 900,       // NASA FIRMS poll is 900s
  market: 300,          // Market ticker poll is 300s
  spaceWeather: 300,    // NOAA SWPC poll is 300s
  argusLandmarks: 86400,// 24h
  static: 86400         // 24h (nuclear, military, conflicts, waterways, cables, etc.)
};

/**
 * Lightweight Bounded LRU Cache for memory-safe key-value retention.
 */
export class LRUMap {
  constructor(maxEntries = 100) {
    this.maxEntries = maxEntries;
    this.map = new Map();
  }

  get(key) {
    if (!this.map.has(key)) return undefined;
    const value = this.map.get(key);
    // Refresh position for LRU
    this.map.delete(key);
    this.map.set(key, value);
    return value;
  }

  set(key, value) {
    if (this.map.has(key)) {
      this.map.delete(key);
    } else if (this.map.size >= this.maxEntries) {
      // Evict oldest entry
      const oldestKey = this.map.keys().next().value;
      this.map.delete(oldestKey);
    }
    this.map.set(key, value);
  }

  has(key) {
    return this.map.has(key);
  }

  delete(key) {
    return this.map.delete(key);
  }

  clear() {
    this.map.clear();
  }

  get size() {
    return this.map.size;
  }

  entries() {
    return this.map.entries();
  }
}

/**
 * Unified Icon / SVG Cache with LRU eviction and permanent pinned entries.
 * Retains GPU textures permanently to eliminate base64 encoding and WebGL re-uploads.
 */
export class GlobeIconCache {
  constructor(maxIcons = 300) {
    this.pinned = new Map(); // Permanent icons that should never be evicted
    this.lru = new LRUMap(maxIcons);
  }

  get(key) {
    if (this.pinned.has(key)) return this.pinned.get(key);
    return this.lru.get(key);
  }

  set(key, value, isPinned = false) {
    if (isPinned) {
      this.pinned.set(key, value);
    } else {
      this.lru.set(key, value);
    }
  }

  has(key) {
    return this.pinned.has(key) || this.lru.has(key);
  }

  clearNonPinned() {
    this.lru.clear();
  }

  get size() {
    return this.pinned.size + this.lru.size;
  }
}

/**
 * IndexedDB Persistence Helper for L2 Cache.
 */
class IndexedDBStore {
  constructor(dbName = 'GeoVigilantGlobeCache', storeName = 'layers') {
    this.dbName = dbName;
    this.storeName = storeName;
    this.dbPromise = null;
    this.isSupported = typeof indexedDB !== 'undefined';
  }

  _getDB() {
    if (!this.isSupported) return Promise.resolve(null);
    if (!this.dbPromise) {
      this.dbPromise = new Promise((resolve) => {
        try {
          const req = indexedDB.open(this.dbName, 1);
          req.onupgradeneeded = (e) => {
            const db = e.target.result;
            if (!db.objectStoreNames.contains(this.storeName)) {
              db.createObjectStore(this.storeName, { keyPath: 'key' });
            }
          };
          req.onsuccess = () => resolve(req.result);
          req.onerror = () => {
            console.warn('[GlobeCache] IndexedDB open error, falling back to L1 memory only');
            resolve(null);
          };
        } catch (_) {
          resolve(null);
        }
      });
    }
    return this.dbPromise;
  }

  async get(key) {
    try {
      const db = await this._getDB();
      if (!db) return null;
      return new Promise((resolve) => {
        const tx = db.transaction(this.storeName, 'readonly');
        const store = tx.objectStore(this.storeName);
        const req = store.get(key);
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => resolve(null);
      });
    } catch (_) {
      return null;
    }
  }

  async set(key, value, expiresAt) {
    try {
      const db = await this._getDB();
      if (!db) return;
      return new Promise((resolve) => {
        const tx = db.transaction(this.storeName, 'readwrite');
        const store = tx.objectStore(this.storeName);
        store.put({ key, value, expiresAt, savedAt: Date.now() });
        tx.oncomplete = () => resolve();
        tx.onerror = () => resolve();
      });
    } catch (_) {}
  }

  async delete(key) {
    try {
      const db = await this._getDB();
      if (!db) return;
      return new Promise((resolve) => {
        const tx = db.transaction(this.storeName, 'readwrite');
        const store = tx.objectStore(this.storeName);
        store.delete(key);
        tx.oncomplete = () => resolve();
        tx.onerror = () => resolve();
      });
    } catch (_) {}
  }
}

/**
 * Main Globe Cache System.
 */
export class GlobeCache {
  constructor(options = {}) {
    this.maxMemoryEntries = options.maxMemoryEntries || 80;
    this.l1 = new LRUMap(this.maxMemoryEntries);
    this.l2 = new IndexedDBStore();
    this.iconCache = new GlobeIconCache(options.maxIcons || 350);
    this.ttls = { ...DEFAULT_TTLS, ...(options.ttls || {}) };

    // Request coalescing: ongoing Promises for in-flight fetches
    this._inFlight = new Map();

    // Fingerprint signatures for rendered states
    this._renderedSignatures = new Map();

    // Telemetry metrics
    this.stats = {
      hits: 0,
      misses: 0,
      deduped: 0,
      rendersSkipped: 0,
      startTime: Date.now()
    };
  }

  /**
   * Generates a fast, lightweight signature of layer data to detect changes
   * without deep JSON stringification of massive arrays.
   */
  generateSignature(data) {
    if (!data) return 'null';
    if (Array.isArray(data)) {
      const len = data.length;
      if (len === 0) return 'empty-array';
      // Sample first, middle, and last items + count
      const first = data[0];
      const mid = data[Math.floor(len / 2)];
      const last = data[len - 1];

      const fId = first?.id ?? first?.icao24 ?? first?.mmsi ?? first?.noradId ?? first?.name ?? '';
      const fPos = `${first?.lat ?? first?.latitude ?? 0},${first?.lon ?? first?.longitude ?? 0}`;
      const mId = mid?.id ?? mid?.icao24 ?? mid?.mmsi ?? mid?.noradId ?? mid?.name ?? '';
      const lId = last?.id ?? last?.icao24 ?? last?.mmsi ?? last?.noradId ?? last?.name ?? '';
      const lPos = `${last?.lat ?? last?.latitude ?? 0},${last?.lon ?? last?.longitude ?? 0}`;

      return `arr:${len}:${fId}:${fPos}:${mId}:${lId}:${lPos}`;
    }
    if (typeof data === 'object') {
      if (data.features && Array.isArray(data.features)) {
        return `geojson:${data.features.length}:${data.features[0]?.id || ''}:${data.features[data.features.length - 1]?.id || ''}`;
      }
      if (data.timestamp || data.updated || data.time) {
        return `obj:${data.timestamp || data.updated || data.time}`;
      }
      return `obj:${Object.keys(data).length}`;
    }
    return String(data);
  }

  /**
   * Checks whether the layer data has changed compared to what was last rendered.
   */
  hasChanged(layerKey, newData) {
    const newSig = this.generateSignature(newData);
    const lastSig = this._renderedSignatures.get(layerKey);
    return newSig !== lastSig;
  }

  /**
   * Records that the given layer data has been rendered to the globe.
   */
  markRendered(layerKey, data) {
    const sig = typeof data === 'string' ? data : this.generateSignature(data);
    this._renderedSignatures.set(layerKey, sig);
  }

  /**
   * Retrieves data from L1 or L2 cache if still valid.
   */
  async get(key) {
    const now = Date.now();
    // 1. Check L1 Memory Cache
    const memEntry = this.l1.get(key);
    if (memEntry) {
      if (now < memEntry.expiresAt) {
        this.stats.hits++;
        memEntry.hits = (memEntry.hits || 0) + 1;
        return memEntry.value;
      }
      this.l1.delete(key);
    }

    // 2. Check L2 IndexedDB Cache
    const dbEntry = await this.l2.get(key);
    if (dbEntry) {
      if (now < dbEntry.expiresAt) {
        this.stats.hits++;
        // Promote back to L1
        this.l1.set(key, {
          value: dbEntry.value,
          expiresAt: dbEntry.expiresAt,
          hits: 1
        });
        return dbEntry.value;
      }
      this.l2.delete(key);
    }

    this.stats.misses++;
    return null;
  }

  /**
   * Stores data in L1 and asynchronously in L2 cache.
   */
  async set(key, value, ttlSec = null) {
    const ttl = ttlSec != null ? ttlSec : (this.ttls[key] || 60);
    const expiresAt = Date.now() + (ttl * 1000);

    // Write to L1 Memory
    this.l1.set(key, { value, expiresAt, hits: 0 });

    // Write to L2 Persistent Cache (for layers with TTL >= 60s or static)
    if (ttl >= 60) {
      this.l2.set(key, value, expiresAt).catch(() => {});
    }
  }

  /**
   * Fetches data with transparent caching, TTL expiration, and in-flight deduplication.
   * If multiple callers request the same layer concurrently, only one network fetch executes.
   */
  async fetchWithCache(key, fetchFn, ttlSec = null) {
    // 1. Check existing fresh cache
    const cached = await this.get(key);
    if (cached !== null) {
      return cached;
    }

    // 2. Coalesce in-flight requests
    if (this._inFlight.has(key)) {
      this.stats.deduped++;
      return this._inFlight.get(key);
    }

    // 3. Execute fetch
    const promise = (async () => {
      try {
        const result = await fetchFn();
        if (result !== undefined && result !== null) {
          await this.set(key, result, ttlSec);
        }
        return result;
      } finally {
        this._inFlight.delete(key);
      }
    })();

    this._inFlight.set(key, promise);
    return promise;
  }

  /**
   * Invalidate a single layer or all cache entries.
   */
  invalidate(key = null) {
    if (key) {
      this.l1.delete(key);
      this.l2.delete(key);
      this._renderedSignatures.delete(key);
    } else {
      this.l1.clear();
      this._renderedSignatures.clear();
    }
  }

  /**
   * Returns runtime telemetry metrics for HUD and diagnostics.
   */
  getTelemetry() {
    const totalReqs = this.stats.hits + this.stats.misses;
    const hitRate = totalReqs > 0 ? ((this.stats.hits / totalReqs) * 100).toFixed(1) + '%' : '0.0%';
    return {
      hits: this.stats.hits,
      misses: this.stats.misses,
      deduped: this.stats.deduped,
      hitRate: hitRate,
      memoryEntries: this.l1.size,
      cachedIcons: this.iconCache.size,
      rendersSkipped: this.stats.rendersSkipped
    };
  }
}

// Global Singleton Instance
export const globeCache = new GlobeCache();
