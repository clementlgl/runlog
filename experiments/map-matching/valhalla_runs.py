"""Prototype: snap the same runs with a local Valhalla (Meili map matching).

Usage: python valhalla_runs.py <out.json from match_runs> <out_valhalla.json>
Adds a "valhalla" geometry + stats to each run of the mappymatch output.
"""

import json
import sys
import time
import urllib.request

from match_runs import haversine, length

URL = "http://127.0.0.1:8002"
OPTIONS = {
    "costing": "pedestrian",
    "shape_match": "map_snap",
    # A point further than search_radius from any path is unmatched and splits the
    # route (30 m cut runs short); 50 m keeps every run whole
    "trace_options": {"gps_accuracy": 15, "search_radius": 50, "breakage_distance": 2000, "interpolation_distance": 10},
    "costing_options": {"pedestrian": {"use_tracks": 1, "walkway_factor": 1, "sidewalk_factor": 1}},
}


def post(endpoint: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{URL}/{endpoint}", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def decode6(s: str) -> list[tuple[float, float]]:
    """Valhalla polyline (precision 6) -> [(lon, lat)]."""
    coords, idx, lat, lon = [], 0, 0, 0
    while idx < len(s):
        for which in (0, 1):
            shift = result = 0
            while True:
                b = ord(s[idx]) - 63
                idx += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if which == 0:
                lat += delta
            else:
                lon += delta
        coords.append((lon / 1e6, lat / 1e6))
    return coords


def main():
    src, out = sys.argv[1:]
    runs = json.load(open(src))
    for run in runs:
        shape = [{"lat": p[1], "lon": p[0]} for p in run["raw"]]
        t0 = time.time()
        route = post("trace_route", {"shape": shape, **OPTIONS})
        # At a discontinuity Valhalla returns the rest as "alternates": each part
        # covers a range of the input points. Join them in order; a gap between two
        # parts (unmatchable points) is bridged with the raw GPS points.
        parts = sorted(
            [route] + route.get("alternates", []),
            key=lambda t: t["trip"]["locations"][0].get("original_index", 0),
        )
        geom: list[tuple[float, float]] = []
        prev_end = None
        for part in parts:
            locs = part["trip"]["locations"]
            start, end = locs[0].get("original_index", 0), locs[-1].get("original_index", 0)
            if prev_end is not None and start > prev_end + 1:
                geom.extend(run["raw"][prev_end + 1 : start])
            for leg in part["trip"]["legs"]:
                seg = decode6(leg["shape"])
                if geom and seg and haversine(geom[-1], seg[0]) < 1:
                    seg = seg[1:]
                geom.extend(seg)
            prev_end = end
        attrs = post("trace_attributes", {"shape": shape, **OPTIONS, "filters": {"attributes": ["matched.type", "matched.distance_from_trace_point"], "action": "include"}})
        mp = attrs.get("matched_points", [])
        matched = [m for m in mp if m.get("type") == "matched"]
        dists = sorted(m.get("distance_from_trace_point", 0) for m in matched)
        run["valhalla"] = geom
        run["stats"].update(
            {
                "valhalla_length_m": round(length(geom)),
                "valhalla_parts": len(parts),
                "valhalla_matched_pct": round(100 * len(matched) / max(1, len(mp)), 1),
                "valhalla_snap_median_m": round(dists[len(dists) // 2], 1) if dists else None,
                "valhalla_snap_p95_m": round(dists[int(len(dists) * 0.95)], 1) if dists else None,
                "valhalla_s": round(time.time() - t0, 2),
            }
        )
        s = run["stats"]
        print(s["date"], {k: s[k] for k in ("raw_gps_length_m", "matched_length_m", "valhalla_length_m", "valhalla_parts", "valhalla_matched_pct", "valhalla_snap_median_m", "valhalla_snap_p95_m", "valhalla_s")}, flush=True)
    json.dump(runs, open(out, "w"))


if __name__ == "__main__":
    main()
