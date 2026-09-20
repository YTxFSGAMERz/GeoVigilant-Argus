/**
 * ARGUS GroundView — Global Landmarks (3.8k POIs, 74k+ Verified Images) Visual Layer
 *
 * Renders 3,806 verified global landmarks across 162 sovereign states with
 * GPU-accelerated MapLibre clustering:
 *   - Clustered view at low/medium zoom: Glowing golden tactical cluster badges
 *   - Unclustered view: Category-tinted glowing aperture markers with localized name labels
 *   - Interactive clicks: Opens the ARGUS Ground Truth Landmark Gallery & Multi-Angle Probes HUD
 */

export const LANDMARK_LAYER_IDS = {
  SRC: 'gv-landmarks-src',
  CLUSTERS: 'gv-landmarks-clusters',
  CLUSTER_COUNT: 'gv-landmarks-cluster-count',
  PULSE: 'gv-landmarks-pulse',
  MARKERS: 'gv-landmarks-markers',
  LABELS: 'gv-landmarks-labels',
};

let _visible = false;
let _currentCategory = null;

/**
 * Initializes the GPU-accelerated Landmarks cluster source and styling layers.
 * @param {import('maplibre-gl').Map} map
 * @param {boolean} [initialVisible=true]
 * @param {Function} [onLandmarkClick]
 */
