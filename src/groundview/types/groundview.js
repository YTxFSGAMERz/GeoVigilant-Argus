/**
 * ARGUS GroundView — Shared Type Definitions & Constants
 *
 * Central registry for layer IDs, trust thresholds, map config constants,
 * and visual encoding parameters used across all GroundView modules.
 *
 * Does NOT import from Cesium or MapLibre — pure data/constants.
 */

// ─── Layer Identifiers ───────────────────────────────────────────────────────
export const LAYER_IDS = {
  // ARGUS Node markers (MapLibre symbol layer)
  ARGUS_NODES:         'gv-argus-nodes',
  ARGUS_NODES_SRC:     'gv-argus-nodes-src',
  ARGUS_NODES_LABELS:  'gv-argus-nodes-labels',

  // Trust-based pulse rings (circle layer around nodes)
  ARGUS_NODES_PULSE:   'gv-argus-nodes-pulse',

  // Incident markers
  INCIDENTS:           'gv-incidents',
  INCIDENTS_SRC:       'gv-incidents-src',
  INCIDENTS_LABELS:    'gv-incidents-labels',

  // Anomaly halo rings
  ANOMALIES:           'gv-anomalies',
  ANOMALIES_SRC:       'gv-anomalies-src',

  // Mapillary coverage (future)
  MAPILLARY_COVERAGE:  'gv-mapillary-coverage',
  MAPILLARY_SRC:       'gv-mapillary-src',

  // Global Streetscapes (10k SVI visual intelligence dataset)
  STREETSCAPES_SRC:          'gv-streetscapes-src',
  STREETSCAPES_CLUSTERS:     'gv-streetscapes-clusters',
  STREETSCAPES_CLUSTER_COUNT: 'gv-streetscapes-cluster-count',
  STREETSCAPES_UNCLUSTERED:  'gv-streetscapes-unclustered',
  STREETSCAPES_PULSE:        'gv-streetscapes-pulse',
};

// ─── Trust Score Thresholds ──────────────────────────────────────────────────
export const TRUST = {
  HIGH:   0.75,   // ≥ 0.75 → green (healthy)
  MEDIUM: 0.45,   // ≥ 0.45 → amber (degraded)
  LOW:    0.0,    // < 0.45 → red   (compromised)
};

// ─── Visual Color Palette (ARGUS cyberpunk theme) ────────────────────────────
export const COLORS = {
  NODE_HEALTHY:        '#00FFD1',  // cyber-cyan
  NODE_DEGRADED:       '#FFCC00',  // cyber-amber
  NODE_COMPROMISED:    '#FF0055',  // cyber-red
  NODE_QUARANTINED:    '#BC13FE',  // cyber-purple
  ANOMALY_HALO:        'rgba(255, 204, 0, 0.35)',
  INCIDENT_MARKER:     '#FF0055',
  INCIDENT_STROKE:     '#FF4488',
  MAP_TEXT:            '#00FFD1',
};

// ─── Map Configuration ───────────────────────────────────────────────────────
export const MAP_CONFIG = {
  // CartoDB Dark Matter — free, no API key, MapLibre native tile URL format
  BASEMAP_DARK: {
    type: 'raster',
    tiles: [
      'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
      'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
      'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
    ],
    tileSize: 256,
    attribution: '© <a href="https://carto.com/attributions">CARTO</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxzoom: 19,
  },

  // OpenStreetMap fallback (no API key)
  BASEMAP_STREETS: {
    type: 'raster',
    tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
    tileSize: 256,
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxzoom: 19,
  },

  // Default camera — SF Bay Area (where ARGUS nodes are seeded)
  DEFAULT_CENTER: [-122.4194, 37.7749],
  DEFAULT_ZOOM: 11,
  DEFAULT_PITCH: 0,
  DEFAULT_BEARING: 0,
};

// ─── Anomaly Score Thresholds ─────────────────────────────────────────────────
export const ANOMALY = {
  THRESHOLD:  0.40,   // minimum score to render halo
  HIGH:       0.70,   // high anomaly — larger halo
  CRITICAL:   0.90,   // critical — maximum pulse
};

// ─── Mapillary Config ─────────────────────────────────────────────────────────
// Access token is passed at runtime; never hardcoded in JS bundles.
// The backend exposes it via /api/groundview/config to keep it server-side.
export const MAPILLARY_CONFIG = {
  CLIENT_ID:    '28129684709980967',
  GRAPH_API:    'https://graph.mapillary.com',
  COVERAGE_ZOOM_THRESHOLD: 14,  // only query coverage at zoom ≥ 14
};

// ─── Scenario Seed (must match globe-main.js for deterministic parity) ────────
export const ARGUS_SEED = 0x1337;
