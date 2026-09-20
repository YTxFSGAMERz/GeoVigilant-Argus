/**
 * ============================================================================
 * ARGUS AI — Universal Geospatial & OSINT Intelligence Core Widget
 * GeoVigilant-Argus Platform
 * Markdown & KaTeX LaTeX Enhanced Edition + Universal Web Request Dispatcher
 * ============================================================================
 */

(function () {
    'use strict';

    // Prevent multiple initializations
    if (window.__ARGUS_AI_INITIALIZED__) return;
    window.__ARGUS_AI_INITIALIZED__ = true;

    // Early stub to ensure clicks immediately open the AI UI even if libraries are loading
    window.openArgusAI = function(optionalPrompt) {
        if (typeof window.__realOpenArgusAI === 'function') {
            window.__realOpenArgusAI(optionalPrompt);
        } else {
            window.__pendingArgusPrompt = optionalPrompt || true;
            if (typeof injectArgusUI === 'function') {
                injectArgusUI();
            }
        }
    };

    // ── DYNAMIC ASSET & SCRIPT LOADER (MARKED + KATEX) ────────────────────────
    function loadDependency(src, isCss = false) {
        return new Promise((resolve) => {
            if (isCss) {
                if (document.querySelector(`link[href="${src}"]`)) return resolve();
                const link = document.createElement('link');
                link.rel = 'stylesheet';
                link.href = src;
                link.onload = () => resolve();
                link.onerror = () => resolve();
                document.head.appendChild(link);
            } else {
                if (document.querySelector(`script[src="${src}"]`)) return resolve();
                const script = document.createElement('script');
                script.src = src;
                script.onload = () => resolve();
                script.onerror = () => resolve();
                document.head.appendChild(script);
            }
        });
    }

    async function initLibraries() {
        // Load KaTeX CSS
        loadDependency('/static/vendor/katex.min.css', true);
        loadDependency('https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css', true);

        // Load Marked & KaTeX JS in parallel
        const promises = [];
        if (typeof window.marked === 'undefined') {
            promises.push(loadDependency('/static/vendor/marked.min.js')
                .then(() => {
                    if (typeof window.marked === 'undefined') {
                        return loadDependency('https://cdn.jsdelivr.net/npm/marked/marked.min.js');
                    }
                }));
        }
        if (typeof window.katex === 'undefined') {
            promises.push(loadDependency('/static/vendor/katex.min.js')
                .then(() => {
                    if (typeof window.katex === 'undefined') {
                        return loadDependency('https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js');
                    }
                })
                .then(() => {
                    return loadDependency('/static/vendor/auto-render.min.js')
                        .catch(() => loadDependency('https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js'));
                }));
        }

        await Promise.all(promises);

        if (typeof window.marked !== 'undefined' && window.marked.setOptions) {
            window.marked.setOptions({
                gfm: true,
                breaks: true,
                smartypants: true
            });
        }
    }
    initLibraries();

    // Detect Page Name for Badge
    function getPageLabel() {
        const path = window.location.pathname.toLowerCase();
        if (path === '/' || path === '/earth' || path.includes('index')) return '3D GLOBE';
        if (path.includes('ground')) return 'GROUNDVIEW';
        if (path.includes('newsnetworks') || path.includes('earthnetworks')) return 'NETWORKS MATRIX';
        if (path.includes('news')) return 'NEWS STREAM';
        if (path.includes('surveillance') || path.includes('map-w') || path.includes('wifi')) return 'RF SURVEILLANCE';
        if (path.includes('social') || path.includes('reddit') || path.includes('twitter')) return 'SOCIAL OSINT';
        if (path.includes('portfolio')) return 'PORTFOLIO';
        return 'ARGUS CORE';
    }

    // ── GATHER LIVE REAL-TIME TELEMETRY FROM CURRENT PAGE ─────────────────────
    function getLivePageTelemetry(customCoords) {
        const telemetry = {
            url: window.location.pathname,
            title: document.title,
            page_label: getPageLabel(),
            timestamp: new Date().toISOString()
        };

        if (customCoords && customCoords.lat && customCoords.lng) {
            telemetry.map_center = {
                lat: Number(customCoords.lat),
                lng: Number(customCoords.lng),
                height_m: customCoords.alt || 35000
            };
            telemetry.coords_display = `${customCoords.lat.toFixed(4)}°N, ${customCoords.lng.toFixed(4)}°E`;
        }

        try {
            // 1. Map Coordinates & Center
            if (!telemetry.map_center) {
                if (typeof window.viewer !== 'undefined' && window.viewer && window.viewer.camera) {
                    const cam = window.viewer.camera;
                    const carto = Cesium.Cartographic.fromCartesian(cam.position);
                    telemetry.map_center = {
                        lat: Number(Cesium.Math.toDegrees(carto.latitude).toFixed(5)),
                        lng: Number(Cesium.Math.toDegrees(carto.longitude).toFixed(5)),
                        height_m: Math.round(carto.height)
                    };
                } else if (typeof window.map !== 'undefined' && window.map) {
                    if (typeof window.map.getCenter === 'function') {
                        const center = window.map.getCenter();
                        telemetry.map_center = {
                            lat: center.lat ? Number(center.lat.toFixed(5)) : (center[1] ? Number(center[1].toFixed(5)) : null),
                            lng: center.lng ? Number(center.lng.toFixed(5)) : (center[0] ? Number(center[0].toFixed(5)) : null),
                            zoom: typeof window.map.getZoom === 'function' ? window.map.getZoom() : null
                        };
                    }
                } else if (document.getElementById('coord-text')) {
                    telemetry.coords_display = document.getElementById('coord-text').innerText;
                } else if (document.getElementById('sv-coord-text')) {
                    telemetry.coords_display = document.getElementById('sv-coord-text').innerText;
                } else if (document.getElementById('hud-deg')) {
                    telemetry.coords_display = document.getElementById('hud-deg').innerText;
                }
            }

            // 2. Active Search & Filter Inputs
            const searchInput = document.getElementById('news-search') || document.getElementById('search-input') || document.querySelector('input[type="search"]') || document.querySelector('input[name="q"]');
            if (searchInput && searchInput.value) {
                telemetry.search_query = searchInput.value.trim();
            }

            const sectorHdr = document.getElementById('sector-header') || document.querySelector('.panel-header h3');
            if (sectorHdr) {
                telemetry.sector_header = sectorHdr.innerText.trim();
            }

            // 3. News Articles (if on /news or global articles available)
            if (window.currentArticles && Array.isArray(window.currentArticles) && window.currentArticles.length > 0) {
                telemetry.news_articles = window.currentArticles.slice(0, 8).map(a => ({
                    title: a.title,
                    source: a.source,
                    published: a.published,
                    sentiment: a.sentiment
                }));
            } else {
                const newsDomItems = document.querySelectorAll('.news-item');
                if (newsDomItems.length > 0) {
                    telemetry.news_headlines_on_screen = Array.from(newsDomItems).slice(0, 6).map(el => {
                        const titleEl = el.querySelector('.news-title') || el.querySelector('h4') || el;
                        return titleEl.innerText.trim().replace(/\n/g, ' ');
                    });
                }
            }

            // 4. RF Surveillance Nodes (if on /surveillance or device scan active)
            if (window.results && Array.isArray(window.results) && window.results.length > 0) {
                telemetry.intercepted_devices = window.results.slice(0, 10).map(d => ({
                    type: d.type,
                    ssid: d.ssid || d.cell_id,
                    bssid: d.bssid,
                    vendor: d.vendor,
                    signal: d.signal,
                    lat: d.lat,
                    lon: d.lon
                }));
            } else {
                const nodeDomItems = document.querySelectorAll('.node-item');
                if (nodeDomItems.length > 0) {
                    telemetry.visible_nodes_count = nodeDomItems.length;
                }
            }

            // 5. Market Rates (if on /news)
            if (window.currentMarketCache) {
                telemetry.market_rates = {
                    brent: window.currentMarketCache.brent_crude?.price,
                    gold: window.currentMarketCache.gold?.price,
                    silver: window.currentMarketCache.silver?.price,
                    btc: window.currentMarketCache.btc?.price
                };
            }

            // 6. Air & Sea Assets (if on /earth or /ground)
            if (window.flightEntities && window.flightEntities.length) {
                telemetry.tracked_flights_count = window.flightEntities.length;
            }
            if (window.vesselEntities && window.vesselEntities.length) {
                telemetry.tracked_vessels_count = window.vesselEntities.length;
            }

        } catch (e) {
            console.debug('[ARGUS AI] Telemetry collector notice:', e);
        }

        return telemetry;
    }

    // ── INJECT UI DOM STRUCTURE ───────────────────────────────────────────────
    function injectArgusUI() {
        if (document.getElementById('argus-ai-modal')) return;

        const pageLabel = getPageLabel();

        // Modal HTML (Cyberpunk Tactical Intelligence Drawer)
        const modalHtml = [
            '<div class="argus-ai-modal" id="argus-ai-modal" aria-hidden="true">',
            '    <!-- Header (Draggable) -->',
            '    <div class="argus-ai-header" id="argus-ai-header" title="Click and drag to move panel • Double-click to reset position">',
            '        <div class="argus-ai-title-wrap">',
            '            <i class="fas fa-grip-vertical argus-ai-drag-handle" title="Drag to move panel"></i>',
            '            <i class="fas fa-shield-alt" style="color: var(--cyber-cyan, #00FFD1); font-size: 16px;"></i>',
            '            <div>',
            '                <div class="argus-ai-title">ARGUS CORE // AI INTEL</div>',
            '                <div class="argus-ai-sub">// MULTI-DOMAIN GEOINT &amp; OSINT MESH</div>',
            '            </div>',
            '        </div>',
            '        <div class="argus-ai-header-controls">',
            '            <button class="argus-ai-clear-btn" id="argus-ai-clear-btn" title="Clear Chat History"><i class="fas fa-trash-alt"></i></button>',
            '            <button class="argus-ai-maximize-btn" id="argus-ai-maximize-btn" title="Maximize Panel"><i class="fas fa-expand"></i></button>',
            '            <button class="argus-ai-close-btn" id="argus-ai-close-btn" title="Close Panel (ESC)"><i class="fas fa-times"></i></button>',
            '        </div>',
            '    </div>',
            '    <!-- Telemetry Status Bar -->',
            '    <div class="argus-ai-telemetry-bar">',
            '        <div class="argus-ai-telemetry-status">',
            '            <span class="dot"></span>',
            '            <span id="argus-ai-status-label">ARGUS LINK: OLLAMA CLOUD</span>',
            '        </div>',
            '        <div class="argus-ai-page-tag" id="argus-ai-page-tag">' + pageLabel + '</div>',
            '    </div>',
            '    <!-- Quick Query Chips -->',
            '    <div class="argus-ai-quick-chips" id="argus-ai-quick-chips">',
            '        <span class="argus-ai-chip" data-query="Analyze what is currently happening on my screen">📡 Analyze Screen</span>',
            '        <span class="argus-ai-chip" data-query="Provide a tactical threat assessment of the current sector">⚡ Threat Assessment</span>',
            '        <span class="argus-ai-chip" data-query="Summarize latest global intelligence and geopolitical shifts">🌍 Global Briefing</span>',
            '        <span class="argus-ai-chip" data-query="Identify anomalies or critical signals in current telemetry">🔍 Find Anomalies</span>',
            '    </div>',
            '    <!-- Messages Container -->',
            '    <div class="argus-ai-messages" id="argus-ai-messages">',
            '        <div class="argus-ai-msg bot">',
            '            <h3>ARGUS OSINT CORE // OLLAMA CLOUD</h3>',
            '            <p>Neural mesh synchronized with Ollama Cloud. Real-time telemetry is linked for <code>' + pageLabel + '</code>.</p>',
            '            <p><em>Ask for tactical briefings, node scans, mathematical modeling, anomaly checks, or screen analysis.</em></p>',
            '        </div>',
            '    </div>',
            '    <!-- Footer / Input Row -->',
            '    <div class="argus-ai-footer">',
            '        <div class="argus-ai-options-row">',
            '            <label class="argus-ai-toggle-label">',
            '                <div class="argus-ai-toggle-switch">',
            '                    <input type="checkbox" id="argus-ai-web-search" checked>',
            '                    <span class="argus-ai-toggle-slider"></span>',
            '                </div>',
            '                <span>Live Web Recon</span>',
            '            </label>',
            '            <span style="font-size: 10.5px; opacity: 0.65; letter-spacing: 0.5px;">HOTKEY: ALT+A / CTRL+SPACE</span>',
            '        </div>',
            '        <div class="argus-ai-input-row">',
            '            <input type="text" class="argus-ai-input" id="argus-ai-input" placeholder="Enter tactical query or directive..." autocomplete="off">',
            '            <button class="argus-ai-send-btn" id="argus-ai-send-btn" aria-label="Send Directive"><i class="fas fa-paper-plane"></i></button>',
            '        </div>',
            '    </div>',
            '</div>'
        ].join('\n');

        const wrapper = document.createElement('div');
        wrapper.id = 'argus-ai-widget-wrapper';
        wrapper.innerHTML = modalHtml;
        document.body.appendChild(wrapper);

        // Bind Events
        bindArgusEvents();

        // Check for URL auto-directives (e.g. ?ask=... or ?url=... or ?lat=...&lon=...&auto_scan=1)
        checkUrlDirectives();

        // Query Live AI Core Status
        fetch('/api/geovigilantai/status')
            .then(r => r.json())
            .then(d => {
                const el = document.getElementById('argus-ai-status-label');
                if (el && d.engine) {
                    el.textContent = 'ARGUS LINK: ' + d.engine.toUpperCase();
                }
            })
            .catch(() => {});
    }

    // ── EVENT LISTENERS & CHAT LOGIC ──────────────────────────────────────────
    function bindArgusEvents() {
        const modal = document.getElementById('argus-ai-modal');
        const closeBtn = document.getElementById('argus-ai-close-btn');
        const clearBtn = document.getElementById('argus-ai-clear-btn');
        const maximizeBtn = document.getElementById('argus-ai-maximize-btn');
        const input = document.getElementById('argus-ai-input');
        const sendBtn = document.getElementById('argus-ai-send-btn');
        const messages = document.getElementById('argus-ai-messages');
        const chipsContainer = document.getElementById('argus-ai-quick-chips');

        // ── MAXIMIZE / RESTORE LOGIC ──────────────────────────────────────────
        function toggleMaximize() {
            if (!modal) return;
            const isMax = modal.classList.contains('maximized');
            if (!isMax) {
                // Save inline styles for restoring later
                modal.dataset.restoreLeft = modal.style.left || '';
                modal.dataset.restoreTop = modal.style.top || '';

                modal.style.removeProperty('left');
                modal.style.removeProperty('top');
                modal.style.removeProperty('right');
                modal.style.removeProperty('bottom');

                modal.classList.add('maximized');
                if (maximizeBtn) {
                    maximizeBtn.innerHTML = '<i class="fas fa-compress"></i>';
                    maximizeBtn.title = 'Restore Panel';
                }
                sessionStorage.setItem('argus_ai_maximized', 'true');
            } else {
                modal.classList.remove('maximized');
                if (modal.dataset.restoreLeft && modal.dataset.restoreTop) {
                    modal.style.setProperty('left', modal.dataset.restoreLeft, 'important');
                    modal.style.setProperty('top', modal.dataset.restoreTop, 'important');
                    modal.style.setProperty('right', 'auto', 'important');
                    modal.style.setProperty('bottom', 'auto', 'important');
                } else {
                    modal.style.removeProperty('left');
                    modal.style.removeProperty('top');
                    modal.style.removeProperty('right');
                    modal.style.removeProperty('bottom');
                }
                if (maximizeBtn) {
                    maximizeBtn.innerHTML = '<i class="fas fa-expand"></i>';
                    maximizeBtn.title = 'Maximize Panel';
                }
                sessionStorage.removeItem('argus_ai_maximized');
            }
        }

        if (maximizeBtn) {
            maximizeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleMaximize();
            });
        }

        // ── DRAGGABLE MODAL IMPLEMENTATION (MOUSE / POINTER) ─────────────────
        function initDraggableArgusModal(modalEl) {
            if (!modalEl) return;
            const header = modalEl.querySelector('.argus-ai-header');
            if (!header) return;

            let isDragging = false;
            let startPointerX = 0;
            let startPointerY = 0;
            let startLeft = 0;
            let startTop = 0;

            // Restore previously saved position from session
            try {
                const saved = sessionStorage.getItem('argus_ai_modal_position');
                if (saved) {
                    const pos = JSON.parse(saved);
                    if (typeof pos.left === 'number' && typeof pos.top === 'number') {
                        const maxL = Math.max(10, window.innerWidth - (modalEl.offsetWidth || 400) - 10);
                        const maxT = Math.max(10, window.innerHeight - (modalEl.offsetHeight || 620) - 10);
                        const clL = Math.max(10, Math.min(pos.left, maxL));
                        const clT = Math.max(10, Math.min(pos.top, maxT));
                        modalEl.style.setProperty('left', clL + 'px', 'important');
                        modalEl.style.setProperty('top', clT + 'px', 'important');
                        modalEl.style.setProperty('right', 'auto', 'important');
                        modalEl.style.setProperty('bottom', 'auto', 'important');
                    }
                }
            } catch (_) {}

            function onPointerDown(e) {
                // Ignore clicks on buttons, inputs, links, or control buttons
                if (e.target.closest('button') || e.target.closest('input') || e.target.closest('a') || e.target.closest('.argus-ai-header-controls')) {
                    return;
                }
                if (e.button !== undefined && e.button !== 0) return; // Left mouse click only

                // If currently maximized, smoothly un-maximize and follow cursor
                if (modalEl.classList.contains('maximized')) {
                    toggleMaximize();
                    const rect = modalEl.getBoundingClientRect();
                    const restoredW = modalEl.offsetWidth || 400;
                    const restoredH = modalEl.offsetHeight || 620;
                    startLeft = Math.max(8, Math.min(e.clientX - (restoredW / 2), window.innerWidth - restoredW - 8));
                    startTop = Math.max(8, Math.min(e.clientY - 20, window.innerHeight - restoredH - 8));
                    modalEl.style.setProperty('left', startLeft + 'px', 'important');
                    modalEl.style.setProperty('top', startTop + 'px', 'important');
                    modalEl.style.setProperty('right', 'auto', 'important');
                    modalEl.style.setProperty('bottom', 'auto', 'important');
                }

                isDragging = true;
                modalEl.classList.add('is-dragging');

                const rect = modalEl.getBoundingClientRect();
                startPointerX = e.clientX;
                startPointerY = e.clientY;
                startLeft = rect.left;
                startTop = rect.top;

                modalEl.style.setProperty('left', startLeft + 'px', 'important');
                modalEl.style.setProperty('top', startTop + 'px', 'important');
                modalEl.style.setProperty('right', 'auto', 'important');
                modalEl.style.setProperty('bottom', 'auto', 'important');

                if (header.setPointerCapture && e.pointerId !== undefined) {
                    try { header.setPointerCapture(e.pointerId); } catch (_) {}
                }

                window.addEventListener('pointermove', onPointerMove, { passive: false });
                window.addEventListener('pointerup', onPointerUp, { passive: false });
                window.addEventListener('pointercancel', onPointerUp, { passive: false });

                e.preventDefault();
            }

            function onPointerMove(e) {
                if (!isDragging) return;
                const dx = e.clientX - startPointerX;
                const dy = e.clientY - startPointerY;

                const modalW = modalEl.offsetWidth || 400;
                const modalH = modalEl.offsetHeight || 620;

                const minX = 8;
                const minY = 8;
                const maxX = Math.max(minX, window.innerWidth - modalW - 8);
                const maxY = Math.max(minY, window.innerHeight - modalH - 8);

                const curLeft = Math.max(minX, Math.min(startLeft + dx, maxX));
                const curTop = Math.max(minY, Math.min(startTop + dy, maxY));

                modalEl.style.setProperty('left', curLeft + 'px', 'important');
                modalEl.style.setProperty('top', curTop + 'px', 'important');
            }

            function onPointerUp(e) {
                if (!isDragging) return;
                isDragging = false;
                modalEl.classList.remove('is-dragging');

                window.removeEventListener('pointermove', onPointerMove);
                window.removeEventListener('pointerup', onPointerUp);
                window.removeEventListener('pointercancel', onPointerUp);

                if (header.releasePointerCapture && e.pointerId !== undefined) {
                    try { header.releasePointerCapture(e.pointerId); } catch (_) {}
                }

                try {
                    const rect = modalEl.getBoundingClientRect();
                    sessionStorage.setItem('argus_ai_modal_position', JSON.stringify({ left: rect.left, top: rect.top }));
                } catch (_) {}
            }

            // Double click header to toggle maximize / restore
            header.addEventListener('dblclick', (e) => {
                if (e.target.closest('button')) return;
                toggleMaximize();
            });

            header.addEventListener('pointerdown', onPointerDown);

            // Keep within bounds on window resize
            window.addEventListener('resize', () => {
                if (!modalEl.style.left || !modalEl.classList.contains('open') || modalEl.classList.contains('maximized')) return;
                const rect = modalEl.getBoundingClientRect();
                const maxX = Math.max(8, window.innerWidth - rect.width - 8);
                const maxY = Math.max(8, window.innerHeight - rect.height - 8);
                const clX = Math.max(8, Math.min(rect.left, maxX));
                const clY = Math.max(8, Math.min(rect.top, maxY));
                modalEl.style.setProperty('left', clX + 'px', 'important');
                modalEl.style.setProperty('top', clY + 'px', 'important');
            });
        }

        initDraggableArgusModal(modal);

        if (sessionStorage.getItem('argus_ai_maximized') === 'true') {
            toggleMaximize();
        }

        window.__realOpenArgusAI = function(optionalPrompt) {
            let m = document.getElementById('argus-ai-modal');
            if (!m) {
                injectArgusUI();
                m = document.getElementById('argus-ai-modal');
            }
            if (!m) return;

            // Set display first so transition from display:none works, then add .open on next frame
            m.style.setProperty('display', 'flex', 'important');
            m.style.setProperty('z-index', '99999999', 'important');
            // Force reflow, then add .open to trigger CSS transition
            void m.offsetWidth;
            m.classList.add('open');
            m.setAttribute('aria-hidden', 'false');
            m.style.setProperty('pointer-events', 'auto', 'important');

            // Sanity check: Ensure panel is within viewport and not lost off-screen
            try {
                const rect = m.getBoundingClientRect();
                if (rect.left < 0 || rect.top < 0 || rect.right > window.innerWidth + 40 || rect.bottom > window.innerHeight + 40 || (rect.width === 0 && rect.height === 0)) {
                    m.style.removeProperty('left');
                    m.style.removeProperty('top');
                    m.style.removeProperty('right');
                    m.style.removeProperty('bottom');
                    sessionStorage.removeItem('argus_ai_modal_position');
                }
            } catch (_) {}

            const tag = document.getElementById('argus-ai-page-tag');
            if (tag) tag.textContent = getPageLabel();
            const inp = document.getElementById('argus-ai-input');
            if (inp) {
                if (optionalPrompt && typeof optionalPrompt === 'string') {
                    inp.value = optionalPrompt;
                    setTimeout(() => window.argusSendDirective && window.argusSendDirective(optionalPrompt), 100);
                } else {
                    setTimeout(() => inp.focus(), 60);
                }
            }
        };

        window.openArgusAI = window.__realOpenArgusAI;

        // Process any prompt queued before init
        if (window.__pendingArgusPrompt) {
            const p = window.__pendingArgusPrompt;
            delete window.__pendingArgusPrompt;
            window.openArgusAI(typeof p === 'string' ? p : undefined);
        }

        window.closeArgusAI = function() {
            const m = document.getElementById('argus-ai-modal');
            if (!m) return;
            m.classList.remove('open');
            m.setAttribute('aria-hidden', 'true');
            // Clear interaction styles immediately
            m.style.removeProperty('opacity');
            m.style.removeProperty('pointer-events');
            m.style.removeProperty('visibility');
            // After the CSS transition finishes (250ms), remove display so the element is truly hidden
            setTimeout(() => {
                if (!m.classList.contains('open')) {
                    m.style.removeProperty('display');
                }
            }, 280);
        };

        window.toggleArgusAI = function(open) {
            const m = document.getElementById('argus-ai-modal');
            if (!m) {
                window.openArgusAI();
                return;
            }
            const shouldOpen = (open !== undefined) ? open : !m.classList.contains('open');
            if (shouldOpen) {
                window.openArgusAI();
            } else {
                window.closeArgusAI();
            }
        };

        if (closeBtn) closeBtn.addEventListener('click', () => window.closeArgusAI());

        // Global Hooks: Hook all ARGUS CORE buttons across headers and panels
        function hookArgusTriggers() {
            document.querySelectorAll('#btn-argus-core, .btn-argus-core, #ai-insights-panel, .open-argus-ai, [data-argus-core]').forEach(el => {
                el.style.cursor = 'pointer';
                if (!el.dataset.argusHooked) {
                    el.dataset.argusHooked = 'true';
                    el.addEventListener('click', (e) => {
                        e.stopPropagation();
                        window.openArgusAI();
                    });
                }
            });
        }
        hookArgusTriggers();
        setInterval(hookArgusTriggers, 2000);

        // Keyboard Shortcut: Alt + A or Ctrl + Space or Cmd + Space
        document.addEventListener('keydown', (e) => {
            if ((e.altKey && (e.key === 'a' || e.key === 'A')) || 
                (e.ctrlKey && e.code === 'Space') ||
                (e.metaKey && e.code === 'Space')) {
                e.preventDefault();
                window.toggleArgusAI();
            } else if (e.key === 'Escape') {
                const m = document.getElementById('argus-ai-modal');
                if (m && m.classList.contains('open')) {
                    window.closeArgusAI();
                }
            }
        });

        // ── PERSISTENT CHAT HISTORY STORAGE (LOCALSTORAGE) ───────────────────
        const CHAT_STORAGE_KEY = 'argus_ai_chat_history';
        const MAX_STORED_MESSAGES = 80;

        function getStoredChatHistory() {
            try {
                const raw = localStorage.getItem(CHAT_STORAGE_KEY);
                if (raw) {
                    const parsed = JSON.parse(raw);
                    if (Array.isArray(parsed)) return parsed;
                }
            } catch (_) {}
            return [];
        }

        function saveMessageToHistory(text, type, time = Date.now()) {
            try {
                const history = getStoredChatHistory();
                history.push({
                    text: text,
                    type: type, // 'user' or 'bot'
                    time: time,
                    page: getPageLabel()
                });
                if (history.length > MAX_STORED_MESSAGES) {
                    history.splice(0, history.length - MAX_STORED_MESSAGES);
                }
                localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(history));
            } catch (_) {}
        }

        function clearChatHistory() {
            try {
                localStorage.removeItem(CHAT_STORAGE_KEY);
            } catch (_) {}
        }

        function loadChatHistory() {
            const history = getStoredChatHistory();
            if (!history || history.length === 0) return;

            // Clear default initial greeting to show restored history
            messages.innerHTML = '';

            // Restored history indicator banner
            const divider = document.createElement('div');
            divider.className = 'argus-ai-history-divider';
            divider.innerHTML = `<span>RESTORED INTEL LOGS (${history.length})</span>`;
            messages.appendChild(divider);

            // Rehydrate past messages
            history.forEach(item => {
                appendMessage(item.text, item.type, false /* do not re-save */, item.time, item.page);
            });

            messages.scrollTop = messages.scrollHeight;
        }

        // Clear Chat History
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                clearChatHistory();
                const pageLabel = getPageLabel();
                messages.innerHTML = [
                    '<div class="argus-ai-msg bot">',
                    '    <h3>ARGUS OSINT CORE // RESET</h3>',
                    '    <p>Conversation and telemetry logs purged from local cache. Ready for new directive on <code>' + pageLabel + '</code>.</p>',
                    '</div>'
                ].join('');
            });
        }

        // Quick Query Chips
        if (chipsContainer) {
            chipsContainer.addEventListener('click', (e) => {
                const chip = e.target.closest('.argus-ai-chip');
                if (chip && chip.dataset.query) {
                    window.argusSendDirective(chip.dataset.query);
                }
            });
        }

        // Append Message Helper (with Timestamps and Storage)
        function appendMessage(text, type, shouldSave = true, customTime = null, customPage = null) {
            const div = document.createElement('div');
            div.className = 'argus-ai-msg ' + type;

            const msgTime = customTime || Date.now();
            const timeStr = new Date(msgTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            const pageStr = customPage || getPageLabel();

            if (type === 'user') {
                const contentDiv = document.createElement('div');
                contentDiv.textContent = text;
                div.appendChild(contentDiv);

                const metaDiv = document.createElement('div');
                metaDiv.className = 'argus-ai-msg-meta';
                metaDiv.innerHTML = `<span>${timeStr}</span><span>•</span><span>${pageStr}</span>`;
                div.appendChild(metaDiv);
            } else {
                const contentDiv = document.createElement('div');
                contentDiv.innerHTML = parseBotMarkdown(text);
                div.appendChild(contentDiv);

                const metaDiv = document.createElement('div');
                metaDiv.className = 'argus-ai-msg-meta';
                metaDiv.innerHTML = `<span>${timeStr}</span><span>•</span><span>ARGUS CORE</span>`;
                div.appendChild(metaDiv);

                // KaTeX auto-render on the message element
                if (typeof window.renderMathInElement === 'function') {
                    try {
                        window.renderMathInElement(contentDiv, {
                            delimiters: [
                                { left: '$$', right: '$$', display: true },
                                { left: '$', right: '$', display: false },
                                { left: '\\[', right: '\\]', display: true },
                                { left: '\\(', right: '\\)', display: false }
                            ],
                            throwOnError: false
                        });
                    } catch (e) { console.debug('[ARGUS AI] KaTeX render error:', e); }
                }

                // Highlight.js syntax highlighting
                if (typeof window.hljs !== 'undefined') {
                    div.querySelectorAll('pre code').forEach(window.hljs.highlightElement);
                }
            }

            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;

            if (shouldSave) {
                saveMessageToHistory(text, type, msgTime);
            }

            return div;
        }

        // Restore chat logs on startup
        loadChatHistory();

        // ── ROBUST MARKDOWN + LATEX PARSER ────────────────────────────────────
        function parseBotMarkdown(rawText) {
            if (!rawText) return '<em>[No telemetry returned]</em>';

            let content = rawText;

            // 1. Protect & pre-render LaTeX blocks before markdown parsing to prevent mangling
            const mathPlaceholders = [];
            
            // Display math $$...$$
            content = content.replace(/\$\$([\s\S]*?)\$\$/g, (match, formula) => {
                const idx = mathPlaceholders.length;
                if (typeof window.katex !== 'undefined') {
                    try {
                        const rendered = window.katex.renderToString(formula.trim(), { displayMode: true, throwOnError: false });
                        mathPlaceholders.push(rendered);
                    } catch (e) {
                        mathPlaceholders.push(`<div class="katex-display">$$${formula}$$</div>`);
                    }
                } else {
                    mathPlaceholders.push(`<div class="katex-display">$$${formula}$$</div>`);
                }
                return `%%ARGUS_MATH_${idx}%%`;
            });

            // Inline math $...$ (ensure not regular dollar currency like $78.40)
            content = content.replace(/(^|[^\\])\$([^\$\n]+?)\$/g, (match, prefix, formula) => {
                if (/^\d+(\.\d+)?$/.test(formula.trim())) {
                    return match;
                }
                const idx = mathPlaceholders.length;
                if (typeof window.katex !== 'undefined') {
                    try {
                        const rendered = window.katex.renderToString(formula.trim(), { displayMode: false, throwOnError: false });
                        mathPlaceholders.push(rendered);
                    } catch (e) {
                        mathPlaceholders.push(`<span class="katex">$${formula}$</span>`);
                    }
                } else {
                    mathPlaceholders.push(`<span class="katex">$${formula}$</span>`);
                }
                return `${prefix}%%ARGUS_MATH_${idx}%%`;
            });

            // 2. Parse Markdown using Marked.js if available, else standard fallback
            let html = '';
            if (typeof window.marked !== 'undefined' && typeof window.marked.parse === 'function') {
                try {
                    html = window.marked.parse(content);
                } catch (err) {
                    console.warn('[ARGUS AI] Marked parse fallback:', err);
                    html = basicMarkdownFallback(content);
                }
            } else {
                html = basicMarkdownFallback(content);
            }

            // 3. Restore LaTeX math blocks
            html = html.replace(/%%ARGUS_MATH_(\d+)%%/g, (match, idx) => {
                return mathPlaceholders[parseInt(idx, 10)] || match;
            });

            // 4. Interactive Action GUI Tags
            html = html.replace(/\[TRACK_FLIGHT:\s*([^\]]+)\]/gi, (match, icao) => {
                const code = icao.trim();
                return `<button class="argus-ai-action-btn flight" onclick="window.argusTrackFlight && window.argusTrackFlight('${code}')"><i class="fas fa-plane"></i> TRACK FLIGHT: ${code}</button>`;
            });

            html = html.replace(/\[TRACK_VESSEL:\s*([^\]]+)\]/gi, (match, mmsi) => {
                const code = mmsi.trim();
                return `<button class="argus-ai-action-btn vessel" onclick="window.argusTrackVessel && window.argusTrackVessel('${code}')"><i class="fas fa-ship"></i> TRACK VESSEL: ${code}</button>`;
            });

            html = html.replace(/\[SCAN_MAP:\s*([^,\]]+),\s*([^\]]+)\]/gi, (match, lat, lng) => {
                const l1 = lat.trim();
                const l2 = lng.trim();
                return `<button class="argus-ai-action-btn scan" onclick="window.argusScanMap && window.argusScanMap(${l1}, ${l2})"><i class="fas fa-crosshairs"></i> SCAN SECTOR: ${l1}, ${l2}</button>`;
            });

            // Status alert tag: [ALERT: CRITICAL]
            html = html.replace(/\[ALERT:\s*([^\]]+)\]/gi, (match, level) => {
                const lvl = level.trim().toUpperCase();
                let color = 'var(--cyber-cyan)';
                if (lvl === 'CRITICAL' || lvl === 'HIGH') color = 'var(--cyber-red, #FF0055)';
                if (lvl === 'ELEVATED' || lvl === 'MEDIUM') color = 'var(--cyber-amber, #FFCC00)';
                return `<span style="display:inline-block; padding:3px 8px; font-weight:bold; font-size:11.5px; border-radius:3px; border:1px solid ${color}; color:${color}; background:${color}22; margin:3px 0;">⚠ ALERT: ${lvl}</span>`;
            });

            return html;
        }

        // Fallback simple markdown parser if marked is still loading
        function basicMarkdownFallback(text) {
            return text
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/^### (.*$)/gim, '<h3>$1</h3>')
                .replace(/^## (.*$)/gim, '<h2>$1</h2>')
                .replace(/^# (.*$)/gim, '<h1>$1</h1>')
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>')
                .replace(/`([^`]+)`/g, '<code>$1</code>')
                .replace(/^> (.*$)/gim, '<blockquote>$1</blockquote>')
                .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color:var(--cyber-cyan, #00FFD1); text-decoration:underline;">$1</a>')
                .replace(/\n\n/g, '<br><br>')
                .replace(/\n/g, '<br>');
        }

        // ── SEND MESSAGE & RECEIVE STREAMED/PARSED RESPONSE ───────────────────
        window.argusSendDirective = async function(promptText, customTelemetry = null) {
            const query = (promptText || input.value || '').trim();
            if (!query) return;

            window.openArgusAI();
            appendMessage(query, 'user');
            if (input) input.value = '';

            // Typing indicator
            const typingEl = document.createElement('div');
            typingEl.className = 'argus-ai-msg bot';
            typingEl.innerHTML = [
                '<div class="argus-ai-typing">',
                '    <span></span><span></span><span></span>',
                '    <em style="margin-left: 6px; color: var(--cyber-cyan, #00FFD1);">ARGUS Neural Core Processing Request...</em>',
                '</div>'
            ].join('');
            messages.appendChild(typingEl);
            messages.scrollTop = messages.scrollHeight;

            const webSearch = document.getElementById('argus-ai-web-search')?.checked ?? true;
            const liveTelemetry = getLivePageTelemetry(customTelemetry);

            try {
                const res = await fetch('/api/geovigilantai/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: query,
                        web_search: webSearch,
                        context: liveTelemetry,
                        page_telemetry: liveTelemetry
                    })
                });

                const data = await res.json();
                typingEl.remove();

                const replyText = data.reply || data.response || data.analysis || (data.error ? '**UPLINK ERROR:** ' + data.error : 'No response from ARGUS core.');
                appendMessage(replyText, 'bot');

            } catch (err) {
                typingEl.remove();
                appendMessage('**ARGUS TRANSMISSION FAILURE:** ' + err.message + '. Check backend neural uplink.', 'bot');
                console.error('[ARGUS AI] Chat error:', err);
            }
        };

        if (sendBtn) sendBtn.addEventListener('click', () => window.argusSendDirective());
        if (input) input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') window.argusSendDirective();
        });
    }

    // ── UNIVERSAL ASK ARGUS AI API (CREATES WEB REQUEST & OPENS AI AUTOMATICALLY) ──
    window.argusAskAbout = function(target) {
        if (!target) return;

        let query = '';
        let customCoords = null;

        if (typeof target === 'string') {
            query = target;
        } else if (target.type === 'news') {
            const title = target.title || 'Intel Intercept';
            const source = target.source || 'Newsfeed';
            const url = target.url || '';
            const desc = target.desc || '';
            query = `⚡ GEOPOLITICAL & OSINT INTEL INQUIRY:\nTitle: "${title}"\nSource: ${source}\nURL: ${url}\n${desc ? `Summary: ${desc}\n` : ''}\nDirective: Perform deep geopolitical risk analysis on this event. Evaluate impact on supply chains, regional tensions, and verify latest developments via live web recon.`;
        } else if (target.type === 'flight' || target.type === 'aircraft') {
            const d = target.data || {};
            const callsign = (d.callsign || d.icao24 || 'UNKNOWN').toUpperCase();
            const icao = (d.icao24 || d.hex || '---').toUpperCase();
            query = `✈ ADS-B AIRCRAFT ASSESSMENT:\nTarget: ${callsign} (ICAO: ${icao})\nType: ${d.aircraft_type || d.type || 'Commercial'}\nReg: ${d.registration || '---'}\nAltitude: ${d.altitude ? d.altitude + ' m' : 'N/A'}\nSpeed: ${d.velocity || d.speed ? (d.velocity || d.speed) + ' km/h' : 'N/A'}\nHeading: ${d.heading || 'N/A'}°\nSquawk: ${d.squawk || '----'}\nDirective: Profile this aircraft, verify flight corridor, identify origin/destination, and check for airspace or transponder anomalies.`;
            if (d.latitude && d.longitude) customCoords = { lat: d.latitude, lng: d.longitude };
        } else if (target.type === 'vessel' || target.type === 'marine') {
            const d = target.data || {};
            const name = (d.name || d.mmsi || 'VESSEL').toUpperCase();
            query = `🚢 AIS MARITIME ASSESSMENT:\nVessel: ${name}\nMMSI: ${d.mmsi || '---'}\nIMO: ${d.imo || '---'}\nCallsign: ${d.callsign || '---'}\nFlag: ${d.flag || d.country || '---'}\nType: ${(d.type || 'Cargo').toUpperCase()}\nSpeed: ${d.speed || '0'} kn\nStatus: ${(d.status || 'UNDERWAY').toUpperCase()}\nDestination: ${d.destination || '---'}\nDraft: ${d.draft ? d.draft + ' m' : 'N/A'}\nDirective: Evaluate voyage risks, check for AIS spoofing/dark vessel indicators, and cross-reference maritime chokepoint security.`;
            if (d.latitude && d.longitude) customCoords = { lat: d.latitude, lng: d.longitude };
        } else if (target.type === 'rf_node' || target.type === 'wifi' || target.type === 'bluetooth') {
            const d = target.data || {};
            const name = d.ssid || d.cell_id || d.ip || 'RF EMITTER';
            query = `📡 SIGINT RF EMITTER EVALUATION:\nIdentifier: "${name}"\nCategory: ${(d.type || 'ROUTER').toUpperCase()}\nBSSID/MAC: ${d.bssid || 'N/A'}\nVendor: ${d.vendor || 'Generic / Unknown'}\nIP/Host: ${d.ip || 'N/A'}\nSignal: ${d.signal || '-'} dBm\nEncryption: ${d.encryption || d.sec || 'WPA2-PSK'}\nDirective: Assess security vulnerabilities, check Shodan reconnaissance profile, and evaluate wireless threat level.`;
            if (d.lat && d.lon) customCoords = { lat: d.lat, lng: d.lon };
        } else if (target.type === 'satellite') {
            const d = target.data || {};
            query = `🛰 ORBITAL SATELLITE ASSESSMENT:\nSatellite: ${(d.name || d.noradId).toUpperCase()}\nNORAD ID: ${d.noradId || '---'}\nAltitude: ${d.altitude ? d.altitude + ' km' : 'N/A'}\nInclination: ${d.inclination || 'N/A'}°\nPeriod: ${d.period_min || 'N/A'} min\nDirective: Profile satellite mission type, operator, orbital track, and ground coverage footprint.`;
        } else if (target.type === 'earthquake' || target.type === 'seismic') {
            const d = target.data || {};
            query = `⚡ SEISMIC EVENT ASSESSMENT:\nMagnitude: M${d.magnitude || '---'}\nLocation: ${d.place || 'Unknown'}\nDepth: ${d.depth || 'N/A'}\nTime: ${d.time ? new Date(Number(d.time)).toUTCString() : 'Recent'}\nDirective: Analyze tectonic fault zone, assess tsunami risks and critical infrastructure vulnerability nearby.`;
        } else if (target.type === 'ground_node') {
            const d = target.data || {};
            query = `🛡 GROUND NODE TELEMETRY INSPECTION:\nNode ID: ${d.nodeId || '---'}\nTrust Score: ${d.trustPct}%\nIntegrity: ${d.integrityStatus}\nAnomaly Score: ${d.anomalyScore || '0'}\nQuarantined: ${d.isQuarantined ? 'YES' : 'NO'}\nTemperature: ${d.temperatureCelsius}°C\nBattery: ${d.batteryPercent}%\nAnomaly Reasons: ${d.anomalyReasons || 'None'}\nDirective: Diagnose root cause of telemetry fluctuations and recommend tactical mitigation protocol.`;
            if (target.coords) customCoords = target.coords;
        } else if (target.type === 'ground_incident') {
            const d = target.data || {};
            query = `🔴 GROUND INCIDENT INVESTIGATION:\nIncident ID: ${d.incidentId || '---'}\nTitle: ${d.title || 'Security Breach'}\nSeverity: ${d.severity}\nStatus: ${d.status}\nContributing Events: ${d.eventCount}\nViolations: ${d.integrityViolations || '---'}\nIndicators: ${d.anomalyReasons || '---'}\nDirective: Conduct tactical incident triage, assess compromise depth, and generate immediate containment instructions.`;
            if (target.coords) customCoords = target.coords;
        } else if (target.type === 'url') {
            const url = target.url || '';
            query = `🌐 WEBPAGE & URL OSINT INVESTIGATION:\nURL: ${url}\nDirective: Intercept live webpage content, analyze domain infrastructure, evaluate intelligence credibility, and summarize key insights.`;
        } else {
            query = `Tactical query regarding: ${JSON.stringify(target)}`;
        }

        // Open AI and immediately dispatch web request
        window.openArgusAI();
        window.argusSendDirective(query, customCoords);
    };

    // ── CHECK URL DIRECTIVES (?ask=... or ?url=... or ?lat=...&lon=...&auto_scan=1) ──
    function checkUrlDirectives() {
        const urlParams = new URLSearchParams(window.location.search);
        const askParam = urlParams.get('ask') || urlParams.get('q') || urlParams.get('query') || urlParams.get('prompt');
        const urlTarget = urlParams.get('url') || urlParams.get('analyze_url');
        const flightParam = urlParams.get('flight') || urlParams.get('icao');
        const vesselParam = urlParams.get('vessel') || urlParams.get('mmsi');
        const nodeParam = urlParams.get('node') || urlParams.get('bssid') || urlParams.get('ssid');
        const latParam = parseFloat(urlParams.get('lat'));
        const lonParam = parseFloat(urlParams.get('lon') || urlParams.get('lng'));
        const autoScan = urlParams.get('auto_scan') === '1' || urlParams.get('scan') === '1';

        if (askParam) {
            setTimeout(() => {
                window.argusAskAbout(decodeURIComponent(askParam));
            }, 800);
        } else if (urlTarget) {
            setTimeout(() => {
                window.argusAskAbout({ type: 'url', url: decodeURIComponent(urlTarget) });
            }, 800);
        } else if (flightParam) {
            setTimeout(() => {
                window.argusAskAbout({ type: 'flight', data: { icao24: flightParam, callsign: flightParam } });
            }, 900);
        } else if (vesselParam) {
            setTimeout(() => {
                window.argusAskAbout({ type: 'vessel', data: { mmsi: vesselParam, name: vesselParam } });
            }, 900);
        } else if (nodeParam) {
            setTimeout(() => {
                window.argusAskAbout({ type: 'rf_node', data: { ssid: nodeParam, bssid: nodeParam } });
            }, 900);
        } else if (autoScan && !isNaN(latParam) && !isNaN(lonParam)) {
            setTimeout(() => {
                window.argusSendDirective(
                    `Target sector locked at ${latParam.toFixed(4)}°N, ${lonParam.toFixed(4)}°E. Execute comprehensive multi-domain tactical intelligence scan on active vessels, aircraft, and signal anomalies in this area.`,
                    { lat: latParam, lng: lonParam }
                );
            }, 900);
        }
    }

    // ── HUD ACTION HANDLERS (MAP CAMERA, FLIGHT & VESSEL TRACKING) ────────────
    window.argusScanMap = function (lat, lng, promptText) {
        const latitude = parseFloat(lat);
        const longitude = parseFloat(lng);
        if (isNaN(latitude) || isNaN(longitude)) return;

        let handledLocally = false;

        // 1. Cesium 3D Globe
        if (typeof window.globe !== 'undefined' && window.globe && typeof window.globe.flyTo === 'function') {
            window.globe.flyTo(latitude, longitude, 35000, 2);
            handledLocally = true;
        } else if (typeof window.viewer !== 'undefined' && window.viewer && window.viewer.camera) {
            window.viewer.camera.flyTo({
                destination: Cesium.Cartesian3.fromDegrees(longitude, latitude, 35000.0),
                duration: 2.0
            });
            handledLocally = true;
        }

        // 2. Leaflet / MapLibre 2D GroundView
        if (!handledLocally && typeof window.flyTo === 'function') {
            window.flyTo(latitude, longitude, 12);
            handledLocally = true;
        } else if (!handledLocally && typeof window.map !== 'undefined' && window.map) {
            if (typeof window.map.flyTo === 'function') {
                window.map.flyTo({ center: [longitude, latitude], zoom: 12, speed: 1.5 });
                handledLocally = true;
            } else if (typeof window.map.setView === 'function') {
                window.map.setView([latitude, longitude], 12);
                handledLocally = true;
            }
        }

        // 3. Dispatch AI Directive
        const directive = promptText || `Initiating active tactical scan on sector ${latitude.toFixed(4)}°N, ${longitude.toFixed(4)}°E. Cross-reference all maritime AIS transponders, airspace ADS-B contacts, and intelligence anomalies in this sector.`;

        if (handledLocally) {
            window.argusSendDirective(directive, { lat: latitude, lng: longitude });
        } else {
            window.location.href = `/earth?lat=${latitude}&lon=${longitude}&auto_scan=1`;
        }
    };

    window.argusTrackFlight = function (icao) {
        if (!icao) return;
        const code = icao.trim();

        const searchInput = document.getElementById('search-input') || document.getElementById('news-search');
        if (searchInput) {
            searchInput.value = code;
            if (typeof window.performSearch === 'function') window.performSearch();
        }
        if (typeof window.highlightFlight === 'function') {
            window.highlightFlight(code);
        }

        window.argusAskAbout({ type: 'flight', data: { icao24: code, callsign: code } });
    };

    window.argusTrackVessel = function (mmsi) {
        if (!mmsi) return;
        const code = mmsi.trim();

        if (typeof window.highlightVessel === 'function') {
            window.highlightVessel(code);
        }

        window.argusAskAbout({ type: 'vessel', data: { mmsi: code, name: code } });
    };

    // Initialize on ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', injectArgusUI);
    } else {
        injectArgusUI();
    }

})();
