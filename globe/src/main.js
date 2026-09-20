// globe/src/main.js

import { Terra5Globe } from './globe.js';

import { APIService } from './services/api.js';

import { MockService } from './services/mock.js'; // Used only for PANOPTIC detection overlay

import { MAP_DATA } from './services/mapData.js';

import { signalAggregator } from './services/signalAggregator.js';
import { RadarScope } from './radarScope.js';
import { globeCache } from './services/globeCache.js';

class AppController {

  constructor() {

    this.globe = new Terra5Globe('cesiumContainer');

    this.timers = {};

    this._isCinemaRunning = false;
    this.state = {

      layers: {

        flights: true, vessels: false, satellites: false, earthquakes: false, weather: false, cctv: false,

        nuclear: false, military: true, conflicts: true,

        hotspots: false, waterways: false, cables: false,

        naturalEvents: false, wildfires: false, weatherAlerts: false,

        spaceports: false, economic: false, argusLandmarks: false

      },

      mode: 'normal',

      sidebarOpen: true,

      panopticEnabled: false,

      airRadarOpen: false,

      camera: { lat: 38.9072, lon: -77.0369, alt: 10000000 }

    };

    this._lockedAircraft = null;
    this.radarScope = null;

    // DOM Elements

    this.ui = {

      sidebar: document.getElementById('sidebar'),

      btnToggleSidebar: document.getElementById('toggle-sidebar-btn'),

      deg: document.getElementById('hud-deg'),

      mgrs: document.getElementById('hud-mgrs'),

      gsd: document.getElementById('hud-gsd'),

      niirs: document.getElementById('hud-niirs'),

      altM: document.getElementById('hud-alt-m'),

      timestamp: document.getElementById('recording-timestamp'),

      layerBtns: document.querySelectorAll('.toggle-btn'),

      modeBtns: document.querySelectorAll('.mode-btn'),

      cityBtns: document.querySelectorAll('.city-btn'),

      counts: {

        flights: document.getElementById('count-flights'),

        vessels: document.getElementById('count-vessels'),

        satellites: document.getElementById('count-satellites'),

        earthquakes: document.getElementById('count-earthquakes'),

        weather: document.getElementById('count-weather'),

        cctv: document.getElementById('count-cctv'),

        nuclear: document.getElementById('count-nuclear'),

        military: document.getElementById('count-military'),

        conflicts: document.getElementById('count-conflicts'),

        hotspots: document.getElementById('count-hotspots'),

        waterways: document.getElementById('count-waterways'),

        cables: document.getElementById('count-cables'),

        naturalEvents: document.getElementById('count-naturalEvents'),

        wildfires: document.getElementById('count-wildfires'),

        weatherAlerts: document.getElementById('count-weatherAlerts'),

        spaceports: document.getElementById('count-spaceports'),

        economic: document.getElementById('count-economic'),

        argusLandmarks: document.getElementById('count-argusLandmarks')

      },

      targetDetails: document.getElementById('target-details'),

      targetContent: document.getElementById('target-content'),

      closeTargetBtn: document.getElementById('close-target-btn'),

      cctvPopup: document.getElementById('cctv-popup'),

      cctvClose: document.querySelector('.cctv-close'),

      cctvId: document.getElementById('cctv-id'),

      cctvName: document.getElementById('cctv-name'),

      status: document.getElementById('status-text'),

      // New Elements

      btnPizzint: document.getElementById('btn-pizzint'),

      pizzintPanel: document.getElementById('pizzint-panel'),

      closePizzintBtn: document.getElementById('close-pizzint-btn'),

      btnLiveNews: document.getElementById('btn-live-news'),

      newsFeedPanel: document.getElementById('news-feed-panel'),

      closeNewsBtn: document.getElementById('close-news-btn'),

      newsBtns: document.querySelectorAll('.news-btn'),

      newsIframe: document.getElementById('news-iframe'),

      aiInsightsText: document.getElementById('ai-insights-text'),

      // Phase 3 New Elements

      btnIntelFeed: document.getElementById('btn-intel-feed'),

      intelFeedPanel: document.getElementById('intel-feed-panel'),

      closeIntelFeed: document.getElementById('close-intel-feed'),

      intelFeedList: document.getElementById('intel-feed-list'),

      breakingNewsTicker: document.getElementById('breaking-news-ticker'),

      tickerText: document.getElementById('ticker-text'),

      worldClock: document.getElementById('world-clock'),

      clockDC: document.getElementById('clock-dc'),

      clockLON: document.getElementById('clock-lon'),

      clockMSK: document.getElementById('clock-msk'),

      clockBEJ: document.getElementById('clock-bej'),

      clockTKY: document.getElementById('clock-tky'),

      // New layer counts

      countHotspots: document.getElementById('count-hotspots'),

      countWaterways: document.getElementById('count-waterways'),

      countCables: document.getElementById('count-cables'),

      countNaturalEvents: document.getElementById('count-naturalEvents'),

      countWildfires: document.getElementById('count-wildfires'),

      countWeatherAlerts: document.getElementById('count-weatherAlerts'),

      countSpaceports: document.getElementById('count-spaceports'),

      countEconomic: document.getElementById('count-economic'),

      countArgusLandmarks: document.getElementById('count-argusLandmarks'),

      // 3D Air Surveillance Radar Elements

      btnAirRadar: document.getElementById('btn-air-radar'),

      airRadarPanel: document.getElementById('air-radar-panel'),

      closeAirRadarBtn: document.getElementById('close-air-radar-btn'),

      toggleRadarSweep: document.getElementById('toggle-radar-sweep'),

      toggleRadarStems: document.getElementById('toggle-radar-stems'),

      toggleRadarEchoes: document.getElementById('toggle-radar-echoes'),

      toggleRadarVectors: document.getElementById('toggle-radar-vectors'),

      toggleRadarRings: document.getElementById('toggle-radar-rings'),

      radarHubBtns: document.querySelectorAll('.radar-hub-btn'),

      radarScaleBtns: document.querySelectorAll('.radar-scale-btn'),

      radarAltScaleLabel: document.getElementById('radar-alt-scale-label'),

      radarTargetBox: document.getElementById('radar-target-box'),

      radarTargetInfo: document.getElementById('radar-target-info'),

      radarBtnIntercept: document.getElementById('radar-btn-intercept'),

      radarBtnChase: document.getElementById('radar-btn-chase'),

      radarUnlockBtn: document.getElementById('radar-unlock-btn'),

      radarSquawksContainer: document.getElementById('radar-squawks-container'),

      radarSquawksList: document.getElementById('radar-squawks-list'),

      radarCounts: {

        total: document.getElementById('radar-count-total'),

        mil: document.getElementById('radar-count-mil'),

        comm: document.getElementById('radar-count-comm'),

        emg: document.getElementById('radar-count-emg'),

        defcon: document.getElementById('air-radar-defcon')

      }

    };

    this.lastAIUpdate = 0;

    this.intelFeedData = [];

  }

  async init() {

    this.loadSettings();

    this.syncAllButtonStates(); // Guarantee every button matches JS state before first interaction

    this.preloadAllCounts(); // Preload all 18 intelligence layer counts instantly

    // Initialize Globe

    this.globe.init();

    // Expose globe & viewer globally for ARGUS AI & HUD interaction
    if (typeof window !== 'undefined') {
      window.app = this;
      window.globe = this.globe;
      window.viewer = this.globe.viewer;
      window.globeCache = globeCache;

      // Register offline map & radar tile Service Worker cache
      if ('serviceWorker' in navigator && (window.location.protocol === 'http:' || window.location.protocol === 'https:')) {
        navigator.serviceWorker.register('/static/sw-globe-cache.js', { scope: '/' })
          .then(reg => {
            console.log('[Globe Cache SW] Registered successfully, scope:', reg.scope);
          })
          .catch(() => {
            navigator.serviceWorker.register('./sw-globe-cache.js')
              .catch(err => console.warn('[Globe Cache SW] Registration fallback failed:', err.message));
          });
      }
    }

    // Check for URL coordinates navigation (?lat=...&lon=...&alt=...)

    const urlParams = new URLSearchParams(window.location.search);

    const latParam = parseFloat(urlParams.get('lat'));

    const lonParam = parseFloat(urlParams.get('lon') || urlParams.get('lng'));

    const altParam = parseFloat(urlParams.get('alt')) || 45000;

    if (!isNaN(latParam) && !isNaN(lonParam)) {

      console.log(`[3D Globe] Navigating to URL coordinates: ${latParam}, ${lonParam}, alt: ${altParam}`);

      setTimeout(() => {

        this.globe.flyTo(latParam, lonParam, altParam, 2);

      }, 700);

    }

    // Initialize Top-Right Tactical Air & Multi-Domain Radar Scope (Window-Synchronized PPI)
    const radarCanvas = document.getElementById('air-radar-canvas');
    if (radarCanvas) {
      this.radarScope = new RadarScope(radarCanvas, {
        rangeNM: 150,
        centerLat: 20.0,
        centerLon: 78.0,
        centerLabel: 'WINDOW VIEW',
        mode: 'view',
        onContactSelect: (c) => {
          this._lockedAircraft = c;
          this.onEntityClick(c);
          const box = document.getElementById('radar-target-box');
          const info = document.getElementById('radar-target-info');
          if (box && info) {
            box.style.display = 'block';
            const rawAlt = c.altitude || 0;
            const altM = Math.round(rawAlt * 0.3048);
            const domain = (c.category || c.layer || 'CONTACT').toUpperCase();
            info.innerHTML = `
              <div style="font-weight:bold; color:#00ffd1; font-size:11px; margin-bottom:2px;">
                🎯 ${(c.callsign || c.name || c.icao24 || 'TARGET').toUpperCase()} [${domain}]
              </div>
              <div><strong>TYPE:</strong> ${c.type || 'N/A'} &nbsp;|&nbsp; <strong>ALT:</strong> ${rawAlt ? rawAlt.toLocaleString() + ' ft' : 'SFC'}</div>
              <div><strong>SPD:</strong> ${c.velocity || 0} km/h &nbsp;|&nbsp; <strong>HDG:</strong> ${Math.round(c.heading || 0)}° &nbsp;|&nbsp; <strong>SQ:</strong> ${c.squawk || '----'}</div>
            `;
          }
          const lat = c.latitude ?? c.lat;
          const lon = c.longitude ?? c.lon;
          if (Number.isFinite(lat) && Number.isFinite(lon)) {
            this.globe.flyTo(lat, lon, 35000, 2);
          }
        }
      });
    }

        // Toggle AI Insights panel collapse/expand
    const btnCollapseAi = document.getElementById('toggle-ai-collapse-btn');
    const aiText = document.getElementById('ai-insights-text');
    if (btnCollapseAi && aiText) {
      btnCollapseAi.addEventListener('click', (e) => {
        e.stopPropagation();
        const isCollapsed = aiText.style.display === 'none';
        aiText.style.display = isCollapsed ? 'block' : 'none';
        btnCollapseAi.textContent = isCollapsed ? '[-]' : '[+]';
      });
    }

    // Auto-launch 3D Air Surveillance Radar if ?radar=1 or ?airradar=1 in URL

    if (urlParams.get('radar') === '1' || urlParams.get('airradar') === '1') {

      setTimeout(() => {

        this.toggleAirRadar(true);

      }, 900);

    }

    // Restore Visual Mode

    this.globe.setVisualMode(this.state.mode);

    this.updateModeUI(this.state.mode);

    // Setup Callbacks

    this.globe.onCameraChange = (cam) => this.onCameraChange(cam);

    this.globe.onEntityClick = (props) => this.onEntityClick(props);

    this.globe.onMapClick = (pos) => {

      this.updateAIInsights(pos, true);

    };

    this.globe.onMouseMove = (pos) => {

      const now = Date.now();

      if (now - this.lastAIUpdate > 150) { // 150ms throttle

        this.updateAIInsights(pos, false);

        this.lastAIUpdate = now;

      }

    };

    // Bind Events

    this.bindEvents();

    // Start Clocks

    setInterval(() => this.updateClock(), 1000);

    this.updateClock();

    // Initial Data Fetch — only fetches layers that are currently ON

    await this.fetchAllData();

    // Setup Page Visibility & Multi-Tab Memory Management
    this.setupPageVisibilityController();
    this.setupMultiTabDetector();

    // Start Timers
    this.startPollingTimers();

    // World clock

    setInterval(() => this.updateWorldClock(), 1000);

    this.updateWorldClock();

    // Initial intel feed

    this.refreshIntelFeed();

    // Initial market ticker, squawks, and space weather (no-wait)

    setTimeout(() => this._fetchMarketTicker(), 2000);

    setTimeout(() => this._fetchSpaceWeather(), 3000);

    setTimeout(() => this._fetchEmergencySquawks(), 5000);

    // Start PANOPTIC Real Entity HUD Tracking
    setInterval(() => {
      if (this.state.panopticEnabled) {
        const dets = MockService.generateDetections(this.globe, this.state.camera.lat, this.state.camera.lon);
        MockService.renderDetectionsUI(dets);
      } else {
        MockService.clearDetectionsUI();
      }
    }, 2000);

    // Fly to saved position

    if (this.state.camera.lat) {
      this.globe.flyTo(this.state.camera.lat, this.state.camera.lon, this.state.camera.alt, 0);
    }
  }

