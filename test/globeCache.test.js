import { describe, it, expect, beforeEach, vi } from 'vitest';
import { LRUMap, GlobeIconCache, GlobeCache, DEFAULT_TTLS } from '../globe/src/services/globeCache.js';

describe('LRUMap (Bounded Memory Cache)', () => {
  it('stores and retrieves items correctly', () => {
    const lru = new LRUMap(3);
    lru.set('a', 1);
    lru.set('b', 2);
    expect(lru.get('a')).toBe(1);
    expect(lru.get('b')).toBe(2);
    expect(lru.has('a')).toBe(true);
    expect(lru.has('nonexistent')).toBe(false);
  });

  it('evicts the oldest entry when capacity is exceeded', () => {
    const lru = new LRUMap(3);
    lru.set('a', 1);
    lru.set('b', 2);
    lru.set('c', 3);
    lru.set('d', 4); // should evict 'a'

    expect(lru.has('a')).toBe(false);
    expect(lru.get('a')).toBeUndefined();
    expect(lru.get('b')).toBe(2);
    expect(lru.get('c')).toBe(3);
    expect(lru.get('d')).toBe(4);
    expect(lru.size).toBe(3);
  });

  it('updates recency on get so accessed items are not evicted first', () => {
    const lru = new LRUMap(3);
    lru.set('a', 1);
    lru.set('b', 2);
    lru.set('c', 3);

    // Access 'a' to make it most recently used; 'b' is now oldest
    lru.get('a');

    lru.set('d', 4); // should evict 'b'
    expect(lru.has('a')).toBe(true);
    expect(lru.has('b')).toBe(false);
    expect(lru.has('c')).toBe(true);
    expect(lru.has('d')).toBe(true);
  });

  it('deletes and clears entries', () => {
    const lru = new LRUMap(3);
    lru.set('a', 1);
    lru.set('b', 2);
    expect(lru.delete('a')).toBe(true);
    expect(lru.size).toBe(1);
    lru.clear();
    expect(lru.size).toBe(0);
    expect(lru.has('b')).toBe(false);
  });
});

describe('GlobeIconCache (Permanent Pinned & LRU SVGs)', () => {
  it('stores pinned icons that are never evicted by LRU capacity', () => {
    const iconCache = new GlobeIconCache(2);
    iconCache.set('vessel-cargo', 'data:image/svg+xml;cargo', true);
    iconCache.set('vessel-tanker', 'data:image/svg+xml;tanker', true);

    // Now fill the LRU portion
    iconCache.set('temp-1', 'data:image/svg+xml;temp1', false);
    iconCache.set('temp-2', 'data:image/svg+xml;temp2', false);
    iconCache.set('temp-3', 'data:image/svg+xml;temp3', false); // evicts temp-1

    expect(iconCache.get('vessel-cargo')).toBe('data:image/svg+xml;cargo');
    expect(iconCache.get('vessel-tanker')).toBe('data:image/svg+xml;tanker');
    expect(iconCache.get('temp-1')).toBeUndefined();
    expect(iconCache.get('temp-2')).toBe('data:image/svg+xml;temp2');
    expect(iconCache.get('temp-3')).toBe('data:image/svg+xml;temp3');
  });

  it('clearNonPinned purges temporary icons while preserving pinned icons', () => {
    const iconCache = new GlobeIconCache(5);
    iconCache.set('pin1', 'data:image/svg+xml;pin1', true);
    iconCache.set('pin2', 'data:image/svg+xml;pin2', true);
    iconCache.set('temp1', 'data:image/svg+xml;temp1', false);

    expect(iconCache.size).toBe(3);
    iconCache.clearNonPinned();
    expect(iconCache.size).toBe(2);
    expect(iconCache.has('pin1')).toBe(true);
    expect(iconCache.has('pin2')).toBe(true);
    expect(iconCache.has('temp1')).toBe(false);
  });
});

