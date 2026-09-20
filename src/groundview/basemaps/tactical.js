/**
 * ARGUS GroundView — Dark Tactical Basemap Definition
 * Signature ARGUS Dark Matter vector style with Palestine/Arabic place names patch.
 */
export function getTacticalStyleUrl() {
  return `/api/groundview/map-style?theme=tactical&t=${Date.now()}`;
}
