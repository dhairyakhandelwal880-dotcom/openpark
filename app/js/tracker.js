// tracker.js — live vehicle marker. Needs MapLibre GL JS (global `maplibregl`).
// Usage:
//   const tracker = new VehicleTracker(map, { wsUrl: 'wss://your-host/ws', deviceId: 'car1' });
//   tracker.start();
import { GpsFilter } from './gps-filter.js';

const toNum = (v) => (v === undefined || v === null || v === '' ? NaN : Number(v));
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

export class VehicleTracker {
  constructor(map, opts = {}) {
    this.map = map;
    this.o = {
      wsUrl: opts.wsUrl ?? `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`,
      deviceId: opts.deviceId ?? null, // null = accept any device
      pingMs: 15000,
      staleMs: 10000, // "GPS signal lost" after this long without an accepted fix
      minBackoff: 1000,
      maxBackoff: 15000,
      follow: true,
      onStatus: null,
      onFix: null,
      ...opts,
    };
    this.filter = new GpsFilter(opts.filter);
    this.status = null;
    this.ws = null;
    this.attempt = 0;
    this.lastRx = 0;
    this.lastFixAt = 0;
    this.shown = null; // currently drawn {lat, lon, heading}
    this.anim = null;
    this.raf = 0;
    this.prevFixAt = 0;
    this.wake = null;
    this.stopped = true;
  }

  start() {
    if (!this.stopped) return;
    this.stopped = false;
    this.startedAt = Date.now();
    this._makeMarker();
    this._makeBanner();
    this.map.on('dragstart', () => (this.o.follow = false)); // user took over the camera
    this._onVis = () => {
      if (document.visibilityState !== 'visible') return;
      this._lockScreen();
      if (!this.ws) this._connect(true);
    };
    this._onOnline = () => !this.ws && this._connect(true);
    document.addEventListener('visibilitychange', this._onVis);
    window.addEventListener('online', this._onOnline);
    this.staleTimer = setInterval(() => this._emit(), 1000);
    this._lockScreen();
    this._connect();
    this._emit();
  }

  stop() {
    this.stopped = true;
    clearInterval(this.staleTimer);
    clearTimeout(this.retryTimer);
    this._stopPing();
    document.removeEventListener('visibilitychange', this._onVis);
    window.removeEventListener('online', this._onOnline);
    if (this.ws) { this._detach(this.ws); try { this.ws.close(); } catch {} this.ws = null; }
    if (this.wake) { this.wake.release().catch(() => {}); this.wake = null; }
    cancelAnimationFrame(this.raf);
    this.raf = 0;
    this.marker?.remove();
    this.banner?.remove();
  }

  recenter() {
    this.o.follow = true;
    if (this.shown) this.map.easeTo({ center: [this.shown.lon, this.shown.lat] }); // [lon, lat]
  }

  // ---------- WebSocket: reconnect with backoff + ping watchdog ----------
  _connect(immediate = false) {
    if (this.stopped) return;
    clearTimeout(this.retryTimer);
    if (immediate) this.attempt = 0;
    let ws;
    try { ws = new WebSocket(this.o.wsUrl); } catch { return this._scheduleReconnect(); }
    this.ws = ws;
    ws.onopen = () => {
      this.attempt = 0;
      this.lastRx = Date.now();
      this._startPing();
      this._emit();
    };
    ws.onmessage = (e) => {
      this.lastRx = Date.now();
      this._onMessage(e.data);
    };
    ws.onerror = () => { try { ws.close(); } catch {} };
    ws.onclose = () => { if (this.ws === ws) this._dropSocket(); };
    this._emit();
  }

  _detach(ws) { ws.onopen = ws.onmessage = ws.onerror = ws.onclose = null; }

  _dropSocket() {
    const ws = this.ws;
    this.ws = null;
    this._stopPing();
    if (ws) { this._detach(ws); try { ws.close(); } catch {} }
    this._scheduleReconnect();
    this._emit();
  }

  _scheduleReconnect() {
    if (this.stopped) return;
    const base = Math.min(this.o.maxBackoff, this.o.minBackoff * 2 ** this.attempt++);
    const delay = base / 2 + Math.random() * (base / 2); // jitter
    this.retryTimer = setTimeout(() => this._connect(), delay);
  }