export function initLandmarkLayer(map, initialVisible = true, onLandmarkClick = null) {
  _visible = initialVisible;

  if (map.getSource(LANDMARK_LAYER_IDS.SRC)) return;

  const dataUrl = '/api/argus/places/geojson';

  // 1. Add clustered GeoJSON source
  map.addSource(LANDMARK_LAYER_IDS.SRC, {
    type: 'geojson',
    data: dataUrl,
    cluster: true,
    clusterMaxZoom: 14,
    clusterRadius: 45,
  });

  const visibility = _visible ? 'visible' : 'none';

  // 2. Cluster circles with cyber-gold / amber tactical styling
  map.addLayer({
    id: LANDMARK_LAYER_IDS.CLUSTERS,
    type: 'circle',
    source: LANDMARK_LAYER_IDS.SRC,
    filter: ['has', 'point_count'],
    layout: { visibility },
    paint: {
      'circle-color': [
        'step',
        ['get', 'point_count'],
        '#FFD700',   // Gold for small clusters (< 25)
        25,
        '#FF9900',   // Amber for medium clusters (25-100)
        100,
        '#00FFD1',   // Cyan for large regional landmark hubs (> 100)
      ],
      'circle-radius': [
        'step',
        ['get', 'point_count'],
        18,
        25,
        24,
        100,
        30,
      ],
      'circle-opacity': 0.90,
      'circle-stroke-width': 2.5,
      'circle-stroke-color': '#0a0a0a',
      'circle-stroke-opacity': 0.95,
    },
  });

  // 3. Cluster count typography
  map.addLayer({
    id: LANDMARK_LAYER_IDS.CLUSTER_COUNT,
    type: 'symbol',
    source: LANDMARK_LAYER_IDS.SRC,
    filter: ['has', 'point_count'],
    layout: {
      'text-field': '{point_count_abbreviated}',
      'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
      'text-size': 12,
      'text-allow-overlap': true,
      visibility,
    },
    paint: {
      'text-color': '#050a0e',
    },
  });

  // 4. Unclustered landmark outer glowing pulse ring
  map.addLayer({
    id: LANDMARK_LAYER_IDS.PULSE,
    type: 'circle',
    source: LANDMARK_LAYER_IDS.SRC,
    filter: ['!', ['has', 'point_count']],
    layout: { visibility },
    paint: {
      'circle-radius': 14,
      'circle-color': ['coalesce', ['get', 'color'], '#FFD700'],
      'circle-opacity': 0.25,
      'circle-stroke-width': 1.5,
      'circle-stroke-color': ['coalesce', ['get', 'color'], '#FFD700'],
      'circle-stroke-opacity': 0.75,
    },
  });

  // 5. Unclustered landmark inner core marker
  map.addLayer({
    id: LANDMARK_LAYER_IDS.MARKERS,
    type: 'circle',
    source: LANDMARK_LAYER_IDS.SRC,
    filter: ['!', ['has', 'point_count']],
    layout: { visibility },
    paint: {
      'circle-radius': 7,
      'circle-color': ['coalesce', ['get', 'color'], '#FFD700'],
      'circle-stroke-width': 2,
      'circle-stroke-color': '#ffffff',
      'circle-opacity': 0.95,
    },
  });

  // 6. Landmark text label (visible at zoom >= 10)
  map.addLayer({
    id: LANDMARK_LAYER_IDS.LABELS,
    type: 'symbol',
    source: LANDMARK_LAYER_IDS.SRC,
    filter: ['!', ['has', 'point_count']],
    minzoom: 10,
    layout: {
      'text-field': ['get', 'name'],
      'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
      'text-size': 11,
      'text-offset': [0, 1.4],
      'text-anchor': 'top',
      'text-allow-overlap': false,
      visibility,
    },
    paint: {
      'text-color': '#ffffff',
      'text-halo-color': '#000000',
      'text-halo-width': 2.0,
    },
  });

  // ─── Click Interactions ───────────────────────────────────────────────────

  // Clicking a cluster zooms in
  map.on('click', LANDMARK_LAYER_IDS.CLUSTERS, async (e) => {
    const features = map.queryRenderedFeatures(e.point, { layers: [LANDMARK_LAYER_IDS.CLUSTERS] });
    if (!features.length) return;

    const clusterId = features[0].properties.cluster_id;
    const source = map.getSource(LANDMARK_LAYER_IDS.SRC);

    try {
      const zoom = await source.getClusterExpansionZoom(clusterId);
      map.easeTo({
        center: features[0].geometry.coordinates,
        zoom: Math.min(zoom + 1, 16),
        duration: 600,
      });
    } catch (err) {
      console.warn('[LandmarkLayer] Cluster expansion error:', err);
    }
  });

  // Hover cursor changes
  [LANDMARK_LAYER_IDS.CLUSTERS, LANDMARK_LAYER_IDS.MARKERS].forEach((layerId) => {
    map.on('mouseenter', layerId, () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', layerId, () => { map.getCanvas().style.cursor = ''; });
  });

  // Clicking an unclustered landmark triggers the ground-truth HUD callback
  if (typeof onLandmarkClick === 'function') {
    map.on('click', LANDMARK_LAYER_IDS.MARKERS, (e) => {
      const features = map.queryRenderedFeatures(e.point, { layers: [LANDMARK_LAYER_IDS.MARKERS] });
      if (!features.length) return;
      onLandmarkClick(features[0].properties, e.lngLat);
    });
  }
}

/**
 * Sets visibility of all landmark layers.
 * @param {import('maplibre-gl').Map} map
 * @param {boolean} visible
 */
export function setLandmarkLayerVisible(map, visible) {
  _visible = visible;
  if (!map || !map.isStyleLoaded()) return;

  const v = visible ? 'visible' : 'none';
  [
    LANDMARK_LAYER_IDS.CLUSTERS,
    LANDMARK_LAYER_IDS.CLUSTER_COUNT,
    LANDMARK_LAYER_IDS.PULSE,
    LANDMARK_LAYER_IDS.MARKERS,
    LANDMARK_LAYER_IDS.LABELS,
  ].forEach((id) => {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', v);
  });
}

/**
 * Filter landmark layers by category.
 * @param {import('maplibre-gl').Map} map
 * @param {string|null} category
 */
export function filterLandmarksByCategory(map, category = null) {
  _currentCategory = category;
  const source = map.getSource(LANDMARK_LAYER_IDS.SRC);
  if (!source) return;

  const url = category && category !== 'ALL'
    ? `/api/argus/places/geojson?category=${encodeURIComponent(category)}`
    : '/api/argus/places/geojson';

  source.setData(url);
}

/**
 * Removes all landmark layers and source from map (e.g. on style reload).
 * @param {import('maplibre-gl').Map} map
 */
export function removeLandmarkLayer(map) {
  [
    LANDMARK_LAYER_IDS.LABELS,
    LANDMARK_LAYER_IDS.MARKERS,
    LANDMARK_LAYER_IDS.PULSE,
    LANDMARK_LAYER_IDS.CLUSTER_COUNT,
    LANDMARK_LAYER_IDS.CLUSTERS,
  ].forEach((id) => {
    if (map.getLayer(id)) map.removeLayer(id);
  });

  if (map.getSource(LANDMARK_LAYER_IDS.SRC)) {
    map.removeSource(LANDMARK_LAYER_IDS.SRC);
  }
}
