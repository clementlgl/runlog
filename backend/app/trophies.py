"""Trophies: distance on one run and cumulative volume, computed from the runs.

Nothing is stored: a trophy's unlock date is that of the run that earned it,
so re-ingesting or syncing older runs keeps the history consistent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# GPS distance of a run on a measured course often falls a little short.
SINGLE_RUN_TOLERANCE = 0.01


@dataclass(frozen=True)
class Def:
    id: str
    family: str  # 'distance' | 'volume' | 'month'
    tier: str  # 'bronze' | 'argent' | 'or' | 'platine'
    title: str
    description: str
    target_m: float


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
)


def compute(runs: list[dict]) -> list[dict]:
    """Every trophy's state from ``runs`` (``id``, ``start_local``, ``distance_m``).

    A trophy is unlocked by the first run, in date order, that meets it;
    ``progress_m`` is the best value reached so far towards ``target_m``.
    """
    runs = sorted(runs, key=lambda r: r["start_local"])
    best_run = 0.0
    total = 0.0
    month_totals: dict[str, float] = {}
    first_hit: dict[str, dict] = {}
    months_hit: set[str] = set()

    def hit(d: Def, run: dict) -> None:
        first_hit.setdefault(d.id, run)

    for run in runs:
        dist = run["distance_m"] or 0.0
        best_run = max(best_run, dist)
        total += dist
        month = _month(run["start_local"])
        month_totals[month] = month_totals.get(month, 0.0) + dist
        for d in DEFS:
            if d.family == "distance" and dist >= d.target_m * (1 - SINGLE_RUN_TOLERANCE):
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
    }
    out = []
    for d in DEFS:
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
        out.append(item)
    return out


def _month(start: datetime | str) -> str:
    return (start.isoformat() if isinstance(start, datetime) else start)[:7]
