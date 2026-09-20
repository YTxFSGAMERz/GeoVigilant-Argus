// globe/src/radarScope.js
// Tactical Plan Position Indicator (PPI) Air & Multi-Domain Radar Scope
// Directly synchronized to the active 3D Cesium camera window in real time.

export class RadarScope {
  constructor(canvas, options = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.options = Object.assign({
      rangeNM: 150,
      centerLat: 20.0,
      centerLon: 78.0,
      centerLabel: 'WINDOW VIEW',
      mode: 'view',
      sweepSpeed: 1.5, // degrees per frame
      onContactSelect: null
    }, options);

    this.rangeNM = this.options.rangeNM;
    this.centerLat = this.options.centerLat;
    this.centerLon = this.options.centerLon;
    this.centerLabel = this.options.centerLabel;
    this.headingDeg = 0;
    this.mode = this.options.mode;

    this.sweepAngle = 0;
    this.contacts = [];
    this.pings = new Map(); // id -> timestamp
    this.lockedContact = null;
    this.hoveredContact = null;
    this.animId = null;
    this.isRunning = false;
    this._projectedCache = [];

    this._setupDimensions();
    this._bindEvents();
  }

  _setupDimensions() {
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const w = rect.width || 300;
    const h = rect.height || 300;
    this.canvas.width = Math.round(w * dpr);
    this.canvas.height = Math.round(h * dpr);
    this.ctx.setTransform(1, 0, 0, 1, 0, 0);
    this.ctx.scale(dpr, dpr);

    this.displayW = w;
    this.displayH = h;
    this.cx = w / 2;
    this.cy = h / 2;
    this.radius = Math.min(this.cx, this.cy) - 18;
    this._projectedCache = this._projectContacts();
  }

  _bindEvents() {
    this.canvas.addEventListener('mousemove', (e) => this._onMouseMove(e));
    this.canvas.addEventListener('click', (e) => this._onClick(e));
    this.canvas.addEventListener('mouseleave', () => {
      this.hoveredContact = null;
      this.canvas.style.cursor = 'default';
    });
  }

