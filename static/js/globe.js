export const RADAR_HUBS = {
    'Europe': { lat: 51.5074, lon: -0.1278, name: 'London / Europe Hub', zoomAlt: 1500000 },
    'North America': { lat: 40.7128, lon: -74.0060, name: 'JFK / Americas Hub', zoomAlt: 1500000 },
    'Middle East': { lat: 25.2048, lon: 55.2708, name: 'Dubai / Mid East Hub', zoomAlt: 1500000 },
    'East Asia': { lat: 35.6762, lon: 139.6503, name: 'Tokyo / East Asia Hub', zoomAlt: 1500000 },
    'South Asia': { lat: 28.6139, lon: 77.2090, name: 'Delhi / South Asia Hub', zoomAlt: 1500000 },
    'Global': { lat: 20.0, lon: 0.0, name: 'Global Center', zoomAlt: 18000000 }
};

export class Terra5Globe {
    constructor(containerId) {
        this.viewer = null;
        this.dataSources = {};
        this.currentMode = 'normal';
        this.containerId = containerId;
        this.onCameraChange = null;
        this.onEntityClick = null;
        this.pinBuilder = new Cesium.PinBuilder();
        this._iconCache = {};
        this._aircraftCache = {};
        this._activeEffects = {}; // Track post-process stages
        this._lastFlightsData = [];
        this._airRadar = {
            enabled: false,
            sweepEnabled: true,
            stemsEnabled: true,
            groundEchoesEnabled: true,
            vectorsEnabled: true,
            rangeRingsEnabled: true,
            altScale: 3,
            activeHub: 'Europe',
            centerLat: 51.5074,
            centerLon: -0.1278,
            sweepAngle: 0,
            chaseEntity: null,
            animFrame: null,
            lockedFlight: null
        };
    }

