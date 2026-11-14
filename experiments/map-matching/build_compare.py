"""Comparison map: raw GPS vs mappymatch vs Valhalla, one button per run.

Usage: python build_compare.py <out_valhalla.json> <compare.html>
The page embeds the tracks: it holds personal location data, keep it out of git.
"""

import json
import sys

PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Recalage GPS</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>body{margin:0;font:14px system-ui,sans-serif}#bar{padding:8px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
#map{height:calc(100vh - 64px)}button{padding:4px 10px;border:1px solid #999;border-radius:14px;background:#fff;cursor:pointer}
button.on{background:#16191b;color:#fff}.k{display:inline-block;width:18px;height:3px;vertical-align:middle;margin:0 4px}</style></head>
<body><div id="bar"></div><div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const DATA = __DATA__;
const map = L.map('map');
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, attribution: '© OpenStreetMap'}).addTo(map);
const bar = document.getElementById('bar');
const opts = {mm: false, vh: true};
let layers = [], cur = 0;
const ll = a => a.map(p => [p[1], p[0]]);
function show(i) {
  cur = i; layers.forEach(l => map.removeLayer(l)); layers = [];
  const r = DATA[i];
  layers.push(L.polyline(ll(r.raw), {color: '#d62728', weight: 3, opacity: .8}).addTo(map));
  if (opts.mm && r.matched) layers.push(L.polyline(ll(r.matched), {color: '#2f6fd6', weight: 4, opacity: .7}).addTo(map));
  if (opts.vh && r.valhalla) layers.push(L.polyline(ll(r.valhalla), {color: '#1a9850', weight: 4, opacity: .9}).addTo(map));
  map.fitBounds(layers[0].getBounds(), {padding: [20, 20]});
  [...bar.querySelectorAll('button')].forEach((b, j) => b.classList.toggle('on', i === j));
  const s = r.stats;
  info.textContent = `${s.date} : montre ${s.watch_distance_m} m, GPS ${s.raw_gps_length_m} m, mappymatch ${s.matched_length_m} m, Valhalla ${s.valhalla_length_m} m`;
}
DATA.forEach((r, i) => { const b = document.createElement('button'); b.textContent = r.stats.date; b.onclick = () => show(i); bar.appendChild(b); });
const legend = document.createElement('span');
legend.innerHTML = '<span class="k" style="background:#d62728"></span>GPS brut '
  + '<label><input type=checkbox id=mm> <span class="k" style="background:#2f6fd6"></span>mappymatch</label> '
  + '<label><input type=checkbox id=vh checked> <span class="k" style="background:#1a9850"></span>Valhalla</label>';
bar.appendChild(legend);
const info = document.createElement('div'); info.style.width = '100%'; bar.appendChild(info);
document.getElementById('mm').onchange = e => { opts.mm = e.target.checked; show(cur); };
document.getElementById('vh').onchange = e => { opts.vh = e.target.checked; show(cur); };
show(0);
</script></body></html>
"""

if __name__ == "__main__":
    src, out = sys.argv[1:]
    with open(out, "w") as f:
        f.write(PAGE.replace("__DATA__", json.dumps(json.load(open(src)))))
