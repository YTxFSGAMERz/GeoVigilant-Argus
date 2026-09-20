import { defineConfig } from 'vite';
import { resolve } from 'path';
import fs from 'fs';

function copyMapLibreWorkerPlugin() {
  return {
    name: 'copy-maplibre-worker',
    closeBundle() {
      const srcWorker = resolve(__dirname, 'node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs');
      const srcShared = resolve(__dirname, 'node_modules/maplibre-gl/dist/maplibre-gl-shared.mjs');
      const outDirs = [
        resolve(__dirname, 'static/js/chunks'),
        resolve(__dirname, 'static/js'),
      ];

      for (const dir of outDirs) {
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        if (fs.existsSync(srcWorker)) fs.copyFileSync(srcWorker, resolve(dir, 'maplibre-gl-worker.mjs'));
        if (fs.existsSync(srcShared)) fs.copyFileSync(srcShared, resolve(dir, 'maplibre-gl-shared.mjs'));
      }
      const swSrc = resolve(__dirname, 'public/sw-globe-cache.js');
      const swDest = resolve(__dirname, 'static/sw-globe-cache.js');
      if (fs.existsSync(swSrc)) fs.copyFileSync(swSrc, swDest);
      console.log('[Vite] MapLibre worker and SW globe cache copied.');
    },
  };
}
function routeRewritePlugin() {
  return {
    name: 'route-rewrite-plugin',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (!req.url) return next();
        const urlObj = new URL(req.url, 'http://localhost');
        const pathname = urlObj.pathname;

        if (pathname === '/api/proxy/rss') {
          const targetUrl = urlObj.searchParams.get('url');
          if (!targetUrl) {
            res.statusCode = 400;
            res.end('Missing url query parameter');
            return;
          }
          try {
            const parsedTarget = new URL(targetUrl);
            if (!['http:', 'https:'].includes(parsedTarget.protocol)) {
              res.statusCode = 403;
              res.end('Disallowed protocol');
              return;
            }
            const host = parsedTarget.hostname.toLowerCase();
            if (
              host === 'localhost' ||
              host === '127.0.0.1' ||
              host === '0.0.0.0' ||
              host === '::1' ||
              host.startsWith('169.254.') ||
              host.startsWith('10.') ||
              host.startsWith('192.168.') ||
              host.endsWith('.local') ||
              host.endsWith('.internal') ||
              host.endsWith('.localhost')
            ) {
              res.statusCode = 403;
              res.end('Access to internal or private addresses is blocked');
              return;
            }
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), 7000);
            const r = await fetch(targetUrl, {
              headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
              },
              signal: controller.signal
            });
            clearTimeout(timer);
            const text = await r.text();
            res.setHeader('Content-Type', r.headers.get('content-type') || 'application/xml; charset=utf-8');
            res.setHeader('Access-Control-Allow-Origin', '*');
            res.end(text);
            return;
          } catch (err) {
            res.statusCode = 502;
            res.end(err.message);
            return;
          }
        }

        if (pathname === '/earth' || pathname === '/earth/') {
          req.url = '/earth.html' + urlObj.search;
        } else if (pathname === '/ground' || pathname === '/ground/') {
          req.url = '/groundview.html' + urlObj.search;
        } else if (pathname === '/news' || pathname === '/news/') {
          req.url = '/news.html' + urlObj.search;
        } else if (pathname === '/surveillance' || pathname === '/surveillance/' || pathname === '/map-w' || pathname === '/map-w/') {
          req.url = '/wifi-search.html' + urlObj.search;
        } else if (pathname === '/newsnetworks' || pathname === '/newsnetworks/' || pathname === '/earthnetworks' || pathname === '/earthnetworks/') {
          req.url = '/newsnetworks.html' + urlObj.search;
        } else if (pathname === '/social/reddit' || pathname === '/social/reddit/') {
          req.url = '/social/reddit.html' + urlObj.search;
        } else if (pathname === '/social/twitter' || pathname === '/social/twitter/') {
          req.url = '/social/twitter.html' + urlObj.search;
        } else if (pathname === '/social' || pathname === '/social/') {
          req.url = '/news.html' + urlObj.search;
        } else if (/^\/(tor-chat|profiles|neural|cctv|mobile|alerts|fit|settings)/.test(pathname)) {
          req.url = '/earth.html' + urlObj.search;
        }
        next();
      });
    }
  };
}

export default defineConfig({
  plugins: [copyMapLibreWorkerPlugin(), routeRewritePlugin()],
  server: {
    host: true,
    watch: {
      ignored: [
        '**/ARGUS_DATASET/**',
        '**/uploads/**',
        '**/__pycache__/**',
        '**/*.log',
        '**/*.db*',
        '**/.git/**',
      ],
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        secure: false,
        configure: (proxy) => {
          proxy.on('error', (err, req, res) => {
            console.warn(`[Vite Proxy] Handled ${req?.url || 'request'} error:`, err.message);
            try {
              if (res && !res.headersSent && typeof res.writeHead === 'function') {
                res.writeHead(502, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Backend proxy error', details: err.message || 'Flask backend (port 5000) is unreachable' }));
              }
            } catch (_) {}
          });
        }
      },
      '/nearby': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        secure: false,
      },
      '/searchzz': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        secure: false,
      },
      '/chatgpt': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        secure: false,
      },
      '/socket.io': {
        target: 'http://127.0.0.1:5000',
        ws: true,
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('error', (err) => {
            console.warn('[Vite Proxy] Handled Socket.IO proxy error:', err.message);
          });
        }
      }
    }
  },
  build: {
    chunkSizeWarningLimit: 3000,
    outDir: 'static/js',
    emptyOutDir: false,
    rollupOptions: {
      input: {
        // Existing Globe entry
        'globe-main': resolve(__dirname, 'globe/src/main.js'),
        // New GroundView entry — completely separate bundle
        'groundview-main': resolve(__dirname, 'src/groundview/main.js'),
      },
      external: [
        // @mapillary/mapillary-js is an optional future dependency.
        // Excluded from build until `npm install @mapillary/mapillary-js` is run.
        '@mapillary/mapillary-js',
      ],
      output: {
        entryFileNames: '[name].js',
        chunkFileNames: 'chunks/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
        manualChunks: {
          turf: ['@turf/turf'],
          // maplibre-gl only lands in GroundView's chunk graph, never globe's
          maplibre: ['maplibre-gl'],
        }
      }
    }
  }
});


