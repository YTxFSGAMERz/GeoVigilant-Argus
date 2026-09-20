/**
 * ARGUS GroundView — Mapillary Service
 *
 * Architecture boundary for future Mapillary street-level imagery integration.
 *
 * MVP STATUS: Coverage check returns "unavailable" gracefully.
 * The interface is fully designed so the real implementation
 * can be dropped in without restructuring GroundView.
 *
 * Future lazy-load pattern (when adding real viewer):
 *   const { Viewer } = await import('@mapillary/mapillary-js');
 *
 * Mapillary Graph API v4 — authenticated via server-proxied token.
 * Token is NEVER embedded in this file — fetched from /api/groundview/config.
 */

import { MAPILLARY_CONFIG } from '../types/groundview.js';

// ─── Module State ─────────────────────────────────────────────────────────────
let _accessToken = null;  // resolved at runtime from backend config endpoint

/**
 * Initializes the Mapillary service by fetching the access token
 * from the backend config endpoint. Safe to call multiple times.
 * @returns {Promise<boolean>} true if token resolved successfully
 */
export async function initMapillaryService() {
  if (_accessToken) return true;
  try {
    const res = await fetch('/api/groundview/config');
    if (!res.ok) throw new Error(`Config fetch failed: ${res.status}`);
    const config = await res.json();
    if (config.mapillaryToken) {
      _accessToken = config.mapillaryToken;
      return true;
    }
    return false;
  } catch (err) {
    console.warn('[Mapillary] Could not resolve access token:', err.message);
    return false;
  }
}

/**
 * Check if Mapillary imagery coverage exists near a coordinate.
 *
 * @param {number} lat
 * @param {number} lon
 * @param {number} [radiusMeters=100]
 * @returns {Promise<{available: boolean, imageCount: number, closestImage: Object|null, message: string}>}
 */
export async function checkCoverage(lat, lon, radiusMeters = 100) {
  if (!_accessToken) {
    return {
      available: false,
      imageCount: 0,
      closestImage: null,
      message: 'Mapillary service not initialized',
    };
  }

  try {
    // Mapillary Graph API v4: search images near point
    const bbox = _buildBbox(lat, lon, radiusMeters);
    const url = new URL(`${MAPILLARY_CONFIG.GRAPH_API}/images`);
    url.searchParams.set('fields', 'id,thumb_256_url,geometry,captured_at,creator');
    url.searchParams.set('bbox', bbox);
    url.searchParams.set('limit', '5');
    url.searchParams.set('access_token', _accessToken);

    const res = await fetch(url.toString());
    if (!res.ok) throw new Error(`Mapillary API ${res.status}`);

    const data = await res.json();
    const images = data.data || [];

    return {
      available: images.length > 0,
      imageCount: images.length,
      closestImage: images[0] || null,
      message: images.length > 0
        ? `${images.length} image(s) found within ${radiusMeters}m`
        : `No imagery within ${radiusMeters}m`,
    };
  } catch (err) {
    console.warn('[Mapillary] Coverage check failed:', err.message);
    return {
      available: false,
      imageCount: 0,
      closestImage: null,
      message: `Coverage check error: ${err.message}`,
    };
  }
}

/**
 * Fetch nearby Mapillary images for a given location.
 *
 * @param {number} lat
 * @param {number} lon
 * @param {number} [count=10]
 * @param {number} [radiusMeters=250]
 * @returns {Promise<Array<{id: string, lat: number, lon: number, thumb: string, capturedAt: string}>>}
 */
export async function getNearbyImages(lat, lon, count = 10, radiusMeters = 250) {
  if (!_accessToken) return [];
  try {
    const bbox = _buildBbox(lat, lon, radiusMeters);
    const url = new URL(`${MAPILLARY_CONFIG.GRAPH_API}/images`);
    url.searchParams.set('fields', 'id,thumb_256_url,geometry,captured_at');
    url.searchParams.set('bbox', bbox);
    url.searchParams.set('limit', String(count));
    url.searchParams.set('access_token', _accessToken);

    const res = await fetch(url.toString());
    if (!res.ok) throw new Error(`Mapillary API ${res.status}`);

    const data = await res.json();
    return (data.data || []).map(img => ({
      id: img.id,
      lat: img.geometry?.coordinates?.[1] ?? lat,
      lon: img.geometry?.coordinates?.[0] ?? lon,
      thumb: img.thumb_256_url || '',
      capturedAt: img.captured_at || '',
    }));
  } catch (err) {
    console.warn('[Mapillary] getNearbyImages failed:', err.message);
    return [];
  }
}

/**
 * Lazy-loads the Mapillary JS viewer and mounts it in a container element.
 * Only called when the user explicitly requests street-level view.
 * Requires @mapillary/mapillary-js to be installed (future dependency).
 *
 * @param {HTMLElement} container
 * @param {string} imageId
 * @returns {Promise<Object|null>} Mapillary Viewer instance or null on failure
 */
export async function openStreetLevelViewer(container, imageId) {
  if (!_accessToken) {
    console.warn('[Mapillary] Cannot open viewer: no access token');
    return null;
  }
  // NOTE: @mapillary/mapillary-js is a future optional dependency.
  // When it is installed via `npm install @mapillary/mapillary-js`,
  // this dynamic import will resolve and the viewer will activate.
  // Until then, this function returns null gracefully.
  try {
    /* eslint-disable-next-line */
    const { Viewer } = await import(/* @vite-ignore */ '@mapillary/mapillary-js');
    const viewer = new Viewer({
      accessToken: _accessToken,
      container,
      imageId,
      component: { cover: false },
    });
    return viewer;
  } catch (err) {
    console.info('[Mapillary] Street-level viewer not available:', err.message);
    console.info('[Mapillary] Run `npm install @mapillary/mapillary-js` to enable.');
    return null;
  }
}

// ─── Internal Helpers ─────────────────────────────────────────────────────────

/**
 * Builds a bounding-box string for Mapillary Graph API queries.
 * @param {number} lat
 * @param {number} lon
 * @param {number} radiusMeters
 * @returns {string} "minLon,minLat,maxLon,maxLat"
 */
function _buildBbox(lat, lon, radiusMeters) {
  const DEG_PER_METER = 1 / 111320;
  const dLat = radiusMeters * DEG_PER_METER;
  const dLon = radiusMeters * DEG_PER_METER / Math.cos((lat * Math.PI) / 180);
  return [
    (lon - dLon).toFixed(6),
    (lat - dLat).toFixed(6),
    (lon + dLon).toFixed(6),
    (lat + dLat).toFixed(6),
  ].join(',');
}
