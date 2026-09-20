/**
 * ARGUS GroundView — Global Streetscapes (10k SVI) Visual Intelligence Layer
 *
 * Renders 10,000 geolocated street-level camera observation points with
 * GPU-accelerated MapLibre clustering:
 *   - Clustered view at low/medium zoom: Glowing holographic badges with observation counts
 *   - Unclustered view at high zoom: High-tech pulsing camera aperture markers
 *   - Interactive clicks: Trigger inspection in the ARGUS Visual Intelligence HUD Modal
 */

import { LAYER_IDS } from '../types/groundview.js';

let _visible = false;

/**
 * Initializes the GPU-accelerated Streetscapes cluster source and layers.
 * @param {import('maplibre-gl').Map} map
 * @param {boolean} [initialVisible=false]
 */
export function initStreetscapesLayer(map, initialVisible = false) {
  _visible = initialVisible;

  if (map.getSource(LAYER_IDS.STREETSCAPES_SRC)) return;

  // 1. Add clustered GeoJSON source
  map.addSource(LAYER_IDS.STREETSCAPES_SRC, {
    type: 'geojson',
    data: '/api/groundview/streetscapes/geojson',
    cluster: true,
    clusterMaxZoom: 13,
    clusterRadius: 50,
  });

  const visibility = _visible ? 'visible' : 'none';

  // 2. Cluster circles with dynamic cyber-glow styling
  map.addLayer({
    id: LAYER_IDS.STREETSCAPES_CLUSTERS,
    type: 'circle',
    source: LAYER_IDS.STREETSCAPES_SRC,
    filter: ['has', 'point_count'],
    layout: { visibility },
    paint: {
      'circle-color': [
        'step',
        ['get', 'point_count'],
        '#00f0ff',   // Cyan for small clusters (< 50)
        50,
        '#00ffa3',   // Emerald for medium clusters (50-250)
        250,
        '#ffb800',   // Amber for large clusters (> 250)
      ],
      'circle-radius': [
        'step',
        ['get', 'point_count'],
        16,
        50,
        22,
        250,
        28,
      ],
      'circle-opacity': 0.88,
      'circle-stroke-width': 2,
      'circle-stroke-color': '#ffffff',
      'circle-stroke-opacity': 0.9,
    },
  });

  // 3. Cluster count typography
  map.addLayer({
    id: LAYER_IDS.STREETSCAPES_CLUSTER_COUNT,
    type: 'symbol',
    source: LAYER_IDS.STREETSCAPES_SRC,
    filter: ['has', 'point_count'],
    layout: {
      'text-field': '{point_count_abbreviated}',
      'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
      'text-size': 12,
      'text-allow-overlap': true,
      'visibility': visibility,
    },
    paint: {
      'text-color': '#050a0e',
    },
  });

  // 4. Unclustered individual camera observation nodes (outer pulse ring)
  map.addLayer({
    id: LAYER_IDS.STREETSCAPES_PULSE,
    type: 'circle',
    source: LAYER_IDS.STREETSCAPES_SRC,
    filter: ['!', ['has', 'point_count']],
    layout: { visibility },
    paint: {
      'circle-radius': 12,
      'circle-color': '#00f0ff',
      'circle-opacity': 0.22,
      'circle-stroke-width': 1,
      'circle-stroke-color': '#00f0ff',
      'circle-stroke-opacity': 0.65,
    },
  });

  // 5. Unclustered camera pin core
  map.addLayer({
    id: LAYER_IDS.STREETSCAPES_UNCLUSTERED,
    type: 'circle',
    source: LAYER_IDS.STREETSCAPES_SRC,
    filter: ['!', ['has', 'point_count']],
    layout: { visibility },
    paint: {
      'circle-radius': 6,
      'circle-color': '#00f0ff',
      'circle-stroke-width': 2,
      'circle-stroke-color': '#ffffff',
      'circle-opacity': 0.95,
    },
  });
}

/**
 * Toggle visibility of all Streetscapes cluster & marker layers.
 * @param {import('maplibre-gl').Map} map
 * @param {boolean} visible
 */
export function setStreetscapesLayerVisible(map, visible) {
  _visible = visible;
  if (!map || !map.isStyleLoaded()) return;

  const visibility = visible ? 'visible' : 'none';
  const layerIds = [
    LAYER_IDS.STREETSCAPES_CLUSTERS,
    LAYER_IDS.STREETSCAPES_CLUSTER_COUNT,
    LAYER_IDS.STREETSCAPES_PULSE,
    LAYER_IDS.STREETSCAPES_UNCLUSTERED,
  ];

  layerIds.forEach((id) => {
    if (map.getLayer(id)) {
      map.setLayoutProperty(id, 'visibility', visibility);
    }
  });
}

/**
 * Destroys all Streetscapes layers and the underlying source.
 * @param {import('maplibre-gl').Map} map
 */
export function destroyStreetscapesLayer(map) {
  const layerIds = [
    LAYER_IDS.STREETSCAPES_CLUSTER_COUNT,
    LAYER_IDS.STREETSCAPES_CLUSTERS,
    LAYER_IDS.STREETSCAPES_UNCLUSTERED,
    LAYER_IDS.STREETSCAPES_PULSE,
  ];

  layerIds.forEach((id) => {
    if (map.getLayer(id)) map.removeLayer(id);
  });

  if (map.getSource(LAYER_IDS.STREETSCAPES_SRC)) {
    map.removeSource(LAYER_IDS.STREETSCAPES_SRC);
  }
}
