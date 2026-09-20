/**
 * ARGUS GroundView — Basemap Manager
 *
 * Orchestrates switching between:
 *   - 'tactical'  (Dark Matter + Cyberpunk overlay)
 *   - 'streets'   (CartoDB Streets / Voyager)
 *   - 'satellite' (ESRI World Imagery + vector labels)
 *
 * Guarantees that all active ARGUS intelligence layers & overlays
 * (Nodes, Anomalies, Incidents, Streetscapes) are preserved across transitions.
 */

import { getTacticalStyleUrl } from './tactical.js';
import { getStreetsStyleUrl } from './streets.js';
import { getSatelliteStyleUrl } from './satellite.js';

export class BasemapManager {
  /**
   * @param {import('maplibre-gl').Map} map
   * @param {Function} onStyleReplacedCallback — invoked after new style loads to re-register overlays
   */
  constructor(map, onStyleReplacedCallback) {
    this.map = map;
    this.currentMode = 'tactical';
    this.onStyleReplaced = onStyleReplacedCallback;
    this._switching = false;
  }

  /**
   * Returns the style URL for a given basemap mode.
   * @param {'tactical'|'streets'|'satellite'} mode
   * @returns {string}
   */
  getStyleUrl(mode) {
    switch (mode) {
      case 'streets':
        return getStreetsStyleUrl();
      case 'satellite':
        return getSatelliteStyleUrl();
      case 'tactical':
      default:
        return getTacticalStyleUrl();
    }
  }

  /**
   * Switches the active basemap mode.
   * @param {'tactical'|'streets'|'satellite'} mode
   * @returns {Promise<void>}
   */
  async setMode(mode) {
    if (!this.map || this.currentMode === mode || this._switching) return;
    this._switching = true;
    this.currentMode = mode;

    const styleUrl = this.getStyleUrl(mode);
    console.log(`[BasemapManager] Switching to ${mode.toUpperCase()} basemap:`, styleUrl);

    this.map.setStyle(styleUrl);

    return new Promise((resolve) => {
      this.map.once('style.load', () => {
        console.log(`[BasemapManager] ${mode.toUpperCase()} style loaded — restoring intelligence overlays`);
        if (typeof this.onStyleReplaced === 'function') {
          this.onStyleReplaced();
        }
        this._switching = false;
        resolve();
      });
    });
  }

  getCurrentMode() {
    return this.currentMode;
  }
}
