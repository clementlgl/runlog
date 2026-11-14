"""Prototype: snap a few Runlog GPS tracks onto OSM paths with mappymatch (LCSS).

Usage: python match_runs.py <region.osm.pbf> <workout_detail_all.json> <out.json> <start_epoch> [...]
Writes raw + matched geometries and stats for the comparison map.
"""

import json
import math
import sys
import time

import pandas as pd
from mappymatch.constructs.trace import Trace
from mappymatch.matchers.lcss.lcss import LCSSMatcher
from osm_local import extract_xml, nx_map_from_xml
from pyproj import Transformer

TO_WGS84 = Transformer.from_crs(3857, 4326, always_xy=True)
STEP_S = 3  # one point every 3 s: plenty for 1 Hz running data, faster matching


def haversine(a, b):
    (lon1, lat1), (lon2, lat2) = a, b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def length(coords):
    return sum(haversine(coords[i], coords[i + 1]) for i in range(len(coords) - 1))


def main():
    pbf, src, out, *ids = sys.argv[1:]
    records = {r["workout"]["start_epoch_s"]: r for r in json.load(open(src))["records"]}
    results = []
    for rid in map(int, ids):
        rec = records[rid]
        pts = [(p["longitude_deg"], p["latitude_deg"]) for p in rec["track"]][::STEP_S]
        df = pd.DataFrame({"longitude": [p[0] for p in pts], "latitude": [p[1] for p in pts]})
        t0 = time.time()
        trace = Trace.from_dataframe(df, xy=True)
        pad = 0.005  # ~500 m around the run
        bbox = (min(p[0] for p in pts) - pad, min(p[1] for p in pts) - pad,
                max(p[0] for p in pts) + pad, max(p[1] for p in pts) + pad)
        xml = f"net_{rid}.osm"
        n_ways = extract_xml(pbf, bbox, xml)
        nx_map = nx_map_from_xml(xml)
        t_map = time.time() - t0
        result = LCSSMatcher(nx_map).match_trace(trace)
        t_match = time.time() - t0 - t_map

        # Matched path: the sequence of roads, back to WGS84.
        path = []
        for road in result.path or []:
            xs, ys = road.geom.xy
            seg = [TO_WGS84.transform(x, y) for x, y in zip(xs, ys)]
            if path and haversine(path[-1], seg[0]) > haversine(path[-1], seg[-1]):
                seg.reverse()
            path.extend(seg)
        matched = sum(1 for m in result.matches if m.road is not None)
        # Distance from the raw point to its matched road (how far the snap moved it).
        offsets = sorted(m.distance for m in result.matches if m.road is not None and m.distance is not None)

        stats = {
            "id": rid,
            "date": time.strftime("%d/%m", time.localtime(rid)),
            "watch_distance_m": rec["workout"]["distance_m"],
            "raw_gps_length_m": round(length(pts)),
            "matched_length_m": round(length(path)),
            "points": len(pts),
            "matched_pct": round(100 * matched / len(pts), 1),
            "snap_median_m": round(offsets[len(offsets) // 2], 1) if offsets else None,
            "snap_p95_m": round(offsets[int(len(offsets) * 0.95)], 1) if offsets else None,
            "osm_ways": n_ways,
            "osm_edges": nx_map.g.number_of_edges(),
            "map_s": round(t_map, 1),
            "match_s": round(t_match, 1),
        }
        print(stats, flush=True)
        results.append({"stats": stats, "raw": pts, "matched": path})
    json.dump(results, open(out, "w"))


if __name__ == "__main__":
    main()
