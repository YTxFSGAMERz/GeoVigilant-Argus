// src/services/mock.js

export class MockService {
    /**
     * Authentic PANOPTIC HUD Detection
     * Scans real entities currently rendered in the active Cesium viewport
     * (flights, vessels, satellites, surveillance cameras, military contacts, argus nodes)
     * and projects their 3D coordinates to window HUD space.
     */
    static generateDetections(globeOrLat, centerLatOrLon, radiusKm = 10, count = 8) {
        // Resolve globe and viewer references
        let globe = null;
        let viewer = null;

        if (globeOrLat && typeof globeOrLat === 'object' && (globeOrLat.viewer || globeOrLat.dataSources)) {
            globe = globeOrLat;
            viewer = globe.viewer;
        } else if (typeof window !== 'undefined') {
            globe = window.globe;
            viewer = window.viewer || (globe ? globe.viewer : null);
        }

        if (!viewer || !viewer.scene || !globe || !globe.dataSources) {
            return [];
        }

        const scene = viewer.scene;
        const width = window.innerWidth;
        const height = window.innerHeight;
        const time = viewer.clock ? viewer.clock.currentTime : (typeof Cesium !== 'undefined' ? Cesium.JulianDate.now() : null);

        const detections = [];
        const checkedLayers = [
            { id: 'flights', category: 'AIRCRAFT' },
            { id: 'vessels', category: 'MARITIME VESSEL' },
            { id: 'satellites', category: 'ORBITAL ASSET' },
            { id: 'cctv', category: 'SURVEILLANCE CAM' },
            { id: 'military', category: 'MILITARY FACILITY' },
            { id: 'argusNodes', category: 'ARGUS SENSOR NODE' }
        ];

        // Search through visible entities in each active data source
        for (const layer of checkedLayers) {
            const ds = globe.dataSources[layer.id];
            if (!ds || ds.show === false) continue;

            const entities = ds.entities ? ds.entities.values : [];
            for (let i = 0; i < entities.length; i++) {
                const entity = entities[i];
                if (!entity || entity.show === false) continue;

                let cartesian = null;
                if (entity.position) {
                    cartesian = typeof entity.position.getValue === 'function' 
                        ? entity.position.getValue(time) 
                        : entity.position;
                }

                if (!cartesian || typeof Cesium === 'undefined' || !Cesium.Cartesian3) continue;

                // Project 3D cartesian coordinates to 2D window coordinates
                let windowCoord = null;
                try {
                    windowCoord = Cesium.SceneTransforms.wgs84ToWindowCoordinates(scene, cartesian);
                } catch {
                    continue;
                }

                if (!windowCoord) continue;

                // Ensure coordinate is within screen bounds with comfortable margin
                if (windowCoord.x >= 60 && windowCoord.x <= width - 60 &&
                    windowCoord.y >= 60 && windowCoord.y <= height - 60) {

                    // Extract authentic properties
                    let name = entity.name || entity.id;
                    let confidence = 0.98;

                    if (entity.properties) {
                        const callsign = entity.properties.callsign ? (entity.properties.callsign.getValue ? entity.properties.callsign.getValue() : entity.properties.callsign) : null;
                        const trust = entity.properties.trustScore ? (entity.properties.trustScore.getValue ? entity.properties.trustScore.getValue() : entity.properties.trustScore) : null;
                        if (callsign) name = callsign;
                        if (trust) {
                            const parsedTrust = parseFloat(trust);
                            if (!isNaN(parsedTrust)) confidence = Math.min(0.99, Math.max(0.60, parsedTrust / 100));
                        }
                    }

                    // Extract lat/lon for metadata
                    let lat = 0, lon = 0;
                    try {
                        const carto = Cesium.Cartographic.fromCartesian(cartesian);
                        lat = Cesium.Math.toDegrees(carto.latitude);
                        lon = Cesium.Math.toDegrees(carto.longitude);
                    } catch {}

                    const boxW = 54;
                    const boxH = 54;

                    detections.push({
                        id: entity.id,
                        category: layer.category,
                        name: String(name).slice(0, 24),
                        confidence: confidence.toFixed(2),
                        latitude: lat,
                        longitude: lon,
                        x: Math.round(windowCoord.x - boxW / 2),
                        y: Math.round(windowCoord.y - boxH / 2),
                        width: boxW,
                        height: boxH
                    });

                    if (detections.length >= count) break;
                }
            }
            if (detections.length >= count) break;
        }

        return detections;
    }

    // Renders the real detection boxes on the DOM over the Cesium canvas
    static renderDetectionsUI(detections) {
        let container = document.getElementById('panoptic-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'panoptic-container';
            container.style.position = 'absolute';
            container.style.top = '0';
            container.style.left = '0';
            container.style.width = '100%';
            container.style.height = '100%';
            container.style.pointerEvents = 'none';
            container.style.zIndex = '5';
            const uiLayer = document.getElementById('ui-layer');
            if (uiLayer) {
                uiLayer.appendChild(container);
            } else {
                document.body.appendChild(container);
            }
        }

        container.innerHTML = ''; // Clear old

        // Add Scanline
        const scanline = document.createElement('div');
        scanline.className = 'panoptic-scanline';
        container.appendChild(scanline);

        detections.forEach(det => {
            const box = document.createElement('div');
            box.className = 'ai-target-box';
            box.style.left = `${det.x}px`;
            box.style.top = `${det.y}px`;
            box.style.width = `${det.width}px`;
            box.style.height = `${det.height}px`;

            const label = document.createElement('div');
            label.className = 'ai-target-label';
            const labelText = det.name ? `${det.category}: ${det.name}` : det.category;
            label.textContent = `${labelText} [${(det.confidence * 100).toFixed(0)}%]`;

            box.appendChild(label);
            container.appendChild(box);
        });
    }

    static clearDetectionsUI() {
        const container = document.getElementById('panoptic-container');
        if (container) {
            container.innerHTML = '';
        }
    }
}
