/**
 * ARGUS GroundView — Streets Basemap Definition
 * CartoDB Voyager / Streets vector style with Palestine/Arabic place names patch.
 */
export function getStreetsStyleUrl() {
  return `/api/groundview/map-style?theme=streets&t=${Date.now()}`;
}
