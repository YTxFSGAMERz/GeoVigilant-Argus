/**
 * ARGUS GroundView — Anomaly Layer
 *
 * Visualizes spatial/behavioral anomalies using SpatialTemporalAnomalyDetector output.
 * Renders halo rings around anomalous nodes. Opacity and radius driven by:
 *   - compositeAnomalyScore (0.0 – 1.0)
 *   - isAnomaly flag
 *   - anomalyReasons (for label)
 *
 * Uses the SAME data already on the argusNodeLayer GeoJSON source —
 * no second data source needed. Filtered by isAnomaly === true.
 */

import { LAYER_IDS } from '../types/groundview.js';

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Registers the anomaly halo layers on the MapLibre map.
 * Must be called after initArgusNodeLayer() since it reuses the node source.
 *
 * @param {import('maplibre-gl').Map} map
 */
export function initAnomalyLayer(map) {
  // Outer diffuse ring
  map.addLayer(
    {
      id: LAYER_IDS.ANOMALIES,
      type: 'circle',
      source: LAYER_IDS.ARGUS_NODES_SRC,
      filter: ['==', ['get', 'isAnomaly'], true],
      paint: {
        'circle-radius': [
          'interpolate', ['linear'], ['get', 'anomalyScore'],
          0.40, 30,
          0.70, 50,
          0.90, 72,
          1.00, 90,
        ],
        'circle-color': [
          'interpolate', ['linear'], ['get', 'anomalyScore'],
          0.40, '#FFCC00',
          0.70, '#FF6600',
          1.00, '#FF0055',
        ],
        'circle-opacity': [
          'interpolate', ['linear'], ['get', 'anomalyScore'],
          0.40, 0.08,
          0.70, 0.14,
          1.00, 0.22,
        ],
        'circle-stroke-width': 1,
        'circle-stroke-color': [
          'interpolate', ['linear'], ['get', 'anomalyScore'],
          0.40, '#FFCC00',
          1.00, '#FF0055',
        ],
        'circle-stroke-opacity': [
          'interpolate', ['linear'], ['get', 'anomalyScore'],
          0.40, 0.4,
          1.00, 0.8,
        ],
        'circle-pitch-alignment': 'map',
      },
    },
    // Insert BELOW the node pulse layer so pulse is on top
    LAYER_IDS.ARGUS_NODES_PULSE,
  );
}

/**
 * Toggles anomaly halo visibility.
 * Data is already kept in sync via updateArgusNodeLayer().
 *
 * @param {import('maplibre-gl').Map} map
 * @param {boolean} visible
 */
export function setAnomalyLayerVisible(map, visible) {
  if (map.getLayer(LAYER_IDS.ANOMALIES)) {
    map.setLayoutProperty(LAYER_IDS.ANOMALIES, 'visibility', visible ? 'visible' : 'none');
  }
}

/**
 * Removes the anomaly layer.
 * @param {import('maplibre-gl').Map} map
 */
export function destroyAnomalyLayer(map) {
  if (map.getLayer(LAYER_IDS.ANOMALIES)) map.removeLayer(LAYER_IDS.ANOMALIES);
}
