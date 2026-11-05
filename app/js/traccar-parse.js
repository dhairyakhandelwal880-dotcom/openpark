// traccar-parse.js — turns whatever Traccar sends into one clean position message.
// Handles: OsmAnd-style GET query / form POST (Traccar Client app) and Traccar's JSON forwarding.
// Output uses {lat, lon}, speed in m/s, ts in ms.

export const KNOT = 0.514444; // Traccar/OsmAnd report speed in knots

const num = (v) => (v === undefined || v === null || v === '' ? NaN : Number(v));
const first = (...vals) => vals.find((v) => v !== undefined && v !== null && v !== '');

function parseTs(v) {
  if (v === undefined || v === null || v === '') return Date.now();
  const n = Number(v);
  if (Number.isFinite(n)) return n < 1e12 ? n * 1000 : n; // seconds -> ms
  const d = Date.parse(v);
  return Number.isFinite(d) ? d : Date.now();
}

export function parseTraccar(query = {}, body = {}) {
  const src = { ...query, ...(body && typeof body === 'object' ? body : {}) };
  const pos = src.position ?? src.location ?? {};
  const dev = src.device && typeof src.device === 'object' ? src.device : {};

  const lat = num(first(src.lat, src.latitude, pos.latitude, pos.lat));
  const lon = num(first(src.lon, src.lng, src.longitude, pos.longitude, pos.lon)); // lon, NOT lng/lat swapped
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
  if (lat === 0 && lon === 0) return null; // "null island" = no fix

  const speedKnots = num(first(src.speed, pos.speed));
  const heading = num(first(src.bearing, src.heading, src.course, pos.course));
  const accuracy = num(first(src.accuracy, pos.accuracy));

  return {
    type: 'position',
    id: String(
      first(src.id, src.deviceid, src.device_id, dev.uniqueId, dev.id, typeof src.device === 'string' ? src.device : undefined, 'unknown'),
    ),
    lat,
    lon,
    speed: Number.isFinite(speedKnots) ? speedKnots * KNOT : null,
    heading: Number.isFinite(heading) ? heading : null,
    accuracy: Number.isFinite(accuracy) ? accuracy : null,
    ts: parseTs(first(src.timestamp, src.time, pos.fixTime, pos.deviceTime)),
  };
}
