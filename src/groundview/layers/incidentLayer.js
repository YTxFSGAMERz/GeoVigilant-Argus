/**
 * ARGUS GroundView — Incident Layer
 *
 * Renders active CyberIncident markers on the MapLibre map.
 * Data model consumed directly from CyberIncidentEngine output:
 *   - incidentId, title, severity, status
 *   - centroid (lat/lon)
 *   - evidence { integrityViolations, anomalyReasons, trustScoreAtDetection }
 *   - confidenceScore, quarantined
 *
 * No new incident model is created. The existing engine's output is displayed.
 */

import { LAYER_IDS, COLORS } from '../types/groundview.js';

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Registers the incident source and layers on the MapLibre map.
 * @param {import('maplibre-gl').Map} map
 */
export function initIncidentLayer(map) {
  map.addSource(LAYER_IDS.INCIDENTS_SRC, {
    type: 'geojson',
    data: _emptyFeatureCollection(),
  });

  // Outer glow ring
  map.addLayer({
    id: 'gv-incidents-glow',
    type: 'circle',
    source: LAYER_IDS.INCIDENTS_SRC,
    paint: {
      'circle-radius': _severityRadius(1.8),
      'circle-color': COLORS.INCIDENT_STROKE,
      'circle-opacity': 0.15,
      'circle-stroke-width': 0,
    },
  });

  // Main incident dot
  map.addLayer({
    id: LAYER_IDS.INCIDENTS,
    type: 'circle',
    source: LAYER_IDS.INCIDENTS_SRC,
    paint: {
      'circle-radius': _severityRadius(1.0),
      'circle-color': COLORS.INCIDENT_MARKER,
      'circle-stroke-width': 2,
      'circle-stroke-color': COLORS.INCIDENT_STROKE,
      'circle-opacity': 0.92,
    },
  });

  // Incident ID label
  map.addLayer({
    id: LAYER_IDS.INCIDENTS_LABELS,
    type: 'symbol',
    source: LAYER_IDS.INCIDENTS_SRC,
    layout: {
      'text-field': ['get', 'incidentId'],
      'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
      'text-size': 9,
      'text-offset': [0, 1.8],
      'text-anchor': 'top',
      'text-allow-overlap': false,
    },
    paint: {
      'text-color': COLORS.INCIDENT_STROKE,
      'text-halo-color': '#000000',
      'text-halo-width': 1.5,
    },
  });
}

/**
 * Updates incident markers from CyberIncidentEngine output.
 *
 * @param {import('maplibre-gl').Map} map
 * @param {Array<Object>} incidents — from CyberIncidentEngine.getActiveIncidents()
 * @param {boolean} visible
 */
export function updateIncidentLayer(map, incidents, visible) {
  const src = map.getSource(LAYER_IDS.INCIDENTS_SRC);
  if (!src) return;

  const features = incidents
    .filter(inc => inc.centroid && typeof inc.centroid.longitude === 'number')
    .map(inc => ({
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [inc.centroid.longitude, inc.centroid.latitude],
      },
      properties: {
        incidentId:          inc.incidentId,
        title:               inc.title,
        severity:            inc.severity,
        status:              inc.status,
        quarantined:         inc.quarantined,
        confidenceScore:     inc.confidenceScore,
        trustAtDetection:    inc.evidence?.trustScoreAtDetection ?? 0,
        primaryNodeId:       inc.primaryNodeId,
        integrityViolations: JSON.stringify(inc.evidence?.integrityViolations || []),
        anomalyReasons:      JSON.stringify(inc.evidence?.anomalyReasons || []),
        eventCount:          inc.evidence?.contributingEventIds?.length || 0,
        detectedAtMs:        inc.detectedAtMs,
        updatedAtMs:         inc.updatedAtMs,
        // severity numeric for MapLibre expressions
        severityNum: { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, INFO: 0 }[inc.severity] ?? 1,
      },
    }));

  src.setData({ type: 'FeatureCollection', features });

  const vis = visible ? 'visible' : 'none';
  [LAYER_IDS.INCIDENTS, 'gv-incidents-glow', LAYER_IDS.INCIDENTS_LABELS].forEach(id => {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', vis);
  });
}

/**
 * Removes incident layers and source.
 * @param {import('maplibre-gl').Map} map
 */
export function destroyIncidentLayer(map) {
  [LAYER_IDS.INCIDENTS_LABELS, LAYER_IDS.INCIDENTS, 'gv-incidents-glow'].forEach(id => {
    if (map.getLayer(id)) map.removeLayer(id);
  });
  if (map.getSource(LAYER_IDS.INCIDENTS_SRC)) map.removeSource(LAYER_IDS.INCIDENTS_SRC);
}

// ─── Internal Helpers ─────────────────────────────────────────────────────────
function _emptyFeatureCollection() {
  return { type: 'FeatureCollection', features: [] };
}

/** MapLibre expression: radius scaled by severity level. */
function _severityRadius(multiplier) {
  return [
    'interpolate', ['linear'], ['get', 'severityNum'],
    0, 8  * multiplier,
    1, 10 * multiplier,
    2, 12 * multiplier,
    3, 15 * multiplier,
    4, 20 * multiplier,
  ];
}