  startPollingTimers() {
    this.stopPollingTimers();
    this.timers.flights = setInterval(() => this.fetchLayer('flights'), 15000);
    this.timers.vessels = setInterval(() => this.fetchLayer('vessels'), 20000);
    this.timers.satellites = setInterval(() => this.fetchLayer('satellites'), 60000);
    this.timers.earthquakes = setInterval(() => this.fetchLayer('earthquakes'), 300000);
    this.timers.weather = setInterval(() => this.fetchLayer('weather'), 300000);
    this.timers.cctv = setInterval(() => this.fetchLayer('cctv'), 60000);
    this.timers.naturalEvents = setInterval(() => this.fetchLayer('naturalEvents'), 600000);
    this.timers.wildfires = setInterval(() => this.fetchLayer('wildfires'), 900000);
    this.timers.weatherAlerts = setInterval(() => this.fetchLayer('weatherAlerts'), 300000);
    this.timers.intelFeed = setInterval(() => this.refreshIntelFeed(), 300000);
    this.timers.squawks = setInterval(() => this._fetchEmergencySquawks(), 20000);
    this.timers.market = setInterval(() => this._fetchMarketTicker(), 300000);
    this.timers.spaceWeather = setInterval(() => this._fetchSpaceWeather(), 300000);
    console.log('[Telemetry] Polling timers active');
  }

  stopPollingTimers() {
    Object.keys(this.timers).forEach(k => {
      if (this.timers[k]) {
        clearInterval(this.timers[k]);
        this.timers[k] = null;
      }
    });
    console.log('[Telemetry] Polling timers suspended');
  }

