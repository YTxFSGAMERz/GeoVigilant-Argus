/**
 * ARGUS GroundView — Satellite Basemap Definition
 * High-resolution ESRI World Imagery raster base with vector labels & Arabic place names patch.
 */
export function getSatelliteStyleUrl() {
  return `/api/groundview/map-style?theme=satellite&t=${Date.now()}`;
}