describe('GlobeCache (Multi-Tier, Deduplication & Fingerprinting)', () => {
  let cache;

  beforeEach(() => {
    cache = new GlobeCache({ maxMemoryEntries: 10, maxIcons: 50 });
  });

  it('exposes default layer TTLs', () => {
    expect(DEFAULT_TTLS.flights).toBe(14);
    expect(DEFAULT_TTLS.vessels).toBe(18);
    expect(DEFAULT_TTLS.earthquakes).toBe(300);
    expect(DEFAULT_TTLS.static).toBe(86400);
  });

  it('coalesces concurrent in-flight requests into a single network call', async () => {
    let callCount = 0;
    const mockFetcher = vi.fn(async () => {
      callCount++;
      await new Promise((res) => setTimeout(res, 20));
      return [{ id: 'flight-1', lat: 35.0, lon: 139.0 }];
    });

    // Fire 3 concurrent calls
    const [res1, res2, res3] = await Promise.all([
      cache.fetchWithCache('flights', mockFetcher, 10),
      cache.fetchWithCache('flights', mockFetcher, 10),
      cache.fetchWithCache('flights', mockFetcher, 10)
    ]);

    expect(callCount).toBe(1);
    expect(mockFetcher).toHaveBeenCalledTimes(1);
    expect(res1).toEqual(res2);
    expect(res2).toEqual(res3);
    expect(cache.stats.deduped).toBe(2);
  });

  it('serves subsequent requests from memory cache before TTL expiry', async () => {
    const mockFetcher = vi.fn(async () => ({ count: 42 }));

    const r1 = await cache.fetchWithCache('metric', mockFetcher, 60);
    expect(mockFetcher).toHaveBeenCalledTimes(1);
    expect(r1).toEqual({ count: 42 });

    const r2 = await cache.fetchWithCache('metric', mockFetcher, 60);
    expect(mockFetcher).toHaveBeenCalledTimes(1); // Cached, no second fetch
    expect(r2).toEqual({ count: 42 });
    expect(cache.stats.hits).toBe(1);
  });

  it('expires cache entry when TTL is exceeded', async () => {
    const mockFetcher = vi.fn(async () => ({ timestamp: Date.now() }));

    // Set TTL to 0.01 seconds (10ms)
    await cache.fetchWithCache('quick', mockFetcher, 0.01);
    expect(mockFetcher).toHaveBeenCalledTimes(1);

    // Wait 25ms for expiry
    await new Promise((res) => setTimeout(res, 25));

    await cache.fetchWithCache('quick', mockFetcher, 0.01);
    expect(mockFetcher).toHaveBeenCalledTimes(2);
  });

  it('correctly fingerprints layer data and detects changes with hasChanged()', () => {
    const dataA = [
      { id: '1', lat: 10, lon: 20 },
      { id: '2', lat: 30, lon: 40 },
      { id: '3', lat: 50, lon: 60 }
    ];
    const dataSame = [
      { id: '1', lat: 10, lon: 20 },
      { id: '2', lat: 30, lon: 40 },
      { id: '3', lat: 50, lon: 60 }
    ];
    const dataMoved = [
      { id: '1', lat: 10.5, lon: 20.5 }, // Moved
      { id: '2', lat: 30, lon: 40 },
      { id: '3', lat: 50, lon: 60 }
    ];

    // Initial check: not rendered yet
    expect(cache.hasChanged('flights', dataA)).toBe(true);

    // Mark rendered
    cache.markRendered('flights', dataA);

    // Identical data: hasChanged should be false
    expect(cache.hasChanged('flights', dataSame)).toBe(false);

    // Modified data: hasChanged should be true
    expect(cache.hasChanged('flights', dataMoved)).toBe(true);
  });

  it('tracks telemetry stats accurately', async () => {
    await cache.set('layer-1', { a: 1 }, 100);
    await cache.get('layer-1'); // hit
    await cache.get('layer-nonexistent'); // miss

    const telemetry = cache.getTelemetry();
    expect(telemetry.hits).toBe(1);
    expect(telemetry.misses).toBe(1);
    expect(telemetry.hitRate).toBe('50.0%');
    expect(telemetry.memoryEntries).toBe(1);
  });

  it('invalidates layer-specific or all cache entries on demand', async () => {
    await cache.set('a', 1, 100);
    await cache.set('b', 2, 100);
    cache.markRendered('a', [1]);

    cache.invalidate('a');
    expect(await cache.get('a')).toBeNull();
    expect(await cache.get('b')).toBe(2);
    expect(cache.hasChanged('a', [1])).toBe(true);

    cache.invalidate();
    expect(await cache.get('b')).toBeNull();
  });
});