    // Render an emoji onto a canvas and return as data URL for billboard use
    _makeIcon(emoji, size = 48) {
        const key = `${emoji}-${size}`;
        if (this._iconCache[key]) return this._iconCache[key];
        const canvas = document.createElement('canvas');
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, size, size);
        ctx.font = `${Math.floor(size * 0.75)}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(emoji, size / 2, size / 2 + 2);
        const dataUrl = canvas.toDataURL();
        this._iconCache[key] = dataUrl;
        return dataUrl;
    }

    init() {
        this.viewer = new Cesium.Viewer(this.containerId, {
            baseLayerPicker: false,
            geocoder: false,
            homeButton: false,
            sceneModePicker: false,
            navigationHelpButton: false,
            animation: false,
            timeline: false,
            fullscreenButton: false,
            vrButton: false,
            selectionIndicator: false,
            infoBox: false,
            shouldAnimate: false, // Performance: Disable default animation loop
            skyBox: false,
            requestRenderMode: true, // Performance: Only render when something changes
            maximumRenderTimeChange: Infinity,
            baseLayer: Cesium.ImageryLayer.fromProviderAsync(Cesium.ArcGisMapServerImageryProvider.fromUrl('https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer', {
                enablePickFeatures: false
            })),
            skyAtmosphere: new Cesium.SkyAtmosphere(),
            contextOptions: {
                webgl: {
                    powerPreference: 'high-performance', // Explicitly request dedicated NVIDIA GPU
                    preserveDrawingBuffer: false,
                    failIfMajorPerformanceCaveat: false
                }
            }
        });

        // Summer Thermal & Performance Optimization:
        // Cap frame rate to 30 FPS by default to avoid burning the GPU at 144Hz/165Hz
        this.viewer.targetFrameRate = 30;

        // Prevent high-DPI supersampling that overloads mobile/laptop GPUs
        const dpr = window.devicePixelRatio || 1;
        this.viewer.resolutionScale = Math.min(1.0, 1.0 / (dpr > 1.2 ? 1.25 : 1.0));

        // Optimization: Disable some heavy features
        this.viewer.scene.globe.showGroundAtmosphere = false;
        this.viewer.scene.globe.enableLighting = false;
        this.viewer.scene.globe.maximumScreenSpaceError = 2.5; // Efficient geometry budget
        this.viewer.scene.highDynamicRange = false;
        this.viewer.scene.postProcessStages.fxaa.enabled = false; // Disable AA for performance

        // Camera Stability: Eliminate momentum / drifting inertia so map stops dead on mouse release
        if (this.viewer.scene.screenSpaceCameraController) {
            this.viewer.scene.screenSpaceCameraController.inertiaSpin = 0.0;
            this.viewer.scene.screenSpaceCameraController.inertiaTranslate = 0.0;
            this.viewer.scene.screenSpaceCameraController.inertiaZoom = 0.0;
        }

        // Disable double-click auto-fly
        if (this.viewer.screenSpaceEventHandler) {
            this.viewer.screenSpaceEventHandler.removeInputAction(Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);
        }

        // Dark styling
        this.viewer.scene.backgroundColor = Cesium.Color.fromCssColorString('#0a0a0a');
        this.viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString('#0a0a0a');
        this.viewer.scene.fog.enabled = true;
        this.viewer.scene.fog.density = 0.0001;

        if (this.viewer.scene.skyAtmosphere) {
            this.viewer.scene.skyAtmosphere.brightnessShift = -0.3;
            this.viewer.scene.skyAtmosphere.saturationShift = -0.5;
        }

        // Render Error Resilience & Recovery
        this.viewer.scene.rethrowRenderErrors = false;
        this.viewer.scene.renderError.addEventListener((scene, error) => {
            console.warn('[Cesium] Suppressed render error & recovering:', error?.message || error);
            setTimeout(() => {
                if (this.viewer && this.viewer.scene && !this.viewer.isDestroyed()) {
                    this.viewer.scene.requestRender();
                }
            }, 50);
        });

        // Terrain & Memory Safeguards: strictly cap tile cache & disable recursive pyramid preloading
        this.viewer.scene.globe.depthTestAgainstTerrain = false;
        this.viewer.scene.globe.tileCacheSize = 50;
        this.viewer.scene.globe.maximumMemoryUsage = 96; // Hard cap on tile/texture RAM to prevent browser bloat
        this.viewer.scene.globe.preloadAncestors = false;
        this.viewer.scene.globe.preloadSiblings = false;

        // Initialize Data Sources
        this.dataSources.flights = new Cesium.CustomDataSource('flights');
        this.dataSources.vessels = new Cesium.CustomDataSource('vessels');
        this.dataSources.satellites = new Cesium.CustomDataSource('satellites');
        this.dataSources.earthquakes = new Cesium.CustomDataSource('earthquakes');
        this.dataSources.weather = new Cesium.CustomDataSource('weather');
        this.dataSources.cctv = new Cesium.CustomDataSource('cctv');
        this.dataSources.nuclear = new Cesium.CustomDataSource('nuclear');
        this.dataSources.military = new Cesium.CustomDataSource('military');
        this.dataSources.conflicts = new Cesium.CustomDataSource('conflicts');
        this.dataSources.waterways = new Cesium.CustomDataSource('waterways');
        this.dataSources.hotspots = new Cesium.CustomDataSource('hotspots');
        this.dataSources.cables = new Cesium.CustomDataSource('cables');
        this.dataSources.naturalEvents = new Cesium.CustomDataSource('naturalEvents');
        this.dataSources.wildfires = new Cesium.CustomDataSource('wildfires');
        this.dataSources.weatherAlerts = new Cesium.CustomDataSource('weatherAlerts');
        this.dataSources.spaceports = new Cesium.CustomDataSource('spaceports');
        this.dataSources.economic = new Cesium.CustomDataSource('economic');

        this.dataSources.celltowers = new Cesium.CustomDataSource('celltowers');
        this.dataSources.argusNodes = new Cesium.CustomDataSource('argusNodes');
        this.dataSources.argusIncidents = new Cesium.CustomDataSource('argusIncidents');
        this.dataSources.argusLandmarks = new Cesium.CustomDataSource('argusLandmarks');
        this.dataSources.airRadar = new Cesium.CustomDataSource('airRadar');

        Object.values(this.dataSources).forEach(ds => {
            this.viewer.dataSources.add(ds);
        });

        // Camera Tracking & Smooth Window Sync (Throttled, 0% CPU when stationary)
        this.viewer.camera.percentageChanged = 0.005;
        this.onCameraMoveContinuous = null;
        let cameraSyncTimer = null;

        this.viewer.camera.changed.addEventListener(() => {
            if (this.onCameraChange) {
                const cartographic = this.viewer.camera.positionCartographic;
                this.onCameraChange({
                    latitude: Cesium.Math.toDegrees(cartographic.latitude),
                    longitude: Cesium.Math.toDegrees(cartographic.longitude),
                    altitude: cartographic.height,
                    heading: Cesium.Math.toDegrees(this.viewer.camera.heading)
                });
            }
            if (typeof this.onCameraMoveContinuous === 'function') {
                if (!cameraSyncTimer) {
                    cameraSyncTimer = setTimeout(() => {
                        cameraSyncTimer = null;
                        if (typeof this.onCameraMoveContinuous === 'function') {
                            this.onCameraMoveContinuous();
                        }
                    }, 160); // 160ms clean throttle during camera interaction, ZERO calls when still
                }
            }
        });

        // Entity Clicking
        this.viewer.screenSpaceEventHandler.setInputAction((click) => {
            const pickedObject = this.viewer.scene.pick(click.position);
            if (Cesium.defined(pickedObject) && pickedObject.id && this.onEntityClick) {
                let entity = pickedObject.id;
                // If user clicked stem, echo, or vector, resolve back to parent flight entity
                if (typeof entity.id === 'string' && (entity.id.startsWith('stem-') || entity.id.startsWith('echo-') || entity.id.startsWith('vec-'))) {
                    const fltId = entity.id.replace(/^(stem|echo|vec)-/, '');
                    const fltEntity = this.dataSources.flights?.entities.getById(fltId);
                    if (fltEntity) entity = fltEntity;
                }
                if (entity.properties) {
                    const props = {};
                    entity.properties.propertyNames.forEach(name => {
                        props[name] = entity.properties[name].getValue();
                    });
                    this.onEntityClick(props);
                }
            } else if (this.onMapClick) {
                const cartesian = this.viewer.camera.pickEllipsoid(click.position, this.viewer.scene.globe.ellipsoid);
                if (cartesian) {
                    const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
                    this.onMapClick({
                        latitude: Cesium.Math.toDegrees(cartographic.latitude),
                        longitude: Cesium.Math.toDegrees(cartographic.longitude)
                    });
                }
            }
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

        // Mouse Hover
        this.viewer.screenSpaceEventHandler.setInputAction((movement) => {
            if (this.onMouseMove) {
                const cartesian = this.viewer.camera.pickEllipsoid(movement.endPosition, this.viewer.scene.globe.ellipsoid);
                if (cartesian) {
                    const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
                    this.onMouseMove({
                        latitude: Cesium.Math.toDegrees(cartographic.latitude),
                        longitude: Cesium.Math.toDegrees(cartographic.longitude)
                    });
                }
            }
        }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);

        // Initial view (Washington DC)
        this.viewer.camera.setView({
            destination: Cesium.Cartesian3.fromDegrees(-77.0369, 38.9072, 10000000)
        });

        console.log('Terra5 Globe initialized');
    }

    setEcoMode(enabled) {
        if (!this.viewer) return;
        this._ecoMode = enabled;
        if (enabled) {
            this.viewer.targetFrameRate = 30;
            const dpr = window.devicePixelRatio || 1;
            this.viewer.resolutionScale = Math.min(0.85, 0.85 / (dpr > 1.2 ? 1.25 : 1.0));
            if (this.viewer.scene.globe) {
                this.viewer.scene.globe.maximumScreenSpaceError = 3.0;
                this.viewer.scene.globe.tileCacheSize = 80;
                this.viewer.scene.globe.maximumMemoryUsage = 96;
            }
        } else {
            this.viewer.targetFrameRate = 60;
            this.viewer.resolutionScale = 1.0;
            if (this.viewer.scene.globe) {
                this.viewer.scene.globe.maximumScreenSpaceError = 2.0;
                this.viewer.scene.globe.tileCacheSize = 120;
                this.viewer.scene.globe.maximumMemoryUsage = 192;
            }
        }
        this.viewer.scene.requestRender();
    }

    pruneMemory() {
        if (!this.viewer || !this.viewer.scene) return;
        try {
            if (this.viewer.scene.globe && typeof this.viewer.scene.globe.clearTileCache === 'function') {
                this.viewer.scene.globe.clearTileCache();
            }
            if (Object.keys(this._iconCache).length > 150) {
                this._iconCache = {};
            }
            if (Object.keys(this._aircraftCache).length > 250) {
                this._aircraftCache = {};
            }
            console.log('[Cesium] Globe memory pruned & tile cache trimmed');
        } catch (e) {
            console.warn('[Cesium] Prune memory error:', e);
        }
    }

    cancelFlight() {
        if (this.viewer && this.viewer.camera) {
            this.viewer.camera.cancelFlight();
        }
        if (this.viewer) {
            this.viewer.trackedEntity = undefined;
        }
    }

    flyTo(lat, lon, alt, duration = 2.0) {
        if (!this.viewer || !Number.isFinite(lat) || !Number.isFinite(lon) || !Number.isFinite(alt)) {
             console.warn("[PERSISTENCE] Invalid flyTo coordinates rejected:", { lat, lon, alt });
             return;
        }

        this.viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(lon, lat, alt),
            duration: duration,
            easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT
        });
    }

    // --- Data Updates ---
    updateFlights(flights) {
        if (!this.viewer) return;
        this._lastFlightsData = flights || [];
        const ds = this.dataSources.flights;
        const radarDs = this.dataSources.airRadar;
        const currentIds = new Set();
        const currentRadarIds = new Set();

        const isRadar = !!(this._airRadar && this._airRadar.enabled);
        const altScale = isRadar ? (this._airRadar.altScale || 3) : 1;
        const stemsOn = isRadar && this._airRadar.stemsEnabled;
        const echoesOn = isRadar && this._airRadar.groundEchoesEnabled;
        const vectorsOn = isRadar && this._airRadar.vectorsEnabled;

        const flightList = (flights || []).slice(0, 1000);
        flightList.forEach(f => {
            const lon = f.longitude ?? f.long ?? f.lon;
            const lat = f.latitude ?? f.lat;
            let rawAlt = f.altitude ?? f.alt ?? 10000;
            if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;

            rawAlt = typeof rawAlt === 'number' ? rawAlt : (parseFloat(rawAlt) || 10000);
            // ADS-B alt is in feet (0 - 45000 ft). Convert to meters: 1 ft = 0.3048 m
            const altMeters = rawAlt * 0.3048;
            const displayAlt = isRadar ? Math.max(800, altMeters * altScale) : (rawAlt > 1000 ? rawAlt : 10000);

            const id = f.icao24 || f.hex || `flt-${lat}-${lon}`;
            currentIds.add(id);
            const position = Cesium.Cartesian3.fromDegrees(lon, lat, displayAlt);
            const groundPos = Cesium.Cartesian3.fromDegrees(lon, lat, 0);

            const isMil = f.type === 'military';
            const isEmergency = f.type === 'emergency';
            const isPriv = f.type === 'private';
            const colorHex = isEmergency ? '#ff3333' : isMil ? '#ffaa00' : isPriv ? '#38bdf8' : '#00d4aa';
            const cesiumColor = Cesium.Color.fromCssColorString(colorHex);

            let entity = ds.entities.getById(id);
            if (entity) {
                entity.position = position;
                if (entity.billboard) {
                    entity.billboard.rotation = Cesium.Math.toRadians(f.heading || 0);
                }
                if (entity.properties) {
                    entity.properties.altitude = Math.round(rawAlt);
                    entity.properties.displayAltitude = Math.round(displayAlt);
                    entity.properties.velocity = Math.round(f.velocity || 0);
                    entity.properties.heading = Math.round(f.heading || 0);
                    entity.properties.squawk = f.squawk || '----';
                }
            } else {
                entity = ds.entities.add({
                    id: id,
                    name: f.callsign || id,
                    position: position,
                    billboard: {
                        image: this._createAircraftSVG(f.heading, colorHex),
                        width: 36,
                        height: 36,
                        verticalOrigin: Cesium.VerticalOrigin.CENTER,
                        horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
                        scaleByDistance: new Cesium.NearFarScalar(500000, 1.2, 1.2e7, 0.6)
                    },
                    properties: {
                        icao24:        id,
                        callsign:      f.callsign || id,
                        registration:  f.registration || '---',
                        aircraft_type: f.aircraft_type || '---',
                        type:          f.type || 'commercial',
                        altitude:      Math.round(rawAlt),
                        displayAltitude: Math.round(displayAlt),
                        velocity:      Math.round(f.velocity || 0),
                        heading:       Math.round(f.heading || 0),
                        squawk:        f.squawk || '----',
                        lat:           lat,
                        lon:           lon
                    }
                });
            }

            // ─── 3D AIR RADAR OVERLAYS ───
            if (isRadar && radarDs) {
                // 1. Vertical 3D Drop Stem
                const stemId = `stem-${id}`;
                currentRadarIds.add(stemId);
                let stemEntity = radarDs.entities.getById(stemId);
                if (stemEntity) {
                    stemEntity.show = stemsOn;
                    stemEntity.polyline.positions = [groundPos, position];
                } else if (stemsOn) {
                    radarDs.entities.add({
                        id: stemId,
                        show: stemsOn,
                        polyline: {
                            positions: [groundPos, position],
                            width: 1.5,
                            material: new Cesium.PolylineGlowMaterialProperty({
                                glowPower: 0.2,
                                color: cesiumColor.withAlpha(0.65)
                            })
                        }
                    });
                }

                // 2. Ground Echo Footprint
                const echoId = `echo-${id}`;
                currentRadarIds.add(echoId);
                let echoEntity = radarDs.entities.getById(echoId);
                if (echoEntity) {
                    echoEntity.show = echoesOn;
                    echoEntity.position = groundPos;
                } else if (echoesOn) {
                    radarDs.entities.add({
                        id: echoId,
                        show: echoesOn,
                        position: groundPos,
                        point: {
                            pixelSize: 6,
                            color: cesiumColor.withAlpha(0.7),
                            outlineColor: Cesium.Color.BLACK,
                            outlineWidth: 1.5
                        }
                    });
                }

                // 3. Lookahead Velocity Vector
                const vecId = `vec-${id}`;
                currentRadarIds.add(vecId);
                const headingDeg = f.heading || 0;
                const headingRad = Cesium.Math.toRadians(headingDeg);
                const speedKmh = f.velocity || 250;
                const lookaheadMeters = Math.max(4000, (speedKmh * (1000 / 3600)) * 60);
                const cosLat = Math.max(0.1, Math.cos(Cesium.Math.toRadians(lat)));
                const dLat = (lookaheadMeters * Math.cos(headingRad)) / 111320;
                const dLon = (lookaheadMeters * Math.sin(headingRad)) / (111320 * cosLat);
                const aheadPos = Cesium.Cartesian3.fromDegrees(lon + dLon, lat + dLat, displayAlt);

                let vecEntity = radarDs.entities.getById(vecId);
                if (vecEntity) {
                    vecEntity.show = vectorsOn;
                    vecEntity.polyline.positions = [position, aheadPos];
                } else if (vectorsOn) {
                    radarDs.entities.add({
                        id: vecId,
                        show: vectorsOn,
                        polyline: {
                            positions: [position, aheadPos],
                            width: 2,
                            material: new Cesium.PolylineDashMaterialProperty({
                                color: cesiumColor.withAlpha(0.85),
                                dashLength: 10
                            })
                        }
                    });
                }
            }
        });

        // Prune removed flights
        const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
        toRemove.forEach(e => ds.entities.remove(e));

        // Prune removed radar stem/echo/vec entities
        if (radarDs) {
            const toRemoveRadar = radarDs.entities.values.filter(e =>
                (e.id.startsWith('stem-') || e.id.startsWith('echo-') || e.id.startsWith('vec-')) &&
                !currentRadarIds.has(e.id)
            );
            toRemoveRadar.forEach(e => radarDs.entities.remove(e));
        }

        this.viewer.scene.requestRender();
    }

    updateVessels(vessels) {
        if (!this.viewer) return;
        const ds = this.dataSources.vessels;
        if (!ds) return;
        const currentIds = new Set();

        const vesselList = (vessels || []).slice(0, 600);
        vesselList.forEach(v => {
            const lon = v.longitude ?? v.lon;
            const lat = v.latitude ?? v.lat;
            if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;
            const id = `vessel-${v.mmsi}`;
            currentIds.add(id);
            const position = Cesium.Cartesian3.fromDegrees(lon, lat);

            let entity = ds.entities.getById(id);
            if (entity) {
                entity.position = position;
            } else {
                ds.entities.add({
                    id: id,
                    name: v.name || `VESSEL-${v.mmsi}`,
                    position: position,
                    billboard: {
                        image: this._createVesselSVG(),
                        width:  28,
                        height: 42,
                        verticalOrigin: Cesium.VerticalOrigin.CENTER,
                        horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
                        scaleByDistance: new Cesium.NearFarScalar(500000, 1.2, 8e6, 0.6)
                    },
                    properties: {
                        mmsi:        v.mmsi,
                        name:        v.name || `VESSEL-${v.mmsi}`,
                        callsign:    v.callsign || '---',
                        type:        v.type || 'cargo',
                        flag:        v.country || v.flag || '---',
                        country:     v.country || v.flag || '---',
                        speed:       v.speed || 0,
                        heading:     v.heading || 0,
                        status:      v.status || 'UNDERWAY',
                        destination: v.destination || v.arrival || '---',
                        imo:         v.imo || '---',
                        draft:       v.draft || 0
                    }
                });
            }
        });

        const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
        toRemove.forEach(e => ds.entities.remove(e));

        this.viewer.scene.requestRender();
    }

    updateCellTowers(towers) {
        if (!this.viewer) return;
        const ds = this.dataSources.celltowers;
        const currentIds = new Set();
        const icon = this._createCellTowerSVG('#00ffaa');

        towers.forEach(tower => {
            if (!Number.isFinite(tower.lon) || !Number.isFinite(tower.lat)) return;
            const id = `cell-${tower.radio}-${tower.mcc}-${tower.mnc}-${tower.lac}-${tower.cell}`;
            currentIds.add(id);
            const position = Cesium.Cartesian3.fromDegrees(tower.lon, tower.lat, 0);

            let entity = ds.entities.getById(id);
            if (entity) {
                entity.position = position;
            } else {
                ds.entities.add({
                    id: id,
                    position: position,
                    billboard: {
                        image: icon,
                        width: 18,
                        height: 18,
                        verticalOrigin: Cesium.VerticalOrigin.CENTER,
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 10000000)
                    },
                    properties: {
                        name: `CELL TOWER - ${tower.net || tower.radio}`,
                        type: tower.radio,
                        ...tower
                    }
                });
            }
        });

        const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
        toRemove.forEach(e => ds.entities.remove(e));
        this.viewer.scene.requestRender();
    }

    updateSatellites(satellites) {
        if (!this.viewer) return;
        const ds = this.dataSources.satellites;
        const currentIds = new Set();

        satellites.forEach(s => {
            const lon = s.longitude ?? s.lon;
            const lat = s.latitude ?? s.lat;
            const rawAlt = s.altitude ?? s.alt;
            const alt = rawAlt != null ? (rawAlt < 20000 ? rawAlt * 1000 : rawAlt) : 550000;
            if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;
            const id = String(s.noradId || s.id || `sat-${lat}-${lon}`);
            currentIds.add(id);
            const pos = Cesium.Cartesian3.fromDegrees(lon, lat, alt);

            let entity = ds.entities.getById(id);
            if (entity) {
                entity.position = pos;
            } else {
                ds.entities.add({
                    id: id,
                    name: s.name || `SAT-${id}`,
                    position: pos,
                    billboard: {
                        image: this._createSatelliteSVG(),
                        width: 36,
                        height: 24,
                        verticalOrigin: Cesium.VerticalOrigin.CENTER,
                        horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
                        scaleByDistance: new Cesium.NearFarScalar(500000, 1.2, 1.5e7, 0.6)
                    },
                    label: {
                        text: s.name || `SAT-${id}`,
                        font: '9px monospace',
                        fillColor: Cesium.Color.fromCssColorString('#00d4aa'),
                        outlineColor: Cesium.Color.BLACK,
                        outlineWidth: 2,
                        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                        pixelOffset: new Cesium.Cartesian2(0, -10),
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 12000000)
                    },
                    properties: {
                        noradId:     id,
                        name:        s.name || `SAT-${id}`,
                        altitude:    Math.round(alt / 1000),
                        inclination: s.inclination || 'N/A',
                        period_min:  s.period_min || 'N/A'
                    }
                });
            }
        });

        const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
        toRemove.forEach(e => ds.entities.remove(e));

        this.viewer.scene.requestRender();
    }

    updateEarthquakes(earthquakes) {
        if (!this.viewer) return;
        const ds = this.dataSources.earthquakes;
        ds.entities.suspendEvents();
        try {
            const currentIds = new Set();

            earthquakes.forEach(e => {
                const lon = e.longitude ?? e.lon;
                const lat = e.latitude ?? e.lat;
                if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;
                const id = String(e.id || `eq-${lat}-${lon}`);
                currentIds.add(id);

                const mag = Math.max(0.1, Number(e.magnitude) || 1.0);
                const colorHex = mag >= 6.0 ? '#ff1133' : 
                                 mag >= 4.5 ? '#ff7700' : 
                                 mag >= 2.5 ? '#ffcc00' : 
                                 '#00ffaa';
                const color = Cesium.Color.fromCssColorString(colorHex);
                const icon = this._createSeismicSVG(mag, colorHex);
                const size = mag >= 6.0 ? 30 : mag >= 4.5 ? 24 : mag >= 3.0 ? 18 : 14;
                const maxDistance = mag >= 4.5 ? 25000000 : mag >= 2.5 ? 8000000 : 3000000;

                const position = Cesium.Cartesian3.fromDegrees(lon, lat, 100);

                let entity = ds.entities.getById(id);
                if (entity) {
                    entity.position = position;
                    if (entity.billboard) {
                        entity.billboard.image = icon;
                    }
                } else {
                    const entityConfig = {
                        id: id,
                        name: `M${mag.toFixed(1)} - ${e.place || 'Seismic Event'}`,
                        position: position,
                        billboard: {
                            image: icon,
                            width: size,
                            height: size,
                            verticalOrigin: Cesium.VerticalOrigin.CENTER,
                            horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
                            distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, maxDistance)
                        },
                        properties: {
                            magnitude: mag.toFixed(1),
                            place:     e.place || 'Unknown',
                            depth:     e.depth ? `${e.depth} km` : 'N/A',
                            time:      e.time || Date.now(),
                            id:        id
                        }
                    };

                    if (mag >= 5.0) {
                        const radiusMeters = Math.min(400000, Math.max(30000, mag * 30000));
                        entityConfig.ellipse = {
                            semiMinorAxis: radiusMeters,
                            semiMajorAxis: radiusMeters,
                            material: color.withAlpha(0.12),
                            height: 0
                        };
                    }

                    ds.entities.add(entityConfig);
                }
            });

            const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
            toRemove.forEach(e => ds.entities.remove(e));
        } finally {
            ds.entities.resumeEvents();
        }

        this.viewer.scene.requestRender();
    }

    updateNaturalEvents(events) {
        if (!this.viewer) return;
        const ds = this.dataSources.naturalEvents;
        const currentIds = new Set();
        const icon = this._createNaturalEventSVG('global', '#ff8800');

        events.forEach(ev => {
            if (!Number.isFinite(ev.latitude) || !Number.isFinite(ev.longitude)) return;
            const id = `ev-${ev.id}`;
            currentIds.add(id);
            const position = Cesium.Cartesian3.fromDegrees(ev.longitude, ev.latitude);

            let entity = ds.entities.getById(id);
            if (entity) {
                entity.position = position;
            } else {
                ds.entities.add({
                    id: id,
                    name: ev.title,
                    position: position,
                    billboard: {
                        image: icon, width: 22, height: 22,
                        verticalOrigin: Cesium.VerticalOrigin.CENTER,
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 15000000)
                    },
                    label: {
                        text: ev.title.slice(0, 20), font: '10px monospace',
                        fillColor: Cesium.Color.WHITE, outlineWidth: 2,
                        pixelOffset: new Cesium.Cartesian2(0, 15),
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 5000000)
                    },
                    properties: ev
                });
            }
        });

        const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
        toRemove.forEach(e => ds.entities.remove(e));
        this.viewer.scene.requestRender();
    }

    updateWildfires(fires) {
        if (!this.viewer) return;
        const ds = this.dataSources.wildfires;
        ds.entities.suspendEvents();
        const currentIds = new Set();

        fires.forEach((f, i) => {
            if (!Number.isFinite(f.latitude) || !Number.isFinite(f.longitude)) return;
            // Use lat+lon+date as a stable ID for FIRMS rows
            const id = `fire-${f.acq_date || ''}-${f.latitude.toFixed(3)}-${f.longitude.toFixed(3)}-${i}`;
            currentIds.add(id);
            const position = Cesium.Cartesian3.fromDegrees(f.longitude, f.latitude);

            // Real FRP-based coloring: megawatts from NASA VIIRS
            const frp = Number(f.frp) || 0;
            const brightness = Number(f.brightness) || 300;
            let colorHex, sizeW;
            if (frp >= 1000 || brightness >= 500) {
                colorHex = '#ff0044'; sizeW = 28; // Extreme (wildfire mega-complex)
            } else if (frp >= 300 || brightness >= 450) {
                colorHex = '#ff3300'; sizeW = 22; // Very high
            } else if (frp >= 100 || brightness >= 420) {
                colorHex = '#ff7700'; sizeW = 18; // High
            } else if (frp >= 30 || brightness >= 380) {
                colorHex = '#ffaa00'; sizeW = 14; // Medium
            } else {
                colorHex = '#ff4400'; sizeW = 11; // Low/agricultural burn
            }
            const icon = this._createThermalSVG(colorHex);

            let entity = ds.entities.getById(id);
            if (entity) {
                entity.position = position;
                if (entity.billboard) { entity.billboard.image = icon; entity.billboard.width = sizeW; entity.billboard.height = sizeW; }
            } else {
                ds.entities.add({
                    id: id,
                    name: `🔥 Fire — FRP: ${frp.toFixed(0)} MW${f.confidence ? ' | Conf: ' + f.confidence : ''}`,
                    position: position,
                    billboard: {
                        image: icon, width: sizeW, height: sizeW,
                        verticalOrigin: Cesium.VerticalOrigin.CENTER,
                        horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 12000000)
                    },
                    properties: {
                        frp: frp,
                        brightness: brightness,
                        satellite: f.satellite || 'SUOMI-NPP',
                        acq_date: f.acq_date || '',
                        acq_time: f.acq_time || '',
                        confidence: f.confidence || '',
                        daynight: f.daynight || '',
                        latitude: f.latitude,
                        longitude: f.longitude
                    }
                });
            }
        });

        const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
        toRemove.forEach(e => ds.entities.remove(e));
        ds.entities.resumeEvents();
        this.viewer.scene.requestRender();
    }


    updateWeatherAlerts(alerts) {
        if (!this.viewer) return;
        const ds = this.dataSources.weatherAlerts;
        const currentIds = new Set();

        alerts.forEach(a => {
            if (!a.centroid || !Number.isFinite(a.centroid[0]) || !Number.isFinite(a.centroid[1])) return;
            currentIds.add(a.id);
            const position = Cesium.Cartesian3.fromDegrees(a.centroid[0], a.centroid[1]);
            const color = a.severity === 'Extreme' ? '#ff0000' : a.severity === 'Severe' ? '#ff8800' : '#ffff00';
            
            let entity = ds.entities.getById(a.id);
            if (entity) {
                entity.position = position;
                entity.label.fillColor = Cesium.Color.fromCssColorString(color);
            } else {
                ds.entities.add({
                    id: a.id,
                    name: a.event,
                    position: position,
                    label: {
                        text: `⚠️ ${a.event}`,
                        font: '12px monospace',
                        fillColor: Cesium.Color.fromCssColorString(color),
                        outlineColor: Cesium.Color.BLACK,
                        outlineWidth: 2,
                        style: Cesium.LabelStyle.FILL_AND_OUTLINE
                    },
                    description: `<b>${a.headline}</b><br><br>${a.description}`
                });
            }
        });

        const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
        toRemove.forEach(e => ds.entities.remove(e));
        this.viewer.scene.requestRender();
    }

    updateWeather(weatherStations) {
        if (!this.viewer) return;
        const ds = this.dataSources.weather;
        const currentIds = new Set();

        const colors = [
            Cesium.Color.fromCssColorString('#00d4aa'), // None
            Cesium.Color.fromCssColorString('#44ff44'), // Light
            Cesium.Color.fromCssColorString('#ffff44'), // Moderate
            Cesium.Color.fromCssColorString('#ff8844'), // Heavy
            Cesium.Color.fromCssColorString('#ff4444')  // Extreme
        ];

        weatherStations.forEach(wx => {
            if (!Number.isFinite(wx.longitude) || !Number.isFinite(wx.latitude)) return;
            currentIds.add(wx.id);
            const lvl = wx.precipitationLevel || 0;
            const colorHex = lvl === 0 ? '#00d4aa' : lvl === 1 ? '#44ff44' : lvl === 2 ? '#ffff44' : lvl === 3 ? '#ff8844' : '#ff4444';
            const icon = this._createWeatherSVG(lvl, colorHex);
            const position = Cesium.Cartesian3.fromDegrees(wx.longitude, wx.latitude);

            let entity = ds.entities.getById(wx.id);
            if (entity) {
                entity.position = position;
                entity.billboard.image = icon;
                entity.label.fillColor = colors[lvl];
            } else {
                ds.entities.add({
                    id: wx.id,
                    position: position,
                    billboard: {
                        image: icon, width: 22, height: 22,
                        verticalOrigin: Cesium.VerticalOrigin.CENTER,
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 8000000)
                    },
                    label: {
                        text: `WXR: ${wx.condition.toUpperCase()}`,
                        font: '10px "Share Tech Mono", monospace',
                        fillColor: colors[lvl],
                        pixelOffset: new Cesium.Cartesian2(0, 15),
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 2000000)
                    },
                    properties: wx
                });
            }
        });

        const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
        toRemove.forEach(e => ds.entities.remove(e));
        this.viewer.scene.requestRender();
    }

    updateCCTV(cameras) {
        if (!this.viewer) return;
        const ds = this.dataSources.cctv;
        const currentIds = new Set();
        const icon = this._createCCTVSVG();

        cameras.forEach(cam => {
            if (!Number.isFinite(cam.longitude) || !Number.isFinite(cam.latitude)) return;
            currentIds.add(cam.id);
            const position = Cesium.Cartesian3.fromDegrees(cam.longitude, cam.latitude);

            let entity = ds.entities.getById(cam.id);
            if (entity) {
                entity.position = position;
                entity.billboard.color = cam.status === 'Recording' ? Cesium.Color.fromCssColorString('#ff3333') : Cesium.Color.fromCssColorString('#00d4aa');
            } else {
                ds.entities.add({
                    id: cam.id,
                    position: position,
                    billboard: {
                        image: icon,
                        width: 20,
                        height: 20,
                        color: cam.status === 'Recording' ? Cesium.Color.fromCssColorString('#ff3333') : Cesium.Color.fromCssColorString('#00d4aa')
                    },
                    label: {
                        text: cam.name,
                        font: '10px "Share Tech Mono", monospace',
                        fillColor: Cesium.Color.fromCssColorString('#00d4aa'),
                        pixelOffset: new Cesium.Cartesian2(15, 0),
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 500000)
                    },
                    properties: cam
                });
            }
        });

        const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
        toRemove.forEach(e => ds.entities.remove(e));
        this.viewer.scene.requestRender();
    }

    updateNuclear(facilities) {
        if (!this.viewer) return;
        const ds = this.dataSources.nuclear;
        const currentIds = new Set();
        const icon = this._createNuclearSVG('#ffaa00');

        facilities.forEach(fac => {
            if (!Number.isFinite(fac.lon) || !Number.isFinite(fac.lat)) return;
            const id = `nuc-${fac.id}`;
            currentIds.add(id);
            const position = Cesium.Cartesian3.fromDegrees(fac.lon, fac.lat);

            let entity = ds.entities.getById(id);
            if (entity) {
                entity.position = position;
            } else {
                ds.entities.add({
                    id: id,
                    position: position,
                    billboard: {
                        image: icon, width: 26, height: 26,
                        verticalOrigin: Cesium.VerticalOrigin.CENTER,
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 20000000)
                    },
                    label: {
                        text: fac.name, font: '10px "Share Tech Mono", monospace',
                        fillColor: Cesium.Color.fromCssColorString('#ffaa00'),
                        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                        outlineColor: Cesium.Color.BLACK, outlineWidth: 3,
                        pixelOffset: new Cesium.Cartesian2(0, 20),
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 5000000)
                    },
                    properties: fac
                });
            }
        });

        const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
        toRemove.forEach(e => ds.entities.remove(e));
        this.viewer.scene.requestRender();
    }

    updateMilitary(bases) {
        if (!this.viewer) return;
        const ds = this.dataSources.military;
        const currentIds = new Set();
        const icon = this._createMilitarySVG('#00aaff');

        bases.forEach(base => {
            if (!Number.isFinite(base.lon) || !Number.isFinite(base.lat)) return;
            const id = `mil-${base.id}`;
            currentIds.add(id);
            const position = Cesium.Cartesian3.fromDegrees(base.lon, base.lat);

            let entity = ds.entities.getById(id);
            if (entity) {
                entity.position = position;
            } else {
                ds.entities.add({
                    id: id,
                    position: position,
                    billboard: {
                        image: icon, width: 24, height: 24,
                        verticalOrigin: Cesium.VerticalOrigin.CENTER,
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 15000000)
                    },
                    label: {
                        text: base.name, font: '9px "Share Tech Mono", monospace',
                        fillColor: Cesium.Color.fromCssColorString('#00aaff'),
                        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                        outlineColor: Cesium.Color.BLACK, outlineWidth: 3,
                        pixelOffset: new Cesium.Cartesian2(0, 18),
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 3000000)
                    },
                    properties: base
                });
            }
        });

        const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
        toRemove.forEach(e => ds.entities.remove(e));
        this.viewer.scene.requestRender();
    }

    updateConflicts(zones) {
        if (!this.viewer) return;
        const ds = this.dataSources.conflicts;
        const currentIds = new Set();

        zones.forEach(zone => {
            if (!zone.coords || zone.coords.length < 3) return;
            const flatCoords = zone.coords.flat();
            if (flatCoords.some(c => !Number.isFinite(c))) return;

            const id = `conf-${zone.id}`;
            currentIds.add(id);
            const hierarchy = Cesium.Cartesian3.fromDegreesArray(flatCoords);
            const position = Cesium.Cartesian3.fromDegrees(zone.coords[0][0], zone.coords[0][1]);

            let entity = ds.entities.getById(id);
            if (entity) {
                entity.polygon.hierarchy = hierarchy;
                entity.position = position;
            } else {
                ds.entities.add({
                    id: id,
                    polygon: {
                        hierarchy: hierarchy,
                        material: Cesium.Color.fromCssColorString('#ff0044').withAlpha(0.2),
                        outline: true,
                        outlineColor: Cesium.Color.fromCssColorString('#ff0044'),
                        outlineWidth: 2
                    },
                    position: position,
                    label: {
                        text: zone.name.toUpperCase(),
                        font: '12px "Share Tech Mono", monospace',
                        fillColor: Cesium.Color.fromCssColorString('#ff0044'),
                        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                        outlineColor: Cesium.Color.BLACK, outlineWidth: 2,
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 8000000)
                    },
                    properties: zone
                });
            }
        });

        const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
        toRemove.forEach(e => ds.entities.remove(e));
        this.viewer.scene.requestRender();
    }

    updateWaterways(waterways) {
        if (!this.viewer) return;
        const ds = this.dataSources.waterways;
        const currentIds = new Set();

        waterways.forEach(way => {
            if (!way.path || way.path.length < 2) return;
            const flatPath = way.path.flat();
            if (flatPath.some(c => !Number.isFinite(c))) return;

            const id = `way-${way.id}`;
            currentIds.add(id);
            const positions = Cesium.Cartesian3.fromDegreesArray(flatPath);

            let entity = ds.entities.getById(id);
            if (entity) {
                entity.polyline.positions = positions;
            } else {
                ds.entities.add({
                    id: id,
                    name: way.name,
                    polyline: {
                        positions: positions,
                        width: 3,
                        material: new Cesium.PolylineDashMaterialProperty({ color: Cesium.Color.CYAN }),
                        clampToGround: true
                    },
                    properties: way
                });
            }
        });

        const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
        toRemove.forEach(e => ds.entities.remove(e));
        this.viewer.scene.requestRender();
    }

    updateHotspots(hotspots) {
        if (!this.viewer) return;
        const ds = this.dataSources.hotspots;
        ds.entities.suspendEvents();
        try {
            const currentIds = new Set();
            const colors = { high: '#ff0044', elevated: '#ff8800', medium: '#ffcc00', low: '#44ff88' };

            hotspots.forEach(h => {
                if (!Number.isFinite(h.lon) || !Number.isFinite(h.lat)) return;
                const id = `hs-${h.id}`;
                currentIds.add(id);
                const position = Cesium.Cartesian3.fromDegrees(h.lon, h.lat);
                const c = colors[h.level] || '#ffcc00';
                const icon = this._createHotspotSVG(c);

                let entity = ds.entities.getById(id);
                if (entity) {
                    entity.position = position;
                } else {
                    ds.entities.add({
                        id: id,
                        position: position,
                        billboard: {
                            image: icon, width: 28, height: 28,
                            verticalOrigin: Cesium.VerticalOrigin.CENTER,
                            distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 20000000)
                        },
                        ellipse: {
                            semiMajorAxis: h.level === 'high' ? 200000 : 150000,
                            semiMinorAxis: h.level === 'high' ? 200000 : 150000,
                            material: Cesium.Color.fromCssColorString(c).withAlpha(0.12),
                            height: 0
                        },
                        label: {
                            text: h.name, font: '10px "Share Tech Mono", monospace',
                            fillColor: Cesium.Color.fromCssColorString(c),
                            style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                            outlineColor: Cesium.Color.BLACK, outlineWidth: 3,
                            pixelOffset: new Cesium.Cartesian2(0, 22),
                            distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 8000000)
                        },
                        properties: { ...h, description: h.description }
                    });
                }
            });

            const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
            toRemove.forEach(e => ds.entities.remove(e));
        } finally {
            ds.entities.resumeEvents();
        }
        this.viewer.scene.requestRender();
    }

    updateCables(cables) {
        if (!this.viewer) return;
        const ds = this.dataSources.cables;
        const currentIds = new Set();
        const icon = this._createCableSVG('#00ccff');

        cables.forEach(cable => {
            if (!cable.points || cable.points.length < 2) return;
            const degs = cable.points.flatMap(p => [p[0], p[1]]);
            if (degs.some(d => !Number.isFinite(d))) return;

            const id = `cable-${cable.id}`;
            currentIds.add(id);
            const positions = Cesium.Cartesian3.fromDegreesArray(degs);
            const firstPos = Cesium.Cartesian3.fromDegrees(cable.points[0][0], cable.points[0][1]);

            let entity = ds.entities.getById(id);
            if (entity) {
                entity.polyline.positions = positions;
                entity.position = firstPos;
            } else {
                ds.entities.add({
                    id: id,
                    polyline: {
                        positions: positions,
                        width: 2,
                        material: new Cesium.PolylineGlowMaterialProperty({ glowPower: 0.3, color: Cesium.Color.fromCssColorString('#00ccff') }),
                        clampToGround: true
                    },
                    position: firstPos,
                    billboard: {
                        image: icon, width: 22, height: 22,
                        verticalOrigin: Cesium.VerticalOrigin.CENTER,
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 15000000)
                    },
                    label: {
                        text: cable.name, font: '10px "Share Tech Mono", monospace',
                        fillColor: Cesium.Color.fromCssColorString('#00ccff'),
                        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                        outlineColor: Cesium.Color.BLACK, outlineWidth: 3,
                        pixelOffset: new Cesium.Cartesian2(0, 18),
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 5000000)
                    },
                    properties: cable
                });
            }
        });

        const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
        toRemove.forEach(e => ds.entities.remove(e));
        this.viewer.scene.requestRender();
    }

    updateSpaceports(spaceports) {
        if (!this.viewer) return;
        const ds = this.dataSources.spaceports;
        const currentIds = new Set();
        const icon = this._createSpaceportSVG('#ff44ff');

        spaceports.forEach(sp => {
            if (!Number.isFinite(sp.lon) || !Number.isFinite(sp.lat)) return;
            const id = `sp-${sp.id}`;
            currentIds.add(id);
            const position = Cesium.Cartesian3.fromDegrees(sp.lon, sp.lat);

            let entity = ds.entities.getById(id);
            if (entity) {
                entity.position = position;
            } else {
                ds.entities.add({
                    id: id,
                    position: position,
                    billboard: {
                        image: icon, width: 26, height: 26,
                        verticalOrigin: Cesium.VerticalOrigin.CENTER,
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 20000000)
                    },
                    label: {
                        text: sp.name, font: '10px "Share Tech Mono", monospace',
                        fillColor: Cesium.Color.fromCssColorString('#ff44ff'),
                        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                        outlineColor: Cesium.Color.BLACK, outlineWidth: 3,
                        pixelOffset: new Cesium.Cartesian2(0, 20),
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 6000000)
                    },
                    properties: sp
                });
            }
        });

        const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
        toRemove.forEach(e => ds.entities.remove(e));
        this.viewer.scene.requestRender();
    }

    updateEconomicCenters(centers) {
        if (!this.viewer) return;
        const ds = this.dataSources.economic;
        const currentIds = new Set();
        const icon = this._createEconomicSVG('#44ff88');

        centers.forEach(ec => {
            if (!Number.isFinite(ec.lon) || !Number.isFinite(ec.lat)) return;
            const id = `ec-${ec.id}`;
            currentIds.add(id);
            const position = Cesium.Cartesian3.fromDegrees(ec.lon, ec.lat);

            let entity = ds.entities.getById(id);
            if (entity) {
                entity.position = position;
            } else {
                ds.entities.add({
                    id: id,
                    position: position,
                    billboard: {
                        image: icon, width: 26, height: 26,
                        verticalOrigin: Cesium.VerticalOrigin.CENTER,
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 20000000)
                    },
                    label: {
                        text: ec.name, font: '10px "Share Tech Mono", monospace',
                        fillColor: Cesium.Color.fromCssColorString('#44ff88'),
                        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                        outlineColor: Cesium.Color.BLACK, outlineWidth: 3,
                        pixelOffset: new Cesium.Cartesian2(0, 20),
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 6000000)
                    },
                    properties: ec
                });
            }
        });

        const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
        toRemove.forEach(e => ds.entities.remove(e));
        this.viewer.scene.requestRender();
    }

    clearEffects() {
        if (!this.viewer) return;
        this.viewer.scene.postProcessStages.removeAll();
        this._activeEffects = {};
        this.viewer.scene.requestRender();
    }

    setVisualMode(mode) {
        if (!this.viewer) return;
        console.log("Setting visual mode:", mode);
        this.currentMode = mode;
        this.clearEffects();

        switch (mode) {
            case 'tactical':
                this._activeEffects.night = this.viewer.scene.postProcessStages.add(Cesium.PostProcessStageLibrary.createNightVisionStage());
                break;
            case 'thermal':
                this._activeEffects.blackAndWhite = this.viewer.scene.postProcessStages.add(Cesium.PostProcessStageLibrary.createBlackAndWhiteStage());
                break;
            case 'scan':
                this._activeEffects.edge = this.viewer.scene.postProcessStages.add(Cesium.PostProcessStageLibrary.createEdgeDetectionStage());
                break;
            case 'crt': this.applyCRTEffect(); break;
            case 'nvg': this.applyNVGEffect(); break;
            case 'flir': this.applyFLIREffect(); break;
            case 'noir': this.applyNoirEffect(); break;
            case 'anime': this.applyAnimeEffect(); break;
            case 'snow': this.applySnowEffect(); break;
            case 'normal':
            default:
                break;
        }
        this.viewer.scene.requestRender();
    }

    setLayerVisibility(layer, visible) {
        if (layer === 'argusLandmarks') {
            this.toggleArgusLandmarks(visible);
            return;
        }
        if (this.dataSources[layer]) {
            this.dataSources[layer].show = visible;
        }
        if (layer === 'argusNodes' && this.dataSources.argusIncidents) {
            this.dataSources.argusIncidents.show = visible;
        }
    }

    applyCRTEffect() {
        const stage = new Cesium.PostProcessStage({
            fragmentShader: `
                uniform sampler2D colorTexture;
                in vec2 v_textureCoordinates;
                void main() {
                    vec2 uv = v_textureCoordinates;
                    vec4 color = texture(colorTexture, uv);
                    float scanline = sin(uv.y * 800.0) * 0.04;
                    color.rgb -= scanline;
                    color.r *= 0.85; color.b *= 0.85; color.g *= 1.1;
                    float vignette = 1.0 - length((uv - 0.5) * 1.3);
                    color.rgb *= vignette;
                    float aberration = 0.001;
                    color.r = texture(colorTexture, uv + vec2(aberration, 0.0)).r * 0.85;
                    color.b = texture(colorTexture, uv - vec2(aberration, 0.0)).b * 0.85;
                    out_FragColor = color;
                }`
        });
        this._activeEffects.crt = stage;
        this.viewer.scene.postProcessStages.add(stage);
    }

    applyNVGEffect() {
        const stage = new Cesium.PostProcessStage({
            fragmentShader: `
                uniform sampler2D colorTexture;
                in vec2 v_textureCoordinates;
                void main() {
                    vec4 color = texture(colorTexture, v_textureCoordinates);
                    float luma = dot(color.rgb, vec3(0.299, 0.587, 0.114));
                    vec3 nvg = vec3(0.0, luma * 1.3, luma * 0.1);
                    float noise = fract(sin(dot(v_textureCoordinates * 1000.0, vec2(12.9898, 78.233))) * 43758.5453);
                    nvg += noise * 0.05;
                    nvg = pow(nvg, vec3(0.85));
                    float vignette = 1.0 - length((v_textureCoordinates - 0.5) * 0.8);
                    nvg *= vignette;
                    out_FragColor = vec4(nvg, 1.0);
                }`
        });
        this._activeEffects.nvg = stage;
        this.viewer.scene.postProcessStages.add(stage);
    }

    applyFLIREffect() {
        const stage = new Cesium.PostProcessStage({
            fragmentShader: `
                uniform sampler2D colorTexture;
                in vec2 v_textureCoordinates;
                void main() {
                    vec4 color = texture(colorTexture, v_textureCoordinates);
                    float luma = dot(color.rgb, vec3(0.299, 0.587, 0.114));
                    vec3 thermal;
                    if (luma < 0.25) { thermal = mix(vec3(0.0, 0.0, 0.1), vec3(0.3, 0.0, 0.4), luma * 4.0); }
                    else if (luma < 0.5) { thermal = mix(vec3(0.3, 0.0, 0.4), vec3(0.8, 0.2, 0.0), (luma - 0.25) * 4.0); }
                    else if (luma < 0.75) { thermal = mix(vec3(0.8, 0.2, 0.0), vec3(1.0, 0.9, 0.0), (luma - 0.5) * 4.0); }
                    else { thermal = mix(vec3(1.0, 0.9, 0.0), vec3(1.0, 1.0, 1.0), (luma - 0.75) * 4.0); }
                    out_FragColor = vec4(thermal, 1.0);
                }`
        });
        this._activeEffects.flir = stage;
        this.viewer.scene.postProcessStages.add(stage);
    }

    applyNoirEffect() {
        const stage = new Cesium.PostProcessStage({
            fragmentShader: `
                uniform sampler2D colorTexture;
                in vec2 v_textureCoordinates;
                void main() {
                    vec4 color = texture(colorTexture, v_textureCoordinates);
                    float luma = dot(color.rgb, vec3(0.299, 0.587, 0.114));
                    luma = pow(luma, 0.7); luma = smoothstep(0.1, 0.9, luma);
                    vec3 noir = vec3(luma * 1.0, luma * 0.95, luma * 0.9);
                    float vignette = 1.0 - length((v_textureCoordinates - 0.5) * 1.2);
                    noir *= vignette;
                    out_FragColor = vec4(noir, 1.0);
                }`
        });
        this._activeEffects.noir = stage;
        this.viewer.scene.postProcessStages.add(stage);
    }

    applyAnimeEffect() {
        const stage = new Cesium.PostProcessStage({
            fragmentShader: `
                uniform sampler2D colorTexture;
                in vec2 v_textureCoordinates;
                void main() {
                    vec4 color = texture(colorTexture, v_textureCoordinates);
                    float levels = 6.0;
                    color.rgb = floor(color.rgb * levels) / levels;
                    float luma = dot(color.rgb, vec3(0.299, 0.587, 0.114));
                    color.rgb = mix(vec3(luma), color.rgb, 1.5);
                    vec2 texelSize = 1.0 / vec2(1920.0, 1080.0);
                    float edge = 0.0;
                    for (int x = -1; x <= 1; x++) {
                        for (int y = -1; y <= 1; y++) {
                            if (x == 0 && y == 0) continue;
                            vec4 neighbor = texture(colorTexture, v_textureCoordinates + vec2(float(x), float(y)) * texelSize * 2.0);
                            edge += length(color.rgb - neighbor.rgb);
                        }
                    }
                    edge = edge > 0.3 ? 1.0 : 0.0;
                    color.rgb = mix(color.rgb, vec3(0.0), edge * 0.5);
                    out_FragColor = color;
                }`
        });
        this._activeEffects.anime = stage;
        this.viewer.scene.postProcessStages.add(stage);
    }

    applySnowEffect() {
        const stage = new Cesium.PostProcessStage({
            fragmentShader: `
                uniform sampler2D colorTexture;
                in vec2 v_textureCoordinates;
                void main() {
                    vec4 color = texture(colorTexture, v_textureCoordinates);
                    float luma = dot(color.rgb, vec3(0.299, 0.587, 0.114));
                    color.rgb = mix(color.rgb, vec3(luma), 0.7);
                    color.r *= 0.85; color.g *= 0.92; color.b *= 1.15;
                    color.rgb = pow(color.rgb, vec3(0.9));
                    float noise = fract(sin(dot(v_textureCoordinates * 500.0, vec2(12.9898, 78.233))) * 43758.5453);
                    color.rgb += noise * 0.02;
                    out_FragColor = color;
                }`
        });
        this._activeEffects.snow = stage;
        this.viewer.scene.postProcessStages.add(stage);
    }

    _createVesselSVG(color = '#00d4aa') {
        const key = `vessel-${color}`;
        if (this._vesselCache && this._vesselCache[key]) return this._vesselCache[key];
        if (!this._vesselCache) this._vesselCache = {};

        // Top-down ship silhouette: tapered bow, wider stern, bridge superstructure
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 36" width="20" height="30">
          <defs>
            <filter id="gs" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="1.2" result="b"/>
              <feComposite in="SourceGraphic" in2="b" operator="over"/>
            </filter>
          </defs>
          <!-- Hull -->
          <path d="M12,1 L19,8 L20,28 L12,32 L4,28 L4,8 Z"
                fill="${color}" fill-opacity="0.15" stroke="${color}" stroke-width="1.5"/>
          <!-- Bow point -->
          <polygon points="12,1 15,8 9,8"
                   fill="${color}" fill-opacity="0.9"/>
          <!-- Bridge superstructure -->
          <rect x="9" y="13" width="6" height="8" rx="1"
                fill="${color}" fill-opacity="0.85" stroke="${color}" stroke-width="0.5"/>
          <!-- Deck lines -->
          <line x1="7" y1="10" x2="17" y2="10" stroke="${color}" stroke-width="0.6" opacity="0.6"/>
          <line x1="6" y1="25" x2="18" y2="25" stroke="${color}" stroke-width="0.6" opacity="0.6"/>
          <!-- Center mast dot -->
          <circle cx="12" cy="17" r="1.2" fill="#fff" opacity="0.9"/>
        </svg>`;

