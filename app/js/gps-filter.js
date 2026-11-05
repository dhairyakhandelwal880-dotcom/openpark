// gps-filter.js — pure logic, no DOM. Coordinates are WGS84 degrees.
// Convention used everywhere in this project: internal objects use {lat, lon};
// anything handed to MapLibre / GeoJSON is [lon, lat].

const R = 6371000; // earth radius, metres
const rad = (d) => (d * Math.PI) / 180;

export function haversine(lat1, lon1, lat2, lon2) {
  const dLat = rad(lat2 - lat1);
  const dLon = rad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

export function bearing(lat1, lon1, lat2, lon2) {
  const y = Math.sin(rad(lon2 - lon1)) * Math.cos(rad(lat2));
  const x =
    Math.cos(rad(lat1)) * Math.sin(rad(lat2)) -
    Math.sin(rad(lat1)) * Math.cos(rad(lat2)) * Math.cos(rad(lon2 - lon1));
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

const finite = (v) => typeof v === 'number' && Number.isFinite(v);

export class GpsFilter {
  constructor(o = {}) {
    this.maxAccuracy = o.maxAccuracy ?? 40; // metres: reject worse fixes
    this.maxSpeed = o.maxSpeed ?? 70; // m/s (~250 km/h): faster implied = jump
    this.minJumpDist = o.minJumpDist ?? 25; // metres: smaller moves are jitter, never a "jump"
    this.alpha = o.alpha ?? 0.35; // EMA weight of the newest point (0..1)
    this.minHeadingSpeed = o.minHeadingSpeed ?? 1; // m/s: below this heading is noise
    this.maxConsecutiveJumps = o.maxConsecutiveJumps ?? 5; // then re-baseline
    this.requireAccuracy = o.requireAccuracy ?? false; // reject fixes with no accuracy field
    this.reset();
  }

  reset() {
    this.last = null; // last accepted RAW point
    this.smooth = null; // EMA state {lat, lon}
    this.heading = null;
    this.jumps = 0;
  }

  /** p = {lat, lon, ts (ms), accuracy?, speed? (m/s), heading? (deg)} */
  update(p) {
    if (!p || !finite(p.lat) || !finite(p.lon) || !finite(p.ts)) return { ok: false, reason: 'invalid' };
    if (Math.abs(p.lat) > 90 || Math.abs(p.lon) > 180) return { ok: false, reason: 'out-of-range (lat/lon swapped?)' };

    if (finite(p.accuracy)) {
      if (p.accuracy >= this.maxAccuracy) return { ok: false, reason: `accuracy ${p.accuracy}m` };
    } else if (this.requireAccuracy) {
      return { ok: false, reason: 'no accuracy' };
    }

    let dist = 0;
    let implied = 0;
    if (this.last) {
      if (p.ts <= this.last.ts) return { ok: false, reason: 'out-of-order' };
      const dt = (p.ts - this.last.ts) / 1000;
      dist = haversine(this.last.lat, this.last.lon, p.lat, p.lon);
      implied = dist / dt;
      if (dist > this.minJumpDist && implied > this.maxSpeed) {
        // Impossible jump. If it keeps happening, our baseline is probably the wrong one.
        if (++this.jumps < this.maxConsecutiveJumps) return { ok: false, reason: `jump ${Math.round(dist)}m` };
        this.smooth = null;
        this.heading = null;
      }
    }
    this.jumps = 0;

    // Exponential moving average on position.
    if (!this.smooth) this.smooth = { lat: p.lat, lon: p.lon };
    else {
      this.smooth.lat += this.alpha * (p.lat - this.smooth.lat);
      this.smooth.lon += this.alpha * (p.lon - this.smooth.lon);
    }

    // Speed: device value if present, otherwise derived.
    const speed = finite(p.speed) && p.speed >= 0 ? p.speed : implied;

    // Heading: only trusted above minHeadingSpeed, otherwise keep the last good one.
    if (speed > this.minHeadingSpeed) {
      if (finite(p.heading)) this.heading = ((p.heading % 360) + 360) % 360;
      else if (this.last && dist > 2) this.heading = bearing(this.last.lat, this.last.lon, p.lat, p.lon);
    }

    this.last = { lat: p.lat, lon: p.lon, ts: p.ts };
    return {
      ok: true,
      fix: {
        lat: this.smooth.lat,
        lon: this.smooth.lon,
        heading: this.heading,
        speed,
        accuracy: p.accuracy ?? null,
        ts: p.ts,
      },
    };
  }
}
