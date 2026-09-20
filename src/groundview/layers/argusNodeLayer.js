/**
 * ARGUS GroundView — ARGUS Node Layer
 *
 * Renders IoT/sensor node markers on a MapLibre GL map.
 * Visual state is derived from existing ARGUS pipeline data:
 *   - trust score   → color (green / amber / red / purple)
 *   - anomaly state → pulse ring visibility and size
 *   - quarantine    → purple override + locked icon
 *   - integrity     → icon badge
 *
 * Data source: ArgusEvent / NodeTrustState produced by DeviceTrustEngine.
 */

import { LAYER_IDS, TRUST, COLORS } from '../types/groundview.js';

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Registers the ARGUS node source and layers on the MapLibre map.
 * Must be called once after the map style loads.
 *
 * @param {import('maplibre-gl').Map} map
 */
export function initArgusNodeLayer(map) {
  // GeoJSON source — updated in place on each tick
  map.addSource(LAYER_IDS.ARGUS_NODES_SRC, {
    type: 'geojson',
    data: _emptyFeatureCollection(),
  });

  // Pulse ring (behind the node icon)
  map.addLayer({
    id: LAYER_IDS.ARGUS_NODES_PULSE,
    type: 'circle',
    source: LAYER_IDS.ARGUS_NODES_SRC,
    filter: ['==', ['get', 'isAnomaly'], true],
    paint: {
      'circle-radius': [
        'interpolate', ['linear'], ['get', 'anomalyScore'],
        0.40, 18,
        0.70, 28,
        1.00, 40,
      ],
      'circle-color': [
        'case',
        ['==', ['get', 'isQuarantined'], true], COLORS.NODE_QUARANTINED,
        COLORS.NODE_DEGRADED,
      ],
      'circle-opacity': 0.25,
      'circle-stroke-width': 1.5,
      'circle-stroke-color': [
        'case',
        ['==', ['get', 'isQuarantined'], true], COLORS.NODE_QUARANTINED,
        COLORS.NODE_DEGRADED,
      ],
      'circle-stroke-opacity': 0.7,
      'circle-pitch-alignment': 'map',
    },
  });

  // Main node dot
  map.addLayer({
    id: LAYER_IDS.ARGUS_NODES,
    type: 'circle',
    source: LAYER_IDS.ARGUS_NODES_SRC,
    paint: {
      'circle-radius': [
        'interpolate', ['linear'], ['zoom'],
        10, 8,
        14, 12,
        18, 18,
      ],
      'circle-color': [
        'case',
        ['==', ['get', 'isQuarantined'], true], COLORS.NODE_QUARANTINED,
        ['>=', ['get', 'trustScore'], TRUST.HIGH],  COLORS.NODE_HEALTHY,
        ['>=', ['get', 'trustScore'], TRUST.MEDIUM], COLORS.NODE_DEGRADED,
        COLORS.NODE_COMPROMISED,
      ],
      'circle-stroke-width': 2,
      'circle-stroke-color': '#000000',
      'circle-opacity': 0.9,
    },
  });

  // Node ID label
  map.addLayer({
    id: LAYER_IDS.ARGUS_NODES_LABELS,
    type: 'symbol',
    source: LAYER_IDS.ARGUS_NODES_SRC,
    layout: {
      'text-field': ['get', 'nodeId'],
      'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
      'text-size': 10,
      'text-offset': [0, 1.6],
      'text-anchor': 'top',
      'text-allow-overlap': false,
    },
    paint: {
      'text-color': ['get', 'labelColor'],
      'text-halo-color': '#000000',
      'text-halo-width': 1.5,
    },
  });
}

/**
 * Updates node markers with fresh pipeline data.
 *
 * @param {import('maplibre-gl').Map} map
 * @param {Map<string, Object>} nodeStateMap — nodeId → NodeTrustState
 * @param {Map<string, Object>} latestEvents — nodeId → ArgusEvent
 * @param {boolean} visible
 */
export function updateArgusNodeLayer(map, nodeStateMap, latestEvents, visible) {
  const src = map.getSource(LAYER_IDS.ARGUS_NODES_SRC);
  if (!src) return;

  const features = [];

  for (const [nodeId, state] of nodeStateMap.entries()) {
    const event = latestEvents.get(nodeId);
    if (!event) continue;

    const { latitude, longitude } = event.location;
    const trustScore = state.compositeTrust;
    const isQuarantined = state.isQuarantined;
    const isAnomaly = event.analytics.isAnomaly;
    const anomalyScore = event.analytics.anomalyScore;
    const integrityStatus = event.integrity.status;

    const labelColor = isQuarantined
      ? COLORS.NODE_QUARANTINED
      : trustScore >= TRUST.HIGH
        ? COLORS.NODE_HEALTHY
        : trustScore >= TRUST.MEDIUM
          ? COLORS.NODE_DEGRADED
          : COLORS.NODE_COMPROMISED;

    features.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [longitude, latitude] },
      properties: {
        nodeId,
        trustScore,
        isQuarantined,
        isAnomaly,
        anomalyScore,
        integrityStatus,
        temperatureCelsius: event.measurements?.temperatureCelsius ?? 0,
        batteryPercent: event.measurements?.batteryPercent ?? 0,
        severity: event.severity,
        anomalyReasons: JSON.stringify(event.analytics.anomalyReasons || []),
        labelColor,
        // Formatted for panel display
        trustPct: Math.round(trustScore * 100),
      },
    });
  }

  src.setData({ type: 'FeatureCollection', features });

  // Toggle visibility
  const vis = visible ? 'visible' : 'none';
  [LAYER_IDS.ARGUS_NODES, LAYER_IDS.ARGUS_NODES_PULSE, LAYER_IDS.ARGUS_NODES_LABELS].forEach(id => {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', vis);
  });
}

/**
 * Removes all ARGUS node layers and source from the map.
 * @param {import('maplibre-gl').Map} map
 */
export function destroyArgusNodeLayer(map) {
  [LAYER_IDS.ARGUS_NODES_LABELS, LAYER_IDS.ARGUS_NODES, LAYER_IDS.ARGUS_NODES_PULSE].forEach(id => {
    if (map.getLayer(id)) map.removeLayer(id);
  });
  if (map.getSource(LAYER_IDS.ARGUS_NODES_SRC)) map.removeSource(LAYER_IDS.ARGUS_NODES_SRC);
}

// ─── Internal Helpers ─────────────────────────────────────────────────────────
function _emptyFeatureCollection() {
  return { type: 'FeatureCollection', features: [] };
}
