import { describe, it, expect, beforeEach, vi } from 'vitest';
import fs from 'fs';
import path from 'path';

describe('Argus Kiosk Suite (Exhibition Edition)', () => {
    let cssContent;
    let jsContent;

    beforeEach(() => {
        cssContent = fs.readFileSync(path.resolve(__dirname, '../static/css/argus-kiosk.css'), 'utf8');
        jsContent = fs.readFileSync(path.resolve(__dirname, '../static/js/argus-kiosk.js'), 'utf8');
    });

    describe('CSS Style Definitions', () => {
        it('defines custom cybernetic text selection highlights with cyan background', () => {
            expect(cssContent).toContain('::selection');
            expect(cssContent).toContain('background: #00ffd1 !important;');
            expect(cssContent).toContain('color: #000000 !important;');
            expect(cssContent).toContain('::-moz-selection');
        });

        it('defines the universal exhibition loader styles matching expo specifications', () => {
            expect(cssContent).toContain('#argus-expo-loader');
            expect(cssContent).toContain('background: #000000 !important;');
            expect(cssContent).toContain('z-index: 99999999 !important;');
            expect(cssContent).toContain('argusGlobeFloat');
            expect(cssContent).toContain('GEOVIGILANT ARGUS EYE');
            expect(cssContent).toContain('MULTI-DOMAIN GEOINT');
            expect(cssContent).toContain('.argus-loader-bar-wrap');
            expect(cssContent).toContain('.argus-loader-bar');
            expect(cssContent).toContain('.argus-loader-pct');
            expect(cssContent).toContain('.argus-loader-status');
        });

        it('defines tactical right-click context menu styles', () => {
            expect(cssContent).toContain('#argus-context-menu');
            expect(cssContent).toContain('backdrop-filter: blur(16px);');
            expect(cssContent).toContain('.argus-menu-header');
            expect(cssContent).toContain('.argus-menu-item');
            expect(cssContent).toContain('.argus-menu-badge');
        });

        it('defines security alert toast styles', () => {
            expect(cssContent).toContain('#argus-security-toast');
            expect(cssContent).toContain('.argus-toast-show');
        });
    });

    describe('JavaScript Logic & Lockdown', () => {
        it('contains F12 and DevTools shortcut blocking mechanisms', () => {
            expect(jsContent).toContain('F12');
            expect(jsContent).toContain('isDevInspect');
            expect(jsContent).toContain('isViewSource');
            expect(jsContent).toContain('isSavePage');
            expect(jsContent).toContain('e.preventDefault()');
            expect(jsContent).toContain('e.stopPropagation()');
        });

        it('contains the tactical HUD context menu initialization with navigation shortcuts', () => {
            expect(jsContent).toContain('argus-context-menu');
            expect(jsContent).toContain('/earth');
            expect(jsContent).toContain('/ground');
            expect(jsContent).toContain('/surveillance');
            expect(jsContent).toContain('/news');
            expect(jsContent).toContain('/newsnetworks');
            expect(jsContent).toContain('Refresh Tactical Feed');
            expect(jsContent).toContain('Toggle Fullscreen Kiosk');
            expect(jsContent).toContain('Copy Selected Intel');
            expect(jsContent).toContain('Tactical Print Briefing');
        });

        it('contains universal loader lifecycle and telemetry phrases', () => {
            expect(jsContent).toContain('INITIALIZING DUAL-ENGINE GEOINT CORE...');
            expect(jsContent).toContain('setupLoaderDOM');
            expect(jsContent).toContain('finishLoader');
            expect(jsContent).toContain('argus-loader-hidden');
        });
    });
});
