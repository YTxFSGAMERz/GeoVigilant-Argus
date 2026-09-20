/**
 * ARGUS GroundView — MapLibre Ground Map Engine
 *
 * ISOLATION GUARANTEE:
 *   - Cesium is NEVER imported or referenced here
 *   - MapLibre is ONLY loaded when initGroundMap() is called
 *
 * Architecture:
 *   - BasemapManager: Handles 'tactical', 'streets', and 'satellite' modes
 *   - Intelligence Layers: ARGUS Nodes, Anomalies, Incidents, Mapillary, and Global Streetscapes (10k SVI)
 */

import { MAP_CONFIG, LAYER_IDS } from './types/groundview.js';
import { BasemapManager } from './basemaps/basemapManager.js';
import { initArgusNodeLayer, updateArgusNodeLayer, destroyArgusNodeLayer } from './layers/argusNodeLayer.js';
import { initIncidentLayer, updateIncidentLayer, destroyIncidentLayer } from './layers/incidentLayer.js';
import { initAnomalyLayer, setAnomalyLayerVisible, destroyAnomalyLayer } from './layers/anomalyLayer.js';
import { initMapillaryLayer, updateMapillaryLayer, destroyMapillaryLayer } from './layers/mapillaryLayer.js';
import { initStreetscapesLayer, setStreetscapesLayerVisible, destroyStreetscapesLayer } from './layers/streetscapesLayer.js';
import { initLandmarkLayer, setLandmarkLayerVisible, filterLandmarksByCategory, removeLandmarkLayer } from './layers/landmarkLayer.js';

// ─── Module State ─────────────────────────────────────────────────────────────
let _map = null;
let _maplibregl = null;
let _popup = null;
let _basemapManager = null;
let _callbacks = {};
let _layerVisible = {
  nodes:        true,
  incidents:    true,
  anomalies:    true,
  landmarks:    true,
  streetscapes: false,
  mapillary:    false,
};

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Lazily imports MapLibre GL JS and initializes the map.
 *
 * @param {string} containerId  — DOM element ID for the map container
 * @param {Object} [callbacks]
 * @param {Function} [callbacks.onNodeClick]
 * @param {Function} [callbacks.onIncidentClick]
 * @param {Function} [callbacks.onMapillaryClick]
 * @param {Function} [callbacks.onStreetscapeClick]
 * @param {Function} [callbacks.onMapReady]  — called when map and all layers are ready
 * @returns {Promise<void>}
 */
export async function initGroundMap(containerId, callbacks = {}) {
  if (_map) return; // already initialized
  _callbacks = callbacks;

  // Verify container
  const container = document.getElementById(containerId);
  if (!container) {
    console.error(`[GroundMap] Container #${containerId} not found in DOM!`);
    return;
  }

  console.log('[GroundMap] Loading MapLibre GL JS chunk...');

  // Dynamic import — Vite builds this into a separate chunk from globe-main.js
  const mod = await import('maplibre-gl');
  _maplibregl = mod.default ?? mod;

  console.log('[GroundMap] MapLibre GL JS loaded. Building map...');

  // Initial style URL (Tactical Dark)
  const initialStyle = `/api/groundview/map-style?theme=tactical&t=${Date.now()}`;

  _map = new _maplibregl.Map({
    container: containerId,
    style: initialStyle,
    center: MAP_CONFIG.DEFAULT_CENTER,
    zoom: MAP_CONFIG.DEFAULT_ZOOM,
    pitch: MAP_CONFIG.DEFAULT_PITCH,
    bearing: MAP_CONFIG.DEFAULT_BEARING,
    attributionControl: false,
    antialias: true,
  });

  if (typeof window !== 'undefined') {
    window._gv_map = _map;
    window.groundMap = _map;
    window.map = _map;
    window.flyTo = flyTo;
  }

  // Surface all map errors immediately to the console
  _map.on('error', (e) => {
    console.error('[GroundMap] MapLibre error:', e?.error?.message ?? e?.error ?? e);
  });

  // Navigation controls (+/- zoom)
  _map.addControl(
    new _maplibregl.NavigationControl({ showCompass: false }),
    'bottom-right',
  );

  // Attribution
  _map.addControl(
    new _maplibregl.AttributionControl({ compact: true }),
    'bottom-right',
  );

  // Reusable popup
  _popup = new _maplibregl.Popup({
    closeButton: true,
    closeOnClick: false,
    maxWidth: '340px',
    className: 'gv-popup',
  });

  // Initialize BasemapManager with callback to restore layers upon style changes
  _basemapManager = new BasemapManager(_map, () => {
    _registerLayers();
  });

  // Register ARGUS layers and fire onMapReady once MapLibre has loaded
  _map.once('load', () => {
    console.log('[GroundMap] Map load event fired — registering ARGUS intelligence layers...');
    _registerLayers();
    _bindMapEvents(callbacks);
    if (typeof callbacks.onMapReady === 'function') {
      callbacks.onMapReady();
    }
  });

  // Safety: warn if map doesn't load within 12 seconds
  const warnTimer = setTimeout(() => {
    console.error('[GroundMap] Timed out waiting for map load event. Check network & tile URLs.');
  }, 12000);
  _map.once('load', () => clearTimeout(warnTimer));
}

