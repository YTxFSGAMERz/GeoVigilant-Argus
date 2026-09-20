/**
 * ═══════════════════════════════════════════════════════════════════════
 * GEOVIGILANT ARGUS EYE — TACTICAL KIOSK & SECURITY SUITE
 * ═══════════════════════════════════════════════════════════════════════
 *
 * Provides:
 * 1. Unified Mission Loading Screen across all pages & internal transitions
 * 2. Tactical Cyber Right-Click Context Menu everywhere
 * 3. Developer Options & F12 Security Interceptor with HUD Toast
 * 4. Custom Highlight Support & Kiosk Controls
 */

(function () {
    'use strict';

    /* ───────────────────────────────────────────────────────────────────
       1. DEVELOPER OPTIONS & F12 LOCKDOWN
       ─────────────────────────────────────────────────────────────────── */
    function initSecurityLockdown() {
        // Log classified security banner in console
        try {
            console.log(
                "%c[CLASSIFIED] GEOVIGILANT ARGUS EYE // MULTI-DOMAIN GEOINT PLATFORM\n%cSECURITY NOTICE: Developer options and inspect tools are disabled on this terminal.",
                "color:#00ffd1; background:#000810; font-size:14px; font-family:'Share Tech Mono', monospace; font-weight:bold; padding:8px 14px; border:1px solid #00ffd1; border-radius:3px; display:inline-block;",
                "color:#ffcc00; background:#000810; font-size:11.5px; font-family:'Share Tech Mono', monospace; padding:4px 14px; display:inline-block;"
            );
        } catch (_) {}

        // Global Keydown Interception (Capture Phase)
        window.addEventListener('keydown', function (e) {
            const key = e.key ? e.key.toUpperCase() : '';
            const code = e.keyCode || e.which;
            const ctrlOrMeta = e.ctrlKey || e.metaKey;

            // F12 (DevTools)
            const isF12 = key === 'F12' || code === 123;

            // Ctrl+Shift+I (Inspect), Ctrl+Shift+J (Console), Ctrl+Shift+C (Inspect Element), Ctrl+Shift+K (Firefox)
            const isDevInspect = ctrlOrMeta && e.shiftKey && (
                key === 'I' || key === 'J' || key === 'C' || key === 'K' ||
                code === 73 || code === 74 || code === 67 || code === 75
            );

            // Ctrl+U (View Page Source)
            const isViewSource = ctrlOrMeta && (key === 'U' || code === 85);

            // Ctrl+S (Save Page Source)
            const isSavePage = ctrlOrMeta && (key === 'S' || code === 83);

            if (isF12 || isDevInspect || isViewSource || isSavePage) {
                e.preventDefault();
                e.stopPropagation();
                if (typeof e.stopImmediatePropagation === 'function') {
                    e.stopImmediatePropagation();
                }

                let reason = 'DEVELOPER OPTIONS LOCKED';
                if (isF12) reason = 'F12 DEVTOOLS RESTRICTED';
                else if (isDevInspect) reason = 'CONSOLE INSPECTION BLOCKED';
                else if (isViewSource) reason = 'SOURCE VIEW RESTRICTED';
                else if (isSavePage) reason = 'PAGE EXPORT PROTECTED';

                showSecurityToast(reason, 'GEOVIGILANT ARGUS // HARDENED RUNTIME');
                return false;
            }
        }, true);
    }

    /* ───────────────────────────────────────────────────────────────────
       2. TACTICAL HUD SECURITY ALERT TOAST
       ─────────────────────────────────────────────────────────────────── */
    let toastTimeout = null;

    function getOrCreateSecurityToast() {
        let toast = document.getElementById('argus-security-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'argus-security-toast';
            toast.innerHTML = `
                <div class="argus-toast-icon">⚠️</div>
                <div class="argus-toast-body">
                    <div class="argus-toast-title" id="argus-toast-title">SECURITY ALERT</div>
                    <div class="argus-toast-msg" id="argus-toast-msg">DEVELOPER OPTIONS DISABLED</div>
                </div>
            `;
            document.body.appendChild(toast);
        }
        return toast;
    }

    function showSecurityToast(title, message) {
        if (!document.body) return;
        const toast = getOrCreateSecurityToast();
        const titleEl = document.getElementById('argus-toast-title');
        const msgEl = document.getElementById('argus-toast-msg');

        if (titleEl) titleEl.textContent = title;
        if (msgEl) msgEl.textContent = message;

        toast.classList.add('argus-toast-show');

        if (toastTimeout) clearTimeout(toastTimeout);
        toastTimeout = setTimeout(() => {
            toast.classList.remove('argus-toast-show');
        }, 2800);
    }

    /* ───────────────────────────────────────────────────────────────────
       3. TACTICAL CUSTOM RIGHT-CLICK CONTEXT MENU
       ─────────────────────────────────────────────────────────────────── */
    function getOrCreateContextMenu() {
        let menu = document.getElementById('argus-context-menu');
        if (!menu) {
            menu = document.createElement('div');
            menu.id = 'argus-context-menu';
            menu.innerHTML = `
                <div class="argus-menu-header">
                    <span><span class="argus-menu-header-dot"></span>ARGUS CONTEXT HUD</span>
                    <span class="argus-menu-badge">EXPO 2026</span>
                </div>

                <a href="/earth" class="argus-menu-item" data-action="nav">
                    <span class="argus-menu-item-left">
                        <span class="argus-menu-icon">🌍</span>
                        <span>3D Globe HUD</span>
                    </span>
                    <span class="argus-menu-badge">/earth</span>
                </a>

                <a href="/ground" class="argus-menu-item" data-action="nav">
                    <span class="argus-menu-item-left">
                        <span class="argus-menu-icon">🗺️</span>
                        <span>2D GroundView Intel</span>
                    </span>
                    <span class="argus-menu-badge">/ground</span>
                </a>

                <a href="/surveillance" class="argus-menu-item" data-action="nav">
                    <span class="argus-menu-item-left">
                        <span class="argus-menu-icon">📶</span>
                        <span>RF Surveillance &amp; WiFi</span>
                    </span>
                    <span class="argus-menu-badge">/surv</span>
                </a>

                <a href="/news" class="argus-menu-item" data-action="nav">
                    <span class="argus-menu-item-left">
                        <span class="argus-menu-icon">📺</span>
                        <span>Global News Stream</span>
                    </span>
                    <span class="argus-menu-badge">/news</span>
                </a>

                <a href="/newsnetworks" class="argus-menu-item" data-action="nav">
                    <span class="argus-menu-item-left">
                        <span class="argus-menu-icon">🌐</span>
                        <span>News Networks Matrix</span>
                    </span>
                    <span class="argus-menu-badge">/matrix</span>
                </a>

                <a href="/" class="argus-menu-item" data-action="nav">
                    <span class="argus-menu-item-left">
                        <span class="argus-menu-icon">🏠</span>
                        <span>Operations Hub</span>
                    </span>
                    <span class="argus-menu-badge">HOME</span>
                </a>

                <div class="argus-menu-separator"></div>

                <div class="argus-menu-item" id="argus-menu-refresh">
                    <span class="argus-menu-item-left">
                        <span class="argus-menu-icon">🔄</span>
                        <span>Refresh Tactical Feed</span>
                    </span>
                    <span class="argus-menu-badge">RELOAD</span>
                </div>

                <div class="argus-menu-item" id="argus-menu-fullscreen">
                    <span class="argus-menu-item-left">
                        <span class="argus-menu-icon">🖥️</span>
                        <span>Toggle Fullscreen Kiosk</span>
                    </span>
                    <span class="argus-menu-badge">[F]</span>
                </div>

                <div class="argus-menu-item" id="argus-menu-copy">
                    <span class="argus-menu-item-left">
                        <span class="argus-menu-icon">📋</span>
                        <span>Copy Selected Intel</span>
                    </span>
                    <span class="argus-menu-badge">COPY</span>
                </div>

                <div class="argus-menu-item" id="argus-menu-print">
                    <span class="argus-menu-item-left">
                        <span class="argus-menu-icon">🖨️</span>
                        <span>Tactical Print Briefing</span>
                    </span>
                    <span class="argus-menu-badge">PRINT</span>
                </div>

                <div class="argus-menu-separator"></div>

                <div class="argus-menu-footer">
                    <span>🔒 RESTRICTED TERMINAL // DEV TOOLS PROTECTED</span>
                </div>
            `;
            document.body.appendChild(menu);

            // Bind Actions
            document.getElementById('argus-menu-refresh').addEventListener('click', function () {
                hideContextMenu();
                triggerPageTransition(window.location.href);
            });

            document.getElementById('argus-menu-fullscreen').addEventListener('click', function () {
                hideContextMenu();
                if (!document.fullscreenElement) {
                    if (document.documentElement.requestFullscreen) {
                        document.documentElement.requestFullscreen().catch(() => {});
                    }
                } else {
                    if (document.exitFullscreen) {
                        document.exitFullscreen().catch(() => {});
                    }
                }
            });

            document.getElementById('argus-menu-copy').addEventListener('click', function () {
                hideContextMenu();
                const sel = window.getSelection ? window.getSelection().toString() : '';
                if (sel) {
                    if (navigator.clipboard && navigator.clipboard.writeText) {
                        navigator.clipboard.writeText(sel).then(() => {
                            showSecurityToast('INTELLIGENCE COPIED', `${sel.length} CHARS TO CLIPBOARD`);
                        }).catch(() => {
                            showSecurityToast('CLIPBOARD ACTIVE', 'SELECTION READY');
                        });
                    }
                } else {
                    showSecurityToast('NO TEXT SELECTED', 'HIGHLIGHT INTEL FIRST');
                }
            });

            document.getElementById('argus-menu-print').addEventListener('click', function () {
                hideContextMenu();
                setTimeout(() => { window.print(); }, 100);
            });

            // Delegate internal navigation
            menu.querySelectorAll('a[data-action="nav"]').forEach(link => {
                link.addEventListener('click', function (e) {
                    const href = this.getAttribute('href');
                    if (href && href.startsWith('/')) {
                        e.preventDefault();
                        hideContextMenu();
                        triggerPageTransition(href);
                    }
                });
            });
        }
        return menu;
    }

    function showContextMenu(e) {
        const menu = getOrCreateContextMenu();
        menu.style.display = 'block';
        menu.style.visibility = 'hidden';

        // Measure menu dimensions
        const menuWidth = menu.offsetWidth || 260;
        const menuHeight = menu.offsetHeight || 380;
        const winWidth = window.innerWidth;
        const winHeight = window.innerHeight;

        let posX = e.clientX;
        let posY = e.clientY;

        // Prevent overflow beyond right edge
        if (posX + menuWidth > winWidth - 10) {
            posX = winWidth - menuWidth - 10;
        }
        // Prevent overflow beyond bottom edge
        if (posY + menuHeight > winHeight - 10) {
            posY = winHeight - menuHeight - 10;
        }

        if (posX < 10) posX = 10;
        if (posY < 10) posY = 10;

        menu.style.left = posX + 'px';
        menu.style.top = posY + 'px';
        menu.style.visibility = 'visible';
    }

    function hideContextMenu() {
        const menu = document.getElementById('argus-context-menu');
        if (menu) {
            menu.style.display = 'none';
        }
    }

    function initCustomContextMenu() {
        // Prevent default browser right-click context menu everywhere
        window.addEventListener('contextmenu', function (e) {
            e.preventDefault();
            showContextMenu(e);
        }, true);

        // Dismiss context menu on click outside, scroll, resize, or Escape
        window.addEventListener('click', function (e) {
            const menu = document.getElementById('argus-context-menu');
            if (menu && !menu.contains(e.target)) {
                hideContextMenu();
            }
        });

        window.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                hideContextMenu();
            }
        });

        window.addEventListener('scroll', hideContextMenu, true);
        window.addEventListener('resize', hideContextMenu);
    }

    /* ───────────────────────────────────────────────────────────────────
       4. UNIVERSAL MISSION LOADING SCREEN
       ─────────────────────────────────────────────────────────────────── */
    const TELEMETRY_PHRASES = [
        "INITIALIZING DUAL-ENGINE GEOINT CORE...",
        "SYNCING SATELLITE TELEMETRY & AIS VESSEL FEEDS...",
        "CALIBRATING PANOPTIC THREAT RECOGNITION V4...",
        "ESTABLISHING ENCRYPTED GEOINT TACTICAL MESH...",
        "INITIALIZING DUAL-ENGINE GEOINT CORE..."
    ];

    let currentProgress = 0;
    let progressTimer = null;
    let isLoadComplete = false;
    let loaderElements = null;

    function buildLoaderHTML() {
        return `
            <div class="argus-loader-logo">🌍</div>
            <div class="argus-loader-title">GEOVIGILANT ARGUS EYE</div>
            <div class="argus-loader-subtitle">MULTI-DOMAIN GEOINT // REAL-TIME INTELLIGENCE PLATFORM</div>
            <div class="argus-loader-bar-wrap"><div class="argus-loader-bar" id="argus-l-bar"></div></div>
            <div class="argus-loader-pct" id="argus-l-pct">0%</div>
            <div class="argus-loader-status" id="argus-l-status">INITIALIZING DUAL-ENGINE GEOINT CORE...</div>
        `;
    }

    function setupLoaderDOM() {
        // If we already have an active loader element in the DOM, keep using it
        if (loaderElements && loaderElements.loader && document.contains(loaderElements.loader)) {
            return loaderElements;
        }

        // Deduplicate: Find any existing loader elements in the page
        const existing = document.querySelectorAll('#argus-expo-loader, #loader, .argus-unified-loader');
        let loader = null;

        if (existing.length > 0) {
            loader = existing[0];
            // Remove any redundant/duplicate loaders to prevent orphaned overlays
            for (let i = 1; i < existing.length; i++) {
                try { existing[i].remove(); } catch (_) {}
            }
        }

        if (loader) {
            loader.classList.add('argus-unified-loader');
            loader.classList.remove('argus-loader-hidden', 'hidden');

            let bar = loader.querySelector('.l-bar, #l-bar, #argus-l-bar, .argus-loader-bar');
            let pct = loader.querySelector('.l-pct, #l-pct, #argus-l-pct, .argus-loader-pct');
            let status = loader.querySelector('.l-status, #l-status, #argus-l-status, .argus-loader-status');

            if (!bar || !pct || !status) {
                loader.innerHTML = buildLoaderHTML();
                bar = loader.querySelector('.l-bar, #l-bar, #argus-l-bar, .argus-loader-bar');
                pct = loader.querySelector('.l-pct, #l-pct, #argus-l-pct, .argus-loader-pct');
                status = loader.querySelector('.l-status, #l-status, #argus-l-status, .argus-loader-status');
            }

            loaderElements = { loader, bar, pct, status };
        } else {
            // Create new loader element
            loader = document.createElement('div');
            loader.id = 'argus-expo-loader';
            loader.className = 'argus-unified-loader';
            loader.innerHTML = buildLoaderHTML();

            const target = document.body || document.documentElement;
            if (target) {
                target.insertBefore(loader, target.firstChild);
            }

            const bar = loader.querySelector('#argus-l-bar');
            const pct = loader.querySelector('#argus-l-pct');
            const status = loader.querySelector('#argus-l-status');

            loaderElements = { loader, bar, pct, status };
        }

        return loaderElements;
    }

    function updateLoader(value, statusText) {
        if (!loaderElements || !document.contains(loaderElements.loader)) setupLoaderDOM();
        if (!loaderElements) return;

        const val = Math.min(100, Math.max(0, value));
        currentProgress = val;

        if (loaderElements.bar) {
            loaderElements.bar.style.width = val + '%';
        }
        if (loaderElements.pct) {
            loaderElements.pct.textContent = Math.floor(val) + '%';
        }
        if (loaderElements.status && statusText) {
            loaderElements.status.textContent = statusText;
        }
    }

    function runLoaderSimulation() {
        setupLoaderDOM();

        let phraseIndex = 0;
        progressTimer = setInterval(() => {
            if (isLoadComplete) return;

            // Increment progressively up to 92%
            if (currentProgress < 90) {
                currentProgress += (Math.random() * 14 + 6);
                if (currentProgress > 90) currentProgress = 90;

                phraseIndex = Math.min(
                    TELEMETRY_PHRASES.length - 1,
                    Math.floor((currentProgress / 90) * TELEMETRY_PHRASES.length)
                );

                updateLoader(currentProgress, TELEMETRY_PHRASES[phraseIndex]);
            }
        }, 70);
    }

    function finishLoader() {
        if (isLoadComplete) return;
        isLoadComplete = true;
        if (progressTimer) {
            clearInterval(progressTimer);
            progressTimer = null;
        }

        // Instant ramp to 100%
        updateLoader(100, "INITIALIZING DUAL-ENGINE GEOINT CORE...");

        // Fade out and completely remove ALL loader instances
        setTimeout(() => {
            const allLoaders = document.querySelectorAll('#argus-expo-loader, #loader, .argus-unified-loader');
            allLoaders.forEach(el => {
                el.classList.add('argus-loader-hidden', 'hidden');
                el.style.opacity = '0';
                el.style.pointerEvents = 'none';
                setTimeout(() => {
                    el.style.display = 'none';
                    try {
                        if (el.parentNode) el.parentNode.removeChild(el);
                    } catch (_) {}
                }, 650);
            });
        }, 320);
    }

    /* ─── Page Transition Interception for SPA feel ───────────────────── */
    function triggerPageTransition(targetUrl) {
        if (!targetUrl) return;

        setupLoaderDOM();
        if (loaderElements && loaderElements.loader) {
            loaderElements.loader.style.display = 'flex';
            loaderElements.loader.classList.remove('argus-loader-hidden', 'hidden');
            updateLoader(15, "CONNECTING TO TACTICAL NODE...");

            let p = 15;
            const tInt = setInterval(() => {
                p += 25;
                if (p >= 90) {
                    p = 90;
                    clearInterval(tInt);
                }
                updateLoader(p, "TRANSFERRING TELEMETRY CONTEXT...");
            }, 50);

            setTimeout(() => {
                window.location.href = targetUrl;
            }, 140);
        } else {
            window.location.href = targetUrl;
        }
    }

    function initPageTransitions() {
        document.addEventListener('click', function (e) {
            const link = e.target.closest('a');
            if (!link) return;

            const href = link.getAttribute('href');
            const target = link.getAttribute('target');

            // Skip anchor jumps, mailto, tel, javascript, or external blank targets
            if (!href || href.startsWith('#') || href.startsWith('javascript:') ||
                href.startsWith('mailto:') || href.startsWith('tel:') || target === '_blank') {
                return;
            }

            // Internal relative navigation or same-origin paths
            if (href.startsWith('/') || href.endsWith('.html')) {
                // If it's the exact same page without query diff, let normal behavior occur
                if (href === window.location.pathname || href === window.location.href) {
                    return;
                }
                e.preventDefault();
                triggerPageTransition(href);
            }
        });
    }

    /* ───────────────────────────────────────────────────────────────────
       5. INITIALIZATION SEQUENCE
       ─────────────────────────────────────────────────────────────────── */
    // 1. Start security lockdown immediately
    initSecurityLockdown();

    // 2. Setup loader as early as possible
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            setupLoaderDOM();
            getOrCreateContextMenu();
            initCustomContextMenu();
            initPageTransitions();
        });
    } else {
        setupLoaderDOM();
        getOrCreateContextMenu();
        initCustomContextMenu();
        initPageTransitions();
    }

    // 3. Start simulated loading ticks
    runLoaderSimulation();

    // 4. Complete loader on window load (or fallback timeout)
    if (document.readyState === 'complete') {
        setTimeout(finishLoader, 200);
    } else {
        window.addEventListener('load', finishLoader);
        // Fallback guard: ensure loader never hangs if external asset hangs
        setTimeout(finishLoader, 2500);
    }

    // Absolute fallback safety: Dismiss unconditionally after 3.2 seconds max
    setTimeout(finishLoader, 3200);

    // Manual escape/click dismiss: User can click loader or press Escape if stuck
    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !isLoadComplete) {
            finishLoader();
        }
    }, true);

    document.addEventListener('click', (e) => {
        const activeLoader = document.getElementById('argus-expo-loader') || document.getElementById('loader') || document.querySelector('.argus-unified-loader');
        if (activeLoader && activeLoader.contains(e.target) && !isLoadComplete) {
            finishLoader();
        }
    }, true);

    // Expose utility to window
    window.ArgusKiosk = {
        showSecurityToast,
        triggerPageTransition,
        finishLoader
    };

})();
