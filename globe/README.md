# 🌍 GeoVigilant Argus Eye — 3D Globe Subsystem

This directory contains the **entire 3D Cesium Globe subsystem** of GeoVigilant Argus Eye, isolated as a self-contained module engineered for high-performance geospatial rendering and tactical reconnaissance.

---

## 📸 3D GLOBE SHOWCASE

### 📡 3D Air Surveillance Radar & Multi-Layer Telemetry
Real-time 3D tactical radar with rotating sweep beam, true altitude drop stems, velocity vectors, and 16 active real-time telemetry layers.

![3D Air Surveillance Radar](../screenshots/radar_and_layers_verified.png)

---

### 🛰️ Photorealistic Orbital Reconnaissance HUD
High-resolution ArcGIS satellite basemap with global flight transponders, satellite orbits, world clocks, and live GEO-AI Uplink threat matrix.

![Photorealistic 3D Planetary HUD](../screenshots/globe_regression_check.png)

---

## 📂 Directory Structure

```
globe/
├── index.html              # Standalone 3D Globe HUD entry point
├── README.md               # Subsystem technical documentation
├── css/
│   ├── globe-style.css     # Primary tactical HUD layout, panels, and responsiveness
│   └── cyberpunk.css       # Cyberpunk theme variables, glows, and animations
├── data/
│   ├── cities.geojson      # Global city points with scale-rank labels
│   ├── countries.geojson   # Country polygon boundaries with country labels
│   ├── states.geojson      # US state / province boundaries
│   ├── palestine.geojson   # Palestine full territory boundaries
│   ├── palestine-1948.geojson # 1948 historical boundary layer
│   └── cover-image.png     # OG/Twitter card image
└── src/
    ├── globe.js            # Terra5Globe — Cesium.js 3D engine, GLSL post-process shaders
    │                         (CRT, NVG, FLIR, Noir, Anime, Snow), layer update methods
    ├── main.js             # AppController — HUD state, layer toggles, polling timers,
    │                         ARGUS core panel, PIZZINT, news, world clock, PANOPTIC AI
    ├── style.css           # Source stylesheet (compiled into globe-style.css)
    ├── counter.js          # Lightweight counter utility
    ├── javascript.svg      # Default asset
    └── services/
        ├── api.js          # Live API feeds: OpenSky (ADS-B flights), AIS vessels,
        │                     N2YO satellites, USGS earthquakes, OpenWeather,
        │                     NASA EONET natural events, FEMA weather alerts,
        │                     CCTV camera proxy, Windy.com radar tiles
        ├── mapData.js      # Geospatial intelligence dataset: military bases,
        │                     nuclear reactors, strategic waterways, undersea cables,
        │                     spaceports, intel hotspots, conflict zones
        ├── mock.js         # HUD entity projection & real-time telemetry overlays
        └── signalAggregator.js # Cross-layer correlation & regional threat evaluation
```

---

## ⚡ How It Works

### Core Stack
- **Cesium.js 1.114**: High-precision 3D photorealistic globe engine with WGS-84 ellipsoid mathematics.
- **ArcGIS World Imagery**: Full-spectrum satellite basemap with multi-resolution tile caching.
- **GLSL Shading Language**: Hardware-accelerated post-processing fragment shaders.
- **Vite 6**: Fast ESM module bundler compiling `globe/src/main.js` → `static/js/globe-main.js`.

### Data Ingestion Pipeline
```
Flask Backend API (app.py) 
       │
       ▼
services/api.js (REST Fetchers & WebSocket Streams)
       │
       ▼
AppController (main.js) (State Management & Signal Correlation)
       │
       ▼
Terra5Globe (globe.js) (Cesium Entity & Primitive Collections)
       │
       ▼
GPU Viewport (Cesium.Viewer with GLSL Post-Process Pipeline)
```

---

## 👁️ Visual Sensor Modes (GLSL Shaders)

| Mode | Shader Pipeline Description |
| :--- | :--- |
| **NORMAL** | Default full-color photorealistic ArcGIS satellite imagery |
| **CRT** | Scanline rasterization, phosphor bleed, and chromatic aberration |
| **NVG** | Gen-3 Night Vision green monochrome with ITU-R BT.601 luma and sensor grain |
| **FLIR** | 4-stage thermal infrared false-color heat mapping |
| **NOIR** | High-contrast black-and-white surveillance film with edge vignetting |
| **ANIME** | Sobel edge detection outline filter with quantized color bands |
| **SNOW** | Simulated severe winter blizzard noise grain |

---

## 🛠️ Build & Development Commands

> [!NOTE]
> **Pre-compiled Assets Included**: `static/js/globe-main.js` is already pre-compiled in the repository. Running `npm run build` is only necessary if you edit source files inside `globe/src/`.

From the project root:

```bash
# Start the Vite development server with hot module replacement (HMR on port 5173)
npm run dev

# Compile changes into static/js/globe-main.js for standalone production deployment
npm run build
```

---

## 📡 Active Telemetry Layers

| Layer | Source | Telemetry Render Method |
| :--- | :--- | :--- |
| **Live Flights** | OpenSky ADS-B | Billboard icons, true heading rotation, altitude stems |
| **Live Vessels** | AISstream.io | Marine hull icons with voyage trails |
| **Satellites** | SatNOGS / CelesTrak | SGP4 TLE orbital tracks and position primitives |
| **Earthquakes** | USGS GeoJSON | Magnitude-scaled shockwave rings and depth cues |
| **Weather Radar** | NOAA / Open-Meteo | Atmospheric reflectivity tile layers |
| **CCTV Cameras** | Global Proxy Nodes | Interactive camera markers with live video modals |
| **Military Bases** | Global GeoINT DB | Strategic defense installation markers |
| **Nuclear Sites** | IAEA Open Geodata | Commercial reactors and enrichment facilities |
| **Conflict Zones** | ACLED Intel | Dynamic geopolitical polygon boundary perimeters |
| **Intel Hotspots** | Strategic Matrix | Risk-assessed severity markers |
| **Waterways** | Chokepoint DB | Critical maritime transit corridors |
| **Undersea Cables** | Submarine Telecom DB | Trans-oceanic fiber-optic cable paths |
| **Wildfires** | NASA FIRMS | VIIRS/MODIS thermal anomaly blooms |
| **Natural Events** | NASA EONET | Active volcanoes, storms, and hazard alerts |
| **Spaceports** | Launch DB | Global orbital launch complexes |
| **Economic Centers** | Financial Matrix | Major stock exchanges and trade centers |

---

## ⌨️ Operator Shortcuts

| Key Binding | Command | Action |
| :--- | :--- | :--- |
| `R` | `TOGGLE_AIR_RADAR` | Toggles the 3D rotating air radar dome and controls |
| `Ctrl + [` | `TOGGLE_SIDEBAR` | Collapses or expands the tactical layers drawer |
| `Ctrl + P` | `TOGGLE_PANOPTIC` | Activates/deactivates the AI target bounding box generator |
| `Escape` | `DISMISS_PANELS` | Closes all open modals and popups |

```
================================================================================
  [ END OF GLOBE SPECIFICATION ] // [ GEOVIGILANT ARGUS EYE ]
================================================================================
```
