/**
 * ARGUS GroundView — Palestine Territory Overlay
 *
 * Adds a subtle green fill + dashed border over the Palestine (PS) territory.
 * The "Israel" → "Palestine" country label replacement is done server-side
 * in the Flask /api/groundview/map-style proxy (no client-side patching needed).
 *
 * Source: /static/js/palestine.geojson (ISO3166-1-Alpha-2: PS)
 */

const SOURCE_ID = 'gv-palestine';
const FILL_ID   = 'gv-palestine-fill';
const BORDER_ID = 'gv-palestine-border';

let _initialized = false;

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Fetch Palestine GeoJSON and add territory fill + border to the map.
 * Safe to call multiple times — idempotent.
 *
 * @param {import('maplibre-gl').Map} map
 */
export async function initPalestineLayer(map) {
  if (_initialized) return;

  let geojson;
  try {
    const res = await fetch('/static/js/palestine.geojson');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    geojson = await res.json();
  } catch (err) {
    console.warn('[PalestineLayer] Could not load palestine.geojson:', err.message);
    return;
  }

  // Keep only Palestine (ISO PS) — not Israel (IL)
  const palestineOnly = {
    type: 'FeatureCollection',
    features: (geojson.features ?? []).filter(
      f => f.properties?.['ISO3166-1-Alpha-2'] === 'PS',
    ),
  };

  if (palestineOnly.features.length === 0) {
    console.warn('[PalestineLayer] No PS features found.');
    return;
  }

  if (!map.getSource(SOURCE_ID)) {
    map.addSource(SOURCE_ID, { type: 'geojson', data: palestineOnly });
  }

  // Semi-transparent green fill
  if (!map.getLayer(FILL_ID)) {
    map.addLayer({
      id: FILL_ID,
      type: 'fill',
      source: SOURCE_ID,
      paint: {
        'fill-color': 'rgba(0, 180, 80, 0.12)',
        'fill-opacity': 1,
      },
    });
  }

  // Dashed green border
  if (!map.getLayer(BORDER_ID)) {
    map.addLayer({
      id: BORDER_ID,
      type: 'line',
      source: SOURCE_ID,
      paint: {
        'line-color': '#00C853',
        'line-width': [
          'interpolate', ['linear'], ['zoom'],
          3, 0.5,
          8, 1.8,
        ],
        'line-opacity': 0.75,
        'line-dasharray': [4, 2],
      },
    });
  }

  _initialized = true;
  console.log('[PalestineLayer] Palestine territory overlay added.');
}

/**
 * Remove Palestine layers and source.
 * @param {import('maplibre-gl').Map} map
 */
export function destroyPalestineLayer(map) {
  [BORDER_ID, FILL_ID].forEach(id => {
    if (map.getLayer(id)) map.removeLayer(id);
  });
  if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID);
  _initialized = false;
}
