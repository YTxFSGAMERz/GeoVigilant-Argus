/**
 * ARGUS GroundView — Main Controller
 *
 * Entry point for the /ground page.
 * Mirrors the AppController pattern from globe-main.js but for 2D MapLibre.
 *
 * ISOLATION: Cesium is NEVER imported. MapLibre loads lazily via groundMap.js.
 *
 * Data pipeline:
 *   createArgusRuntime(ARGUS_SEED) → tickArgusPipeline() every 2000ms
 *   → updateGroundMapData() → MapLibre layer updates
 */

import { createArgusRuntime } from '../core/runtime.js';
import {
  initGroundMap,
  updateGroundMapData,
  updateMapillaryData,
  setLayerVisible,
  setBasemap,
  flyTo,
  filterLandmarks,
  destroyGroundMap,
} from './groundMap.js';
import { initMapillaryService, getNearbyImages } from './services/mapillaryService.js';
import { ARGUS_SEED } from './types/groundview.js';
import { IntegrityStatus } from '../core/types/events.js';

// ─── Controller Class ─────────────────────────────────────────────────────────

class GroundViewController {
  constructor() {
    // ARGUS Intelligence Pipeline (own instance, same seed as globe for determinism)
    this.runtime = createArgusRuntime(ARGUS_SEED);

    // Live ARGUS state
    this.argusState = {
      nodeStateMap:  new Map(),  // nodeId → NodeTrustState
      latestEvents:  new Map(),  // nodeId → ArgusEvent (most recent)
      incidents:     [],
      anomalyCount:  0,
      scenarioStage: 1,
    };

    // Layer toggles
    this.layers = {
      nodes:        true,
      incidents:    true,
      anomalies:    true,
      landmarks:    true,
      streetscapes: false,
      mapillary:    false,
    };

    // Selected entity for investigation panel
    this.selected = { type: null, data: null };

    // Timers
    this._tickTimer = null;
    this._clockTimer = null;

    // Mapillary state
    this._mapillaryReady = false;

    // Landmark gallery state
    this._landmarkImages = [];
    this._landmarkImgIdx = 0;
    this._isGalleryDragging = false;

    // UI references (populated in bindUI)
    this.ui = {};
  }

  // ─── Initialization ─────────────────────────────────────────────────────────

  async init() {
    this._bindUI();
    this._bindEvents();
    this._initVisualSearch();
    this._loadCategories();
    this._updateClock();
    this._clockTimer = setInterval(() => this._updateClock(), 1000);

    // Status: initializing
    this._setStatus('INITIALIZING GROUNDVIEW...');

    try {
      // Initialize MapLibre map (lazy — downloads maplibre-gl chunk now)
      await initGroundMap('groundview-map', {
        onNodeClick:        (props, lngLat) => this._onNodeClick(props, lngLat),
        onIncidentClick:    (props, lngLat) => this._onIncidentClick(props, lngLat),
        onMapillaryClick:   (props, lngLat) => this._onMapillaryImageClick(props, lngLat),
        onStreetscapeClick: (props, lngLat) => this._onStreetscapeClick(props, lngLat),
        onLandmarkClick:    (props, lngLat) => this._onLandmarkClick(props, lngLat),
        onMapReady: () => {
          // Hide loading overlay — map canvas is now live
          const overlay = document.getElementById('gv-map-loading');
          if (overlay) overlay.classList.add('hidden');

          this._setStatus('MAP ONLINE // ARGUS PIPELINE ACTIVE');
          // Initial tick to populate the map immediately
          this._tickArgusPipeline();
          // Start pipeline loop at 2s intervals
          this._tickTimer = setInterval(() => this._tickArgusPipeline(), 2000);
        },
      });

      // Initialize Mapillary service in background (non-blocking)
      initMapillaryService().then(ready => {
        this._mapillaryReady = ready;
        if (ready) {
          console.log('[GroundView] Mapillary service ready');
        }
      });

      // Expose controller globally
      if (typeof window !== 'undefined') {
        window.groundViewController = this;
      }

      // Check URL parameters for lat, lon / lng, zoom
      const urlParams = new URLSearchParams(window.location.search);
      const latParam = parseFloat(urlParams.get('lat'));
      const lonParam = parseFloat(urlParams.get('lon') || urlParams.get('lng'));
      const zoomParam = parseFloat(urlParams.get('zoom')) || 12;

      if (!isNaN(latParam) && !isNaN(lonParam)) {
        console.log(`[GroundView] Navigating to URL coordinates: ${latParam}, ${lonParam}`);
        setTimeout(() => flyTo(latParam, lonParam, zoomParam), 500);
      } else {
        // Default fallback to SF Bay (ARGUS node cluster location)
        setTimeout(() => flyTo(37.7749, -122.4194, 12), 500);
      }

    } catch (err) {
      console.error('[GroundView] Initialization failed:', err);
      this._setStatus('ERROR: MAP INITIALIZATION FAILED');
    }
  }

  // ─── ARGUS Pipeline Tick ────────────────────────────────────────────────────

