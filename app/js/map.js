// map.js — needs MapLibre GL JS (global `maplibregl`), e.g.
//   <link  href="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.css" rel="stylesheet">
//   <script src="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.js"></script>
//
// LON/LAT RULES (the usual source of "map shows the ocean" bugs):
//   MapLibre / GeoJSON ........ [lon, lat]
//   Overpass JSON ............. {lat, lon}
//   Overpass bbox filter ...... (south, west, north, east)  i.e. (minLat, minLon, maxLat, maxLon)

export const STYLE_LIGHT = 'https://tiles.openfreemap.org/styles/liberty';
// OpenFreeMap has no dark *Liberty*; its dark style is /styles/dark.
export const STYLE_DARK = 'https://tiles.openfreemap.org/styles/dark';

export const OVERPASS = [
  '/api/osm/overpass',
  'https://overpass-api.de/api/interpreter',
  'https://overpass.kumi.systems/api/interpreter',
];
export const MIN_OVERPASS_ZOOM = 14; // below this the bbox is too big to query politely

export function createMap(container, opts = {}) {
  const mq = window.matchMedia('(prefers-color-scheme: dark)');
  const map = new maplibregl.Map({
    container,
    style: mq.matches ? STYLE_DARK : STYLE_LIGHT,
    center: opts.center ?? [77.5946, 12.9716], // [lon, lat] — Bengaluru
    zoom: opts.zoom ?? 13,
    maxZoom: 19,
  });
  map.addControl(new maplibregl.NavigationControl(), 'top-right');
  setupOverlays(map);
  mq.addEventListener('change', (e) => setTheme(map, e.matches ? 'dark' : 'light'));
  return map;
}

/** Call this too if your app has its own theme toggle. Overlays are re-added on 'style.load'. */
export function setTheme(map, theme) {
  map.setStyle(theme === 'dark' ? STYLE_DARK : STYLE_LIGHT);
}

