# 🤝 Contributing to GeoVigilant Argus Eye
```
================================================================================
  [ OPEN SOURCE CONTRIBUTION & COLLABORATION GUIDELINES ]
================================================================================
```

Thank you for your interest in contributing to **GeoVigilant Argus Eye**!
Open-source contributions help enhance telemetry accuracy, expand OSINT capabilities, optimize GLSL shaders, and build defense-grade situational awareness tools.

![Tactical HUD Overview](screenshots/sidebar_radar_removed.png)

---

## 🚀 How You Can Contribute

* 🐞 **Report Issues**: Open an issue on GitHub with reproduction steps, coordinates, browser console logs, and screenshots.
* 💡 **Propose Features**: Submit feature requests for new telemetry feeds, UI widgets, or AI models.
* 🧑‍💻 **Submit Code**: Open a Pull Request for bug fixes, performance improvements, or new layers.
* 📖 **Improve Documentation**: Enhance developer documentation, API references, or tutorials.
* 🛰️ **Integrate New Telemetry Feeds**: Connect public ADS-B receivers, marine AIS nodes, or satellite orbital DBs.

---

## 🔧 Development Workflow

### 1. Fork & Clone
```bash
git clone https://github.com/YOUR_USERNAME/GeoVigilant-Argus.git
cd GeoVigilant-Argus
```

### 2. Zero-Config Environment
> [!TIP]
> **No API keys are required for local development!** The application automatically uses free public feeds and local heuristic fallbacks. You only need a `.env` file if testing specific third-party commercial APIs (e.g. OpenRouter cloud AI or Twitter v2).

### 3. Install Dependencies
```bash
# Python backend dependencies
pip install -r requirements.txt

# (Optional) Node.js dependencies — only needed if editing globe frontend source
npm install
```

### 4. Run Locally
* **Windows (1-Click)**: Run `.\start.bat` (select `1` for Eco Dev Mode with Vite HMR, or `3` for Standalone Flask).
* **Linux / macOS (1-Command)**: Run `./start.sh` or `python app.py`.
* **Frontend Dev Server (Optional)**: `npm run dev` (Port 5173 with hot module reloading).

### 5. Create a Feature Branch & Commit
```bash
git checkout -b feat/your-feature-name
git commit -m "feat: Add new telemetry layer"
git push origin feat/your-feature-name
```

---

## 🧠 Architectural Guidelines & Standards

### 🌐 Layer Isolation & Performance
* **Zero GPU Overhead**: Any new 3D layer added to `static/js/services/` or `globe/src/` must use billboard caching and distance-based display thresholds (`distanceDisplayCondition`) to prevent FPS drops.
* **Dual-Engine Decoupling**: Keep the 3D Cesium engine (`globe/`) and 2D MapLibre engine (`groundview.html`) completely decoupled to prevent WebGL context conflicts.
* **Serverless Safety**: In `app.py`, external HTTP requests must include strict timeouts (`timeout=5`) to prevent blocking Vercel serverless functions.
* **Environment Safety**: Never hardcode API keys or secret tokens into client-side templates or bundled scripts. Always query backend routes that read from `.env`.

---

## 🧪 Automated Testing & Verification

Run tests to ensure code integrity:
```bash
# Run backend tests
pytest

# Run frontend bundle build
npm run build
```

```
================================================================================
  [ THANK YOU FOR SUPPORTING GEOVIGILANT ARGUS EYE ]
================================================================================
```