  _tickArgusPipeline() {
    const now = Date.now();
    const rt = this.runtime;
    const frames = rt.scenarioRunner.generateTickFrames(now);
    let anomalyCount = 0;

    for (const { event, rawPayloadBytes, signatureBytes, nonce } of frames) {
      // 1. Integrity check
      const receivedAtMs = now + 6;
      const integrityResult = rt.integrityChecker.verifyFrame(
        event.sourceId, rawPayloadBytes, signatureBytes, nonce,
        event.timestamp, receivedAtMs, event.integrity.crcValid,
      );
      event.integrity.status           = integrityResult.status;
      event.integrity.signatureValid   = integrityResult.signatureValid;
      event.integrity.nonceSeen        = integrityResult.nonceSeen;
      event.integrity.timestampDriftMs = integrityResult.timestampDriftMs;

      // 2. Anomaly detection
      const anomalyResult = rt.anomalyDetector.evaluate(event);
      event.analytics.isAnomaly              = anomalyResult.isAnomaly;
      event.analytics.anomalyScore           = anomalyResult.compositeAnomalyScore;
      event.analytics.behavioralAnomalyScore = anomalyResult.behavioralAnomalyScore;
      event.analytics.kinematicAnomalyScore  = anomalyResult.kinematicAnomalyScore;
      event.analytics.frequencyAnomalyScore  = anomalyResult.frequencyAnomalyScore;
      event.analytics.anomalyReasons         = anomalyResult.reasons;

      if (anomalyResult.isAnomaly) anomalyCount++;

      // 3. Trust score update
      const nodeTrustState = rt.trustEngine.evaluateTrust(
        event.sourceId,
        integrityResult,
        anomalyResult.behavioralAnomalyScore,
        anomalyResult.kinematicAnomalyScore,
        anomalyResult.frequencyAnomalyScore,
        event.timestamp,
      );
      event.analytics.trustScore = nodeTrustState.compositeTrust;

      // 4. Incident engine
      rt.incidentEngine.evaluateEventForIncident(event, this.argusState.scenarioStage);

      // Cache state
      this.argusState.nodeStateMap.set(event.sourceId, nodeTrustState);
      this.argusState.latestEvents.set(event.sourceId, event);
    }

    this.argusState.incidents    = rt.incidentEngine.getActiveIncidents();
    this.argusState.anomalyCount = anomalyCount;

    // Push state to map layers
    updateGroundMapData(this.argusState);

    // Update status bar counters
    this._updateStatusBar();
  }

  // ─── UI Binding ─────────────────────────────────────────────────────────────

  _bindUI() {
    const $ = (id) => document.getElementById(id);
    this.ui = {
      status:            $('gv-status-text'),
      timestamp:         $('gv-timestamp'),
      countNodes:        $('gv-count-nodes'),
      countAnomalies:    $('gv-count-anomalies'),
      countIncidents:    $('gv-count-incidents'),

      // Layer toggles
      toggleNodes:       $('toggle-nodes'),
      toggleIncidents:   $('toggle-incidents'),
      toggleAnomalies:   $('toggle-anomalies'),
      toggleLandmarks:   $('toggle-landmarks'),
      categoryFilter:    $('argus-category-filter'),
      toggleStreetscapes:$('toggle-streetscapes'),
      toggleMapillary:   $('toggle-mapillary'),

      // Basemap selectors (3 modes)
      basemapTactical:   $('basemap-tactical') || $('basemap-dark'),
      basemapStreets:    $('basemap-streets'),
      basemapSatellite:  $('basemap-satellite'),

      // Stage controls
      btnStep:           $('gv-btn-step'),
      btnReset:          $('gv-btn-reset'),
      stageBadge:        $('gv-stage-badge'),

      // Investigation panel
      intelPanel:        $('gv-intel-panel'),
      intelClose:        $('gv-intel-close'),
      intelContent:      $('gv-intel-content'),
      intelTitle:        $('gv-intel-title'),

      // SVI HUD Modal
      sviModal:          $('gv-streetscapes-modal'),
      sviClose:          $('gv-svi-close'),

      // Landmark Ground Truth Modal
      landmarkModal:     $('gv-landmark-modal'),
      landmarkClose:     $('gv-landmark-close'),
      landmarkViewport:  $('gv-landmark-viewport'),
      landmarkMainImg:   $('gv-landmark-main-img'),
      landmarkGallery:   $('gv-landmark-gallery'),
      landmarkPrevBtn:   $('gv-lm-prev-btn'),
      landmarkNextBtn:   $('gv-lm-next-btn'),
      landmarkCounter:   $('gv-lm-counter'),

      // Visual Search Modal
      btnVisualSearch:   $('btn-visual-search'),
      visualSearchModal: $('gv-visual-search-modal'),
      visualSearchClose: $('gv-visual-search-close'),

      // Navigation
      btnBackToGlobe:    $('btn-back-to-globe'),

      // Mapillary panel
      mapillaryPanel:    $('gv-mapillary-panel'),
      mapillaryClose:    $('gv-mapillary-close'),
      mapillaryStatus:   $('gv-mapillary-status'),
      mapillaryImages:   $('gv-mapillary-images'),
    };
  }