// ---------------------------------------------------------------- overlays
export function setupOverlays(map) {
  const empty = { type: 'FeatureCollection', features: [] };
  let data = { parking: empty, poi: empty };
  let abort = null;
  let timer = null;
  const cache = new Map();

  const addLayers = () => {
    if (map.getSource('op-parking')) return;
    map.addSource('op-parking', { type: 'geojson', data: data.parking });
    map.addSource('op-poi', { type: 'geojson', data: data.poi });
    map.addLayer({
      id: 'op-parking-fill',
      type: 'fill',
      source: 'op-parking',
      paint: { 'fill-color': '#2a7de1', 'fill-opacity': 0.25 }
    });
    map.addLayer({
      id: 'op-parking-line',
      type: 'line',
      source: 'op-parking',
      paint: { 'line-color': '#2a7de1', 'line-width': 1.5 }
    });
    map.addLayer({
      id: 'op-poi',
      type: 'circle',
      source: 'op-poi',
      paint: {
        'circle-radius': 7,
        'circle-color': ['match', ['get', 'kind'], 'fuel', '#f59e0b', 'toll', '#8b5cf6', '#888'],
        'circle-stroke-color': '#fff',
        'circle-stroke-width': 2,
      }
    });
  };
  map.on('style.load', addLayers); // fires on first load AND after every setStyle (theme switch)

  const setData = (d) => {
    data = d;
    map.getSource('op-parking')?.setData(d.parking);
    map.getSource('op-poi')?.setData(d.poi);
  };

  // Click popups. Built with textContent so OSM tag values can never inject HTML.
  const popup = (e, title, lines) => {
    const box = document.createElement('div');
    const h = document.createElement('strong');
    h.textContent = title;
    box.append(h);
    for (const l of lines.filter(Boolean)) {
      const p = document.createElement('div');
      p.textContent = l;
      box.append(p);
    }
    new maplibregl.Popup().setLngLat(e.lngLat).setDOMContent(box).addTo(map);
  };
  map.on('click', 'op-poi', (e) => {
    const p = e.features[0].properties;
    popup(e, p.name || (p.kind === 'fuel' ? 'Fuel station' : 'Toll'), [p.kind === 'fuel' ? 'Fuel' : 'Toll', p.operator]);
  });
  map.on('click', 'op-parking-fill', (e) => {
    const p = e.features[0].properties;
    popup(e, p.name || 'Parking', [p.parking && `Type: ${p.parking}`, p.capacity && `Capacity: ${p.capacity}`, p.fee && `Fee: ${p.fee}`]);
  });
  for (const id of ['op-poi', 'op-parking-fill']) {
    map.on('mouseenter', id, () => (map.getCanvas().style.cursor = 'pointer'));
    map.on('mouseleave', id, () => (map.getCanvas().style.cursor = ''));
  }

  async function refresh() {
    if (map.getZoom() < MIN_OVERPASS_ZOOM) return setData({ parking: empty, poi: empty });
    const b = map.getBounds();
    const snap = (v, f) => Math[f](v / 0.01) * 0.01; // snap outward to a 0.01° grid => cacheable
    const south = snap(b.getSouth(), 'floor'), west = snap(b.getWest(), 'floor');
    const north = snap(b.getNorth(), 'ceil'), east = snap(b.getEast(), 'ceil');
    const key = [south, west, north, east].map((n) => n.toFixed(2)).join(',');
    if (cache.has(key)) return setData(cache.get(key));

    abort?.abort();
    abort = new AbortController();
    const bbox = `${south},${west},${north},${east}`; // S,W,N,E

    // First try internal backend endpoint which caches Bengaluru OSM Overpass data
    try {
      const localRes = await fetch(`/api/osm/overpass?bbox=${west},${south},${east},${north}`, { signal: abort.signal });
      if (localRes.ok) {
        const localGeo = await localRes.json();
        const parking = [];
        const poi = [];
        for (const feat of localGeo.features || []) {
          const kind = feat.properties?.category || feat.properties?.amenity;
          if (kind === 'parking_outline' || kind === 'parking') {
            parking.push(feat);
          } else {
            poi.push({
              ...feat,
              properties: {
                ...feat.properties,
                kind: feat.properties?.category || (feat.properties?.amenity === 'fuel' ? 'fuel' : 'toll')
              }
            });
          }
        }
        const out = {
          parking: { type: 'FeatureCollection', features: parking },
          poi: { type: 'FeatureCollection', features: poi }
        };
        cache.set(key, out);
        return setData(out);
      }
    } catch (e) {
      if (e.name === 'AbortError') return;
    }

    const query = `[out:json][timeout:25];
(way["amenity"="parking"](${bbox});relation["amenity"="parking"](${bbox}););
out geom;
(nwr["amenity"="fuel"](${bbox});nwr["barrier"="toll_booth"](${bbox});nwr["highway"="toll_gantry"](${bbox}););
out center;`;

    for (const url of OVERPASS) {
      if (url.startsWith('/api/')) continue;
      try {
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: 'data=' + encodeURIComponent(query),
          signal: abort.signal,
        });
        if (!res.ok) throw new Error('Overpass HTTP ' + res.status);
        const out = toGeoJSON(await res.json());
        if (cache.size > 40) cache.delete(cache.keys().next().value);
        cache.set(key, out);
        return setData(out);
      } catch (err) {
        if (err.name === 'AbortError') return;
        console.warn('[map] Overpass failed, trying next endpoint:', err.message);
      }
    }
  }

  map.on('moveend', () => {
    clearTimeout(timer);
    timer = setTimeout(refresh, 500);
  });
  map.once('load', refresh);
}

// Overpass JSON -> GeoJSON ([lon, lat] everywhere)
export function toGeoJSON(json) {
  const parking = [];
  const poi = [];
  const closedRing = (geom) => {
    const ring = geom.map((g) => [g.lon, g.lat]);
    const a = ring[0], z = ring[ring.length - 1];
    return ring.length >= 4 && a[0] === z[0] && a[1] === z[1] ? ring : null;
  };
  for (const el of json.elements ?? []) {
    const t = el.tags ?? {};
    if (t.amenity === 'parking') {
      const props = { name: t.name, parking: t.parking, capacity: t.capacity, fee: t.fee };
      const rings = [];
      if (el.type === 'way' && el.geometry) rings.push(closedRing(el.geometry));
      if (el.type === 'relation')
        for (const m of el.members ?? []) if (m.role === 'outer' && m.geometry) rings.push(closedRing(m.geometry));
      for (const ring of rings.filter(Boolean))
        parking.push({ type: 'Feature', properties: props, geometry: { type: 'Polygon', coordinates: [ring] } });
      continue;
    }
    const kind = t.amenity === 'fuel' ? 'fuel' : t.barrier === 'toll_booth' || t.highway === 'toll_gantry' ? 'toll' : null;
    if (!kind) continue;
    const c = el.type === 'node' ? { lat: el.lat, lon: el.lon } : el.center;
    if (!c) continue;
    poi.push({
      type: 'Feature',
      properties: { kind, name: t.name ?? t.brand, operator: t.operator },
      geometry: { type: 'Point', coordinates: [c.lon, c.lat] },
    });
  }
  return {
    parking: { type: 'FeatureCollection', features: parking },
    poi: { type: 'FeatureCollection', features: poi },
  };
}