  _startPing() {
    this._stopPing();
    this.pingTimer = setInterval(() => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
      // Nothing (not even a pong) for two ping periods => half-open socket, force a reconnect.
      if (Date.now() - this.lastRx > this.o.pingMs * 2) return this._dropSocket();
      this.ws.send(JSON.stringify({ type: 'ping', t: Date.now() }));
    }, this.o.pingMs);
  }
  _stopPing() { clearInterval(this.pingTimer); }

  // ---------- incoming data ----------
  _onMessage(raw) {
    let m;
    try { m = JSON.parse(raw); } catch { return; }
    if (!m || m.type === 'pong') return;
    const pos = (m.positions && m.positions[0]) || m.position || m;
    const id = pos.id ?? pos.deviceId ?? m.id ?? m.deviceId;
    if (this.o.deviceId && id !== undefined && String(id) !== String(this.o.deviceId)) return;

    let ts = toNum(pos.ts ?? pos.timestamp ?? pos.fixTime ?? pos.deviceTime ?? m.ts);
    if (!Number.isFinite(ts)) ts = Date.now();
    else if (ts < 1e12) ts *= 1000; // seconds -> ms

    const r = this.filter.update({
      lat: toNum(pos.lat ?? pos.latitude),
      lon: toNum(pos.lon ?? pos.lng ?? pos.longitude),
      ts,
      accuracy: toNum(pos.accuracy),
      speed: toNum(pos.speed), // m/s
      heading: toNum(pos.heading ?? pos.bearing ?? pos.course),
    });
    if (!r.ok) { console.debug('[tracker] rejected:', r.reason); return; }
    this.lastFixAt = Date.now(); // local clock on purpose: immune to device clock skew
    this._animateTo(r.fix);
    this._emit();
    this.o.onFix?.(r.fix);
  }

  // ---------- Screen Wake Lock ----------
  async _lockScreen() {
    if (!('wakeLock' in navigator) || document.visibilityState !== 'visible' || this.wake) return;
    try {
      this.wake = await navigator.wakeLock.request('screen'); // needs HTTPS or localhost
      this.wake.addEventListener('release', () => (this.wake = null)); // re-requested on next visibilitychange
    } catch (err) {
      console.warn('[tracker] wake lock unavailable:', err.name);
    }
  }

  // ---------- status / UI ----------
  _emit() {
    const gpsAge = Date.now() - (this.lastFixAt || this.startedAt);
    let s;
    if (gpsAge > this.o.staleMs) s = 'lost';
    else if (this.ws?.readyState === WebSocket.OPEN) s = 'live';
    else s = this.attempt > 0 ? 'reconnecting' : 'connecting';
    if (s === this.status) return;
    this.status = s;
    if (this.el) {
      this.el.style.opacity = s === 'lost' ? '0.45' : '1';
      this.el.style.filter = s === 'lost' ? 'grayscale(1)' : 'none';
    }
    if (this.banner) {
      this.banner.style.display = s === 'lost' ? 'block' : 'none';
    }
    this.o.onStatus?.(s);
  }

  _makeMarker() {
    this.el = document.createElement('div');
    this.el.className = 'op-vehicle-marker';
    this.el.innerHTML =
      '<svg width="36" height="36" viewBox="0 0 34 34"><circle cx="17" cy="17" r="15" fill="#fff" opacity=".85"/>' +
      '<path d="M17 4 L26 27 L17 22 L8 27 Z" fill="#1a73e8" stroke="#fff" stroke-width="1.5"/></svg>';
    this.el.style.transition = 'opacity .3s, filter .3s';
    this.marker = new maplibregl.Marker({ element: this.el, rotationAlignment: 'map', pitchAlignment: 'map' });
  }

  _makeBanner() {
    let existing = document.getElementById('gps-lost-banner');
    if (existing) {
      this.banner = existing;
      return;
    }
    this.banner = document.createElement('div');
    this.banner.id = 'gps-lost-banner';
    this.banner.textContent = 'GPS signal lost';
    Object.assign(this.banner.style, {
      position: 'fixed', top: '16px', left: '50%', transform: 'translateX(-50%)', zIndex: 1000,
      padding: '8px 16px', borderRadius: '999px', background: '#d93025', color: '#fff',
      font: '600 13px system-ui, -apple-system, sans-serif', display: 'none',
      boxShadow: '0 4px 12px rgba(0,0,0,0.4)', pointerEvents: 'none'
    });
    document.body.appendChild(this.banner);
  }

  // ---------- smooth interpolation (requestAnimationFrame) ----------
  _animateTo(fix) {
    const now = performance.now();
    const heading = fix.heading ?? this.shown?.heading ?? 0;
    if (!this.shown) {
      this.shown = { lat: fix.lat, lon: fix.lon, heading };
      this.marker.setLngLat([fix.lon, fix.lat]).setRotation(heading).addTo(this.map); // [lon, lat]
      this.map.jumpTo({ center: [fix.lon, fix.lat], zoom: Math.max(this.map.getZoom(), 16) });
      this.prevFixAt = now;
      return;
    }
    // Glide over roughly the time since the previous fix, so motion looks continuous.
    const dur = clamp(now - this.prevFixAt, 250, 2000);
    this.prevFixAt = now;
    this.anim = { from: { ...this.shown }, to: { lat: fix.lat, lon: fix.lon, heading }, start: now, dur };
    if (!this.raf) this.raf = requestAnimationFrame(this._tick);
  }

  _tick = (t) => {
    const a = this.anim;
    if (!a) { this.raf = 0; return; }
    const k = clamp((t - a.start) / a.dur, 0, 1);
    let dh = ((a.to.heading - a.from.heading + 540) % 360) - 180; // shortest arc
    this.shown = {
      lat: a.from.lat + (a.to.lat - a.from.lat) * k,
      lon: a.from.lon + (a.to.lon - a.from.lon) * k,
      heading: (a.from.heading + dh * k + 360) % 360,
    };
    this.marker.setLngLat([this.shown.lon, this.shown.lat]).setRotation(this.shown.heading);
    if (this.o.follow) this.map.jumpTo({ center: [this.shown.lon, this.shown.lat] });
    if (k < 1) this.raf = requestAnimationFrame(this._tick);
    else { this.anim = null; this.raf = 0; }
  };
}
