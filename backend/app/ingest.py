"""Load mifit `workout_detail` JSON exports into DuckDB (idempotent upsert)."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from .config import DATA_DIR
from .db import cursor

_SAMPLE_SCHEMA = {
    "run_id": pl.Int64,
    "t_s": pl.Int32,
    "epoch_s": pl.Int64,
    "heart_rate_bpm": pl.Int16,
    "distance_m": pl.Float64,
    "steps": pl.Int32,
    "cadence_spm": pl.Int16,
    "pace_s_per_km": pl.Int32,
    "speed_mps": pl.Float64,
}
_TRACK_SCHEMA = {"run_id": pl.Int64, "epoch_s": pl.Int64, "lat": pl.Float64, "lon": pl.Float64}


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text())["records"]


def ingest(data_dir: Path = DATA_DIR) -> dict:
    """Read every ``workout_detail*.json`` in ``data_dir`` and upsert runs."""
    workouts: dict[int, dict] = {}
    for path in sorted(data_dir.glob("workout_detail*.json")):
        for rec in _load(path):
            w = rec["workout"]
            if w.get("start_epoch_s") is None:
                continue
            workouts[w["start_epoch_s"]] = rec  # later files win

    if not workouts:
        return {"runs": 0, "samples": 0, "track_points": 0}

    runs, samples, track = [], [], []
    for run_id, rec in workouts.items():
        w = rec["workout"]
        runs.append(
            {
                "id": run_id,
                "start_epoch_s": run_id,
                "utc_offset_s": w.get("utc_offset_s"),
                "sport": w.get("sport"),
                "sport_code": w.get("source_sport_code"),
                "duration_s": w.get("duration_s"),
                "distance_m": w.get("distance_m"),
                "active_kcal": w.get("active_kcal"),
                "total_kcal": w.get("total_kcal"),
                "avg_hr_bpm": w.get("avg_hr_bpm"),
                "max_hr_bpm": w.get("max_hr_bpm"),
                "steps": w.get("steps"),
            }
        )
        for s in rec.get("samples") or []:
            samples.append(
                {
                    "run_id": run_id,
                    "t_s": s["epoch_s"] - run_id,
                    "epoch_s": s["epoch_s"],
                    "heart_rate_bpm": s.get("heart_rate_bpm"),
                    "distance_m": s.get("distance_m"),
                    "steps": s.get("steps"),
                    "cadence_spm": s.get("cadence_spm"),
                    "pace_s_per_km": s.get("pace_s_per_km"),
                    "speed_mps": s.get("speed_mps"),
                }
            )
        for p in rec.get("track") or []:
            track.append(
                {"run_id": run_id, "epoch_s": p["epoch_s"], "lat": p["latitude_deg"], "lon": p["longitude_deg"]}
            )

    runs_df = pl.DataFrame(runs)  # noqa: F841 — referenced by name in SQL
    samples_df = pl.DataFrame(samples, schema=_SAMPLE_SCHEMA)  # noqa: F841
    track_df = pl.DataFrame(track, schema=_TRACK_SCHEMA)  # noqa: F841
    ids_df = pl.DataFrame({"id": list(workouts)})  # noqa: F841

    with cursor() as cur:
        cur.execute("BEGIN")
        for table, key in (("samples", "run_id"), ("track", "run_id"), ("runs", "id")):
            cur.execute(f"DELETE FROM {table} WHERE {key} IN (SELECT id FROM ids_df)")
        cur.execute(
            """
            INSERT INTO runs
            SELECT id, to_timestamp(start_epoch_s)::TIMESTAMP, utc_offset_s, sport, sport_code,
                   duration_s, distance_m, active_kcal, total_kcal, avg_hr_bpm, max_hr_bpm, steps
            FROM runs_df
            """
        )
        cur.execute("INSERT INTO samples SELECT * FROM samples_df")
        cur.execute("INSERT INTO track SELECT * FROM track_df")
        cur.execute("COMMIT")

    return {"runs": len(runs), "samples": len(samples), "track_points": len(track)}


if __name__ == "__main__":
    print(ingest())
