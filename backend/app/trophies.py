"""Trophies: distance on one run, cumulative volume and personal records.

Nothing is stored: a trophy's unlock date is that of the run that earned it,
so re-ingesting or syncing older runs keeps the history consistent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .intervals import _fastest_window

# GPS distance of a run on a measured course often falls a little short.
SINGLE_RUN_TOLERANCE = 0.01


@dataclass(frozen=True)
class Def:
    id: str
    family: str  # 'distance' | 'volume' | 'month' | 'record' | 'chrono'
    tier: str  # 'bronze' | 'argent' | 'or' | 'platine' | 'record'
    title: str
    description: str
    target_m: float
    target_s: int | None = None  # 'chrono' only: time to beat over target_m


DEFS: tuple[Def, ...] = (
    Def("distance-5k", "distance", "bronze", "5 km", "Courir 5 km en une sortie.", 5_000),
    Def("distance-10k", "distance", "argent", "10 km", "Courir 10 km en une sortie.", 10_000),
    Def("distance-15k", "distance", "or", "15 km", "Courir 15 km en une sortie.", 15_000),
    Def("distance-semi", "distance", "or", "Semi-marathon", "Courir 21,1 km en une sortie.", 21_097.5),
    Def("distance-marathon", "distance", "platine", "Marathon", "Courir 42,2 km en une sortie.", 42_195),
    Def("volume-100k", "volume", "bronze", "100 km", "Cumuler 100 km de course.", 100_000),
    Def("volume-250k", "volume", "argent", "250 km", "Cumuler 250 km de course.", 250_000),
    Def("volume-500k", "volume", "or", "500 km", "Cumuler 500 km de course.", 500_000),
    Def("volume-1000k", "volume", "platine", "1 000 km", "Cumuler 1 000 km de course.", 1_000_000),
    Def("month-100k", "month", "or", "Mois à 100 km", "Courir 100 km dans le même mois.", 100_000),
    Def("record-1k", "record", "record", "Record 1 km", "Meilleur temps sur 1 km.", 1_000),
    Def("record-5k", "record", "record", "Record 5 km", "Meilleur temps sur 5 km.", 5_000),
    Def("record-10k", "record", "record", "Record 10 km", "Meilleur temps sur 10 km.", 10_000),
    Def("chrono-5k-25", "chrono", "bronze", "5 km en 25 min", "Courir 5 km en moins de 25 min.", 5_000, 25 * 60),
    Def("chrono-10k-50", "chrono", "argent", "10 km en 50 min", "Courir 10 km en moins de 50 min.", 10_000, 50 * 60),
    Def("chrono-1k-4", "chrono", "or", "1 km en 4 min", "Courir 1 km en moins de 4 min.", 1_000, 4 * 60),
)

EFFORT_DISTANCES = sorted({d.target_m for d in DEFS if d.family in ("record", "chrono")})


def best_efforts(samples: list[tuple[int, float]]) -> dict[float, int]:
    """Quickest time (s) over each of ``EFFORT_DISTANCES`` within one run,
    from its ``(t_s, distance_m)`` samples; distances never covered are left out."""
    pts = [(t, d) for t, d in samples if d is not None]
    t = [p[0] for p in pts]
    d = [p[1] for p in pts]
    out = {}
    for dist in EFFORT_DISTANCES:
        w = _fastest_window(t, d, 0, len(t), dist)
        if w is None:
            break  # longer distances are not covered either
        i, j = w
        # Trim the overshoot: d[j] - d[i] is >= dist, scale time to dist exactly.
        out[dist] = round((t[j] - t[i]) * dist / (d[j] - d[i]))
    return out


def compute(runs: list[dict], efforts: dict[int, dict[float, int]] | None = None) -> list[dict]:
    """Every trophy's state from ``runs`` (``id``, ``start_local``, ``distance_m``)
    and their ``best_efforts``, keyed by run id.

    A trophy is unlocked by the first run, in date order, that meets it;
    ``progress_m`` is the best value reached so far towards ``target_m``.
    A record is held by the latest run that beat it; ``history`` lists every
    time it was beaten, oldest first. ``time_s`` is the best time over ``target_m``.
    """
    efforts = efforts or {}
    runs = sorted(runs, key=lambda r: r["start_local"])
    best_run = 0.0
    total = 0.0
    month_totals: dict[str, float] = {}
    first_hit: dict[str, dict] = {}
    months_hit: set[str] = set()
    best_time: dict[float, int] = {}
    history: dict[float, list[dict]] = {dist: [] for dist in EFFORT_DISTANCES}

    def hit(d: Def, run: dict) -> None:
        first_hit.setdefault(d.id, run)

    for run in runs:
        dist = run["distance_m"] or 0.0
        best_run = max(best_run, dist)
        total += dist
        month = _month(run["start_local"])
        month_totals[month] = month_totals.get(month, 0.0) + dist
        for effort_m, secs in efforts.get(run["id"], {}).items():
            if effort_m in best_time and secs >= best_time[effort_m]:
                continue
            best_time[effort_m] = secs
            history[effort_m].append({"run_id": run["id"], "at": run["start_local"], "time_s": secs})
        for d in DEFS:
            if d.family == "chrono" and best_time.get(d.target_m, d.target_s + 1) <= d.target_s:
                hit(d, run)
            elif d.family == "distance" and dist >= d.target_m * (1 - SINGLE_RUN_TOLERANCE):
                hit(d, run)
            elif d.family == "volume" and total >= d.target_m:
                hit(d, run)
            elif d.family == "month" and month_totals[month] >= d.target_m:
                hit(d, run)
                months_hit.add(month)

    progress = {
        "distance": best_run,
        "volume": total,
        "month": max(month_totals.values(), default=0.0),
        "record": best_run,
        "chrono": best_run,
    }
    out = []
    for d in DEFS:
        if d.family == "record":
            past = history[d.target_m]
            run = {"id": past[-1]["run_id"], "start_local": past[-1]["at"]} if past else None
        else:
            run = first_hit.get(d.id)
        item = {
            "id": d.id,
            "family": d.family,
            "tier": d.tier,
            "title": d.title,
            "description": d.description,
            "target_m": d.target_m,
            "progress_m": round(min(progress[d.family], d.target_m) if run else progress[d.family], 1),
            "unlocked": run is not None,
            "unlocked_at": run["start_local"] if run else None,
            "run_id": run["id"] if run else None,
        }
        if d.family == "month":
            item["times"] = len(months_hit)
        if d.family in ("record", "chrono"):
            item["time_s"] = best_time.get(d.target_m)
        if d.family == "record":
            item["history"] = history[d.target_m]
        if d.family == "chrono":
            item["target_s"] = d.target_s
        out.append(item)
    return out


def _month(start: datetime | str) -> str:
    return (start.isoformat() if isinstance(start, datetime) else start)[:7]