/**
 * Push fresh ARGUS data to all map layers.
 */
export function updateGroundMapData(data) {
  if (!_map || !_map.isStyleLoaded()) return;
  const { nodeStateMap, latestEvents, incidents } = data;
  updateArgusNodeLayer(_map, nodeStateMap, latestEvents, _layerVisible.nodes);
  updateIncidentLayer(_map, incidents, _layerVisible.incidents);
  setAnomalyLayerVisible(_map, _layerVisible.anomalies);
}

/**
 * Update Mapillary street image layer.
 */
export function updateMapillaryData(images) {
  if (!_map) return;
  updateMapillaryLayer(_map, images, _layerVisible.mapillary);
}

/**
 * Filter landmarks by category.
 */
export function filterLandmarks(category) {
  if (!_map) return;
  filterLandmarksByCategory(_map, category);
}

/**
 * Toggle a named layer group on/off.
 * @param {'nodes'|'incidents'|'anomalies'|'landmarks'|'streetscapes'|'mapillary'} layerName
 * @param {boolean} visible
 */
export function setLayerVisible(layerName, visible) {
  _layerVisible[layerName] = visible;
  if (!_map || !_map.isStyleLoaded()) return;

  if (layerName === 'nodes') {
    [LAYER_IDS.ARGUS_NODES, LAYER_IDS.ARGUS_NODES_PULSE, LAYER_IDS.ARGUS_NODES_LABELS].forEach(id => {
      if (_map.getLayer(id)) _map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
    });
  } else if (layerName === 'incidents') {
    [LAYER_IDS.INCIDENTS, 'gv-incidents-glow', LAYER_IDS.INCIDENTS_LABELS].forEach(id => {
      if (_map.getLayer(id)) _map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
    });
  } else if (layerName === 'anomalies') {
    setAnomalyLayerVisible(_map, visible);
  } else if (layerName === 'landmarks') {
    setLandmarkLayerVisible(_map, visible);
  } else if (layerName === 'streetscapes') {
    setStreetscapesLayerVisible(_map, visible);
  } else if (layerName === 'mapillary') {
    if (_map.getLayer(LAYER_IDS.MAPILLARY_COVERAGE)) {
      _map.setLayoutProperty(LAYER_IDS.MAPILLARY_COVERAGE, 'visibility', visible ? 'visible' : 'none');
    }
  }
}

/**
 * Switch the active basemap mode via BasemapManager.
 * @param {'tactical'|'streets'|'satellite'} mode
 */
export async function setBasemap(mode) {
  if (!_basemapManager) return;
  await _basemapManager.setMode(mode);
}

/**
 * Returns current basemap mode.
 */
export function getBasemapMode() {
  return _basemapManager?.getCurrentMode() ?? 'tactical';
}

/**
 * Animated flyTo.
 * @param {number} lat
 * @param {number} lon
 * @param {number} [zoom=14]
 */