  _getCanvasCoords(e) {
    const rect = this.canvas.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    };
  }

  _onMouseMove(e) {
    const { x, y } = this._getCanvasCoords(e);
    let found = null;
    const projected = this._projectedCache;

    for (let i = 0; i < projected.length; i++) {
      const c = projected[i];
      const dx = x - c.x;
      const dy = y - c.y;
      if (Math.hypot(dx, dy) <= 12) {
        found = c.raw;
        break;
      }
    }

    this.hoveredContact = found;
    this.canvas.style.cursor = found ? 'pointer' : 'default';
  }

  _onClick(e) {
    const { x, y } = this._getCanvasCoords(e);
    const projected = this._projectedCache;

    for (let i = 0; i < projected.length; i++) {
      const c = projected[i];
      const dx = x - c.x;
      const dy = y - c.y;
      if (Math.hypot(dx, dy) <= 14) {
        this.lockedContact = c.raw;
        if (typeof this.options.onContactSelect === 'function') {
          this.options.onContactSelect(c.raw);
        }
        return;
      }
    }
  }

  /**
   * Update the radar with the contacts currently showing in the window.
   */
  updateWindowContacts(payload) {
    if (!payload) return;
    if (Array.isArray(payload.contacts)) {
      this.contacts = payload.contacts;
    }
    if (Number.isFinite(payload.rangeNM)) {
      this.rangeNM = payload.rangeNM;
    }
    if (Number.isFinite(payload.headingDeg)) {
      this.headingDeg = payload.headingDeg;
    }
    if (Number.isFinite(payload.centerLat) && Number.isFinite(payload.centerLon)) {
      this.centerLat = payload.centerLat;
      this.centerLon = payload.centerLon;
    }
    if (payload.centerLabel) {
      this.centerLabel = payload.centerLabel;
    }
    this._projectedCache = this._projectContacts();
  }

  // Compatibility helper
  updateFlights(flights) {
    if (!Array.isArray(flights)) return;
    // Fallback if updateWindowContacts isn't called directly
    this.contacts = flights.map(f => Object.assign({ layer: 'flights', category: 'air' }, f));
    this._projectedCache = this._projectContacts();
  }

  setCenter(lat, lon, label = 'WINDOW VIEW', mode = null) {
    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      this.centerLat = lat;
      this.centerLon = lon;
      this.centerLabel = label;
      if (mode) this.mode = mode;
    }
  }

  setRange(rangeNM) {
    this.rangeNM = Math.max(15, Math.min(3500, rangeNM));
  }

  start() {
    if (this.isRunning) return;
    this.isRunning = true;
    this._setupDimensions();

    let lastTime = 0;
    const interval = 1000 / 30; // Cap at 30 FPS for summer thermal efficiency

    const loop = (timestamp) => {
      if (!this.isRunning) return;
      this.animId = requestAnimationFrame(loop);
      if (!timestamp) timestamp = performance.now();
      const elapsed = timestamp - lastTime;
      if (elapsed >= interval) {
        lastTime = timestamp - (elapsed % interval);
        this.render();
      }
    };
    this.animId = requestAnimationFrame(loop);
  }

  stop() {
    this.isRunning = false;
    if (this.animId) {
      cancelAnimationFrame(this.animId);
      this.animId = null;
    }
  }

  /**
   * Projects each window contact onto the 2D circular radar scope.
   * Uses screen-normalized coordinates so contacts match window positions 1:1.
   */
  _projectContacts() {
    const result = [];
    const R = this.radius;
    const cx = this.cx;
    const cy = this.cy;

    const maxContacts = Math.min(this.contacts.length, 120);
    for (let i = 0; i < maxContacts; i++) {
      const c = this.contacts[i];
      let normX = c.winNormX;
      let normY = c.winNormY;

      // If contact doesn't have screen coordinates, calculate from polar center
      if (normX == null || normY == null) {
        const lat = c.latitude ?? c.lat;
        const lon = c.longitude ?? c.lon;
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
        const cosLat = Math.cos(this.centerLat * Math.PI / 180);
        const dLatKm = (lat - this.centerLat) * 111.139;
        const dLonKm = (lon - this.centerLon) * 111.139 * cosLat;
        const distKm = Math.hypot(dLatKm, dLonKm);
        const distNM = distKm / 1.852;
        if (distNM > this.rangeNM) continue;
        const brgRad = Math.atan2(dLonKm, dLatKm);
        normX = Math.sin(brgRad) * (distNM / this.rangeNM);
        normY = -Math.cos(brgRad) * (distNM / this.rangeNM);
      }

      const distNorm = Math.hypot(normX, normY);
      const angle = Math.atan2(normX, -normY); // 0 = UP (screen top), PI/2 = RIGHT
      const angleDeg = ((angle * 180 / Math.PI) + 360) % 360;

      // Scale to fit gracefully within the circular scope dial
      const r = Math.min(R * 0.94, (distNorm / 1.35) * R);
      const x = cx + r * Math.sin(angle);
      const y = cy - r * Math.cos(angle);

      result.push({
        x,
        y,
        r,
        angleDeg,
        raw: c
      });
    }

    return result;
  }

  render() {
    const ctx = this.ctx;
    const w = this.displayW;
    const h = this.displayH;
    const cx = this.cx;
    const cy = this.cy;
    const R = this.radius;

    this.sweepAngle = (this.sweepAngle + this.options.sweepSpeed) % 360;
    const sweepRad = (this.sweepAngle * Math.PI) / 180;
    const now = Date.now();

    ctx.clearRect(0, 0, w, h);

    // 1. Circular Scope Mask & Deep Tactical Glass
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.clip();

    const bgGrad = ctx.createRadialGradient(cx, cy, 4, cx, cy, R);
    bgGrad.addColorStop(0, 'rgba(4, 22, 28, 0.97)');
    bgGrad.addColorStop(0.7, 'rgba(2, 12, 16, 0.98)');
    bgGrad.addColorStop(1, 'rgba(1, 6, 8, 1.0)');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, w, h);

    // CRT Scanlines
    ctx.fillStyle = 'rgba(0, 255, 209, 0.025)';
    for (let y = 0; y < h; y += 4) {
      ctx.fillRect(0, y, w, 1);
    }

    // 2. Concentric Range Rings
    const ringFractions = [0.25, 0.5, 0.75, 1.0];
    ctx.strokeStyle = 'rgba(0, 255, 209, 0.18)';
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);

    ringFractions.forEach((frac) => {
      const r = R * frac;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();

      const labelNM = Math.round(this.rangeNM * frac);
      const lx = cx + r * 0.707 + 3;
      const ly = cy - r * 0.707 - 2;
      ctx.fillStyle = 'rgba(0, 255, 209, 0.5)';
      ctx.font = '8px monospace';
      ctx.fillText(labelNM + 'NM', lx, ly);
    });
    ctx.setLineDash([]);

    // 3. Crosshairs
    ctx.strokeStyle = 'rgba(0, 255, 209, 0.15)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(cx - R, cy);
    ctx.lineTo(cx + R, cy);
    ctx.moveTo(cx, cy - R);
    ctx.lineTo(cx, cy + R);
    ctx.stroke();

    // 4. Phosphor Sweep Trail (Persistence Glow)
    const trailSpanDeg = 48;
    for (let i = 0; i < trailSpanDeg; i += 2) {
      const alpha = ((trailSpanDeg - i) / trailSpanDeg) * 0.22;
      const a1 = ((this.sweepAngle - i - 2) * Math.PI) / 180;
      const a2 = ((this.sweepAngle - i) * Math.PI) / 180;
      ctx.fillStyle = `rgba(0, 255, 209, ${alpha})`;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, R, a1 - Math.PI / 2, a2 - Math.PI / 2);
      ctx.closePath();
      ctx.fill();
    }

    // 5. Leading Sweep Beam
    const sweepEndX = cx + R * Math.sin(sweepRad);
    const sweepEndY = cy - R * Math.cos(sweepRad);
    ctx.save();
    ctx.strokeStyle = '#00ffd1';
    ctx.lineWidth = 1.5;
    ctx.shadowColor = '#00ffd1';
    ctx.shadowBlur = 9;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(sweepEndX, sweepEndY);
    ctx.stroke();
    ctx.restore();

    // 6. Draw Pre-Projected Contacts in Current Window (Zero per-frame allocation)
    const contacts = this._projectedCache || [];
    for (let i = 0; i < contacts.length; i++) {
      const item = contacts[i];
      const c = item.raw;
      const id = c.id || c.icao24 || c.callsign || `contact-${i}`;

      // Calculate sweep ping
      const diffDeg = (this.sweepAngle - item.angleDeg + 360) % 360;
      if (diffDeg < 5) {
        this.pings.set(id, now);
      }

      const lastPing = this.pings.get(id) || 0;
      const ageMs = now - lastPing;
      const pingIntensity = Math.max(0.35, 1.0 - ageMs / 2500);

      const isHovered = this.hoveredContact && (this.hoveredContact.id === c.id);
      const isLocked = this.lockedContact && (this.lockedContact.id === c.id);

      const layer = c.layer || 'flights';
      const isMil = c.type === 'military' || layer === 'military';
      const isEmg = c.type === 'emergency' || c.squawk === '7700' || c.squawk === '7600';
      const isVessel = layer === 'vessels';
      const isSat = layer === 'satellites';
      const isNuclear = layer === 'nuclear';
      const isConflict = layer === 'conflicts' || layer === 'hotspots';

      // Base color by domain
      let col = isEmg ? `rgba(255, 51, 51, ${pingIntensity})` :
        isMil ? `rgba(255, 170, 0, ${pingIntensity})` :
          isVessel ? `rgba(16, 185, 129, ${pingIntensity})` :
            isSat ? `rgba(192, 132, 252, ${pingIntensity})` :
              isNuclear ? `rgba(250, 204, 21, ${pingIntensity})` :
                isConflict ? `rgba(244, 63, 94, ${pingIntensity})` :
                  `rgba(0, 255, 209, ${pingIntensity})`;

      if (isHovered || isLocked) {
        col = '#ffffff';
      }

      ctx.save();
      ctx.fillStyle = col;
      ctx.strokeStyle = col;

      // Draw blip shapes
      if (isMil) {
        // Military: diamond blip
        const s = isHovered ? 6 : 4;
        ctx.beginPath();
        ctx.moveTo(item.x, item.y - s);
        ctx.lineTo(item.x + s, item.y);
        ctx.lineTo(item.x, item.y + s);
        ctx.lineTo(item.x - s, item.y);
        ctx.closePath();
        ctx.fill();
      } else if (isVessel) {
        // Vessel: triangle chevron pointing up / heading
        const s = isHovered ? 5 : 3.5;
        const hRad = ((c.heading || 0) * Math.PI) / 180;
        ctx.save();
        ctx.translate(item.x, item.y);
        ctx.rotate(hRad);
        ctx.beginPath();
        ctx.moveTo(0, -s - 2);
        ctx.lineTo(s, s);
        ctx.lineTo(0, s - 1);
        ctx.lineTo(-s, s);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
      } else if (isSat) {
        // Satellite: crosshair blip
        const s = isHovered ? 4.5 : 3;
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(item.x - s, item.y);
        ctx.lineTo(item.x + s, item.y);
        ctx.moveTo(item.x, item.y - s);
        ctx.lineTo(item.x, item.y + s);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(item.x, item.y, 1.5, 0, Math.PI * 2);
        ctx.fill();
      } else if (isNuclear || isConflict) {
        // Tactical / Hazard: square blip
        const s = isHovered ? 4.5 : 3;
        ctx.fillRect(item.x - s / 2, item.y - s / 2, s, s);
      } else {
        // Commercial aircraft / standard blip: circle
        const rad = isHovered ? 4.5 : 2.5;
        ctx.beginPath();
        ctx.arc(item.x, item.y, rad, 0, Math.PI * 2);
        ctx.fill();
      }

      // Emergency flashing beacon
      if (isEmg) {
        ctx.strokeStyle = '#ff3333';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(item.x, item.y, 7 + Math.sin(now / 150) * 2, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Heading tick vector
      if (Number.isFinite(c.heading) && !isSat && !isNuclear) {
        const hRad = (c.heading * Math.PI) / 180;
        const tickLen = 6;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(item.x, item.y);
        ctx.lineTo(item.x + tickLen * Math.sin(hRad), item.y - tickLen * Math.cos(hRad));
        ctx.stroke();
      }

      // Target lock bracket
      if (isLocked) {
        ctx.strokeStyle = '#00ffd1';
        ctx.lineWidth = 1.5;
        const sz = 8;
        ctx.strokeRect(item.x - sz, item.y - sz, sz * 2, sz * 2);
      }

      // Contact callsign / name label
      if (isHovered || isLocked || pingIntensity > 0.6) {
        const label = (c.callsign || c.name || c.icao24 || '').trim();
        if (label) {
          ctx.fillStyle = isMil ? '#ffaa00' : isVessel ? '#10b981' : isSat ? '#c084fc' : '#00ffd1';
          ctx.font = 'bold 8px monospace';
          ctx.fillText(label, item.x + 6, item.y - 2);
        }
      }

      ctx.restore();
    }

    // 7. Center Origin Crosshair (Window Target Point)
    ctx.fillStyle = '#00ffd1';
    ctx.beginPath();
    ctx.arc(cx, cy, 3, 0, Math.PI * 2);
    ctx.fill();

    // Top status on scope
    ctx.font = '8px monospace';
    ctx.fillStyle = 'rgba(0, 255, 209, 0.75)';
    ctx.textAlign = 'center';
    ctx.fillText(`LIVE WINDOW • ${this.contacts.length} TARGETS`, cx, cy + 13);
    ctx.textAlign = 'left';

    ctx.restore(); // Exit clip

    // 8. Outer Compass Bezel with Dynamic North Rotation
    ctx.strokeStyle = '#00ffd1';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.stroke();

    // Rotate compass dial by -this.headingDeg so North aligns to screen true North!
    const headingRad = (this.headingDeg * Math.PI) / 180;

    for (let deg = 0; deg < 360; deg += 30) {
      const dialRad = ((deg * Math.PI) / 180) - headingRad;
      const isCardinal = deg % 90 === 0;
      const tickLen = isCardinal ? 6 : 3;

      const x1 = cx + R * Math.sin(dialRad);
      const y1 = cy - R * Math.cos(dialRad);
      const x2 = cx + (R + tickLen) * Math.sin(dialRad);
      const y2 = cy - (R + tickLen) * Math.cos(dialRad);

      ctx.strokeStyle = isCardinal ? '#00ffd1' : 'rgba(0, 255, 209, 0.35)';
      ctx.lineWidth = isCardinal ? 1.5 : 1;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();

      if (isCardinal) {
        const label = deg === 0 ? 'N' : deg === 90 ? 'E' : deg === 180 ? 'S' : 'W';
        const lx = cx + (R + 11) * Math.sin(dialRad);
        const ly = cy - (R + 11) * Math.cos(dialRad);
        ctx.fillStyle = deg === 0 ? '#ffaa00' : '#00ffd1';
        ctx.font = 'bold 9px monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(label, lx, ly);
      }
    }

    // Top screen view direction marker (amber notch at 12 o'clock)
    ctx.fillStyle = '#ffaa00';
    ctx.beginPath();
    ctx.moveTo(cx, cy - R - 1);
    ctx.lineTo(cx - 3, cy - R - 6);
    ctx.lineTo(cx + 3, cy - R - 6);
    ctx.closePath();
    ctx.fill();
  }
}