  _bindEvents() {
    // Layer toggles
    this.ui.toggleNodes?.addEventListener('change', (e) => {
      this.layers.nodes = e.target.checked;
      setLayerVisible('nodes', this.layers.nodes);
    });
    this.ui.toggleIncidents?.addEventListener('change', (e) => {
      this.layers.incidents = e.target.checked;
      setLayerVisible('incidents', this.layers.incidents);
    });
    this.ui.toggleAnomalies?.addEventListener('change', (e) => {
      this.layers.anomalies = e.target.checked;
      setLayerVisible('anomalies', this.layers.anomalies);
    });
    this.ui.toggleLandmarks?.addEventListener('change', (e) => {
      this.layers.landmarks = e.target.checked;
      setLayerVisible('landmarks', this.layers.landmarks);
      if (this.layers.landmarks) {
        this._setStatus('ARGUS LANDMARKS // 3.8K VERIFIED TARGETS ONLINE');
      } else {
        this._setStatus('MAP ONLINE // ARGUS PIPELINE ACTIVE');
      }
    });
    this.ui.categoryFilter?.addEventListener('change', (e) => {
      filterLandmarks(e.target.value);
    });
    this.ui.toggleStreetscapes?.addEventListener('change', (e) => {
      this.layers.streetscapes = e.target.checked;
      setLayerVisible('streetscapes', this.layers.streetscapes);
      if (this.layers.streetscapes) {
        this._setStatus('GLOBAL STREETSCAPES // 10K OBSERVATIONS ONLINE');
      } else {
        this._setStatus('MAP ONLINE // ARGUS PIPELINE ACTIVE');
      }
    });
    this.ui.toggleMapillary?.addEventListener('change', async (e) => {
      this.layers.mapillary = e.target.checked;
      setLayerVisible('mapillary', this.layers.mapillary);
      if (this.layers.mapillary) {
        this._setStatus('QUERYING MAPILLARY COVERAGE...');
        await this._loadMapillaryCoverage();
      } else {
        updateMapillaryData([]);
        this._setStatus('MAP ONLINE // ARGUS PIPELINE ACTIVE');
      }
    });

    // Basemap modes: Tactical, Streets, Satellite
    const updateBasemapActive = (activeBtn) => {
      [this.ui.basemapTactical, this.ui.basemapStreets, this.ui.basemapSatellite].forEach(b => {
        if (b) b.classList.remove('active');
      });
      if (activeBtn) activeBtn.classList.add('active');
    };

    this.ui.basemapTactical?.addEventListener('click', async () => {
      updateBasemapActive(this.ui.basemapTactical);
      await setBasemap('tactical');
    });
    this.ui.basemapStreets?.addEventListener('click', async () => {
      updateBasemapActive(this.ui.basemapStreets);
      await setBasemap('streets');
    });
    this.ui.basemapSatellite?.addEventListener('click', async () => {
      updateBasemapActive(this.ui.basemapSatellite);
      await setBasemap('satellite');
    });

    // Sensor mesh scan & sync controls
    this.ui.btnStep?.addEventListener('click', () => {
      if (this.ui.stageBadge) {
        this.ui.stageBadge.textContent = 'SCANNING GRID...';
        this.ui.stageBadge.style.color = '#FFCC00';
      }
      this._setStatus('SCANNING SENSOR MESH TELEMETRY...');
      this._tickArgusPipeline();
      setTimeout(() => {
        if (this.ui.stageBadge) {
          this.ui.stageBadge.textContent = 'GRID ONLINE';
          this.ui.stageBadge.style.color = '#00FFD1';
        }
        this._setStatus('MAP ONLINE // SENSOR MESH VERIFIED');
      }, 800);
    });
    this.ui.btnReset?.addEventListener('click', () => {
      if (this.ui.stageBadge) {
        this.ui.stageBadge.textContent = 'SYNCING MESH...';
        this.ui.stageBadge.style.color = '#00FFD1';
      }
      this._setStatus('SYNCHRONIZING SENSOR MESH...');
      for (const nodeId of this.argusState.nodeStateMap.keys()) {
        this.runtime.trustEngine.resetNode(nodeId, Date.now());
      }
      this._tickArgusPipeline();
      setTimeout(() => {
        if (this.ui.stageBadge) {
          this.ui.stageBadge.textContent = 'MESH SYNCED';
          this.ui.stageBadge.style.color = '#00FFD1';
        }
        this._setStatus('MAP ONLINE // SENSOR MESH SYNCHRONIZED');
      }, 600);
    });

    // Intel panel close
    this.ui.intelClose?.addEventListener('click', () => {
      this.ui.intelPanel?.classList.add('hidden');
      this.selected = { type: null, data: null };
    });

    // SVI Modal close
    this.ui.sviClose?.addEventListener('click', () => {
      this.ui.sviModal?.classList.add('hidden');
    });

    // Landmark Modal close
    this.ui.landmarkClose?.addEventListener('click', () => {
      this.ui.landmarkModal?.classList.add('hidden');
    });

    // Landmark Modal gallery mouse wheel & drag-to-scroll
    const galleryEl = this.ui.landmarkGallery || document.getElementById('gv-landmark-gallery');
    if (galleryEl) {
      // Horizontal mouse wheel scrolling without needing bottom scrollbar or Shift key
      galleryEl.addEventListener('wheel', (e) => {
        e.preventDefault();
        let delta = Math.abs(e.deltaY) >= Math.abs(e.deltaX) ? e.deltaY : e.deltaX;
        if (e.deltaMode === 1) delta *= 33;
        else if (e.deltaMode === 2) delta *= 100;
        galleryEl.scrollLeft += delta;
      }, { passive: false });

      // Mouse drag-to-scroll
      let isDown = false;
      let startX = 0;
      let scrollLeftStart = 0;
      let hasDragged = false;

      galleryEl.addEventListener('mousedown', (e) => {
        if (e.button !== 0) return;
        isDown = true;
        hasDragged = false;
        this._isGalleryDragging = false;
        galleryEl.classList.add('is-dragging');
        startX = e.pageX - galleryEl.offsetLeft;
        scrollLeftStart = galleryEl.scrollLeft;
      });

      window.addEventListener('mouseup', () => {
        if (isDown) {
          isDown = false;
          galleryEl.classList.remove('is-dragging');
          if (hasDragged) {
            setTimeout(() => { this._isGalleryDragging = false; }, 50);
          } else {
            this._isGalleryDragging = false;
          }
        }
      });

      galleryEl.addEventListener('mousemove', (e) => {
        if (!isDown) return;
        const x = e.pageX - galleryEl.offsetLeft;
        const walk = (x - startX);
        if (Math.abs(walk) > 4) {
          hasDragged = true;
          this._isGalleryDragging = true;
          e.preventDefault();
        }
        galleryEl.scrollLeft = scrollLeftStart - walk;
      });
    }

    // Viewport mouse wheel: cycle next/previous photo
    const viewportEl = this.ui.landmarkViewport || document.getElementById('gv-landmark-viewport');
    if (viewportEl) {
      let lastWheelTime = 0;
      viewportEl.addEventListener('wheel', (e) => {
        e.preventDefault();
        const now = Date.now();
        if (now - lastWheelTime < 180) return;
        lastWheelTime = now;
        if (e.deltaY > 0 || e.deltaX > 0) {
          this._selectLandmarkImage(this._landmarkImgIdx + 1);
        } else if (e.deltaY < 0 || e.deltaX < 0) {
          this._selectLandmarkImage(this._landmarkImgIdx - 1);
        }
      }, { passive: false });
    }

    // Viewport prev / next buttons
    this.ui.landmarkPrevBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      this._selectLandmarkImage(this._landmarkImgIdx - 1);
    });
    this.ui.landmarkNextBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      this._selectLandmarkImage(this._landmarkImgIdx + 1);
    });

    // Visual Search Modal open/close
    this.ui.btnVisualSearch?.addEventListener('click', () => {
      this.ui.visualSearchModal?.classList.remove('hidden');
    });
    this.ui.visualSearchClose?.addEventListener('click', () => {
      this.ui.visualSearchModal?.classList.add('hidden');
    });

    // Mapillary panel close
    this.ui.mapillaryClose?.addEventListener('click', () => {
      this.ui.mapillaryPanel?.classList.add('hidden');
    });

    // Back to globe
    this.ui.btnBackToGlobe?.addEventListener('click', () => {
      window.location.href = '/earth';
    });

    // Keyboard: Escape closes panels; Arrow keys navigate photos
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        this.ui.intelPanel?.classList.add('hidden');
        this.ui.mapillaryPanel?.classList.add('hidden');
        this.ui.sviModal?.classList.add('hidden');
        this.ui.landmarkModal?.classList.add('hidden');
        this.ui.visualSearchModal?.classList.add('hidden');
        this.selected = { type: null, data: null };
      }
      const lmModal = this.ui.landmarkModal || document.getElementById('gv-landmark-modal');
      if (lmModal && !lmModal.classList.contains('hidden')) {
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
          e.preventDefault();
          this._selectLandmarkImage(this._landmarkImgIdx + 1);
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
          e.preventDefault();
          this._selectLandmarkImage(this._landmarkImgIdx - 1);
        }
      }
    });
  }

  // ─── Categories Loader ───────────────────────────────────────────────────────

  async _loadCategories() {
    try {
      const res = await fetch('/api/argus/categories');
      if (!res.ok) return;
      const categories = await res.json();
      const sel = this.ui.categoryFilter;
      if (!sel) return;

      sel.innerHTML = '<option value="ALL">🏛️ ALL CATEGORIES (3.8K)</option>';
      categories.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.id;
        opt.textContent = `${c.icon} ${c.label.toUpperCase()} (${c.count})`;
        sel.appendChild(opt);
      });
    } catch (err) {
      console.warn('[GroundView] Error loading categories:', err);
    }
  }

  // ─── Landmark Image Selection ───────────────────────────────────────────────

  _selectLandmarkImage(idx) {
    if (!this._landmarkImages || this._landmarkImages.length === 0) return;
    const total = this._landmarkImages.length;
    const newIdx = (idx % total + total) % total;
    this._landmarkImgIdx = newIdx;
    const img = this._landmarkImages[newIdx];

    const mainImg = this.ui.landmarkMainImg || document.getElementById('gv-landmark-main-img');
    if (mainImg && img) {
      mainImg.src = img.url;
      const authorEl = document.getElementById('gv-landmark-author');
      if (authorEl) authorEl.textContent = img.attribution || img.author || 'Open Source';
      const licenseEl = document.getElementById('gv-landmark-license');
      if (licenseEl) licenseEl.textContent = img.license || 'CC BY-SA';
    }

    const counterEl = this.ui.landmarkCounter || document.getElementById('gv-lm-counter');
    if (counterEl) {
      counterEl.textContent = `${newIdx + 1} / ${total}`;
    }

    const galleryEl = this.ui.landmarkGallery || document.getElementById('gv-landmark-gallery');
    if (galleryEl) {
      const thumbs = galleryEl.querySelectorAll('.gv-gallery-thumb');
      thumbs.forEach((t, i) => {
        if (i === newIdx) {
          t.classList.add('active');
          t.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        } else {
          t.classList.remove('active');
        }
      });
    }
  }

  // ─── Landmark Click Handler ──────────────────────────────────────────────────

  async _onLandmarkClick(props, lngLat) {
    const placeId = props.place_id;
    const modal = document.getElementById('gv-landmark-modal');
    if (!modal) return;

    modal.classList.remove('hidden');
    document.getElementById('gv-landmark-name').textContent = props.name || 'LANDMARK TARGET';
    document.getElementById('gv-landmark-category').textContent = (props.category_label || props.category || 'MONUMENT').toUpperCase();
    document.getElementById('gv-landmark-country').textContent = `${props.city ? props.city + ', ' : ''}${props.country || ''}`;
    document.getElementById('gv-landmark-coords').textContent = `${Number(props.latitude ?? lngLat.lat).toFixed(5)}°N, ${Number(props.longitude ?? lngLat.lng).toFixed(5)}°E`;

    const galleryEl = this.ui.landmarkGallery || document.getElementById('gv-landmark-gallery');
    if (galleryEl) {
      galleryEl.innerHTML = '<div style="color:rgba(0,255,209,0.5); padding:20px; font-family:monospace;">FETCHING MULTI-PERSPECTIVE VISUAL ASSETS...</div>';
    }

    try {
      const res = await fetch(`/api/argus/places/${placeId}`);
      if (!res.ok) return;
      const place = await res.json();

      this._landmarkImages = place.images || [];
      this._landmarkImgIdx = 0;
      const total = this._landmarkImages.length;

      const prevBtn = this.ui.landmarkPrevBtn || document.getElementById('gv-lm-prev-btn');
      const nextBtn = this.ui.landmarkNextBtn || document.getElementById('gv-lm-next-btn');
      const counterEl = this.ui.landmarkCounter || document.getElementById('gv-lm-counter');
      if (prevBtn) prevBtn.style.display = total > 1 ? 'flex' : 'none';
      if (nextBtn) nextBtn.style.display = total > 1 ? 'flex' : 'none';
      if (counterEl) counterEl.style.display = total > 1 ? 'block' : 'none';

      if (galleryEl) {
        galleryEl.innerHTML = '';
        this._landmarkImages.forEach((img, idx) => {
          const card = document.createElement('div');
          card.className = 'gv-gallery-thumb' + (idx === 0 ? ' active' : '');
          const headingLabel = img.heading !== null && img.heading !== undefined ? `${Math.round(img.heading)}°` : (img.image_type === 'landmark' ? 'CANONICAL' : 'STREET');
          card.innerHTML = `
            <img src="${img.url}" alt="Heading ${headingLabel}" loading="lazy" draggable="false" />
            <span class="gv-thumb-badge">${headingLabel}</span>
          `;
          card.onclick = () => {
            if (this._isGalleryDragging) return;
            this._selectLandmarkImage(idx);
          };
          galleryEl.appendChild(card);
        });
      }

      this._selectLandmarkImage(0);

      // External links
      const wikiBtn = document.getElementById('gv-landmark-wiki-link');
      if (wikiBtn) {
        wikiBtn.onclick = () => {
          if (place.wikipedia_url) window.open(place.wikipedia_url, '_blank');
        };
        wikiBtn.style.display = place.wikipedia_url ? 'inline-block' : 'none';
      }

      const flyBtn = document.getElementById('gv-landmark-fly');
      if (flyBtn) {
        flyBtn.onclick = () => {
          flyTo(place.latitude, place.longitude, 16);
        };
      }

      const aiBtn = document.getElementById('gv-landmark-ask-ai');
      if (aiBtn) {
        aiBtn.onclick = () => {
          if (window.argusAskAbout) {
            window.argusAskAbout({
              type: 'landmark',
              data: place,
              coords: { lat: place.latitude, lng: place.longitude }
            });
          }
        };
      }

    } catch (err) {
      console.error('[GroundView] Error fetching landmark detail:', err);
    }
  }

  // ─── Visual Search Module ───────────────────────────────────────────────────

  _initVisualSearch() {
    const dropzone = document.getElementById('gv-vs-dropzone');
    const fileInput = document.getElementById('gv-vs-file-input');
    const resultsContainer = document.getElementById('gv-vs-results');
    const statusText = document.getElementById('gv-vs-status');

    if (!dropzone || !fileInput) return;

    dropzone.onclick = () => fileInput.click();

    dropzone.ondragover = (e) => {
      e.preventDefault();
      dropzone.classList.add('drag-active');
    };
    dropzone.ondragleave = () => dropzone.classList.remove('drag-active');
    dropzone.ondrop = (e) => {
      e.preventDefault();
      dropzone.classList.remove('drag-active');
      if (e.dataTransfer.files.length) {
        this._executeVisualSearch(e.dataTransfer.files[0]);
      }
    };

    fileInput.onchange = () => {
      if (fileInput.files.length) {
        this._executeVisualSearch(fileInput.files[0]);
      }
    };
  }

  async _executeVisualSearch(file) {
    const resultsContainer = document.getElementById('gv-vs-results');
    const statusText = document.getElementById('gv-vs-status');
    const previewImg = document.getElementById('gv-vs-preview');

    if (previewImg) {
      previewImg.src = URL.createObjectURL(file);
      previewImg.style.display = 'block';
    }

    if (statusText) statusText.textContent = 'COMPUTING 64-BIT DCT PHASH & SCANNING BK-TREE...';
    if (resultsContainer) resultsContainer.innerHTML = '';

    const formData = new FormData();
    formData.append('image', file);

    try {
      const res = await fetch('/api/argus/visual-search?max_dist=16&limit=8', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();

      if (!data.matches || data.matches.length === 0) {
        if (statusText) statusText.textContent = `NO EXACT LANDMARK MATCH FOUND (pHash: ${data.computed_phash || '---'})`;
        return;
      }

      if (statusText) {
        statusText.innerHTML = `MATCHED <span style="color:#00FFD1;">${data.matches.length} TARGETS</span> VIA BK-TREE (pHash: <code>${data.computed_phash}</code>)`;
      }

      data.matches.forEach((m) => {
        const item = document.createElement('div');
        item.className = 'gv-vs-result-card';
        item.innerHTML = `
          <img src="${m.image_url}" alt="${m.place_name}" />
          <div class="gv-vs-info">
            <div class="gv-vs-name">${m.place_name}</div>
            <div class="gv-vs-meta">${m.city ? m.city + ', ' : ''}${m.country} // ${m.category.toUpperCase()}</div>
            <div class="gv-vs-score">
              <span class="gv-vs-conf">CONFIDENCE: ${m.confidence_percent}%</span>
              <span class="gv-vs-dist">HAMMING: ${m.hamming_distance}</span>
            </div>
            <button class="gv-vs-fly-btn" data-lat="${m.latitude}" data-lon="${m.longitude}">🎯 FLY TO TARGET</button>
          </div>
        `;

        item.querySelector('.gv-vs-fly-btn').onclick = (e) => {
          e.stopPropagation();
          const lat = parseFloat(e.target.dataset.lat);
          const lon = parseFloat(e.target.dataset.lon);
          flyTo(lat, lon, 15);
          this.ui.visualSearchModal?.classList.add('hidden');
        };

        item.onclick = () => {
          this._onLandmarkClick({ place_id: m.place_id, name: m.place_name, country: m.country, city: m.city, category: m.category, latitude: m.latitude, longitude: m.longitude }, { lat: m.latitude, lng: m.longitude });
        };

        resultsContainer.appendChild(item);
      });

    } catch (err) {
      console.error('[VisualSearch] Search failed:', err);
      if (statusText) statusText.textContent = 'ERROR PERFORMING VISUAL SEARCH';
    }
  }

  // ─── Streetscapes Click Handler ───────────────────────────────────────────────

  _onStreetscapeClick(props, lngLat) {
    const id = props.id ?? 0;
    const lat = Number(props.lat ?? lngLat.lat).toFixed(6);
    const lon = Number(props.lon ?? lngLat.lng).toFixed(6);

    const $ = (id) => document.getElementById(id);
    const modal = $('gv-streetscapes-modal');
    if (!modal) return;

    $('gv-svi-id').textContent = `ARGUS VISUAL SENSOR // SVI-${String(id).padStart(4, '0')}`;
    $('gv-svi-lat').textContent = `${lat}°`;
    $('gv-svi-lon').textContent = `${lon}°`;
    $('gv-svi-lighting').textContent = props.lighting || 'DAYLIGHT';
    $('gv-svi-weather').textContent = props.weather || 'CLEAR';
    $('gv-svi-platform').textContent = props.platform || 'STREET LEVEL';
    $('gv-svi-quality').textContent = props.quality || 'HD // OPTICAL';

    // Set image source with smooth fade-in
    const img = $('gv-svi-image');
    if (img) {
      img.style.opacity = '0.3';
      img.onload = () => { img.style.opacity = '1'; };
      img.onerror = () => { img.style.opacity = '0.8'; };
      img.src = `/api/groundview/streetscapes/image/${id}`;
    }

    modal.classList.remove('hidden');

    // Wire up fly button
    const flyBtn = $('gv-svi-fly');
    if (flyBtn) {
      flyBtn.onclick = () => {
        flyTo(Number(lat), Number(lon), 16);
      };
    }

    // Wire up scan pipeline button
    const scanBtn = $('gv-svi-scan');
    if (scanBtn) {
      scanBtn.onclick = () => {
        scanBtn.textContent = 'SCANNING...';
        setTimeout(() => {
          scanBtn.textContent = '✓ SCAN COMPLETE';
          setTimeout(() => { scanBtn.textContent = '⚡ SCAN PIPELINE'; }, 2000);
        }, 1200);
      };
    }
  }

  // ─── Entity Click Handlers ──────────────────────────────────────────────────

  _onNodeClick(props, lngLat) {
    this.selected = { type: 'node', data: props };
    flyTo(lngLat.lat, lngLat.lng, 14);

    const reasons = _parseJsonArray(props.anomalyReasons);
    const integrityClass = props.integrityStatus === IntegrityStatus.VERIFIED
      ? 'gv-good' : 'gv-alert';

    const trustColor = props.trustScore >= 0.75 ? 'gv-good'
      : props.trustScore >= 0.45 ? 'gv-warn' : 'gv-alert';

    this.ui.intelTitle.textContent = `📡 ${props.nodeId}`;
    this.ui.intelContent.innerHTML = `
      <div class="gv-intel-row">
        <span class="gv-intel-label">TRUST SCORE</span>
        <span class="gv-intel-value ${trustColor}">${props.trustPct}%</span>
      </div>
      <div class="gv-intel-row">
        <span class="gv-intel-label">INTEGRITY</span>
        <span class="gv-intel-value ${integrityClass}">${props.integrityStatus}</span>
      </div>
      <div class="gv-intel-row">
        <span class="gv-intel-label">ANOMALY</span>
        <span class="gv-intel-value ${props.isAnomaly ? 'gv-alert' : 'gv-good'}">
          ${props.isAnomaly ? `⚠ ${Math.round(props.anomalyScore * 100)}%` : '✓ NOMINAL'}
        </span>
      </div>
      <div class="gv-intel-row">
        <span class="gv-intel-label">QUARANTINE</span>
        <span class="gv-intel-value ${props.isQuarantined ? 'gv-purple' : 'gv-good'}">
          ${props.isQuarantined ? '⛔ ACTIVE' : '✓ NONE'}
        </span>
      </div>
      <div class="gv-intel-row">
        <span class="gv-intel-label">TEMPERATURE</span>
        <span class="gv-intel-value">${Number(props.temperatureCelsius).toFixed(1)}°C</span>
      </div>
      <div class="gv-intel-row">
        <span class="gv-intel-label">BATTERY</span>
        <span class="gv-intel-value">${props.batteryPercent}%</span>
      </div>
      <div class="gv-intel-row">
        <span class="gv-intel-label">SEVERITY</span>
        <span class="gv-intel-value">${props.severity}</span>
      </div>
      ${reasons.length > 0 ? `
      <div class="gv-intel-section-label">ANOMALY REASONS</div>
      ${reasons.map(r => `<div class="gv-intel-reason">⚠ ${r}</div>`).join('')}
      ` : ''}
      <div class="gv-intel-section-label">GEOLOCATION</div>
      <div class="gv-intel-coord">${lngLat.lat.toFixed(5)}°N ${lngLat.lng.toFixed(5)}°E</div>
      <button class="gv-mapillary-btn" onclick="window.argusAskAbout && window.argusAskAbout({ type: 'ground_node', data: ${JSON.stringify(props).replace(/"/g, '&quot;')}, coords: { lat: ${lngLat.lat}, lng: ${lngLat.lng} } })" style="margin-top:8px; border-color:var(--cyber-cyan); background:rgba(0,255,209,0.18); color:#fff; font-weight:bold;">
        🛡 ⚡ ASK ARGUS AI
      </button>
      ${this._mapillaryReady ? `
      <button class="gv-mapillary-btn" id="gv-open-mapillary"
        data-lat="${lngLat.lat}" data-lon="${lngLat.lng}">
        🗺 STREET-LEVEL VIEW
      </button>` : '<div class="gv-intel-muted">Mapillary: enable layer for coverage</div>'}
    `;

    // Bind mapillary button if it appears
    const mlBtn = document.getElementById('gv-open-mapillary');
    if (mlBtn) {
      mlBtn.addEventListener('click', async () => {
        const lat = parseFloat(mlBtn.dataset.lat);
        const lon = parseFloat(mlBtn.dataset.lon);
        await this._openMapillaryForLocation(lat, lon);
      });
    }

    this.ui.intelPanel?.classList.remove('hidden');
  }

  _onIncidentClick(props, lngLat) {
    this.selected = { type: 'incident', data: props };
    flyTo(lngLat.lat, lngLat.lng, 14);

    const violations = _parseJsonArray(props.integrityViolations);
    const reasons    = _parseJsonArray(props.anomalyReasons);
    const detectedAt = props.detectedAtMs
      ? new Date(props.detectedAtMs).toISOString().substring(0, 19) + 'Z'
      : '---';

    const sevClass = { CRITICAL: 'gv-alert', HIGH: 'gv-alert', MEDIUM: 'gv-warn', LOW: 'gv-good' }[props.severity] || 'gv-good';

    this.ui.intelTitle.textContent = `🔴 ${props.incidentId}`;
    this.ui.intelContent.innerHTML = `
      <div class="gv-intel-row">
        <span class="gv-intel-label">SEVERITY</span>
        <span class="gv-intel-value ${sevClass}">${props.severity}</span>
      </div>
      <div class="gv-intel-row">
        <span class="gv-intel-label">STATUS</span>
        <span class="gv-intel-value gv-warn">${props.status}</span>
      </div>
      <div class="gv-intel-row">
        <span class="gv-intel-label">PRIMARY NODE</span>
        <span class="gv-intel-value">${props.primaryNodeId}</span>
      </div>
      <div class="gv-intel-row">
        <span class="gv-intel-label">CONFIDENCE</span>
        <span class="gv-intel-value">${Math.round(props.confidenceScore * 100)}%</span>
      </div>
      <div class="gv-intel-row">
        <span class="gv-intel-label">TRUST @ DETECT</span>
        <span class="gv-intel-value gv-alert">${Math.round(props.trustAtDetection * 100)}%</span>
      </div>
      <div class="gv-intel-row">
        <span class="gv-intel-label">QUARANTINED</span>
        <span class="gv-intel-value ${props.quarantined ? 'gv-purple' : 'gv-good'}">
          ${props.quarantined ? '⛔ YES' : '✗ NO'}
        </span>
      </div>
      <div class="gv-intel-row">
        <span class="gv-intel-label">EVENTS</span>
        <span class="gv-intel-value">${props.eventCount} contributing</span>
      </div>
      <div class="gv-intel-row">
        <span class="gv-intel-label">DETECTED</span>
        <span class="gv-intel-value gv-muted">${detectedAt}</span>
      </div>
      <div class="gv-intel-section-label">TITLE</div>
      <div class="gv-intel-desc">${props.title}</div>
      ${violations.length > 0 ? `
      <div class="gv-intel-section-label">INTEGRITY VIOLATIONS</div>
      ${violations.map(v => `<div class="gv-intel-reason">⛔ ${v}</div>`).join('')}` : ''}
      ${reasons.slice(0, 4).length > 0 ? `
      <div class="gv-intel-section-label">ANOMALY INDICATORS</div>
      ${reasons.slice(0, 4).map(r => `<div class="gv-intel-reason">⚠ ${r}</div>`).join('')}` : ''}
      <div class="gv-intel-coord">${lngLat.lat.toFixed(5)}°N ${lngLat.lng.toFixed(5)}°E</div>
      <button class="gv-mapillary-btn" onclick="window.argusAskAbout && window.argusAskAbout({ type: 'ground_incident', data: ${JSON.stringify(props).replace(/"/g, '&quot;')}, coords: { lat: ${lngLat.lat}, lng: ${lngLat.lng} } })" style="margin-top:8px; border-color:var(--cyber-cyan); background:rgba(0,255,209,0.18); color:#fff; font-weight:bold;">
        🛡 ⚡ ASK ARGUS AI
      </button>
    `;

    this.ui.intelPanel?.classList.remove('hidden');
  }

  _onMapillaryImageClick(props, lngLat) {
    // Show thumbnail in mapillary panel
    if (this.ui.mapillaryPanel) {
      this.ui.mapillaryPanel.classList.remove('hidden');
      if (this.ui.mapillaryStatus) {
        this.ui.mapillaryStatus.textContent = `Image ID: ${props.id}`;
      }
    }
  }

  // ─── Mapillary Coverage Loading ─────────────────────────────────────────────

  async _loadMapillaryCoverage() {
    if (!this._mapillaryReady) {
      this._setStatus('MAPILLARY: SERVICE NOT INITIALIZED');
      return;
    }
    // Load coverage for current ARGUS node positions
    const allImages = [];
    for (const [, event] of this.argusState.latestEvents) {
      const { latitude, longitude } = event.location;
      const images = await getNearbyImages(latitude, longitude, 5, 300);
      allImages.push(...images);
    }
    updateMapillaryData(allImages);
    this._setStatus(`MAPILLARY: ${allImages.length} IMAGES INDEXED`);
  }

  // ─── UI Updates ─────────────────────────────────────────────────────────────

  _updateStatusBar() {
    const nodeCount = this.argusState.nodeStateMap.size;
    const incCount  = this.argusState.incidents.length;
    const anomCount = this.argusState.anomalyCount;

    if (this.ui.countNodes)     this.ui.countNodes.textContent     = nodeCount;
    if (this.ui.countAnomalies) this.ui.countAnomalies.textContent = anomCount;
    if (this.ui.countIncidents) this.ui.countIncidents.textContent = incCount;
  }

  _updateStageBadge(status) {
    if (this.ui.stageBadge) {
      if (typeof status === 'string') {
        this.ui.stageBadge.textContent = status;
      } else {
        this.ui.stageBadge.textContent = 'GRID ONLINE';
      }
    }
  }

  _setStatus(msg) {
    if (this.ui.status) this.ui.status.textContent = msg;
  }

  _updateClock() {
    if (this.ui.timestamp) {
      const now = new Date();
      this.ui.timestamp.textContent = 'REC ' + now.toISOString().substring(0, 19).replace('T', ' ') + 'Z';
    }
  }

  // ─── Cleanup ─────────────────────────────────────────────────────────────────

  destroy() {
    clearInterval(this._tickTimer);
    clearInterval(this._clockTimer);
    destroyGroundMap();
  }
}

// ─── Bootstrap ───────────────────────────────────────────────────────────────

function _parseJsonArray(val) {
  if (!val) return [];
  try { return JSON.parse(val); } catch { return []; }
}

const controller = new GroundViewController();

document.addEventListener('DOMContentLoaded', () => {
  controller.init();
});

window.addEventListener('beforeunload', () => {
  controller.destroy();
});