export function flyTo(lat, lon, zoom = 14) {
  if (!_map) return;
  _map.flyTo({ center: [lon, lat], zoom, duration: 1200, essential: true });
}

/**
 * Destroy map and release memory.
 */
export function destroyGroundMap() {
  if (!_map) return;
  _popup?.remove();
  removeLandmarkLayer(_map);
  destroyStreetscapesLayer(_map);
  destroyAnomalyLayer(_map);
  destroyMapillaryLayer(_map);
  destroyIncidentLayer(_map);
  destroyArgusNodeLayer(_map);
  _map.remove();
  _map = null;
  _maplibregl = null;
  _popup = null;
  _basemapManager = null;
}

export function getMap() { return _map; }

// ─── Internal: Layer Registration ─────────────────────────────────────────────

function _registerLayers() {
  try {
    // ARGUS intelligence layers (rendered above active basemap)
    initArgusNodeLayer(_map);
    initAnomalyLayer(_map);
    initIncidentLayer(_map);
    initMapillaryLayer(_map);
    initLandmarkLayer(_map, _layerVisible.landmarks, _callbacks.onLandmarkClick);
    initStreetscapesLayer(_map, _layerVisible.streetscapes);
    console.log('[GroundMap] All ARGUS & Visual Intelligence layers registered.');
  } catch (err) {
    console.error('[GroundMap] Layer registration failed:', err);
  }
}

// ─── Internal: Event Binding ───────────────────────────────────────────────────

function _bindMapEvents(callbacks) {
  const hoverLayers = [
    LAYER_IDS.ARGUS_NODES,
    LAYER_IDS.INCIDENTS,
    LAYER_IDS.MAPILLARY_COVERAGE,
    LAYER_IDS.STREETSCAPES_CLUSTERS,
    LAYER_IDS.STREETSCAPES_UNCLUSTERED,
  ];

  hoverLayers.forEach(id => {
    _map.on('mouseenter', id, () => { _map.getCanvas().style.cursor = 'crosshair'; });
    _map.on('mouseleave', id, () => { _map.getCanvas().style.cursor = ''; });
  });

  _map.on('click', LAYER_IDS.ARGUS_NODES, (e) => {
    const props = e.features?.[0]?.properties;
    if (props && typeof callbacks.onNodeClick === 'function') {
      e.originalEvent.stopPropagation();
      callbacks.onNodeClick(props, e.lngLat);
    }
  });

  _map.on('click', LAYER_IDS.INCIDENTS, (e) => {
    const props = e.features?.[0]?.properties;
    if (props && typeof callbacks.onIncidentClick === 'function') {
      e.originalEvent.stopPropagation();
      callbacks.onIncidentClick(props, e.lngLat);
    }
  });

  _map.on('click', LAYER_IDS.MAPILLARY_COVERAGE, (e) => {
    const props = e.features?.[0]?.properties;
    if (props && typeof callbacks.onMapillaryClick === 'function') {
      e.originalEvent.stopPropagation();
      callbacks.onMapillaryClick(props, e.lngLat);
    }
  });

  // Streetscapes Cluster Expansion Click
  _map.on('click', LAYER_IDS.STREETSCAPES_CLUSTERS, (e) => {
    const features = _map.queryRenderedFeatures(e.point, { layers: [LAYER_IDS.STREETSCAPES_CLUSTERS] });
    const clusterId = features[0]?.properties?.cluster_id;
    const src = _map.getSource(LAYER_IDS.STREETSCAPES_SRC);
    if (src && clusterId !== undefined) {
      src.getClusterExpansionZoom(clusterId, (err, zoom) => {
        if (err) return;
        _map.easeTo({
          center: features[0].geometry.coordinates,
          zoom: zoom + 1,
          duration: 600,
        });
      });
    }
  });

  // Streetscapes Unclustered Camera Marker Click
  _map.on('click', LAYER_IDS.STREETSCAPES_UNCLUSTERED, (e) => {
    const props = e.features?.[0]?.properties;
    if (props && typeof callbacks.onStreetscapeClick === 'function') {
      e.originalEvent.stopPropagation();
      callbacks.onStreetscapeClick(props, e.lngLat);
    }
  });
}