  setupPageVisibilityController() {
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        console.log('[Visibility] Tab inactive/hidden — sleeping polling timers & trimming memory');
        this.stopPollingTimers();
        if (this.radarScope && this.radarScope.isRunning) {
          this._wasRadarRunning = true;
          this.radarScope.stop();
        }
        if (this.globe && typeof this.globe.pruneMemory === 'function') {
          this.globe.pruneMemory();
        }
      } else {
        console.log('[Visibility] Tab active — resuming telemetry uplink');
        this.startPollingTimers();
        if (this._wasRadarRunning && this.radarScope && this.state.airRadarOpen) {
          this._wasRadarRunning = false;
          this.radarScope.start();
          this.syncRadarWithCurrentWindow();
        }
        this.fetchAllData();
        if (this.globe && this.globe.viewer) {
          this.globe.viewer.scene.requestRender();
        }
      }
    });

    // Periodic memory trimming (every 60s) to keep browser heap lean
    setInterval(() => {
      if (this.globe && typeof this.globe.pruneMemory === 'function') {
        this.globe.pruneMemory();
      }
    }, 60000);
  }

  setupMultiTabDetector() {
    if (typeof BroadcastChannel !== 'undefined') {
      try {
        const channel = new BroadcastChannel('geovigilant_tab_detector');
        channel.postMessage({ type: 'PING_EXISTING_TABS' });
        channel.onmessage = (e) => {
          if (e.data && e.data.type === 'PING_EXISTING_TABS') {
            channel.postMessage({ type: 'TAB_ACTIVE' });
          } else if (e.data && e.data.type === 'TAB_ACTIVE') {
            console.warn('[Memory] Multiple GeoVigilant 3D tabs detected. Multiple tabs multiply WebGL RAM usage.');
            if (this.ui && this.ui.status) {
              this.ui.status.textContent = 'NOTE: MULTIPLE 3D TABS DETECTED — CLOSE EXTRA TABS TO SAVE 2-3 GB RAM';
            }
          }
        };
      } catch (_) {}
    }
  }

  bindEvents() {

    // Prevent Context Menu (Right Click)

    document.addEventListener('contextmenu', (e) => e.preventDefault());

    // Sidebar Toggle

    this.ui.btnToggleSidebar.addEventListener('click', () => this.toggleSidebar());

    // Keyboard Shortcuts

    document.addEventListener('keydown', (e) => {

      // Block DevTools shortcuts: F12, Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+U

      if (

        e.key === 'F12' ||

        (e.ctrlKey && e.shiftKey && (e.key.toLowerCase() === 'i' || e.key.toLowerCase() === 'j' || e.key.toLowerCase() === 'c')) ||

        (e.ctrlKey && e.key.toLowerCase() === 'u')

      ) {

        e.preventDefault();

        return;

      }

      if (e.metaKey || e.ctrlKey) {

        if (e.key === '[') {

          e.preventDefault();

          this.toggleSidebar();

        } else if (!e.shiftKey && e.key.toLowerCase() === 'p') {

          e.preventDefault();

          this.state.panopticEnabled = !this.state.panopticEnabled;

        }

      } else if (!e.altKey && e.key.toLowerCase() === 'r') {

        const tag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';

        if (tag !== 'input' && tag !== 'textarea') {

          e.preventDefault();

          this.toggleAirRadar();

        }

      }

    });

    // Layer Toggles

    this.ui.layerBtns.forEach(btn => {

      btn.addEventListener('click', (e) => {

        const layerDiv = e.target.closest('.layer-toggle');

        const layerName = layerDiv.dataset.layer;

        this.toggleLayer(layerName);

      });

    });

    // Visual Mode Toggles

    this.ui.modeBtns.forEach(btn => {

      btn.addEventListener('click', (e) => {

        const mode = e.target.dataset.mode;

        this.setMode(mode);

      });

    });

    // City Presets

    this.ui.cityBtns.forEach(btn => {

      btn.addEventListener('click', (e) => {

        const { lat, lon, alt } = e.target.dataset;

        this.globe.flyTo(parseFloat(lat), parseFloat(lon), parseFloat(alt));

      });

    });

    // Target Closure

    this.ui.closeTargetBtn.addEventListener('click', () => {

      this.ui.targetDetails.classList.add('hidden');

    });

    if (this.ui.cctvClose) {

      this.ui.cctvClose.addEventListener('click', () => {
        this.ui.cctvPopup.classList.add('hidden');
        // Stop snapshot polling and HUD timers on close
        clearInterval(this._snapTimer);
        this._snapTimer = null;
        clearInterval(this._cctvHudTimer);
        this._cctvHudTimer = null;
        const container = document.querySelector('.cctv-feed-container');
        if (container) container.innerHTML = '';
      });

    }

    // Real-time detection: YouTube iframe error listener to purge unplayable feeds immediately
    window.addEventListener('message', (event) => {
      const origin = event.origin || '';
      if (!origin.includes('youtube.com') && !origin.includes('youtube-nocookie.com')) {
        return;
      }
      try {
        let data = event.data;
        if (typeof data === 'string') {
          try { data = JSON.parse(data); } catch {}
        }
        if (!data) return;
        // YouTube onError codes: 101/150 (embed disabled by owner), 100 (deleted/private), 2 (invalid), 5 (HTML5 error)
        const isError = data.event === 'onError' ||
                        data.info === 101 || data.info === 150 || data.info === 100 ||
                        (data.event === 'infoDelivery' && data.info && data.info.playerState === -1 && data.info.errorCode);
        if (isError && this._currentCCTVId) {
          console.warn(`[CCTV] Stream playback restricted for ${this._currentCCTVId}. Removing node.`);
          this._removeDeadCamera(this._currentCCTVId, 'RESTRICTED PLAYBACK');
        }
      } catch {}
    });

    // PizzINT Events

    if (this.ui.btnPizzint) {

      this.ui.btnPizzint.addEventListener('click', () => {

        this.ui.pizzintPanel.classList.toggle('hidden');

      });

    }

    if (this.ui.closePizzintBtn) {

      this.ui.closePizzintBtn.addEventListener('click', () => {

        this.ui.pizzintPanel.classList.add('hidden');

      });

    }

    // News Events

    if (this.ui.btnLiveNews) {

      this.ui.btnLiveNews.addEventListener('click', () => {

        this.ui.newsFeedPanel.classList.toggle('hidden');

        if (!this.ui.newsFeedPanel.classList.contains('hidden') && !this.ui.newsIframe.src) {

          this.setNewsChannel('aljazeera');

        }

      });

    }

    if (this.ui.closeNewsBtn) {

      this.ui.closeNewsBtn.addEventListener('click', () => {

        this.ui.newsFeedPanel.classList.add('hidden');

      });

    }

    this.ui.newsBtns.forEach(btn => {

      btn.addEventListener('click', (e) => {

        this.setNewsChannel(e.target.dataset.channel);

      });

    });

    // Intel Feed Events

    if (this.ui.btnIntelFeed) {

      this.ui.btnIntelFeed.addEventListener('click', () => {

        this.ui.intelFeedPanel.classList.toggle('hidden');

        if (!this.ui.intelFeedPanel.classList.contains('hidden') && this.intelFeedData.length === 0) {

          this.refreshIntelFeed();

        }

      });

    }

    if (this.ui.closeIntelFeed) {
      this.ui.closeIntelFeed.addEventListener('click', () => {
        this.ui.intelFeedPanel.classList.add('hidden');
      });
    }

    // Allow dragging the INTEL RSS feed panel by its header
    if (this.ui.intelFeedPanel) {
      const feedHeader = this.ui.intelFeedPanel.querySelector('.intel-feed-header');
      if (feedHeader) {
        let isDragging = false;
        let startX = 0, startY = 0;
        let startLeft = 0, startTop = 0;

        feedHeader.addEventListener('mousedown', (e) => {
          if (e.target.tagName === 'BUTTON' || e.target.closest('button')) return;
          isDragging = true;
          const rect = this.ui.intelFeedPanel.getBoundingClientRect();
          startX = e.clientX;
          startY = e.clientY;
          startLeft = rect.left;
          startTop = rect.top;

          this.ui.intelFeedPanel.style.left = `${startLeft}px`;
          this.ui.intelFeedPanel.style.top = `${startTop}px`;
          this.ui.intelFeedPanel.style.right = 'auto';

          const onMouseMove = (ev) => {
            if (!isDragging) return;
            const dx = ev.clientX - startX;
            const dy = ev.clientY - startY;
            const newLeft = Math.max(10, Math.min(window.innerWidth - this.ui.intelFeedPanel.offsetWidth - 10, startLeft + dx));
            const newTop = Math.max(40, Math.min(window.innerHeight - this.ui.intelFeedPanel.offsetHeight - 10, startTop + dy));
            this.ui.intelFeedPanel.style.left = `${newLeft}px`;
            this.ui.intelFeedPanel.style.top = `${newTop}px`;
          };

          const onMouseUp = () => {
            isDragging = false;
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
          };

          document.addEventListener('mousemove', onMouseMove);
          document.addEventListener('mouseup', onMouseUp);
        });
      }
    }

    // Keyboard shortcuts for new features

    document.addEventListener('keydown', (e) => {

      if (e.key === 'Escape') {

        this.ui.intelFeedPanel?.classList.add('hidden');

        this.ui.pizzintPanel?.classList.add('hidden');

        this.ui.newsFeedPanel?.classList.add('hidden');

        this.ui.targetDetails?.classList.add('hidden');

        document.getElementById('presets-panel')?.classList.add('hidden');

        if (this.ui.cctvPopup && !this.ui.cctvPopup.classList.contains('hidden')) {
          this.ui.cctvPopup.classList.add('hidden');
          clearInterval(this._snapTimer);
          this._snapTimer = null;
          clearInterval(this._cctvHudTimer);
          this._cctvHudTimer = null;
          const container = document.querySelector('.cctv-feed-container');
          if (container) container.innerHTML = '';
        }
        if (this.state.airRadarOpen) this.toggleAirRadar(false);
      }

    });

    // ── Thermal / Eco Mode (Summer Cooling) ───────────────────────
    const btnThermalEco = document.getElementById('btn-thermal-eco');
    const urlParamsThermal = new URLSearchParams(window.location.search);
    const envMode = window.ARGUS_DEFAULT_MODE || 'eco';
    const hasPerfParam = urlParamsThermal.has('perf') || urlParamsThermal.get('mode') === 'perf' || urlParamsThermal.has('turbo') || (!urlParamsThermal.has('eco') && envMode === 'perf');
    this._ecoMode = !hasPerfParam; // Default TRUE (Eco 30 FPS) unless perf specified
    if (this.globe && typeof this.globe.setEcoMode === 'function') {
      this.globe.setEcoMode(this._ecoMode);
    }
    if (btnThermalEco) {
      if (!this._ecoMode) {
        btnThermalEco.innerHTML = '⚡ MAX: 60 FPS';
        btnThermalEco.style.color = '#f59e0b';
        btnThermalEco.style.borderColor = 'rgba(245,158,11,0.4)';
        btnThermalEco.style.background = 'rgba(245,158,11,0.15)';
      }
      btnThermalEco.addEventListener('click', () => {
        this._ecoMode = !this._ecoMode;
        if (this.globe && typeof this.globe.setEcoMode === 'function') {
          this.globe.setEcoMode(this._ecoMode);
        }
        if (this._ecoMode) {
          btnThermalEco.innerHTML = '❄️ ECO: 30 FPS';
          btnThermalEco.style.color = '#38bdf8';
          btnThermalEco.style.borderColor = 'rgba(56,189,248,0.4)';
          btnThermalEco.style.background = 'rgba(56,189,248,0.15)';
          if (this.ui.status) this.ui.status.textContent = 'THERMAL ECO MODE: ACTIVE (30 FPS // LOW HEAT)';
        } else {
          btnThermalEco.innerHTML = '⚡ MAX: 60 FPS';
          btnThermalEco.style.color = '#f59e0b';
          btnThermalEco.style.borderColor = 'rgba(245,158,11,0.4)';
          btnThermalEco.style.background = 'rgba(245,158,11,0.15)';
          if (this.ui.status) this.ui.status.textContent = 'PERFORMANCE MODE: ACTIVE (60 FPS)';
        }
      });
    }

    // ── Cinema Mode ─────────────────────────────────────────────

    const btnCinema = document.getElementById('btn-cinema');

    if (btnCinema) btnCinema.addEventListener('click', () => this._toggleCinema());

    // Manual camera override: clicking or wheeling halts automated Cinema tour
    const cesiumContainer = document.getElementById('cesiumContainer');
    if (cesiumContainer) {
      cesiumContainer.addEventListener('pointerdown', () => {
        if (this._isCinemaRunning || this._cinemaInterval) {
          this._toggleCinema(true);
        } else if (this.globe) {
          this.globe.cancelFlight();
        }
      });
      cesiumContainer.addEventListener('wheel', () => {
        if (this._isCinemaRunning || this._cinemaInterval) {
          this._toggleCinema(true);
        }
      }, { passive: true });
    }

    // ── Situational Presets ──────────────────────────────────────

    const btnPresets = document.getElementById('btn-presets');

    const presetsPanel = document.getElementById('presets-panel');

    const closePresetsBtn = document.getElementById('close-presets-btn');

    if (btnPresets && presetsPanel) {

      btnPresets.addEventListener('click', () => presetsPanel.classList.toggle('hidden'));

    }

    if (closePresetsBtn && presetsPanel) {

      closePresetsBtn.addEventListener('click', () => presetsPanel.classList.add('hidden'));

    }

    document.querySelectorAll('.preset-btn').forEach(btn => {

      btn.addEventListener('click', (e) => {

        const preset = e.target.dataset.preset;

        this._applyPreset(preset);

        presetsPanel?.classList.add('hidden');

      });

    });

    // ── RainViewer Radar Toggle ──────────────────────────────────

    const btnRainViewer = document.getElementById('btn-rainviewer');

    if (btnRainViewer) {

      btnRainViewer.addEventListener('click', async () => {

        if (this._rainViewerOn) {
          this.globe.removeRainViewerLayer();
          this._rainViewerOn = false;
          btnRainViewer.textContent = '🌧️ RADAR';
          btnRainViewer.style.background = '';
        } else {

          btnRainViewer.textContent = '🌧️ LOADING...';

          const meta = await APIService.fetchRainViewerMeta();

          if (meta.path) {

            this.globe.addRainViewerLayer(meta.path, meta.host);

            this._rainViewerOn = true;

            btnRainViewer.textContent = '🌧️ RADAR ON';

            btnRainViewer.style.background = 'rgba(96,165,250,0.2)';

          } else {

            btnRainViewer.textContent = '🌧️ RADAR';

            console.warn('[Cinema] RainViewer: no data path available');

          }

        }

      });

    }

    // ── 3D Tactical Air Surveillance Radar Events ────────────────

    if (this.ui.btnAirRadar) {

      this.ui.btnAirRadar.addEventListener('click', () => this.toggleAirRadar());

    }

    const sidebarAirRadar = document.getElementById('sidebar-btn-air-radar');

    if (sidebarAirRadar) {

      sidebarAirRadar.addEventListener('click', () => this.toggleAirRadar());

    }

    // ── Batch Intelligence Layer Controls (⚡ ALL ON / OFF) ───────

    const btnAllOn = document.getElementById('btn-all-layers-on');

    if (btnAllOn) {

      btnAllOn.addEventListener('click', () => this.toggleAllLayers(true));

    }

    const btnAllOff = document.getElementById('btn-all-layers-off');

    if (btnAllOff) {

      btnAllOff.addEventListener('click', () => this.toggleAllLayers(false));

    }

    if (this.ui.closeAirRadarBtn) {

      this.ui.closeAirRadarBtn.addEventListener('click', () => this.toggleAirRadar(false));

    }

    // ── Top-Right Tactical Radar View Sync & Range Controls ───────────
    const hubButtons = document.querySelectorAll('.radar-hub-btn');
    const REGIONS = {
      view: { label: 'WINDOW' },
      India: { lat: 20.5937, lon: 78.9629, alt: 3500000, label: 'INDIA' },
      'Middle East': { lat: 25.2048, lon: 55.2708, alt: 2800000, label: 'MIDDLE EAST' },
      Europe: { lat: 50.1109, lon: 8.6821, alt: 3500000, label: 'EUROPE' },
      'North America': { lat: 39.8283, lon: -98.5795, alt: 4500000, label: 'NORTH AMERICA' },
      'East Asia': { lat: 35.6762, lon: 139.6503, alt: 3200000, label: 'EAST ASIA' }
    };

    hubButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const hubKey = e.currentTarget.dataset.hub;
        hubButtons.forEach(b => {
          b.classList.remove('active');
          b.style.background = 'rgba(0,0,0,0.4)';
          b.style.borderColor = 'rgba(0,255,209,0.25)';
          b.style.color = '#94a3b8';
          b.style.fontWeight = 'normal';
        });
        e.currentTarget.classList.add('active');
        e.currentTarget.style.background = 'rgba(0,255,209,0.2)';
        e.currentTarget.style.borderColor = '#00ffd1';
        e.currentTarget.style.color = '#00ffd1';
        e.currentTarget.style.fontWeight = 'bold';

        const info = REGIONS[hubKey];
        if (info) {
          if (hubKey !== 'view') {
            this.globe.flyTo(info.lat, info.lon, info.alt, 2.0);
          }
          this.syncRadarWithCurrentWindow();
        }
      });
    });

    const rangeButtons = document.querySelectorAll('.radar-range-btn');
    rangeButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const rangeVal = e.currentTarget.dataset.range;
        rangeButtons.forEach(b => {
          b.classList.remove('active');
          b.style.background = 'rgba(0,0,0,0.4)';
          b.style.borderColor = 'rgba(0,255,209,0.25)';
          b.style.color = '#94a3b8';
          b.style.fontWeight = 'normal';
        });
        e.currentTarget.classList.add('active');
        e.currentTarget.style.background = 'rgba(0,255,209,0.2)';
        e.currentTarget.style.borderColor = '#00ffd1';
        e.currentTarget.style.color = '#00ffd1';
        e.currentTarget.style.fontWeight = 'bold';

        if (rangeVal === 'auto') {
          this.syncRadarWithCurrentWindow();
        } else {
          const nm = Number(rangeVal);
          // Zoom camera to approximately fit that range
          const targetAlt = nm * 1852 * 2.2;
          const currentCenter = this.globe.getVisibleContactsInWindow();
          this.globe.flyTo(currentCenter.centerLat, currentCenter.centerLon, targetAlt, 1.5);
        }
      });
    });

    // Radar Target Lock Controls

    if (this.ui.radarUnlockBtn) {

      this.ui.radarUnlockBtn.addEventListener('click', () => {

        this.globe.stopChaseCam();

        if (this.ui.radarTargetBox) this.ui.radarTargetBox.style.display = 'none';

        this._lockedAircraft = null;
    this.radarScope = null;

      });

    }

    if (this.ui.radarBtnIntercept) {

      this.ui.radarBtnIntercept.addEventListener('click', () => {

        if (this._lockedAircraft && this._lockedAircraft.icao24) {

          this.globe.interceptFlight(this._lockedAircraft.icao24);

        }

      });

    }

    if (this.ui.radarBtnChase) {

      this.ui.radarBtnChase.addEventListener('click', () => {

        if (this._lockedAircraft && this._lockedAircraft.icao24) {

          this.globe.startChaseCam(this._lockedAircraft.icao24);

        }

      });

    }

  }

  // --- State Actions ---

  toggleSidebar() {

    this.state.sidebarOpen = !this.state.sidebarOpen;

    if (this.state.sidebarOpen) {

      this.ui.sidebar.classList.remove('collapsed');

    } else {

      this.ui.sidebar.classList.add('collapsed');

    }

    this.saveSettings();

  }

  toggleLayer(layerName) {

    this.state.layers[layerName] = !this.state.layers[layerName];

    this.globe.setLayerVisibility(layerName, this.state.layers[layerName]);

    // Fetch data when enabling a layer for the first time

    if (this.state.layers[layerName]) {

      this.fetchLayer(layerName);

    }

    // Update UI

    const btn = document.getElementById(`btn-${layerName}`);

    if (btn) {

      if (this.state.layers[layerName]) {

        btn.classList.add('active');

        btn.textContent = 'ON';

      } else {

        btn.classList.remove('active');

        btn.textContent = 'OFF';

      }

    }

    this.saveSettings();

  }

  toggleAllLayers(enable = true) {

    Object.keys(this.state.layers).forEach(layer => {

      if (layer === 'argusLandmarks') return;

      this.state.layers[layer] = enable;

      this.globe.setLayerVisibility(layer, enable);

      if (enable) {

        this.fetchLayer(layer);

      }

      const btn = document.getElementById(`btn-${layer}`);

      if (btn) {

        if (enable) {

          btn.classList.add('active');

          btn.textContent = 'ON';

        } else {

          btn.classList.remove('active');

          btn.textContent = 'OFF';

        }

      }

    });

    this.saveSettings();

    if (this.ui.status) {

      this.ui.status.textContent = enable ? 'ALL INTEL LAYERS ACTIVATED' : 'ALL OPTIONAL LAYERS DEACTIVATED';

    }

  }

  preloadAllCounts() {

    // 1. Immediately populate counts from local MAP_DATA (instant 0ms, zero network latency)

    const staticCounts = {

      nuclear: MAP_DATA.NUCLEAR_FACILITIES?.length || 0,

      military: MAP_DATA.MILITARY_BASES?.length || 0,

      conflicts: MAP_DATA.CONFLICT_ZONES?.length || 0,

      hotspots: MAP_DATA.INTEL_HOTSPOTS?.length || 0,

      waterways: MAP_DATA.STRATEGIC_WATERWAYS?.length || 0,

      cables: MAP_DATA.UNDERSEA_CABLES?.length || 0,

      spaceports: MAP_DATA.SPACEPORTS?.length || 0,

      economic: MAP_DATA.ECONOMIC_CENTERS?.length || 0,

    };

    Object.entries(staticCounts).forEach(([layer, count]) => {

      const el = (this.ui.counts && this.ui.counts[layer]) || document.getElementById(`count-${layer}`);

      if (el) el.textContent = count.toLocaleString();

    });

    // 2. Pre-query live sensor feeds asynchronously so sidebar numbers populate without waiting for layer click

    APIService.fetchEarthquakes().then(eqs => {

      const el = (this.ui.counts && this.ui.counts.earthquakes) || document.getElementById('count-earthquakes');

      if (el && Array.isArray(eqs)) el.textContent = eqs.length.toLocaleString();

    }).catch(() => {});

    APIService.fetchNaturalEvents().then(evs => {

      const el = (this.ui.counts && this.ui.counts.naturalEvents) || document.getElementById('count-naturalEvents');

      if (el && Array.isArray(evs)) el.textContent = evs.length.toLocaleString();

    }).catch(() => {});

    APIService.fetchWeatherAlerts().then(alerts => {

      const elAlerts = (this.ui.counts && this.ui.counts.weatherAlerts) || document.getElementById('count-weatherAlerts');

      if (elAlerts && Array.isArray(alerts)) elAlerts.textContent = alerts.length.toLocaleString();

      const elWeather = (this.ui.counts && this.ui.counts.weather) || document.getElementById('count-weather');

      if (elWeather && Array.isArray(alerts)) elWeather.textContent = alerts.length.toLocaleString();

    }).catch(() => {});

    APIService.fetchNASA_FIRMS().then(fires => {

      const elFires = (this.ui.counts && this.ui.counts.wildfires) || document.getElementById('count-wildfires');

      if (elFires && Array.isArray(fires)) elFires.textContent = fires.length.toLocaleString();

    }).catch(() => {});

    const camLat = this.state.camera.latitude ?? this.state.camera.lat ?? 38.9072;

    const camLon = this.state.camera.longitude ?? this.state.camera.lon ?? -77.0369;

    const camAlt = this.state.camera.altitude ?? this.state.camera.alt ?? 10000000;

    APIService.fetchCCTV(camLat, camLon, camAlt).then(cams => {

      const el = (this.ui.counts && this.ui.counts.cctv) || document.getElementById('count-cctv');

      if (el && Array.isArray(cams)) el.textContent = cams.length.toLocaleString();

    }).catch(() => {});

  }

  setMode(mode) {

    this.state.mode = mode;

    this.globe.setVisualMode(mode);

    this.updateModeUI(mode);

    this.saveSettings();

  }

  updateModeUI(mode) {

    this.ui.modeBtns.forEach(b => b.classList.remove('active'));

    const btn = Array.from(this.ui.modeBtns).find(b => b.dataset.mode === mode);

    if (btn) btn.classList.add('active');

  }

  setNewsChannel(channel) {

    this.ui.newsBtns.forEach(b => b.classList.remove('active'));

    const btn = Array.from(this.ui.newsBtns).find(b => b.dataset.channel === channel);

    if (btn) btn.classList.add('active');

    const streams = {

      aljazeera: 'https://www.youtube.com/embed/bBYNUMCTsHA?autoplay=1&mute=1',

      sky: 'https://www.youtube.com/embed/9Auq9mYxFEE?autoplay=1&mute=1',

      dw: 'https://www.youtube.com/embed/nwyxhe0-U_s?autoplay=1&mute=1',

      nasa: 'https://www.youtube.com/embed/21X5lGlDOfg?autoplay=1&mute=1'

    };

    this.ui.newsIframe.src = streams[channel] || streams.aljazeera;

  }

  // --- Data Fetching ---

  async fetchAllData() {

    this.ui.status.textContent = 'UPLINK ESTABLISHED... FETCHING ACTIVE LAYERS';

    // Only fetch layers that are currently ON — off layers stay empty until the user enables them

    const activeFetches = Object.entries(this.state.layers)

      .filter(([, visible]) => visible)

      .map(([layer]) => this.fetchLayer(layer));

    if (activeFetches.length > 0) {

      await Promise.all(activeFetches);

    }

    this.ui.status.textContent = 'ALL SYSTEMS NOMINAL';

  }

  async fetchLayer(layer) {
    try {
      if (layer === 'flights') {
        const flights = await APIService.fetchFlights();
        if (this.ui.counts.flights) this.ui.counts.flights.textContent = flights.length.toLocaleString();
        this.updateAirRadarTelemetry(flights);

        if (globeCache.hasChanged('flights', flights)) {
          this.globe.updateFlights(flights);
          globeCache.markRendered('flights', flights);
        } else {
          globeCache.stats.rendersSkipped++;
        }
      } else if (layer === 'vessels') {
        const vessels = await APIService.fetchVessels();
        if (this.ui.counts.vessels) this.ui.counts.vessels.textContent = vessels.length.toLocaleString();

        if (globeCache.hasChanged('vessels', vessels)) {
          this.globe.updateVessels(vessels);
          globeCache.markRendered('vessels', vessels);
        } else {
          globeCache.stats.rendersSkipped++;
        }
      } else if (layer === 'satellites') {
        const sats = await APIService.fetchSatellites();
        if (this.ui.counts.satellites) this.ui.counts.satellites.textContent = sats.length.toLocaleString();

        if (globeCache.hasChanged('satellites', sats)) {
          this.globe.updateSatellites(sats);
          globeCache.markRendered('satellites', sats);
        } else {
          globeCache.stats.rendersSkipped++;
        }
      } else if (layer === 'earthquakes') {
        const eqs = await APIService.fetchEarthquakes();
        if (this.ui.counts.earthquakes) this.ui.counts.earthquakes.textContent = eqs.length.toLocaleString();

        if (globeCache.hasChanged('earthquakes', eqs)) {
          this.globe.updateEarthquakes(eqs);
          globeCache.markRendered('earthquakes', eqs);
        } else {
          globeCache.stats.rendersSkipped++;
        }
      } else if (layer === 'weather') {
        // Real weather layer: NWS active alerts as a globe layer (distinct from weatherAlerts sidebar layer)
        const alerts = await APIService.fetchWeatherAlerts();
        if (this.ui.counts.weather) this.ui.counts.weather.textContent = alerts.length.toLocaleString();

        if (globeCache.hasChanged('weather', alerts)) {
          this.globe.updateWeatherAlerts(alerts);
          globeCache.markRendered('weather', alerts);
        } else {
          globeCache.stats.rendersSkipped++;
        }
      } else if (layer === 'cctv') {
        // camera state uses latitude/longitude/altitude (from globe.js camera change event)
        const camLat = this.state.camera.latitude ?? this.state.camera.lat ?? 38.9072;
        const camLon = this.state.camera.longitude ?? this.state.camera.lon ?? -77.0369;
        const camAlt = this.state.camera.altitude ?? this.state.camera.alt ?? 10000000;
        const cams = await APIService.fetchCCTV(camLat, camLon, camAlt);
        if (this.ui.counts.cctv) this.ui.counts.cctv.textContent = cams.length.toLocaleString();

        if (globeCache.hasChanged('cctv', cams)) {
          this.globe.updateCCTV(cams);
          globeCache.markRendered('cctv', cams);
        } else {
          globeCache.stats.rendersSkipped++;
        }

        // If catalog still loading (empty array returned), retry in 5 s
        if (cams.length === 0 && this.state.layers.cctv) {
          clearTimeout(this._cctvRetry);
          this._cctvRetry = setTimeout(() => this.fetchLayer('cctv'), 5000);
        }
      } else if (layer === 'nuclear') {
        if (this.ui.counts.nuclear) this.ui.counts.nuclear.textContent = MAP_DATA.NUCLEAR_FACILITIES.length;
        if (globeCache.hasChanged('nuclear', MAP_DATA.NUCLEAR_FACILITIES)) {
          if (this.globe.updateNuclear) this.globe.updateNuclear(MAP_DATA.NUCLEAR_FACILITIES);
          globeCache.markRendered('nuclear', MAP_DATA.NUCLEAR_FACILITIES);
        } else {
          globeCache.stats.rendersSkipped++;
        }
      } else if (layer === 'military') {
        if (this.ui.counts.military) this.ui.counts.military.textContent = MAP_DATA.MILITARY_BASES.length;
        if (globeCache.hasChanged('military', MAP_DATA.MILITARY_BASES)) {
          if (this.globe.updateMilitary) this.globe.updateMilitary(MAP_DATA.MILITARY_BASES);
          globeCache.markRendered('military', MAP_DATA.MILITARY_BASES);
        } else {
          globeCache.stats.rendersSkipped++;
        }
      } else if (layer === 'conflicts') {
        if (this.ui.counts.conflicts) this.ui.counts.conflicts.textContent = MAP_DATA.CONFLICT_ZONES.length;
        if (globeCache.hasChanged('conflicts', MAP_DATA.CONFLICT_ZONES)) {
          if (this.globe.updateConflicts) this.globe.updateConflicts(MAP_DATA.CONFLICT_ZONES);
          globeCache.markRendered('conflicts', MAP_DATA.CONFLICT_ZONES);
        } else {
          globeCache.stats.rendersSkipped++;
        }
      } else if (layer === 'hotspots') {
        if (this.ui.countHotspots) this.ui.countHotspots.textContent = MAP_DATA.INTEL_HOTSPOTS.length;
        if (globeCache.hasChanged('hotspots', MAP_DATA.INTEL_HOTSPOTS)) {
          this.globe.updateHotspots(MAP_DATA.INTEL_HOTSPOTS);
          globeCache.markRendered('hotspots', MAP_DATA.INTEL_HOTSPOTS);
        } else {
          globeCache.stats.rendersSkipped++;
        }
      } else if (layer === 'waterways') {
        if (this.ui.countWaterways) this.ui.countWaterways.textContent = MAP_DATA.STRATEGIC_WATERWAYS.length;
        if (globeCache.hasChanged('waterways', MAP_DATA.STRATEGIC_WATERWAYS)) {
          this.globe.updateWaterways(MAP_DATA.STRATEGIC_WATERWAYS);
          globeCache.markRendered('waterways', MAP_DATA.STRATEGIC_WATERWAYS);
        } else {
          globeCache.stats.rendersSkipped++;
        }
      } else if (layer === 'cables') {
        if (this.ui.countCables) this.ui.countCables.textContent = MAP_DATA.UNDERSEA_CABLES.length;
        if (globeCache.hasChanged('cables', MAP_DATA.UNDERSEA_CABLES)) {
          this.globe.updateCables(MAP_DATA.UNDERSEA_CABLES);
          globeCache.markRendered('cables', MAP_DATA.UNDERSEA_CABLES);
        } else {
          globeCache.stats.rendersSkipped++;
        }
      } else if (layer === 'naturalEvents') {
        const events = await APIService.fetchNaturalEvents();
        if (this.ui.countNaturalEvents) this.ui.countNaturalEvents.textContent = events.length;
        signalAggregator.ingestNaturalEvents(events);

        if (globeCache.hasChanged('naturalEvents', events)) {
          this.globe.updateNaturalEvents(events);
          globeCache.markRendered('naturalEvents', events);
        } else {
          globeCache.stats.rendersSkipped++;
        }
      } else if (layer === 'wildfires') {
        const fires = await APIService.fetchNASA_FIRMS(); // Real NASA VIIRS 375m active fires
        if (this.ui.countWildfires) this.ui.countWildfires.textContent = fires.length;
        signalAggregator.ingestWildfires(fires);

        if (globeCache.hasChanged('wildfires', fires)) {
          this.globe.updateWildfires(fires);
          globeCache.markRendered('wildfires', fires);
        } else {
          globeCache.stats.rendersSkipped++;
        }
      } else if (layer === 'weatherAlerts') {
        const alerts = await APIService.fetchWeatherAlerts();
        if (this.ui.countWeatherAlerts) this.ui.countWeatherAlerts.textContent = alerts.length;
        signalAggregator.ingestWeatherAlerts(alerts);

        if (globeCache.hasChanged('weatherAlerts', alerts)) {
          this.globe.updateWeatherAlerts(alerts);
          globeCache.markRendered('weatherAlerts', alerts);
        } else {
          globeCache.stats.rendersSkipped++;
        }
      } else if (layer === 'spaceports') {
        if (this.ui.countSpaceports) this.ui.countSpaceports.textContent = MAP_DATA.SPACEPORTS.length;
        if (globeCache.hasChanged('spaceports', MAP_DATA.SPACEPORTS)) {
          this.globe.updateSpaceports(MAP_DATA.SPACEPORTS);
          globeCache.markRendered('spaceports', MAP_DATA.SPACEPORTS);
        } else {
          globeCache.stats.rendersSkipped++;
        }
      } else if (layer === 'economic') {
        if (this.ui.countEconomic) this.ui.countEconomic.textContent = MAP_DATA.ECONOMIC_CENTERS.length;
        if (globeCache.hasChanged('economic', MAP_DATA.ECONOMIC_CENTERS)) {
          this.globe.updateEconomicCenters(MAP_DATA.ECONOMIC_CENTERS);
          globeCache.markRendered('economic', MAP_DATA.ECONOMIC_CENTERS);
        } else {
          globeCache.stats.rendersSkipped++;
        }
      }

      // Re-enforce layer visibility after every fetch so timer-triggered re-fetches
      // never make a user-disabled layer reappear on the globe.
      this.globe.setLayerVisibility(layer, !!this.state.layers[layer]);
    } catch (e) {
      console.error(`Error fetching layer ${layer}:`, e);
      if (this.ui.status) this.ui.status.textContent = `WARN: ${layer.toUpperCase()} UPLINK FAILED`;
    }
  }

  // --- Globe Events ---

  onCameraChange(cam) {

    this.state.camera = cam;
    if (this.state.airRadarOpen) {
      this.syncRadarWithCurrentWindow();
    }

    const latStr = (cam.latitude >= 0 ? 'N' : 'S');

    const lonStr = (cam.longitude >= 0 ? 'E' : 'W');

    // Degrees

    const degStr = `${Math.abs(cam.latitude).toFixed(4)}°${latStr} ${Math.abs(cam.longitude).toFixed(4)}°${lonStr}`;

    this.ui.deg.textContent = degStr;

    // MGRS (Simulated)

    const bands = "CDEFGHJKLMNPQRSTUVWX";

    const bandIdx = Math.min(Math.max(Math.floor((cam.latitude + 80) / 8), 0), bands.length - 1);

    const band = bands.charAt(bandIdx);

    const zone = Math.floor((cam.longitude + 180) / 6) + 1;

    const e = Math.floor(Math.abs(cam.longitude % 6) * 100000 / 6).toString().padStart(5, '0');

    const n = Math.floor(Math.abs(cam.latitude % 8) * 100000 / 8).toString().padStart(5, '0');

    this.ui.mgrs.textContent = `MGRS: ${zone.toString().padStart(2, '0')}${band} ${e} ${n}`;

    // Altitude

    let altStr = '';

    if (cam.altitude >= 1000000) altStr = (cam.altitude / 1000000).toFixed(1) + 'M';

    else if (cam.altitude >= 1000) altStr = (cam.altitude / 1000).toFixed(1) + 'K';

    else altStr = Math.floor(cam.altitude) + 'm';

    this.ui.altM.textContent = altStr.toUpperCase();

    // GSD

    const gsd = cam.altitude * 0.00001;

    this.ui.gsd.textContent = (gsd >= 1 ? gsd.toFixed(2) + 'M' : (gsd * 100).toFixed(2) + 'cm').toUpperCase();

    // NIIRS

    const rating = Math.max(0, Math.min(9, 9 - Math.log10(cam.altitude / 1000)));

    this.ui.niirs.textContent = rating.toFixed(1);

    // Debounce saving camera state

    clearTimeout(this.saveTimer);

    this.saveTimer = setTimeout(() => this.saveSettings(), 2000);

    // Debounced refresh for CCTV if active and camera moved

    if (this.state.layers && this.state.layers.cctv) {

      clearTimeout(this._cctvDebounce);

      this._cctvDebounce = setTimeout(() => this.fetchLayer('cctv'), 800);

    }

  }

  onEntityClick(props) {

    this.ui.targetDetails.classList.remove('hidden');

    let html = '';

    if (props.icao24) {

      // ── AIRCRAFT ──────────────────────────────────────────────

      const typeLabel = {

        military:   '✈ MILITARY',

        emergency:  '🚨 EMERGENCY',

        private:    '✈ PRIVATE',

        commercial: '✈ COMMERCIAL'

      }[props.type] || '✈ AIRCRAFT';

      html += `<h3>TARGET: ${(props.callsign || props.icao24).toUpperCase()}</h3>`;

      html += `<p><strong>CLASS:</strong> <span class="${props.type === 'military' ? 'text-red' : props.type === 'emergency' ? 'text-red' : 'text-cyan'}">${typeLabel}</span></p>`;

      html += `<p><strong>ICAO24:</strong> ${props.icao24.toUpperCase()}</p>`;

      html += `<p><strong>REG:</strong> ${props.registration || '---'}</p>`;

      html += `<p><strong>A/C TYPE:</strong> ${props.aircraft_type || '---'}</p>`;

      html += `<p><strong>ALTITUDE:</strong> ${props.altitude ? props.altitude.toLocaleString() + ' m' : 'N/A'}</p>`;

      html += `<p><strong>SPEED:</strong> ${props.velocity ? props.velocity + ' km/h' : 'N/A'}</p>`;

      html += `<p><strong>HEADING:</strong> ${props.heading !== undefined ? props.heading + '°' : 'N/A'}</p>`;

      html += `<p><strong>SQUAWK:</strong> ${props.squawk || '----'}</p>`;

      // Populate 3D Air Surveillance Radar target lock card

      this._lockedAircraft = props;

      if (this.ui.radarTargetBox && this.ui.radarTargetInfo) {

        this.ui.radarTargetBox.style.display = 'block';

        const rawAlt = props.altitude || 0;

        const altMeters = Math.round(rawAlt * 0.3048);

        this.ui.radarTargetInfo.innerHTML = `

          <div style="font-weight:bold; color:#00ffd1; font-size:11px; margin-bottom:3px;">

            ✈ ${(props.callsign || props.icao24).toUpperCase()} [${(props.type || 'COMMERCIAL').toUpperCase()}]

          </div>

          <div><strong>ICAO24:</strong> ${props.icao24.toUpperCase()} &nbsp;|&nbsp; <strong>REG:</strong> ${props.registration || '---'}</div>

          <div><strong>TYPE:</strong> ${props.aircraft_type || '---'} &nbsp;|&nbsp; <strong>SQUAWK:</strong> <span style="color:${props.squawk === '7700' || props.squawk === '7500' ? '#ff3333' : '#00ffd1'}">${props.squawk || '----'}</span></div>

          <div><strong>ALTITUDE:</strong> ${rawAlt.toLocaleString()} ft (${altMeters.toLocaleString()} m)</div>

          <div><strong>GROUND SPEED:</strong> ${props.velocity || 0} km/h &nbsp;|&nbsp; <strong>HEADING:</strong> ${props.heading || 0}°</div>

        `;

      }

    } else if (props.mmsi) {

      // ── VESSEL ────────────────────────────────────────────────

      html += `<h3>TARGET: ${(props.name || 'VESSEL').toUpperCase()}</h3>`;

      html += `<p><strong>CLASS:</strong> <span class="text-cyan">🚢 VESSEL</span></p>`;

      html += `<p><strong>MMSI:</strong> ${props.mmsi}</p>`;

      html += `<p><strong>IMO:</strong> ${props.imo || '---'}</p>`;

      html += `<p><strong>CALLSIGN:</strong> ${props.callsign || '---'}</p>`;

      html += `<p><strong>TYPE:</strong> ${(props.type || 'cargo').toUpperCase()}</p>`;

      html += `<p><strong>FLAG:</strong> ${props.flag || props.country || '---'}</p>`;

      const vesselSpeed = Number.isFinite(Number(props.speed)) ? Number(props.speed).toFixed(1) : 'N/A';

      const vesselDraft = Number.isFinite(Number(props.draft)) && Number(props.draft) > 0 ? Number(props.draft).toFixed(1) : null;

      html += `<p><strong>SPEED:</strong> ${vesselSpeed !== 'N/A' ? vesselSpeed + ' kn' : 'N/A'}</p>`;

      html += `<p><strong>STATUS:</strong> ${(props.status || 'UNDERWAY').toString().toUpperCase()}</p>`;

      html += `<p><strong>DESTINATION:</strong> ${props.destination || props.arrival || '---'}</p>`;

      if (vesselDraft) html += `<p><strong>DRAFT:</strong> ${vesselDraft} m</p>`;

    } else if (props.noradId) {

      // ── SATELLITE ─────────────────────────────────────────────

      html += `<h3>TARGET: ${(props.name || props.noradId).toUpperCase()}</h3>`;

      html += `<p><strong>CLASS:</strong> <span class="text-cyan">🛰 ORBITAL ASSET</span></p>`;

      html += `<p><strong>NORAD ID:</strong> ${props.noradId}</p>`;

      html += `<p><strong>ALTITUDE:</strong> ${props.altitude ? props.altitude + ' km' : 'N/A'}</p>`;

      html += `<p><strong>INCLINATION:</strong> ${props.inclination !== 'N/A' ? props.inclination + '°' : 'N/A'}</p>`;

      html += `<p><strong>PERIOD:</strong> ${props.period_min !== 'N/A' ? props.period_min + ' min' : 'N/A'}</p>`;

    } else if (props.magnitude) {

      // ── EARTHQUAKE ────────────────────────────────────────────

      const mag = parseFloat(props.magnitude);

      const magClass = mag >= 6.0 ? 'text-red' : mag >= 4.5 ? 'text-red' : 'text-cyan';

      html += `<h3>TARGET: SEISMIC EVENT</h3>`;

      html += `<p><strong>CLASS:</strong> <span class="text-red">⚡ EARTHQUAKE</span></p>`;

      html += `<p><strong>MAGNITUDE:</strong> <span class="${magClass}">M ${parseFloat(props.magnitude).toFixed(1)}</span></p>`;

      html += `<p><strong>DEPTH:</strong> ${props.depth || 'N/A'}</p>`;

      html += `<p><strong>LOCATION:</strong> ${props.place || 'Unknown'}</p>`;

      html += `<p><strong>TIME:</strong> ${props.time ? new Date(Number(props.time)).toUTCString() : 'Recent'}</p>`;

    } else if (props.condition) {

      html += `<h3>TARGET: ${props.name}</h3>`;

      html += `<p><strong>TYPE:</strong> WEATHER RADAR</p>`;

      html += `<p><strong>CONDITION:</strong> ${props.condition.toUpperCase()}</p>`;

      html += `<p><strong>LEVEL:</strong> ${props.precipitationLevel}/4</p>`;

    } else if (props.level) {

      html += `<h3>TARGET: ${props.name.toUpperCase()}</h3>`;

      html += `<p><strong>TYPE:</strong> INTEL HOTSPOT</p>`;

      html += `<p class="${props.level === 'high' ? 'text-red' : 'text-cyan'}"><strong>THREAT LEVEL:</strong> ${props.level.toUpperCase()}</p>`;

      html += `<p><strong>INTEL:</strong> ${props.description || 'Classified'}</p>`;

    } else if (props.dailyTraffic) {

      html += `<h3>TARGET: ${props.name.toUpperCase()}</h3>`;

      html += `<p><strong>TYPE:</strong> STRATEGIC WATERWAY</p>`;

      html += `<p><strong>TRAFFIC:</strong> ${props.dailyTraffic}</p>`;

      html += `<p><strong>INTEL:</strong> ${props.description || 'Monitored chokepoint'}</p>`;

    } else if (props.capacity) {

      html += `<h3>TARGET: ${props.name.toUpperCase()}</h3>`;

      html += `<p><strong>TYPE:</strong> UNDERSEA CABLE</p>`;

      html += `<p><strong>CAPACITY:</strong> ${props.capacity}</p>`;

      html += `<p class="text-cyan"><strong>STATUS:</strong> OPERATIONAL</p>`;

    } else if (props.categoryId) {

      html += `<h3>TARGET: ${(props.title || 'NATURAL EVENT').toUpperCase()}</h3>`;

      html += `<p><strong>TYPE:</strong> NATURAL EVENT</p>`;

      html += `<p><strong>CATEGORY:</strong> ${props.categoryId.toUpperCase()}</p>`;

      if (props.date) html += `<p><strong>DATE:</strong> ${props.date}</p>`;

    } else if (props.event && props.severity) {

      html += `<h3>TARGET: WEATHER ALERT</h3>`;

      html += `<p><strong>EVENT:</strong> ${props.event}</p>`;

      html += `<p class="${props.severity === 'Extreme' || props.severity === 'Severe' ? 'text-red' : 'text-cyan'}"><strong>SEVERITY:</strong> ${props.severity.toUpperCase()}</p>`;

      if (props.headline) html += `<p><strong>DETAILS:</strong> ${props.headline.slice(0, 120)}</p>`;

    } else if (props.operator) {

      html += `<h3>TARGET: ${props.name.toUpperCase()}</h3>`;

      html += `<p><strong>TYPE:</strong> LAUNCH FACILITY</p>`;

      html += `<p><strong>COUNTRY:</strong> ${props.country}</p>`;

      html += `<p><strong>OPERATOR:</strong> ${props.operator}</p>`;

      html += `<p class="text-cyan"><strong>STATUS:</strong> OPERATIONAL</p>`;

    } else if (props.gdpWeight) {

      html += `<h3>TARGET: ${props.name.toUpperCase()}</h3>`;

      html += `<p><strong>TYPE:</strong> ECONOMIC CENTER</p>`;

      html += `<p><strong>GDP WEIGHT:</strong> ${props.gdpWeight}</p>`;

      html += `<p><strong>INTEL:</strong> ${props.description || 'Financial hub under monitoring'}</p>`;

    } else if (props.id && String(props.id).startsWith('cctv-')) {

      // CCTV — show popup and load live feed

      this.ui.targetDetails.classList.add('hidden');

      this.ui.cctvPopup.classList.remove('hidden');

      const displayId = String(props.id).replace('cctv-', '');
      if (this.ui.cctvId) {
        const loc = [props.city, props.country].filter(Boolean).join(', ');
        this.ui.cctvId.textContent = loc ? `NODE CAM-${displayId} // ${loc.toUpperCase()}` : `NODE CAM-${displayId}`;
      }
      if (this.ui.cctvName) this.ui.cctvName.textContent = props.name || 'CAMERA';
      this._loadCCTVFeed(props);
      return;

    } else if (props.type && ['weapons','enrichment','plant'].includes(props.type)) {

      html += `<h3>TARGET: ${props.name.toUpperCase()}</h3>`;

      html += `<p><strong>TYPE:</strong> NUCLEAR FACILITY</p>`;

      html += `<p><strong>CLASS:</strong> ${props.type.toUpperCase()}</p>`;

      html += `<p class="text-red"><strong>THREAT:</strong> ${props.type === 'weapons' ? 'HIGH' : props.type === 'enrichment' ? 'ELEVATED' : 'MODERATE'}</p>`;

    } else if (props.type) {

      // Military base

      html += `<h3>TARGET: ${(props.name || 'INSTALLATION').toUpperCase()}</h3>`;

      html += `<p><strong>TYPE:</strong> MILITARY INSTALLATION</p>`;

      html += `<p><strong>ALLEGIANCE:</strong> ${props.type.toUpperCase()}</p>`;

      html += `<p class="text-cyan"><strong>STATUS:</strong> MONITORED</p>`;

    } else {

      // Generic fallback

      html += `<h3>TARGET: ${(props.name || props.title || props.id || 'UNKNOWN').toString().toUpperCase()}</h3>`;

      html += `<p><strong>TYPE:</strong> UNCLASSIFIED</p>`;

      const keys = Object.keys(props).slice(0, 5);

      keys.forEach(k => { html += `<p><strong>${k.toUpperCase()}:</strong> ${props[k]}</p>`; });

    }

    // Interactive ARGUS AI Action Button

    html += `

      <div style="margin-top: 14px; padding-top: 10px; border-top: 1px solid rgba(0, 255, 209, 0.25);">

        <button id="btn-target-ask-ai" style="width: 100%; display: flex; align-items: center; justify-content: center; gap: 8px; padding: 8px 12px; background: rgba(0, 255, 209, 0.15); border: 1px solid var(--cyber-cyan, #00FFD1); color: #ffffff; border-radius: 3px; font-family: var(--cyber-font-orbitron, monospace); font-size: 10px; letter-spacing: 1px; cursor: pointer; transition: all 0.2s ease; box-shadow: 0 0 10px rgba(0,255,209,0.2);">

          <i class="fas fa-shield-alt" style="color: var(--cyber-cyan, #00FFD1);"></i> ⚡ ASK ARGUS AI ABOUT TARGET

        </button>

      </div>

    `;

    this.ui.targetContent.innerHTML = html;

    const askBtn = document.getElementById('btn-target-ask-ai');

    if (askBtn) {

      askBtn.addEventListener('click', () => {

        if (typeof window.argusAskAbout === 'function') {

          window.argusAskAbout({

            type: props.icao24 ? 'flight' : (props.mmsi ? 'vessel' : (props.noradId ? 'satellite' : (props.magnitude ? 'earthquake' : 'entity'))),

            data: props

          });

        }

      });

    }

  }

  updateAIInsights(pos, isClick = false) {

    if (!this.ui.aiInsightsText) return;

    // Validate position object

    if (!pos || typeof pos.latitude !== 'number' || typeof pos.longitude !== 'number' || isNaN(pos.latitude) || isNaN(pos.longitude)) return;

    const latStr = (pos.latitude >= 0 ? 'N' : 'S');

    const lonStr = (pos.longitude >= 0 ? 'E' : 'W');

    const lat = Math.abs(pos.latitude).toFixed(4);

    const lon = Math.abs(pos.longitude).toFixed(4);

    // Use a 2-degree grid to keep anomalies stable while hovering over a general area

    const gridLat = Math.round(pos.latitude / 2) * 2;

    const gridLon = Math.round(pos.longitude / 2) * 2;

    const hash = Math.floor(Math.abs(gridLat * 1337 + gridLon * 31337));

    const anomalyTypes = [

      "ANOMALY DETECTED IN",

      "NAVAL MOVEMENT:",

      "UNAUTHORIZED FLIGHT PATH:",

      "ENCRYPTED COMM BURST:",

      "THERMAL BLOOM:",

      "TROOP BUILDUP:",

      "SUBTERRANEAN ACTIVITY:",

      "RADAR ANOMALY:",

      "CYBER ATTACK ORIGIN:"

    ];

    // 30% chance for a sector to appear normal

    const isNormal = (hash % 100) < 30;

    let anomalyStr1 = "";

    let anomalyStr2 = "";

    let statusClass = "text-red";

    if (isNormal) {

      statusClass = "text-cyan";

      anomalyStr1 = "STATUS: CLEAR";

      anomalyStr2 = "NO ANOMALIES DETECTED in current grid";

    } else {

      const type1 = anomalyTypes[hash % anomalyTypes.length];

      const type2 = anomalyTypes[(hash + 7) % anomalyTypes.length];

      const loc1 = `SECTOR ${Math.abs(gridLat)}°${latStr} ${Math.abs(gridLon)}°${lonStr}`;

      // Secondary anomaly slightly offset

      const offsetLat = Math.abs(gridLat) > 80 ? Math.abs(gridLat) - 2 : Math.abs(gridLat) + 2;

      const loc2 = `SECTOR ${offsetLat}°${latStr} ${Math.abs(gridLon)}°${lonStr}`;

      anomalyStr1 = `${type1} ${loc1}`;

      anomalyStr2 = `${type2} ${loc2}`;

    }

    const threatLevel = isNormal ? "1.0" : ((hash % 8) + 2.1).toFixed(1);

    let html = `

INITIALIZING THREAT ANALYSIS...<br>

ANALYZING SECTOR: <span class="text-cyan">${lat}°${latStr} ${lon}°${lonStr}</span><br>

> SCANNING COMMUNICATIONS... ${isClick ? '<span class="text-red">DEEP SCAN</span>' : 'OK'}<br>

> <span class="${statusClass}">${anomalyStr1}</span><br>

> <span class="${statusClass}">${anomalyStr2}</span><br>

> THREAT LEVEL: ${threatLevel} / 10.0<br>

> AWAITING FURTHER TELEMETRY...

    `;

    this.ui.aiInsightsText.innerHTML = html.trim();

  }

  updateClock() {

    const now = new Date();

    this.ui.timestamp.textContent = 'REC ' + now.toISOString().substring(0, 19).replace('T', ' ') + 'Z';

  }

  // --- Persistence ---

  loadSettings() {

    try {

      const saved = localStorage.getItem('terra5_settings');

      if (saved) {

        const parsed = JSON.parse(saved);

        // Deep-merge only known layer keys so corrupt or outdated saves can't

        // inject unexpected state or overwrite new layer defaults.

        if (parsed.layers && typeof parsed.layers === 'object') {

          Object.keys(this.state.layers).forEach(k => {

            if (typeof parsed.layers[k] === 'boolean') {

              this.state.layers[k] = parsed.layers[k];

            }

          });

        }

        if (typeof parsed.mode === 'string')        this.state.mode        = parsed.mode;

        if (typeof parsed.sidebarOpen === 'boolean') this.state.sidebarOpen = parsed.sidebarOpen;

        if (parsed.camera && typeof parsed.camera === 'object') this.state.camera = parsed.camera;

      }

      // Ensure primary flight tracking is active
      this.state.layers.flights = true;

      // Sync sidebar collapse state

      if (!this.state.sidebarOpen) {

        this.ui.sidebar.classList.add('collapsed');

      }

    } catch (e) {

      console.error('Failed to load settings from localStorage', e);

      // Clear corrupt data so next load starts fresh

      try { localStorage.removeItem('terra5_settings'); } catch (_) {}

    }

  }

  // Syncs every toggle button's text and active-class to the current JS state.

  // Called once after loadSettings() to guarantee visual/state parity before

  // the user can click anything — this is the root fix for the double-click bug.

  syncAllButtonStates() {

    Object.entries(this.state.layers).forEach(([layer, visible]) => {

      const btn = document.getElementById(`btn-${layer}`);

      if (!btn) return;

      if (visible) {

        btn.classList.add('active');

        btn.textContent = 'ON';

      } else {

        btn.classList.remove('active');

        btn.textContent = 'OFF';

      }

    });

  }

  saveSettings() {

    try {

      const toSave = {

        layers: this.state.layers,

        mode: this.state.mode,

        sidebarOpen: this.state.sidebarOpen,

        camera: this.state.camera

      };

      localStorage.setItem('terra5_settings', JSON.stringify(toSave));

    } catch (e) {

      // Ignore quota errors etc

    }

  }

  // ═══════════════════════════════════════════════

  //  INTEL FEED — RSS Aggregator

  // ═══════════════════════════════════════════════

  async refreshIntelFeed() {

    try {

      this.ui.status.textContent = 'FETCHING SIGINT RSS FEEDS...';

      const items = await APIService.fetchIntelFeed();

      this.intelFeedData = items;

      signalAggregator.ingestNewsItems(items);

      this.renderIntelFeed(items);

      this.updateBreakingNews(items);

      this.ui.status.textContent = `INTEL: ${items.length} ITEMS INGESTED`;

    } catch (e) {

      console.error('[INTEL] Feed refresh failed:', e);

      this.ui.status.textContent = 'WARN: SIGINT UPLINK DEGRADED';

    }

  }

  renderIntelFeed(items) {
    const container = this.ui.intelFeedList;
    if (!container) return;

    if (!items || items.length === 0) {
      container.innerHTML = `
        <div class="intel-degraded-state" style="padding: 20px 12px; text-align: center; font-family: var(--font-mono, monospace);">
          <div style="color: var(--alert, #ff3333); font-size: 11px; font-weight: bold; margin-bottom: 6px; letter-spacing: 1px;">
            ⚠️ SIGINT UPLINK DEGRADED
          </div>
          <div style="color: var(--text-muted, #7a889b); font-size: 10px; line-height: 1.4; margin-bottom: 14px;">
            External RSS proxies unresponsive. Re-attempting signal intercept...
          </div>
          <button id="retry-intel-feed-btn" style="background: rgba(0, 255, 209, 0.15); border: 1px solid var(--accent, #00ffd1); color: var(--accent, #00ffd1); padding: 6px 14px; font-size: 10px; cursor: pointer; border-radius: 3px; font-family: inherit; text-transform: uppercase; letter-spacing: 1px;">
            RETRY UPLINK
          </button>
        </div>
      `;
      const retryBtn = document.getElementById('retry-intel-feed-btn');
      if (retryBtn) {
        retryBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.refreshIntelFeed();
        });
      }
      return;
    }

    container.innerHTML = items.map(item => {
      const threatClass = item.threatLevel === 'CRITICAL' ? 'threat-critical' :
        item.threatLevel === 'HIGH' ? 'threat-high' :
          item.threatLevel === 'ELEVATED' ? 'threat-elevated' : '';
      const timeAgo = this._timeAgo(item.pubDate);
      return `<div class="intel-item" onclick="window.open('${item.link}','_blank')">
        <div class="intel-item-source">
          <span>[${item.source}]</span>
          <span class="intel-item-time">${timeAgo}</span>
        </div>
        <div class="intel-item-title ${threatClass}">${item.title}</div>
      </div>`;
    }).join('');
  }

  updateBreakingNews(items) {

    const critical = items.filter(i => i.threatLevel === 'CRITICAL' || i.threatLevel === 'HIGH');

    if (critical.length > 0 && this.ui.breakingNewsTicker) {

      const headlines = critical.slice(0, 5).map(i => `[${i.source}] ${i.title}`).join('  ///  ');

      this.ui.tickerText.textContent = headlines;

      this.ui.breakingNewsTicker.classList.remove('hidden');

    }

  }

  // ═══════════════════════════════════════════════

  //  WORLD CLOCK — 5 Timezones

  // ═══════════════════════════════════════════════

  updateWorldClock() {

    const now = new Date();

    const fmt = (tz) => now.toLocaleTimeString('en-US', { timeZone: tz, hour: '2-digit', minute: '2-digit', hour12: false });

    if (this.ui.clockDC) this.ui.clockDC.textContent = fmt('America/New_York');

    if (this.ui.clockLON) this.ui.clockLON.textContent = fmt('Europe/London');

    if (this.ui.clockMSK) this.ui.clockMSK.textContent = fmt('Europe/Moscow');

    if (this.ui.clockBEJ) this.ui.clockBEJ.textContent = fmt('Asia/Shanghai');

    if (this.ui.clockTKY) this.ui.clockTKY.textContent = fmt('Asia/Tokyo');

  }

  // ═══════════════════════════════════════════════

  //  HELPER — Relative time

  // ═══════════════════════════════════════════════

  _timeAgo(date) {

    if (!date) return '';

    const secs = Math.floor((Date.now() - new Date(date).getTime()) / 1000);

    if (secs < 60) return 'JUST NOW';

    if (secs < 3600) return `${Math.floor(secs / 60)}M AGO`;

    if (secs < 86400) return `${Math.floor(secs / 3600)}H AGO`;

    return `${Math.floor(secs / 86400)}D AGO`;

  }

  // ═══════════════════════════════════════════════
  //  CCTV — Unplayable Camera Purge Handler
  // ═══════════════════════════════════════════════

  _removeDeadCamera(camId, reason = 'RESTRICTED') {
    if (!camId) return;
    const cleanId = String(camId).replace('cctv-', '');

    // 1. Close modal immediately so the user never sees a broken/blocked player
    if (this.ui.cctvPopup) {
      this.ui.cctvPopup.classList.add('hidden');
    }

    // 2. Clear HUD & snapshot timers
    clearInterval(this._snapTimer);
    this._snapTimer = null;
    clearInterval(this._cctvHudTimer);
    this._cctvHudTimer = null;
    const container = document.querySelector('.cctv-feed-container');
    if (container) container.innerHTML = '';

    // 3. Remove pin from Cesium globe
    this.globe.removeCCTV(camId);

    // 4. Decrement HUD camera count
    const countEl = (this.ui.counts && this.ui.counts.cctv) || document.getElementById('count-cctv');
    if (countEl) {
      const current = parseInt(countEl.textContent.replace(/,/g, ''), 10) || 0;
      if (current > 0) {
        countEl.textContent = (current - 1).toLocaleString();
      }
    }

    // 5. Notify backend to permanently blacklist from catalog and cache
    fetch(`/api/geo/cctv-report-unplayable?id=${encodeURIComponent(cleanId)}`, { method: 'POST' }).catch(() => {});

    // 6. Tactical status notification
    if (this.ui.status) {
      this.ui.status.textContent = `[NODE CAM-${cleanId} PURGED] ${reason} // REMOVED FROM ACTIVE GRID`;
      setTimeout(() => {
        if (this.ui.status && this.ui.status.textContent.includes('PURGED')) {
          this.ui.status.textContent = 'ONLINE // SURVEILLANCE GRID ACTIVE';
        }
      }, 4500);
    }
    this._currentCCTVId = null;
  }

  // ═══════════════════════════════════════════════
  //  CCTV — Live Feed Loader
  // ═══════════════════════════════════════════════

  async _loadCCTVFeed(props) {
    const container = document.querySelector('.cctv-feed-container');
    if (!container) return;

    this._currentCCTVId = props.id;

    // Clear any previous snapshot timer
    clearInterval(this._snapTimer);
    this._snapTimer = null;
    clearInterval(this._cctvHudTimer);
    this._cctvHudTimer = null;

    // Show loading state immediately
    container.innerHTML = '<div class="cctv-static" style="display:flex;align-items:center;justify-content:center;height:100%;font-family:\'Share Tech Mono\',monospace;font-size:11px;color:#00d4aa;letter-spacing:2px;">⟳ ACQUIRING SIGNAL...</div>';

    // If we already have feed_url from the marker properties (rare), skip the fetch
    let feedData = null;
    if (props.feed_url) {
      feedData = {
        name: props.name,
        feed_url: props.feed_url,
        feed_type: props.feed_type || 'image',
        city: props.city || '',
        country: props.country || '',
      };
    } else {
      // Fetch full camera details from backend
      try {
        const camId = String(props.id || '');
        const res = await fetch(`/api/geo/cctv-feed?id=${encodeURIComponent(camId)}`, {
          signal: AbortSignal.timeout(8000),
        });
        if (res.status === 410) {
          this._removeDeadCamera(props.id, 'RESTRICTED PLAYBACK');
          return;
        }
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          if (errData.unplayable || res.status === 404) {
            this._removeDeadCamera(props.id, 'FEED UNAVAILABLE');
            return;
          }
          throw new Error(errData.error || `HTTP ${res.status}`);
        }
        feedData = await res.json();
      } catch (err) {
        this._removeDeadCamera(props.id, 'FEED UNAVAILABLE');
        return;
      }
    }

    if (!feedData || !feedData.feed_url) {
      this._removeDeadCamera(props.id, 'NO FEED URL');
      return;
    }

    // Update popup info with full camera name if better
    if (feedData.name && this.ui.cctvName) this.ui.cctvName.textContent = feedData.name;
    if ((feedData.city || feedData.country) && this.ui.cctvId) {
      const loc = [feedData.city, feedData.country].filter(Boolean).join(', ');
      const camId = String(props.id || '').replace('cctv-', '');
      this.ui.cctvId.textContent = `NODE CAM-${camId} // ${loc.toUpperCase()}`;
    }

    const { feed_url, feed_type } = feedData;
    const baseStyle = 'width:100%;height:100%;display:block;object-fit:contain;border:none;pointer-events:none;user-select:none;';

    // Build the Tactical CCTV HUD Overlay (Pointer events none, authentic military live monitor overlay)
    const hudOverlayHtml = `
      <div class="cctv-hud-overlay">
        <div class="cctv-hud-optic-corners"></div>
        <div class="cctv-hud-center-cross"></div>
        <div class="cctv-hud-top">
          <div class="cctv-hud-live-tag">
            <span class="cctv-live-pulse"></span>
            <span>● REC // LIVE</span>
          </div>
          <div class="cctv-hud-time" id="cctv-hud-time">UTC --:--:--</div>
        </div>
        <div class="cctv-hud-bottom">
          <span>SIG: 99.4% [SECURE] // 1080P</span>
          <span>OPTIC: AUTO // 30FPS</span>
        </div>
      </div>
    `;

    // Start live clock for HUD
    const startHudClock = () => {
      const updateClock = () => {
        const el = document.getElementById('cctv-hud-time');
        if (el) {
          const d = new Date();
          el.textContent = d.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
        }
      };
      updateClock();
      this._cctvHudTimer = setInterval(updateClock, 1000);
    };

    if (feed_type === 'm3u8' || feed_type === 'mp4') {
      // HLS / MP4 — native <video> element with autostart and no controls
      container.innerHTML = `
        <div class="cctv-video-wrap">
          <video autoplay muted loop playsinline crossorigin="anonymous"
            style="${baseStyle}" title="LIVE">
            <source src="${feed_url}" type="application/x-mpegURL">
            <source src="${feed_url}" type="video/mp4">
          </video>
          ${hudOverlayHtml}
        </div>
      `;
      startHudClock();
      const vid = container.querySelector('video');
      if (vid) {
        vid.play().catch(() => {});
        vid.onerror = () => { this._removeDeadCamera(props.id, 'STREAM OFFLINE'); };
      }
    } else if (feed_type === 'mjpeg') {
      // MJPEG motion JPEG — proxied through our backend to bypass CORS
      const proxyUrl = (window.apiUrl ? window.apiUrl(`/api/geo/cctv-stream?url=${encodeURIComponent(feed_url)}`) : `/api/geo/cctv-stream?url=${encodeURIComponent(feed_url)}`);
      container.innerHTML = `
        <div class="cctv-video-wrap">
          <img src="${proxyUrl}" style="${baseStyle}" alt="LIVE STREAM">
          ${hudOverlayHtml}
        </div>
      `;
      startHudClock();
      const img = container.querySelector('img');
      if (img) img.onerror = () => { this._removeDeadCamera(props.id, 'STREAM OFFLINE'); };
    } else if (feed_type === 'image') {
      // Snapshot — proxy + auto-refresh every 30 s
      const snap = () => (window.apiUrl ? window.apiUrl(`/api/geo/cctv-stream?url=${encodeURIComponent(feed_url)}&_t=${Date.now()}`) : `/api/geo/cctv-stream?url=${encodeURIComponent(feed_url)}&_t=${Date.now()}`);
      container.innerHTML = `
        <div class="cctv-video-wrap">
          <img id="cctv-snap" src="${snap()}" style="${baseStyle}" alt="LIVE SNAPSHOT">
          ${hudOverlayHtml}
        </div>
      `;
      startHudClock();
      const img = container.querySelector('#cctv-snap');
      if (img) {
        img.onerror = () => { this._removeDeadCamera(props.id, 'STREAM OFFLINE'); };
        this._snapTimer = setInterval(() => {
          const el = document.getElementById('cctv-snap');
          if (el) el.src = snap();
        }, 30000);
      }
    } else if (feed_type === 'iframe' || feed_type === 'direct') {
      // Embed — YouTube or third-party player
      let formattedUrl = feed_url;
      let isYouTube = false;
      let vidId = '';

      if (feed_url.includes('youtube.com/embed/')) {
        vidId = feed_url.split('youtube.com/embed/')[1].split(/[?&]/)[0];
        isYouTube = true;
      } else if (feed_url.includes('youtu.be/')) {
        vidId = feed_url.split('youtu.be/')[1].split(/[?&]/)[0];
        isYouTube = true;
      } else if (feed_url.includes('youtube.com/watch')) {
        try {
          const u = new URL(feed_url);
          vidId = u.searchParams.get('v') || '';
          if (vidId) isYouTube = true;
        } catch {}
      }

      if (isYouTube && vidId) {
        // Enforce autoplay, mute, hide controls, hide annotations, loop, modestbranding, no cookies
        const origin = window.location.origin;
        formattedUrl = `https://www.youtube-nocookie.com/embed/${vidId}?autoplay=1&mute=1&controls=0&modestbranding=1&rel=0&iv_load_policy=3&disablekb=1&fs=0&playsinline=1&enablejsapi=1&loop=1&playlist=${vidId}&origin=${encodeURIComponent(origin)}`;
      } else if (formattedUrl.includes('?') && !formattedUrl.includes('autoplay=')) {
        formattedUrl += '&autoplay=1&muted=1';
      } else if (!formattedUrl.includes('?')) {
        formattedUrl += '?autoplay=1&muted=1';
      }

      const frameClass = isYouTube ? 'cctv-embedded-frame cctv-youtube-crop' : 'cctv-embedded-frame';

      container.innerHTML = `
        <div class="cctv-video-wrap">
          <iframe src="${formattedUrl}"
            class="${frameClass}"
            sandbox="allow-scripts allow-same-origin allow-popups"
            allow="autoplay; encrypted-media"
            allowfullscreen
            title="LIVE STREAM" loading="lazy"></iframe>
          ${hudOverlayHtml}
        </div>
      `;
      startHudClock();
    } else {
      // Unknown type — try as direct video first, then image
      container.innerHTML = `
        <div class="cctv-video-wrap">
          <video autoplay muted loop playsinline style="${baseStyle}" title="LIVE">
            <source src="${feed_url}">
          </video>
          ${hudOverlayHtml}
        </div>
      `;
      startHudClock();
      const vid = container.querySelector('video');
      if (vid) {
        vid.play().catch(() => {});
        vid.onerror = () => {
          container.innerHTML = `
            <div class="cctv-video-wrap">
              <img src="${feed_url}" style="${baseStyle}" alt="LIVE"
                onerror="this.parentElement.parentElement.innerHTML=''">
              ${hudOverlayHtml}
            </div>
          `;
          startHudClock();
        };
      }
    }

  }

  // ═══════════════════════════════════════════════

  //  CINEMA MODE — Automated surveillance tour of real events

  // ═══════════════════════════════════════════════

  _toggleCinema(forceOff = false) {
    const btnCinema = document.getElementById('btn-cinema');

    if (this._isCinemaRunning || this._cinemaInterval || forceOff) {
      this._isCinemaRunning = false;
      if (this._cinemaInterval) {
        clearInterval(this._cinemaInterval);
        this._cinemaInterval = null;
      }
      this._cinemaTourTargets = [];
      this._cinemaTourIdx = 0;
      if (this.globe) {
        this.globe.cancelFlight();
        this.globe.stopChaseCam();
      }
      if (btnCinema) {
        btnCinema.textContent = '🎬 CINEMA';
        btnCinema.style.background = '';
      }
      if (this.ui.status) this.ui.status.textContent = 'CINEMA TOUR: OFF // CAMERA LOCKED';
      console.log('[Cinema] Tour halted immediately.');
      return;
    }

    this._isCinemaRunning = true;
    if (btnCinema) {
      btnCinema.textContent = '🎬 CINEMA ●';
      btnCinema.style.background = 'rgba(255,107,107,0.35)';
    }
    if (this.ui.status) this.ui.status.textContent = 'CINEMA TOUR: ACTIVE (PRESS ESC OR TOUCH GLOBE TO STOP)';
    console.log('[Cinema] Tour started.');

    this._cinemaTourTargets = [];
    this._cinemaTourIdx = 0;
    this._buildCinemaTour().then(() => {
      if (!this._isCinemaRunning) return; // Abort if user toggled off while building tour
      this._cinemaTick();
      if (!this._isCinemaRunning) return;
      this._cinemaInterval = setInterval(() => {
        if (!this._isCinemaRunning) {
          clearInterval(this._cinemaInterval);
          this._cinemaInterval = null;
          return;
        }
        this._cinemaTick();
      }, 12000);
    }).catch(e => {
      console.warn('[Cinema] Error building tour:', e);
      this._isCinemaRunning = false;
      if (btnCinema) { btnCinema.textContent = '🎬 CINEMA'; btnCinema.style.background = ''; }
    });
  }

  async _buildCinemaTour() {

    const targets = [];

    // Earthquakes ≥ 5.0

    try {

      const eqs = await APIService.fetchEarthquakes();

      eqs.filter(e => e.magnitude >= 5.0).slice(0, 5).forEach(e => targets.push({

        lat: e.latitude, lon: e.longitude, alt: 500000,

        label: `M${e.magnitude.toFixed(1)} Earthquake — ${e.place}`

      }));

    } catch (_) {}

    // Active wildfires with high FRP

    if (this.globe.dataSources?.wildfires?.entities?.values?.length > 0) {

      const fireEntities = this.globe.dataSources.wildfires.entities.values;

      fireEntities.filter(e => (e.properties?.frp?.getValue?.() || 0) >= 300).slice(0, 5).forEach(e => {

        const lat = e.properties.latitude?.getValue?.();

        const lon = e.properties.longitude?.getValue?.();

        if (lat && lon) targets.push({ lat, lon, alt: 250000, label: `🔥 Wildfire — FRP ${e.properties.frp?.getValue?.()}MW` });

      });

    }

    // Emergency squawks

    if (this._lastSquawks?.length > 0) {

      this._lastSquawks.slice(0, 3).forEach(ac => targets.push({

        lat: ac.latitude ?? ac.lat, lon: ac.longitude ?? ac.long, alt: 150000,

        label: `🚨 SQUAWK ${ac.squawk} — ${ac.callsign || ac.icao24}`

      }));

    }

    // Weather alerts: extreme severity

    try {

      const alerts = await APIService.fetchWeatherAlerts();

      alerts.filter(a => a.severity === 'Extreme' && a.centroid).slice(0, 5).forEach(a => targets.push({

        lat: a.centroid[1], lon: a.centroid[0], alt: 1000000,

        label: `⚠️ ${a.event} — ${a.areaDesc}`

      }));

    } catch (_) {}

    // Fallback to notable real locations if no events

    if (targets.length < 3) {

      targets.push(

        { lat: 33.6844, lon: 73.0479, alt: 2000000, label: 'South Asia Region' },

        { lat: 48.3794, lon: 31.1656, alt: 2000000, label: 'Eastern Europe' },

        { lat: 35.6762, lon: 139.6503, alt: 1500000, label: 'Tokyo Metro' },

        { lat: 40.7128, lon: -74.0060, alt: 1500000, label: 'New York City' },

        { lat: 51.5074, lon: -0.1278, alt: 1500000, label: 'London' }

      );

    }

    this._cinemaTourTargets = targets;

  }

  _cinemaTick() {
    if (!this._isCinemaRunning) return;
    if (!this._cinemaTourTargets?.length) return;

    const t = this._cinemaTourTargets[this._cinemaTourIdx % this._cinemaTourTargets.length];

    this._cinemaTourIdx++;

    if (!t || !Number.isFinite(t.lat) || !Number.isFinite(t.lon)) return;

    this.globe.flyTo(t.lat, t.lon, t.alt || 800000, 4);

    if (this.ui.status) this.ui.status.textContent = `🎬 ${t.label}`;

  }

  // ═══════════════════════════════════════════════

  //  PRESET SWITCHER — Enable layer combinations for quick SA

  // ═══════════════════════════════════════════════

  _applyPreset(preset) {

    const PRESETS = {

      'command-center':    { flights: true, vessels: true, satellites: true, earthquakes: false, cctv: false, nuclear: false, military: true, conflicts: true, wildfires: false, weatherAlerts: true },

      'war-conflict':      { flights: true, vessels: true, satellites: false, earthquakes: false, cctv: false, nuclear: true, military: true, conflicts: true, wildfires: false, weatherAlerts: false },

      'natural-disaster':  { flights: true, vessels: false, satellites: false, earthquakes: true, cctv: false, nuclear: false, military: false, conflicts: false, wildfires: true, weatherAlerts: true, naturalEvents: true },

      'maritime':          { flights: false, vessels: true, satellites: false, earthquakes: false, cctv: false, nuclear: false, military: false, conflicts: false, wildfires: false, weatherAlerts: false, waterways: true, cables: true },

      'aviation':          { flights: true, vessels: false, satellites: true, earthquakes: false, cctv: false, nuclear: false, military: false, conflicts: false, wildfires: false, weatherAlerts: false },

      'nuclear':           { flights: false, vessels: false, satellites: true, earthquakes: false, cctv: false, nuclear: true, military: true, conflicts: false, wildfires: false, weatherAlerts: false },

      'cyber-intel':       { flights: false, vessels: false, satellites: true, earthquakes: false, cctv: true, nuclear: false, military: false, conflicts: false, wildfires: false, weatherAlerts: false, cables: true, hotspots: true },

      'space-weather':     { flights: false, vessels: false, satellites: true, earthquakes: false, cctv: false, nuclear: false, military: false, conflicts: false, wildfires: false, weatherAlerts: false, spaceports: true },

    };

    const config = PRESETS[preset];

    if (!config) return;

    Object.entries(config).forEach(([layer, on]) => {

      if (this.state.layers[layer] !== on) this.toggleLayer(layer);

    });

    if (this.ui.status) this.ui.status.textContent = `Preset applied: ${preset.toUpperCase().replace(/-/g, ' ')}`;

  }

  // ═══════════════════════════════════════════════

  //  EMERGENCY SQUAWKS — Real 7500/7600/7700 polling

  // ═══════════════════════════════════════════════

  async _fetchEmergencySquawks() {

    try {

      const squawks = await APIService.fetchEmergencySquawks();

      this._lastSquawks = squawks;

      this.globe.updateEmergencySquawks(squawks);

      this.updateRadarSquawksUI(squawks);

      const alertBanner = document.getElementById('ticker-squawk-alert');

      if (alertBanner) alertBanner.style.display = squawks.length > 0 ? 'inline' : 'none';

    } catch (e) {

      console.warn('[AppController] Emergency squawks error:', e.message);

    }

  }

  // ═══════════════════════════════════════════════

  //  3D TACTICAL AIR SURVEILLANCE RADAR METHODS

  // ═══════════════════════════════════════════════

    syncRadarWithCurrentWindow() {
    if (!this.radarScope || !this.state.airRadarOpen) return;
    const payload = this.globe.getVisibleContactsInWindow();
    this.radarScope.updateWindowContacts(payload);

    // Update Situation Telemetry Counters
    if (this.ui.radarCounts) {
      if (this.ui.radarCounts.total) this.ui.radarCounts.total.textContent = payload.counts.air.toLocaleString();
      if (this.ui.radarCounts.mil) this.ui.radarCounts.mil.textContent = payload.counts.sea.toLocaleString();
      if (this.ui.radarCounts.comm) this.ui.radarCounts.comm.textContent = payload.counts.sat.toLocaleString();
      if (this.ui.radarCounts.emg) this.ui.radarCounts.emg.textContent = payload.counts.tactical.toLocaleString();
    }

    const modeBadge = document.getElementById('radar-scope-mode-badge');
    if (modeBadge) {
      modeBadge.textContent = `SYNC: WINDOW (${payload.counts.total} LIVE)`;
    }
  }

  toggleAirRadar(forceState = null) {

    const next = forceState !== null ? forceState : !this.state.airRadarOpen;

    this.state.airRadarOpen = next;

    if (this.ui.btnAirRadar) {

      if (next) {

        this.ui.btnAirRadar.classList.add('active');

        this.ui.btnAirRadar.style.background = 'rgba(0,255,209,0.3)';

        this.ui.btnAirRadar.style.boxShadow = '0 0 12px rgba(0,255,209,0.6)';

      } else {

        this.ui.btnAirRadar.classList.remove('active');

        this.ui.btnAirRadar.style.background = 'rgba(0,255,209,0.12)';

        this.ui.btnAirRadar.style.boxShadow = 'none';

      }

    }

    const sidebarAirRadarEl = document.getElementById('sidebar-btn-air-radar');

    if (sidebarAirRadarEl) {

      if (next) {

        sidebarAirRadarEl.style.background = 'rgba(0,255,209,0.38)';

        sidebarAirRadarEl.style.boxShadow = '0 0 20px rgba(0,255,209,0.7)';

        sidebarAirRadarEl.style.borderColor = '#00ffd1';

      } else {

        sidebarAirRadarEl.style.background = 'rgba(0,255,209,0.18)';

        sidebarAirRadarEl.style.boxShadow = '0 0 15px rgba(0,255,209,0.3)';

      }

    }

    if (this.ui.airRadarPanel) {

      if (next) {

        this.ui.airRadarPanel.classList.remove('hidden');

      } else {

        this.ui.airRadarPanel.classList.add('hidden');

      }

    }

    this.globe.setAirRadarMode(next);

    if (next) {
      if (this.radarScope) {
        this.radarScope.start();
        this.syncRadarWithCurrentWindow();
      }
      this.globe.onCameraMoveContinuous = () => this.syncRadarWithCurrentWindow();
      this.fetchLayer('flights');
    } else {
      if (this.radarScope) {
        this.radarScope.stop();
      }
      this.globe.onCameraMoveContinuous = null;
    }

    if (next) {

      this.fetchLayer('flights');

      if (this._lastSquawks) {

        this.updateRadarSquawksUI(this._lastSquawks);

      }

    }

  }

  updateAirRadarTelemetry(flights) {

    if (!flights || !Array.isArray(flights)) return;
    this._lastFlights = flights;
    if (this.state.airRadarOpen) {
      this.syncRadarWithCurrentWindow();
    }

    const total = flights.length;

    const mil = flights.filter(f => f.type === 'military').length;

    const comm = flights.filter(f => f.type === 'commercial').length;

    const emg = flights.filter(f => f.type === 'emergency').length;

    if (this.ui.radarCounts.total) this.ui.radarCounts.total.textContent = total.toLocaleString();

    if (this.ui.radarCounts.mil) this.ui.radarCounts.mil.textContent = mil.toLocaleString();

    if (this.ui.radarCounts.comm) this.ui.radarCounts.comm.textContent = comm.toLocaleString();

    if (this.ui.radarCounts.emg) this.ui.radarCounts.emg.textContent = emg.toLocaleString();

    if (this.ui.radarCounts.defcon) {

      if (emg > 0) {

        this.ui.radarCounts.defcon.textContent = 'DEFCON 1 // SQUAWK ALERT';

        this.ui.radarCounts.defcon.style.color = '#ff3333';

      } else if (mil > 40) {

        this.ui.radarCounts.defcon.textContent = 'DEFCON 2 // HIGH MIL AIR';

        this.ui.radarCounts.defcon.style.color = '#ffaa00';

      } else {

        this.ui.radarCounts.defcon.textContent = 'DEFCON 4 // NOMINAL';

        this.ui.radarCounts.defcon.style.color = '#00ff88';

      }

    }

  }

  updateRadarSquawksUI(squawks) {

    if (!this.ui.radarSquawksContainer || !this.ui.radarSquawksList) return;

    if (!squawks || squawks.length === 0) {

      this.ui.radarSquawksContainer.style.display = 'none';

      this.ui.radarSquawksList.innerHTML = '';

      return;

    }

    this.ui.radarSquawksContainer.style.display = 'block';

    this.ui.radarSquawksList.innerHTML = squawks.map(sq => {

      const cs = sq.callsign || sq.icao24;

      return `

        <div class="radar-squawk-card" data-icao="${sq.icao24}">

          <div>

            <span style="font-weight:bold; color:#ff3333;">🚨 SQ ${sq.squawk}</span>

            <span style="color:#fff; margin-left:6px;">${cs}</span>

          </div>

          <div style="color:#aaa; font-size:9px;">${sq.squawk_meaning || 'EMERGENCY'}</div>

        </div>

      `;

    }).join('');

    this.ui.radarSquawksList.querySelectorAll('.radar-squawk-card').forEach(card => {

      card.addEventListener('click', (e) => {

        const icao = e.currentTarget.dataset.icao;

        if (icao) {

          this.globe.interceptFlight(icao);

        }

      });

    });

  }

  // ═══════════════════════════════════════════════

  //  MARKET TICKER — Real Yahoo Finance + CoinGecko

  // ═══════════════════════════════════════════════

  async _fetchMarketTicker() {

    try {

      const [market, sentiment] = await Promise.allSettled([

        APIService.fetchMarketData(),

        APIService.fetchMarketSentiment()

      ]);

      const m = market.status === 'fulfilled' ? market.value : {};

      const s = sentiment.status === 'fulfilled' ? sentiment.value : {};

      const fmt = (v, prefix='$') => v != null ? `${prefix}${Number(v).toLocaleString('en-US', {maximumFractionDigits:2})}` : '—';

      const chg = (v) => v != null ? ` (${v >= 0 ? '+' : ''}${Number(v).toFixed(2)}%)` : '';

      if (m.crypto?.bitcoin) {

        const btc = m.crypto.bitcoin;

        const el = document.getElementById('ticker-btc');

        if (el) el.textContent = `BTC: ${fmt(btc.price)}${chg(btc.change_24h)}`;

      }

      if (m.commodities?.brent_crude) {

        const oil = m.commodities.brent_crude;

        const el = document.getElementById('ticker-oil');

        if (el) el.textContent = `OIL: ${fmt(oil.price)}${chg(oil.change)}`;

      }

      if (m.commodities?.gold) {

        const gold = m.commodities.gold;

        const el = document.getElementById('ticker-gold');

        if (el) el.textContent = `GOLD: ${fmt(gold.price)}${chg(gold.change)}`;

      }

      if (m.commodities?.silver) {

        const silver = m.commodities.silver;

        const el = document.getElementById('ticker-silver');

        if (el) el.textContent = `SILVER: ${fmt(silver.price)}${chg(silver.change)}`;

      }

      if (m.indices?.sp500) {

        const sp = m.indices.sp500;

        const el = document.getElementById('ticker-sp500');

        if (el) el.textContent = `S&P500: ${fmt(sp.price, '')}${chg(sp.change)}`;

      }

      if (s.label && s.value != null) {

        const el = document.getElementById('ticker-sentiment');

        if (el) el.textContent = `FEAR/GREED: ${s.value} (${s.label})`;

      }

    } catch (e) {

      console.warn('[AppController] Market ticker error:', e.message);

    }

  }

  // ═══════════════════════════════════════════════

  //  SPACE WEATHER — NOAA Kp Index polling

  // ═══════════════════════════════════════════════

  async _fetchSpaceWeather() {

    try {

      const data = await APIService.fetchSpaceWeather();

      if (data && data.status !== 'DEGRADED') {

        this.globe.updateSpaceWeatherAlert(data);

      }

    } catch (e) {

      console.warn('[AppController] Space weather error:', e.message);

    }

  }

}

// Start app

const app = new AppController();

document.addEventListener('DOMContentLoaded', () => {

  app.init();

});

// Initialize Vercel Web Analytics

// inject();

