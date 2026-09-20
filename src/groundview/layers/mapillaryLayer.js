/**
 * ARGUS GroundView — Mapillary Coverage Layer (Stub)
 *
 * Placeholder layer for future Mapillary street-level imagery coverage display.
 * When activated, shows a GeoJSON point layer of image locations.
 *
 * Architecture:
 *   - Layer exists in the map from initialization
 *   - Data is empty until user enables Mapillary AND coverage is found
 *   - Real data is injected via mapillaryService.getNearbyImages()
 */

import { LAYER_IDS } from '../types/groundview.js';

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Registers the Mapillary coverage layer (empty, invisible by default).
 * @param {import('maplibre-gl').Map} map
 */
export function initMapillaryLayer(map) {
  map.addSource(LAYER_IDS.MAPILLARY_SRC, {
    type: 'geojson',
    data: _emptyFeatureCollection(),
  });

  map.addLayer({
    id: LAYER_IDS.MAPILLARY_COVERAGE,
    type: 'circle',
    source: LAYER_IDS.MAPILLARY_SRC,
    layout: { visibility: 'none' },
    paint: {
      'circle-radius': 6,
      'circle-color': '#1DB954',     // Mapillary green
      'circle-stroke-width': 1.5,
      'circle-stroke-color': '#ffffff',
      'circle-opacity': 0.8,
    },
  });
}

/**
 * Updates Mapillary coverage points on the map.
 *
 * @param {import('maplibre-gl').Map} map
 * @param {Array<{id: string, lat: number, lon: number, thumb: string, capturedAt: string}>} images
 * @param {boolean} visible
 */
export function updateMapillaryLayer(map, images, visible) {
  const src = map.getSource(LAYER_IDS.MAPILLARY_SRC);
  if (!src) return;

  const features = images.map(img => ({
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [img.lon, img.lat] },
    properties: {
      id: img.id,
      thumb: img.thumb,
      capturedAt: img.capturedAt,
    },
  }));

  src.setData({ type: 'FeatureCollection', features });

  if (map.getLayer(LAYER_IDS.MAPILLARY_COVERAGE)) {
    map.setLayoutProperty(LAYER_IDS.MAPILLARY_COVERAGE, 'visibility', visible ? 'visible' : 'none');
  }
}

/**
 * Clears all Mapillary coverage points.
 * @param {import('maplibre-gl').Map} map
 */
export function clearMapillaryLayer(map) {
  const src = map.getSource(LAYER_IDS.MAPILLARY_SRC);
  if (src) src.setData(_emptyFeatureCollection());
  if (map.getLayer(LAYER_IDS.MAPILLARY_COVERAGE)) {
    map.setLayoutProperty(LAYER_IDS.MAPILLARY_COVERAGE, 'visibility', 'none');
  }
}

/**
 * Removes the Mapillary layer and source from the map.
 * @param {import('maplibre-gl').Map} map
 */
export function destroyMapillaryLayer(map) {
  if (map.getLayer(LAYER_IDS.MAPILLARY_COVERAGE)) map.removeLayer(LAYER_IDS.MAPILLARY_COVERAGE);
  if (map.getSource(LAYER_IDS.MAPILLARY_SRC)) map.removeSource(LAYER_IDS.MAPILLARY_SRC);
}

// ─── Internal Helpers ─────────────────────────────────────────────────────────
function _emptyFeatureCollection() {
  return { type: 'FeatureCollection', features: [] };
}