        const url = `data:image/svg+xml;base64,${btoa(svg)}`;
        this._vesselCache[key] = url;
        return url;
    }

    _createSatelliteSVG(color = '#00d4aa') {
        const key = `sat-${color}`;
        if (this._satCache && this._satCache[key]) return this._satCache[key];
        if (!this._satCache) this._satCache = {};

        // Satellite: central body + solar panel arrays left/right
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 20" width="80" height="40">
          <defs>
            <filter id="sat-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="1.5" result="blur"/>
              <feComposite in="SourceGraphic" in2="blur" operator="over"/>
            </filter>
          </defs>
          <g filter="url(#sat-glow)">
              <!-- Left solar panel array -->
              <rect x="0" y="6" width="12" height="8" rx="1"
                    fill="${color}" fill-opacity="0.35" stroke="${color}" stroke-width="1"/>
              <line x1="3" y1="6" x2="3" y2="14" stroke="${color}" stroke-width="0.5" opacity="0.7"/>
              <line x1="6" y1="6" x2="6" y2="14" stroke="${color}" stroke-width="0.5" opacity="0.7"/>
              <line x1="9" y1="6" x2="9" y2="14" stroke="${color}" stroke-width="0.5" opacity="0.7"/>
              <!-- Panel strut left -->
              <line x1="12" y1="10" x2="15" y2="10" stroke="${color}" stroke-width="1.5"/>
              <!-- Satellite body -->
              <rect x="15" y="5" width="10" height="10" rx="1.5"
                    fill="${color}" fill-opacity="0.9" stroke="#fff" stroke-width="1"/>
              <!-- Dish antenna -->
              <circle cx="20" cy="10" r="2.5" fill="none" stroke="#fff" stroke-width="1" opacity="0.9"/>
              <circle cx="20" cy="10" r="1" fill="#fff" opacity="1"/>
              <!-- Panel strut right -->
              <line x1="25" y1="10" x2="28" y2="10" stroke="${color}" stroke-width="1.5"/>
              <!-- Right solar panel array -->
              <rect x="28" y="6" width="12" height="8" rx="1"
                    fill="${color}" fill-opacity="0.35" stroke="${color}" stroke-width="1"/>
              <line x1="31" y1="6" x2="31" y2="14" stroke="${color}" stroke-width="0.5" opacity="0.7"/>
              <line x1="34" y1="6" x2="34" y2="14" stroke="${color}" stroke-width="0.5" opacity="0.7"/>
              <line x1="37" y1="6" x2="37" y2="14" stroke="${color}" stroke-width="0.5" opacity="0.7"/>
          </g>
        </svg>`;

        const url = `data:image/svg+xml;base64,${btoa(svg)}`;
        this._satCache[key] = url;
        return url;
    }

    _createAircraftSVG(heading, color = '#00d4aa') {
        const bucket = (Math.round((heading || 0) / 5) * 5) % 360;
        const key = `aircraft-${bucket}-${color}`;
        if (this._aircraftCache[key]) return this._aircraftCache[key];

        // Proper top-down aircraft silhouette:
        // fuselage, swept wings, twin tail stabilisers
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="28" height="28">
          <g transform="rotate(${bucket}, 16, 16)">
            <!-- Fuselage -->
            <ellipse cx="16" cy="16" rx="2.2" ry="11"
                     fill="${color}" fill-opacity="0.95"/>
            <!-- Nose tip -->
            <ellipse cx="16" cy="6" rx="1.5" ry="2.5"
                     fill="#ffffff" fill-opacity="0.9"/>
            <!-- Main swept wings -->
            <path d="M16,12 L4,22 L6,24 L16,18 L26,24 L28,22 Z"
                  fill="${color}" fill-opacity="0.85"/>
            <!-- Wing leading edge highlight -->
            <path d="M16,12 L4,22 M16,12 L28,22"
                  stroke="#ffffff" stroke-width="0.4" opacity="0.5"/>
            <!-- Tail stabilisers -->
            <path d="M16,24 L10,29 L11,30 L16,27 L21,30 L22,29 Z"
                  fill="${color}" fill-opacity="0.9"/>
            <!-- Engine nacelles -->
            <ellipse cx="11" cy="18" rx="1.2" ry="2.5"
                     fill="${color}" stroke="#fff" stroke-width="0.3" fill-opacity="0.7"/>
            <ellipse cx="21" cy="18" rx="1.2" ry="2.5"
                     fill="${color}" stroke="#fff" stroke-width="0.3" fill-opacity="0.7"/>
          </g>
        </svg>`;

        const url = `data:image/svg+xml;base64,${btoa(svg)}`;
        this._aircraftCache[key] = url;
        return url;
    }

    _createCCTVSVG() {
        if (this._iconCache['cctv']) return this._iconCache['cctv'];

        const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
          <circle cx="12" cy="12" r="10" fill="#011018" fill-opacity="0.85" stroke="#00d4aa" stroke-width="1.2"/>
          <path d="M6,8 L14,10 L14,14 L6,16 Z" fill="#00d4aa"/>
          <polygon points="14,10 18,7 18,17 14,14" fill="#00d4aa"/>
          <circle cx="12" cy="12" r="1.5" fill="#fff"/>
        </svg>`;
        
        const dataUrl = `data:image/svg+xml;base64,${btoa(svg)}`;
        this._iconCache['cctv'] = dataUrl;
        return dataUrl;
    }

    _createArgusNodeSVG(color = '#00FFD1', isQuarantined = false) {
        const key = `argus-node-${color}-${isQuarantined}`;
        if (this._iconCache[key]) return this._iconCache[key];
        const strokeCol = isQuarantined ? '#BC13FE' : color;
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">
          <defs>
            <filter id="glow-argus" x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="2.5" result="blur"/>
              <feComposite in="SourceGraphic" in2="blur" operator="over"/>
            </filter>
          </defs>
          <g filter="url(#glow-argus)">
            <!-- Tactical Hexagon Shield Base -->
            <polygon points="24,4 42,14 42,34 24,44 6,34 6,14" fill="#020e16" fill-opacity="0.9" stroke="${strokeCol}" stroke-width="2"/>
            <!-- Inner Concentric Reticle -->
            <circle cx="24" cy="24" r="11" fill="none" stroke="${strokeCol}" stroke-width="1.2" stroke-dasharray="3,2"/>
            <circle cx="24" cy="24" r="5" fill="${strokeCol}" fill-opacity="0.95"/>
            <!-- Crosshairs -->
            <line x1="24" y1="8" x2="24" y2="15" stroke="${strokeCol}" stroke-width="1.5"/>
            <line x1="24" y1="33" x2="24" y2="40" stroke="${strokeCol}" stroke-width="1.5"/>
            <line x1="8" y1="24" x2="15" y2="24" stroke="${strokeCol}" stroke-width="1.5"/>
            <line x1="33" y1="24" x2="40" y2="24" stroke="${strokeCol}" stroke-width="1.5"/>
          </g>
        </svg>`;
        const url = `data:image/svg+xml;base64,${btoa(svg)}`;
        this._iconCache[key] = url;
        return url;
    }

    _createNuclearSVG(color = '#ffaa00') {
        const key = `nuc-${color}`;
        if (this._iconCache[key]) return this._iconCache[key];
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36" width="36" height="36">
          <circle cx="18" cy="18" r="16" fill="#0f0800" fill-opacity="0.9" stroke="${color}" stroke-width="1.5"/>
          <!-- Trefoil blades -->
          <path d="M18,18 L13,6 A14,14 0 0,1 23,6 Z" fill="${color}"/>
          <path d="M18,18 L27.7,21.5 A14,14 0 0,1 22.7,30.2 Z" fill="${color}"/>
          <path d="M18,18 L8.3,21.5 A14,14 0 0,0 13.3,30.2 Z" fill="${color}"/>
          <circle cx="18" cy="18" r="6" fill="#0f0800"/>
          <circle cx="18" cy="18" r="3" fill="${color}"/>
        </svg>`;
        const url = `data:image/svg+xml;base64,${btoa(svg)}`;
        this._iconCache[key] = url;
        return url;
    }

    _createMilitarySVG(color = '#00aaff') {
        const key = `mil-${color}`;
        if (this._iconCache[key]) return this._iconCache[key];
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36" width="36" height="36">
          <path d="M18,3 L32,8 L32,20 C32,27 26,32 18,34 C10,32 4,27 4,20 L4,8 Z" fill="#021020" fill-opacity="0.9" stroke="${color}" stroke-width="1.5"/>
          <polygon points="18,10 20.5,15 26,15.5 22,19 23,24.5 18,21.8 13,24.5 14,19 10,15.5 15.5,15" fill="${color}"/>
        </svg>`;
        const url = `data:image/svg+xml;base64,${btoa(svg)}`;
        this._iconCache[key] = url;
        return url;
    }

    _createHotspotSVG(color = '#ff0044') {
        const key = `hotspot-${color}`;
        if (this._iconCache[key]) return this._iconCache[key];
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36" width="36" height="36">
          <circle cx="18" cy="18" r="15" fill="#180006" fill-opacity="0.85" stroke="${color}" stroke-width="1.5"/>
          <circle cx="18" cy="18" r="9" fill="none" stroke="${color}" stroke-width="1" stroke-dasharray="2,2"/>
          <circle cx="18" cy="18" r="3.5" fill="${color}"/>
          <line x1="18" y1="2" x2="18" y2="8" stroke="${color}" stroke-width="1.5"/>
          <line x1="18" y1="28" x2="18" y2="34" stroke="${color}" stroke-width="1.5"/>
          <line x1="2" y1="18" x2="8" y2="18" stroke="${color}" stroke-width="1.5"/>
          <line x1="28" y1="18" x2="34" y2="18" stroke="${color}" stroke-width="1.5"/>
        </svg>`;
        const url = `data:image/svg+xml;base64,${btoa(svg)}`;
        this._iconCache[key] = url;
        return url;
    }

    _createCableSVG(color = '#00ccff') {
        const key = `cable-${color}`;
        if (this._iconCache[key]) return this._iconCache[key];
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
          <circle cx="16" cy="16" r="13" fill="#001420" fill-opacity="0.9" stroke="${color}" stroke-width="1.2"/>
          <line x1="4" y1="16" x2="12" y2="16" stroke="${color}" stroke-width="2"/>
          <line x1="20" y1="16" x2="28" y2="16" stroke="${color}" stroke-width="2"/>
          <circle cx="16" cy="16" r="4.5" fill="${color}" fill-opacity="0.8"/>
          <circle cx="16" cy="16" r="2" fill="#fff"/>
        </svg>`;
        const url = `data:image/svg+xml;base64,${btoa(svg)}`;
        this._iconCache[key] = url;
        return url;
    }

    _createSpaceportSVG(color = '#ff44ff') {
        const key = `spaceport-${color}`;
        if (this._iconCache[key]) return this._iconCache[key];
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36" width="36" height="36">
          <circle cx="18" cy="18" r="15" fill="#140014" fill-opacity="0.9" stroke="${color}" stroke-width="1.5"/>
          <path d="M18,6 C20,11 23,19 23,24 L13,24 C13,19 16,11 18,6 Z" fill="${color}"/>
          <polygon points="13,21 9,25 13,25" fill="${color}"/>
          <polygon points="23,21 27,25 23,25" fill="${color}"/>
          <polygon points="16,25 18,30 20,25" fill="#ffaa00"/>
        </svg>`;
        const url = `data:image/svg+xml;base64,${btoa(svg)}`;
        this._iconCache[key] = url;
        return url;
    }

    _createEconomicSVG(color = '#00ff88') {
        const key = `econ-${color}`;
        if (this._iconCache[key]) return this._iconCache[key];
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36" width="36" height="36">
          <polygon points="18,3 33,18 18,33 3,18" fill="#001a10" fill-opacity="0.9" stroke="${color}" stroke-width="1.5"/>
          <circle cx="18" cy="18" r="5" fill="${color}"/>
          <line x1="18" y1="8" x2="18" y2="13" stroke="${color}" stroke-width="1.5"/>
          <line x1="18" y1="23" x2="18" y2="28" stroke="${color}" stroke-width="1.5"/>
          <line x1="8" y1="18" x2="13" y2="18" stroke="${color}" stroke-width="1.5"/>
          <line x1="23" y1="18" x2="28" y2="18" stroke="${color}" stroke-width="1.5"/>
        </svg>`;
        const url = `data:image/svg+xml;base64,${btoa(svg)}`;
        this._iconCache[key] = url;
        return url;
    }

    _createThermalSVG(color = '#ff5500') {
        const key = `thermal-${color}`;
        if (this._iconCache[key]) return this._iconCache[key];
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
          <circle cx="16" cy="16" r="14" fill="#200a00" fill-opacity="0.9" stroke="${color}" stroke-width="1.5"/>
          <circle cx="16" cy="16" r="8" fill="${color}" fill-opacity="0.3"/>
          <path d="M16,7 C18,12 22,15 22,19 C22,23 19,25 16,25 C13,25 10,23 10,19 C10,15 14,12 16,7 Z" fill="${color}"/>
          <path d="M16,14 C17,17 19,18 19,20 C19,22 17,23 16,23 C15,23 13,22 13,20 C13,18 15,17 16,14 Z" fill="#ffea00"/>
        </svg>`;
        const url = `data:image/svg+xml;base64,${btoa(svg)}`;
        this._iconCache[key] = url;
        return url;
    }

    _createNaturalEventSVG(type = 'default', color = '#ff8800') {
        const key = `natevt-${type}-${color}`;
        if (this._iconCache[key]) return this._iconCache[key];
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
          <polygon points="16,3 30,28 2,28" fill="#1c1000" fill-opacity="0.9" stroke="${color}" stroke-width="1.5"/>
          <line x1="16" y1="12" x2="16" y2="19" stroke="${color}" stroke-width="2"/>
          <circle cx="16" cy="23" r="1.5" fill="${color}"/>
        </svg>`;
        const url = `data:image/svg+xml;base64,${btoa(svg)}`;
        this._iconCache[key] = url;
        return url;
    }

    _createWeatherSVG(level = 0, color = '#00d4aa') {
        const key = `weather-${level}-${color}`;
        if (this._iconCache[key]) return this._iconCache[key];
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
          <circle cx="16" cy="16" r="14" fill="#001824" fill-opacity="0.9" stroke="${color}" stroke-width="1.2"/>
          <circle cx="16" cy="16" r="9" fill="none" stroke="${color}" stroke-width="0.8" opacity="0.6"/>
          <circle cx="16" cy="16" r="4" fill="${color}" fill-opacity="0.7"/>
          <path d="M16,16 L25,10 A12,12 0 0,0 20,5 Z" fill="${color}" fill-opacity="0.4"/>
          <line x1="16" y1="16" x2="25" y2="10" stroke="${color}" stroke-width="1.2"/>
        </svg>`;
        const url = `data:image/svg+xml;base64,${btoa(svg)}`;
        this._iconCache[key] = url;
        return url;
    }

    _createCellTowerSVG(color = '#00ffaa') {
        const key = `cell-${color}`;
        if (this._iconCache[key]) return this._iconCache[key];
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
          <circle cx="16" cy="16" r="14" fill="#001a14" fill-opacity="0.9" stroke="${color}" stroke-width="1.2"/>
          <line x1="16" y1="8" x2="16" y2="25" stroke="${color}" stroke-width="2"/>
          <line x1="12" y1="25" x2="20" y2="25" stroke="${color}" stroke-width="2"/>
          <line x1="13" y1="18" x2="19" y2="18" stroke="${color}" stroke-width="1.5"/>
          <line x1="14" y1="13" x2="18" y2="13" stroke="${color}" stroke-width="1.5"/>
          <path d="M11,10 A6,6 0 0,1 21,10" fill="none" stroke="${color}" stroke-width="1"/>
          <path d="M8,7 A10,10 0 0,1 24,7" fill="none" stroke="${color}" stroke-width="1"/>
        </svg>`;
        const url = `data:image/svg+xml;base64,${btoa(svg)}`;
        this._iconCache[key] = url;
        return url;
    }

    _createSeismicSVG(mag, color = '#00ffaa') {
        const key = `seismic-${color}`;
        if (this._iconCache[key]) return this._iconCache[key];
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36" width="36" height="36">
          <!-- Epicenter Outer Ring -->
          <circle cx="18" cy="18" r="15" fill="#120400" fill-opacity="0.85" stroke="${color}" stroke-width="1.5"/>
          <circle cx="18" cy="18" r="9" fill="none" stroke="${color}" stroke-width="1" stroke-dasharray="2,2"/>
          <!-- Waveform Pulse Spike -->
          <path d="M6,18 L12,18 L15,10 L18,26 L21,12 L24,18 L30,18" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="18" cy="18" r="2.5" fill="#ffffff"/>
        </svg>`;
        const url = `data:image/svg+xml;base64,${btoa(svg)}`;
        this._iconCache[key] = url;
        return url;
    }

    /**
     * Updates and visualizes ARGUS Cyber-Physical Sensor Nodes.
     * @param {Array<Object>} events - Normalized ArgusEvents
     * @param {Map<string, Object>} nodeTrustMap - Node ID -> NodeTrustState
     */
    updateArgusNodes(events, nodeTrustMap = new Map()) {
        if (!this.viewer || !this.dataSources.argusNodes) return;
        const ds = this.dataSources.argusNodes;
        const currentIds = new Set();

        events.forEach(evt => {
            if (!evt.location) return;
            const nodeId = evt.sourceId;
            const lat = evt.location.latitude;
            const lon = evt.location.longitude;
            const alt = Math.max(10, evt.location.altitudeMeters || 10);
            if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;

            const entityId = `argus-node-${nodeId}`;
            currentIds.add(entityId);

            const trustState = nodeTrustMap.get(nodeId);
            const trust = trustState ? trustState.compositeTrust : evt.analytics?.trustScore ?? 1.0;
            const isQuarantined = trustState?.isQuarantined || false;
            const integrity = evt.integrity?.status || 'VERIFIED';

            // Determine tactical color based on trust & integrity state
            let colorHex = '#00FFD1'; // Cyber Cyan
            let statusLabel = 'VERIFIED';

            if (isQuarantined) {
                colorHex = '#BC13FE'; // Cyber Purple / Quarantine
                statusLabel = 'QUARANTINED';
            } else if (integrity === 'INVALID_SIGNATURE' || integrity === 'CRC_FAILURE' || trust < 0.50) {
                colorHex = '#FF0055'; // Cyber Red / Alert
                statusLabel = 'COMPROMISED';
            } else if (trust < 0.85 || evt.analytics?.isAnomaly) {
                colorHex = '#FFCC00'; // Cyber Amber / Warning
                statusLabel = 'DEGRADED';
            }

            const color = Cesium.Color.fromCssColorString(colorHex);
            const position = Cesium.Cartesian3.fromDegrees(lon, lat, alt);
            const nodeIcon = this._createArgusNodeSVG(colorHex, isQuarantined);

            let entity = ds.entities.getById(entityId);
            if (entity) {
                entity.position = position;
                if (entity.billboard) {
                    entity.billboard.image = nodeIcon;
                }
                if (entity.label) {
                    entity.label.text = `${nodeId} [${statusLabel}] ${(trust * 100).toFixed(0)}%`;
                    entity.label.fillColor = color;
                }
                if (entity.properties) {
                    entity.properties.trustScore = (trust * 100).toFixed(1) + '%';
                    entity.properties.integrityStatus = integrity;
                    entity.properties.temperature = (evt.measurements?.temperatureCelsius ?? 24).toFixed(1) + ' °C';
                    entity.properties.anomalyScore = ((evt.analytics?.anomalyScore ?? 0) * 100).toFixed(1) + '%';
                    entity.properties.anomalyReasons = (evt.analytics?.anomalyReasons || []).join('; ') || 'None';
                    entity.properties.isQuarantined = isQuarantined ? 'YES (ISOLATED)' : 'NO';
                }
            } else {
                ds.entities.add({
                    id: entityId,
                    name: `ARGUS NODE: ${nodeId} (${statusLabel})`,
                    position: position,
                    billboard: {
                        image: nodeIcon,
                        width: 38,
                        height: 38,
                        verticalOrigin: Cesium.VerticalOrigin.CENTER,
                        horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
                        scaleByDistance: new Cesium.NearFarScalar(1e5, 1.3, 1.5e7, 0.85),
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 30000000)
                    },
                    label: {
                        text: `${nodeId} [${statusLabel}] ${(trust * 100).toFixed(0)}%`,
                        font: 'bold 12px "Share Tech Mono", monospace',
                        fillColor: color,
                        outlineColor: Cesium.Color.BLACK,
                        outlineWidth: 3,
                        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                        pixelOffset: new Cesium.Cartesian2(0, -20),
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 15000000)
                    },
                    properties: {
                        nodeId: nodeId,
                        type: 'ARGUS CYBER-PHYSICAL SENSOR NODE',
                        trustScore: (trust * 100).toFixed(1) + '%',
                        integrityStatus: integrity,
                        temperature: (evt.measurements?.temperatureCelsius ?? 24).toFixed(1) + ' °C',
                        humidity: (evt.measurements?.relativeHumidityPercent ?? 50).toFixed(1) + ' %',
                        battery: (evt.measurements?.batteryVoltageMv ?? 4120) + ' mV',
                        anomalyScore: ((evt.analytics?.anomalyScore ?? 0) * 100).toFixed(1) + '%',
                        anomalyReasons: (evt.analytics?.anomalyReasons || []).join('; ') || 'None',
                        isQuarantined: isQuarantined ? 'YES (ISOLATED)' : 'NO',
                        timestamp: new Date(evt.timestamp).toISOString()
                    }
                });

                // Add ground perimeter reticle
                ds.entities.add({
                    id: `${entityId}-ring`,
                    position: Cesium.Cartesian3.fromDegrees(lon, lat, 0),
                    ellipse: {
                        semiMajorAxis: 2500.0,
                        semiMinorAxis: 2500.0,
                        material: color.withAlpha(0.18),
                        height: 0
                    }
                });
            }
        });

        const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id) && !currentIds.has(e.id.replace('-ring', '')));
        toRemove.forEach(e => ds.entities.remove(e));

        this.viewer.scene.requestRender();
    }

    /**
     * Updates and visualizes Active Cyber-Physical Incidents.
     * @param {Array<Object>} incidents
     */
    updateArgusIncidents(incidents) {
        if (!this.viewer || !this.dataSources.argusIncidents) return;
        const ds = this.dataSources.argusIncidents;
        const activeIds = new Set();

        incidents.forEach(inc => {
            if (!inc.centroid || inc.status === 'RESOLVED') return;
            const entityId = `argus-inc-${inc.incidentId}`;
            activeIds.add(entityId);

            const isContained = inc.status === 'CONTAINED';
            const colorHex = isContained ? '#BC13FE' : inc.severity === 'CRITICAL' ? '#FF0055' : '#FFCC00';
            const color = Cesium.Color.fromCssColorString(colorHex);
            const position = Cesium.Cartesian3.fromDegrees(inc.centroid.longitude, inc.centroid.latitude, 0);

            let entity = ds.entities.getById(entityId);
            if (entity) {
                if (entity.ellipse) {
                    entity.ellipse.material = color.withAlpha(0.25);
                }
                if (entity.label) {
                    entity.label.text = `🚨 INCIDENT ${inc.incidentId} [${inc.status}]`;
                    entity.label.fillColor = color;
                }
            } else {
                ds.entities.add({
                    id: entityId,
                    name: `INCIDENT: ${inc.incidentId} - ${inc.title}`,
                    position: position,
                    ellipse: {
                        semiMajorAxis: 8000.0,
                        semiMinorAxis: 8000.0,
                        material: color.withAlpha(0.22),
                        height: 0
                    },
                    label: {
                        text: `🚨 INCIDENT ${inc.incidentId} [${inc.status}]`,
                        font: 'bold 13px "Orbitron", sans-serif',
                        fillColor: color,
                        outlineColor: Cesium.Color.BLACK,
                        outlineWidth: 3,
                        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                        pixelOffset: new Cesium.Cartesian2(0, -20)
                    },
                    properties: {
                        incidentId: inc.incidentId,
                        title: inc.title,
                        severity: inc.severity,
                        status: inc.status,
                        primaryNodeId: inc.primaryNodeId,
                        confidenceScore: (inc.confidenceScore * 100).toFixed(1) + '%',
                        integrityViolations: (inc.evidence?.integrityViolations || []).join(', ') || 'None',
                        anomalyReasons: (inc.evidence?.anomalyReasons || []).join('; ') || 'None',
                        quarantined: inc.quarantined ? 'YES' : 'NO'
                    }
                });
            }
        });

        const toRemove = ds.entities.values.filter(e => !activeIds.has(e.id));
        toRemove.forEach(e => ds.entities.remove(e));

        this.viewer.scene.requestRender();
    }

    /**
     * Loads and visualizes global ARGUS landmarks on the 3D globe.
     * @param {string|null} category
     */
    async loadArgusLandmarks(category = null) {
        if (!this.viewer || !this.dataSources.argusLandmarks) return;
        const ds = this.dataSources.argusLandmarks;
        ds.entities.removeAll();

        const url = category && category !== 'ALL'
            ? `/api/argus/places/geojson?category=${encodeURIComponent(category)}`
            : '/api/argus/places/geojson';

        try {
            const res = await fetch(url);
            if (!res.ok) return;
            const geojson = await res.json();
            const features = geojson.features || [];

            features.forEach(feat => {
                const props = feat.properties || {};
                const [lon, lat] = feat.geometry.coordinates;
                const entityId = `argus-lm-${props.place_id}`;
                const icon = this._makeIcon(props.icon || '🏛️', 36);

                ds.entities.add({
                    id: entityId,
                    name: props.name,
                    position: Cesium.Cartesian3.fromDegrees(lon, lat, 20),
                    billboard: {
                        image: icon,
                        width: 24,
                        height: 24,
                        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 5000000)
                    },
                    label: {
                        text: props.name,
                        font: 'bold 11px "Share Tech Mono", monospace',
                        fillColor: Cesium.Color.fromCssColorString(props.color || '#FFD700'),
                        outlineColor: Cesium.Color.BLACK,
                        outlineWidth: 2,
                        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                        verticalOrigin: Cesium.VerticalOrigin.TOP,
                        pixelOffset: new Cesium.Cartesian2(0, 4),
                        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 1500000)
                    },
                    properties: {
                        ...props,
                        isArgusLandmark: true,
                        targetType: 'ARGUS_LANDMARK',
                        targetName: props.name,
                        category: props.category_label || props.category,
                        location: `${props.city ? props.city + ', ' : ''}${props.country || ''}`,
                        coordinates: `${lat.toFixed(5)}°N, ${lon.toFixed(5)}°E`,
                        imagesCount: props.images_count,
                        thumbnailUrl: props.thumbnail_url,
                        wikidataId: props.wikidata_id,
                        osmId: props.osm_id
                    }
                });
            });

            this.viewer.scene.requestRender();
            console.log(`[Globe] Loaded ${features.length} ARGUS landmarks.`);
        } catch (err) {
            console.error('[Globe] Failed to load ARGUS landmarks:', err);
        }
    }

    /**
     * Toggles visibility of the ARGUS landmarks data source.
     * @param {boolean} visible
     */
    toggleArgusLandmarks(visible) {
        if (!this.dataSources.argusLandmarks) return;
        this.dataSources.argusLandmarks.show = visible;
        if (visible && this.dataSources.argusLandmarks.entities.values.length === 0) {
            this.loadArgusLandmarks();
        }
        if (this.viewer) this.viewer.scene.requestRender();
    }

    // ═══════════════════════════════════════════════
    //  RAINVIEWER — Real Doppler Weather Radar Tiles
    // ═══════════════════════════════════════════════
    addRainViewerLayer(path, host = 'https://tilecache.rainviewer.com') {
        if (!this.viewer) return;
        // Remove any existing RainViewer layer
        if (this._rainViewerLayer) {
            this.viewer.imageryLayers.remove(this._rainViewerLayer, true);
            this._rainViewerLayer = null;
        }
        if (!path) return;

        const cleanHost = (host || 'https://tilecache.rainviewer.com').replace(/\/+$/, '');
        let cleanPath = String(path || '').trim();
        if (!cleanPath.startsWith('/')) cleanPath = '/' + cleanPath;
        if (!cleanPath.startsWith('/v2/radar/')) {
            cleanPath = `/v2/radar${cleanPath}`;
        }
        const tileUrl = `${cleanHost}${cleanPath}/512/{z}/{x}/{y}/2/1_1.png`;
        try {
            this._rainViewerLayer = this.viewer.imageryLayers.addImageryProvider(
                new Cesium.UrlTemplateImageryProvider({
                    url: tileUrl,
                    credit: 'RainViewer.com',
                    tilingScheme: new Cesium.WebMercatorTilingScheme(),
                    tileWidth: 512,
                    tileHeight: 512,
                    minimumLevel: 0,
                    maximumLevel: 10,
                    hasAlphaChannel: true
                })
            );
            this._rainViewerLayer.alpha = 0.75;
            this._rainViewerLayer.brightness = 1.2;
            if (this.viewer.imageryLayers.raiseToTop) {
                this.viewer.imageryLayers.raiseToTop(this._rainViewerLayer);
            }
            this.viewer.scene.requestRender();
            console.log('[Globe] RainViewer layer added:', tileUrl);
        } catch (e) {
            console.warn('[Globe] RainViewer layer error:', e.message);
        }
    }

    removeRainViewerLayer() {
        if (this._rainViewerLayer && this.viewer) {
            this.viewer.imageryLayers.remove(this._rainViewerLayer, true);
            this._rainViewerLayer = null;
            this.viewer.scene.requestRender();
        }
    }

    // ═══════════════════════════════════════════════
    //  EMERGENCY SQUAWKS — Pulsing Red Halos for 7500/7600/7700
    // ═══════════════════════════════════════════════
    updateEmergencySquawks(squawks) {
        if (!this.viewer) return;
        // Use 'flights' data source but tag emergency aircraft with pulsing red halos
        // We do this by adding ellipses around squawk aircraft in a dedicated source
        if (!this.dataSources.squawks) {
            this.dataSources.squawks = new Cesium.CustomDataSource('squawks');
            this.viewer.dataSources.add(this.dataSources.squawks);
        }
        const ds = this.dataSources.squawks;
        const currentIds = new Set();

        squawks.forEach(ac => {
            const lon = ac.longitude ?? ac.long ?? ac.lon;
            const lat = ac.latitude ?? ac.lat;
            const alt = ac.altitude ?? ac.alt ?? 10000;
            if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;
            const id = `sq-${ac.icao24}`;
            currentIds.add(id);
            const position = Cesium.Cartesian3.fromDegrees(lon, lat, alt);
            const sq = String(ac.squawk || '');
            const isHijack = sq === '7500';
            const color = isHijack
                ? Cesium.Color.fromCssColorString('#ff0000')
                : Cesium.Color.fromCssColorString('#ff8800');
            const ringRadius = 80000; // 80 km visible halo

            let entity = ds.entities.getById(id);
            if (entity) {
                entity.position = position;
            } else {
                ds.entities.add({
                    id: id,
                    name: `🚨 SQUAWK ${sq} — ${ac.squawk_meaning || 'EMERGENCY'} — ${ac.callsign || ac.icao24}`,
                    position: position,
                    ellipse: {
                        semiMinorAxis: ringRadius,
                        semiMajorAxis: ringRadius,
                        material: color.withAlpha(0.25),
                        outlineColor: color,
                        outline: true,
                        outlineWidth: 3,
                        height: alt
                    },
                    properties: {
                        squawk: sq,
                        squawk_meaning: ac.squawk_meaning || 'EMERGENCY',
                        callsign: ac.callsign || ac.icao24,
                        alert_level: ac.alert_level || 'HIGH',
                        altitude: Math.round(alt),
                        velocity: Math.round(ac.velocity || 0),
                        heading: Math.round(ac.heading || 0)
                    }
                });
            }
        });

        const toRemove = ds.entities.values.filter(e => !currentIds.has(e.id));
        toRemove.forEach(e => ds.entities.remove(e));
        this.viewer.scene.requestRender();

        if (squawks.length > 0) {
            console.warn(`[Globe] ${squawks.length} emergency squawk(s) active!`, squawks.map(a => `${a.callsign} SQUAWK ${a.squawk}`));
        }
    }

    // ═══════════════════════════════════════════════
    //  3D TACTICAL AIR SURVEILLANCE RADAR
    // ═══════════════════════════════════════════════

    setAirRadarMode(enabled) {
        if (!this._airRadar) return;
        this._airRadar.enabled = enabled;

        if (this.dataSources.airRadar) {
            this.dataSources.airRadar.show = false;
            this.dataSources.airRadar.entities.removeAll();
        }

        if (enabled) {
            // Ensure flights layer is visible on the 3D globe
            if (this.dataSources.flights) {
                this.dataSources.flights.show = true;
            }
            this.renderAirRadarHubOverlays();
        } else {
            this._stopRadarAnimation();
            this.stopChaseCam();
        }

        if (this._lastFlightsData && this._lastFlightsData.length > 0) {
            this.updateFlights(this._lastFlightsData);
        }
        this.viewer.scene.requestRender();
    }

    renderAirRadarHubOverlays() {
        // Radar display is rendered in the sleek Top-Right Tactical Radar Scope HUD
        if (this.dataSources.airRadar) {
            this.dataSources.airRadar.entities.removeAll();
        }
    }

    setAirRadarHub(hubKey) {
        const hub = RADAR_HUBS[hubKey];
        if (!hub) return;
        this._airRadar.activeHub = hubKey;
        this._airRadar.centerLat = hub.lat;
        this._airRadar.centerLon = hub.lon;
    }

    startChaseCam(icao24) {
        if (!this.viewer || !this.dataSources.flights) return false;
        const entity = this.dataSources.flights.entities.getById(icao24);
        if (!entity) return false;
        this._airRadar.chaseEntity = entity;
        this.viewer.trackedEntity = entity;
        return true;
    }

    stopChaseCam() {
        this._airRadar.chaseEntity = null;
        if (this.viewer) {
            this.viewer.trackedEntity = undefined;
        }
    }

    interceptFlight(icao24) {
        if (!this.viewer || !this.dataSources.flights) return false;
        const entity = this.dataSources.flights.entities.getById(icao24);
        if (!entity) return false;
        const pos = entity.position.getValue(this.viewer.clock.currentTime);
        if (!pos) return false;
        const carto = Cesium.Cartographic.fromCartesian(pos);
        const lon = Cesium.Math.toDegrees(carto.longitude);
        const lat = Cesium.Math.toDegrees(carto.latitude);
        const alt = carto.height;

        this.viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(lon, lat - 0.08, alt + 3500),
            orientation: {
                heading: Cesium.Math.toRadians(0),
                pitch: Cesium.Math.toRadians(-25),
                roll: 0
            },
            duration: 2.0,
            easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT
        });
        return true;
    }

    _startRadarAnimation() {
        if (this._airRadar.animFrame) return;
        const animate = () => {
            if (!this._airRadar.enabled) {
                this._airRadar.animFrame = null;
                return;
            }
            if (this._airRadar.sweepEnabled) {
                this._airRadar.sweepAngle = (this._airRadar.sweepAngle + 0.8) % 360;
            }
            if (this.viewer && this.viewer.scene && !this.viewer.isDestroyed()) {
                this.viewer.scene.requestRender();
            }
            this._airRadar.animFrame = requestAnimationFrame(animate);
        };
        this._airRadar.animFrame = requestAnimationFrame(animate);
    }

    _stopRadarAnimation() {
        if (this._airRadar.animFrame) {
            cancelAnimationFrame(this._airRadar.animFrame);
            this._airRadar.animFrame = null;
        }
    }

    // ═══════════════════════════════════════════════
    //  LIVE WINDOW CONTACT EXTRACTION FOR RADAR
    // ═══════════════════════════════════════════════
    getVisibleContactsInWindow() {
        if (!this.viewer || !this.viewer.scene) {
            return { contacts: [], rangeNM: 150, headingDeg: 0, centerLat: 0, centerLon: 0, counts: { air: 0, sea: 0, sat: 0, tactical: 0, total: 0 } };
        }

        const scene = this.viewer.scene;
        const camera = this.viewer.camera;
        const canvas = this.viewer.canvas;
        const clientW = canvas.clientWidth || 1920;
        const clientH = canvas.clientHeight || 1080;

        // 1. Raycast ground coordinate at center of window
        const centerWin = new Cesium.Cartesian2(clientW / 2, clientH / 2);
        const centerRay = camera.getPickRay(centerWin);
        let centerCartesian = scene.globe.pick(centerRay, scene);
        if (!centerCartesian) {
            centerCartesian = camera.pickEllipsoid(centerWin, scene.globe.ellipsoid);
        }

        let centerLat = 0, centerLon = 0;
        if (centerCartesian) {
            const carto = Cesium.Cartographic.fromCartesian(centerCartesian);
            centerLat = Cesium.Math.toDegrees(carto.latitude);
            centerLon = Cesium.Math.toDegrees(carto.longitude);
        } else {
            const camCarto = camera.positionCartographic;
            centerLat = Cesium.Math.toDegrees(camCarto.latitude);
            centerLon = Cesium.Math.toDegrees(camCarto.longitude);
        }

        // 2. Window range in NM (from center to right edge of screen)
        const edgeWin = new Cesium.Cartesian2(clientW, clientH / 2);
        const edgeRay = camera.getPickRay(edgeWin);
        let edgeCartesian = scene.globe.pick(edgeRay, scene);
        if (!edgeCartesian) {
            edgeCartesian = camera.pickEllipsoid(edgeWin, scene.globe.ellipsoid);
        }
        let rangeNM = 150;
        if (centerCartesian && edgeCartesian) {
            const distM = Cesium.Cartesian3.distance(centerCartesian, edgeCartesian);
            rangeNM = Math.max(15, Math.min(3500, Math.round(distM / 1852.0)));
        } else {
            const camH = (camera.positionCartographic.height || 1000000) / 1000.0;
            rangeNM = Math.max(25, Math.min(3500, Math.round(camH * 0.42)));
        }

        // 3. Camera Heading (degrees)
        const headingDeg = Cesium.Math.toDegrees(camera.heading);

        // 4. Occlusion and Viewport Filtering
        const occluder = new Cesium.EllipsoidalOccluder(scene.globe.ellipsoid, camera.position);
        const cameraPos = camera.positionWC;
        const cameraDir = camera.direction;
        const now = Cesium.JulianDate.now();

        const scratchToPos = new Cesium.Cartesian3();
        const contacts = [];
        const counts = { air: 0, sea: 0, sat: 0, tactical: 0, total: 0 };

        const layerKeys = [
            'flights', 'vessels', 'satellites',
            'military', 'nuclear', 'conflicts',
            'hotspots', 'cctv', 'earthquakes', 'naturalEvents'
        ];

        for (const key of layerKeys) {
            const ds = this.dataSources[key];
            if (!ds || ds.show === false) continue;

            const entities = ds.entities.values;
            const len = entities.length;
            for (let i = 0; i < len; i++) {
                const ent = entities[i];
                if (ent.show === false) continue;

                let pos = null;
                if (ent.position) {
                    pos = ent.position.getValue ? ent.position.getValue(now) : ent.position;
                }
                if (!pos) continue;

                // Check if in front of camera plane
                Cesium.Cartesian3.subtract(pos, cameraPos, scratchToPos);
                if (Cesium.Cartesian3.dot(cameraDir, scratchToPos) <= 0) continue;

                // Check if behind globe curvature (occluded)
                if (!occluder.isPointVisible(pos)) continue;

                // Screen coordinates
                const winPos = Cesium.SceneTransforms.wgs84ToWindowCoordinates(scene, pos);
                if (!winPos) continue;

                // STRICT: Must be inside current window bounds
                if (winPos.x < 0 || winPos.x > clientW || winPos.y < 0 || winPos.y > clientH) continue;

                // Extract properties
                const props = {};
                if (ent.properties) {
                    ent.properties.propertyNames.forEach(pn => {
                        const val = ent.properties[pn];
                        props[pn] = val?.getValue ? val.getValue() : val;
                    });
                }

                const carto = Cesium.Cartographic.fromCartesian(pos);
                const lat = Cesium.Math.toDegrees(carto.latitude);
                const lon = Cesium.Math.toDegrees(carto.longitude);

                // Determine classification
                let layerCategory = 'tactical';
                if (key === 'flights') {
                    layerCategory = 'air';
                    counts.air++;
                } else if (key === 'vessels') {
                    layerCategory = 'sea';
                    counts.sea++;
                } else if (key === 'satellites') {
                    layerCategory = 'sat';
                    counts.sat++;
                } else {
                    layerCategory = 'tactical';
                    counts.tactical++;
                }
                counts.total++;

                contacts.push({
                    id: ent.id,
                    layer: key,
                    category: layerCategory,
                    name: ent.name || props.callsign || props.name || props.icao24 || ent.id,
                    callsign: props.callsign || ent.name || ent.id,
                    icao24: props.icao24 || ent.id,
                    type: props.type || (key === 'vessels' ? 'vessel' : key === 'satellites' ? 'satellite' : key),
                    latitude: lat,
                    longitude: lon,
                    altitude: carto.height,
                    heading: props.heading ?? props.course ?? 0,
                    velocity: props.velocity ?? props.speed ?? 0,
                    squawk: props.squawk ?? '',
                    winX: winPos.x,
                    winY: winPos.y,
                    winNormX: (winPos.x - clientW / 2) / (clientW / 2),
                    winNormY: (winPos.y - clientH / 2) / (clientH / 2),
                    cartesian: pos
                });
            }
        }

        return {
            centerLat,
            centerLon,
            rangeNM,
            headingDeg,
            contacts,
            counts
        };
    }

    // ═══════════════════════════════════════════════
    //  SPACE WEATHER — Visual Kp index overlay
    // ═══════════════════════════════════════════════
    updateSpaceWeatherAlert(data) {
        const el = document.getElementById('space-weather-hud');
        if (!el) return;
        const kp = data.kp_index;
        const level = data.storm_level || 'G0';
        const color = level === 'G5' ? '#ff0000' : level === 'G4' ? '#ff3300' :
                      level === 'G3' ? '#ff7700' : level === 'G2' ? '#ffaa00' :
                      level === 'G1' ? '#ffff00' : '#00d4aa';
        el.innerHTML = `☀️ KP: ${kp !== null ? kp.toFixed(1) : '--'} | ${level} ${data.alerts?.length > 0 ? '⚠️ ' + data.alerts.length + ' ALERT(S)' : ''}`;
        el.style.color = color;
        el.style.display = 'block';
    }
}

