"""FastAPI app: runs, per-second samples and GPS tracks from DuckDB."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import date, timedelta

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.concurrency import run_in_threadpool

from .analysis import analyse_runs, ensure_analysed
from .db import cursor
from .ingest import ingest
from .login_job import LoginManager, session_info
from .sync_job import SyncManager
from .trophies import best_efforts
from .trophies import compute as compute_trophies


def _rows(sql: str, params: list | None = None) -> list[dict]:
    with cursor() as cur:
        res = cur.execute(sql, params or [])
        cols = [d[0] for d in res.description]
        return [dict(zip(cols, row, strict=True)) for row in res.fetchall()]


@asynccontextmanager
async def lifespan(_: FastAPI):
    with cursor() as cur:
        empty = cur.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
    if empty:
        await run_in_threadpool(ingest)
    await run_in_threadpool(ensure_analysed)
    yield


app = FastAPI(title="Runlog", lifespan=lifespan)
sync_manager = SyncManager()
login_manager = LoginManager()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


_RUN_SELECT = """
    SELECT id, a.workout_type, a.label AS workout_label, start_utc + to_seconds(coalesce(utc_offset_s, 0)) AS start_local,
           sport, duration_s, distance_m, avg_hr_bpm, max_hr_bpm, steps, total_kcal,
           CASE WHEN distance_m > 0 THEN round(duration_s / distance_m * 1000) END AS pace_s_per_km,
           CASE WHEN duration_s > 0 THEN round(steps * 60.0 / duration_s) END AS avg_cadence_spm
    FROM runs LEFT JOIN run_analysis a ON a.run_id = runs.id
"""


@app.get("/api/runs")
def list_runs(sport: str | None = None) -> list[dict]:
    return _rows(_RUN_SELECT + " WHERE ($1::VARCHAR IS NULL OR sport = $1) ORDER BY id DESC", [sport])


@app.get("/api/runs/{run_id}")
def get_run(run_id: int) -> dict:
    rows = _rows(_RUN_SELECT + " WHERE id = ?", [run_id])
    if not rows:
        raise HTTPException(404, "run not found")
    return rows[0]


@app.get("/api/runs/{run_id}/samples")
def run_samples(run_id: int) -> list[dict]:
    return _rows(
        """SELECT t_s, heart_rate_bpm, distance_m, steps, cadence_spm, pace_s_per_km
           FROM samples WHERE run_id = ? ORDER BY t_s""",
        [run_id],
    )


@app.get("/api/runs/{run_id}/track")
def run_track(run_id: int) -> list[list[float]]:
    """``[lon, lat, t_s]`` points; ``t_s`` aligns with ``/samples``."""
    with cursor() as cur:
        res = cur.execute("SELECT lon, lat, epoch_s - run_id FROM track WHERE run_id = ? ORDER BY epoch_s", [run_id])
        return [list(r) for r in res.fetchall()]


@app.get("/api/routes")
def route_shapes(points: int = Query(80, ge=10, le=500)) -> dict[str, list[list[float]]]:
    """Every run's GPS shape, thinned to about ``points`` ``[lon, lat]`` pairs (for glyphs)."""
    rows = _rows(
        """
        WITH t AS (
            SELECT run_id, lon, lat,
                   row_number() OVER (PARTITION BY run_id ORDER BY epoch_s) - 1 AS i,
                   count(*) OVER (PARTITION BY run_id) AS n
            FROM track
        )
        SELECT run_id, list([lon, lat] ORDER BY i) AS pts
        FROM t
        WHERE i % greatest(1, n // ?) = 0 OR i = n - 1
        GROUP BY run_id
        """,
        [points],
    )
    return {str(r["run_id"]): r["pts"] for r in rows}


@app.get("/api/runs/{run_id}/analysis")
def run_analysis(run_id: int) -> dict:
    """Workout type and, for interval sessions, warm-up / reps / recoveries / cool-down."""
    with cursor() as cur:
        row = cur.execute("SELECT analysis FROM run_analysis WHERE run_id = ?", [run_id]).fetchone()
    if row is None:
        raise HTTPException(404, "no analysis for this run")
    return json.loads(row[0])


@app.post("/api/analyse")
async def reanalyse() -> dict:
    """Recompute every run's analysis (after tuning the detection)."""
    return await run_in_threadpool(analyse_runs)


@app.get("/api/runs/{run_id}/splits")
def run_splits(run_id: int) -> list[dict]:
    """Per-kilometre splits; the last one is partial (its ``distance_m`` < 1000)."""
    return _rows(
        """
        WITH s AS (
            SELECT t_s, distance_m, heart_rate_bpm, cadence_spm,
                   floor(distance_m / 1000)::INT AS km
            FROM samples WHERE run_id = ? AND distance_m IS NOT NULL
        ), b AS (
            SELECT km, min(t_s) AS t0, max(t_s) AS t1,
                   min(distance_m) AS d0, max(distance_m) AS d1,
                   round(avg(heart_rate_bpm)) AS avg_hr_bpm,
                   round(avg(cadence_spm) FILTER (WHERE cadence_spm > 0)) AS avg_cadence_spm
            FROM s GROUP BY km
        )
        SELECT km + 1 AS km,
               t1 - coalesce(lag(t1) OVER (ORDER BY km), t0) AS duration_s,
               round(d1 - coalesce(lag(d1) OVER (ORDER BY km), d0)) AS distance_m,
               avg_hr_bpm, avg_cadence_spm
        FROM b ORDER BY km
        """,
        [run_id],
    )


@app.get("/api/stats/weekly")
def weekly_stats() -> list[dict]:
    return _rows(
        """
        SELECT date_trunc('week', start_utc)::DATE AS week,
               count(*) AS runs,
               round(sum(distance_m) / 1000, 2) AS distance_km,
               sum(duration_s) AS duration_s,
               round(avg(avg_hr_bpm)) AS avg_hr_bpm
        FROM runs WHERE sport = 'running'
        GROUP BY 1 ORDER BY 1
        """
    )


@app.get("/api/trophies")
def trophies() -> list[dict]:
    """Distance, volume and record trophies, unlocked or with their progress."""
    runs = _rows(
        """SELECT id, start_utc + to_seconds(coalesce(utc_offset_s, 0)) AS start_local, distance_m
           FROM runs WHERE sport = 'running'"""
    )
    # A run's samples never change once ingested: compute its best efforts once.
    missing = [r["id"] for r in runs if r["id"] not in _efforts_cache]
    if missing:
        with cursor() as cur:
            rows = cur.execute(
                """SELECT run_id, t_s, distance_m FROM samples
                   WHERE run_id IN (SELECT unnest(?::BIGINT[])) AND distance_m IS NOT NULL
                   ORDER BY run_id, t_s""",
                [missing],
            ).fetchall()
        by_run: dict[int, list[tuple[int, float]]] = {rid: [] for rid in missing}
        for rid, t_s, d in rows:
            by_run[rid].append((t_s, d))
        for rid, samples in by_run.items():
            _efforts_cache[rid] = best_efforts(samples)
    return compute_trophies(runs, _efforts_cache)


_efforts_cache: dict[int, dict[float, int]] = {}


@app.post("/api/ingest")
async def reingest() -> dict:
    return await run_in_threadpool(ingest)


MAX_SYNC_DAYS = 730


def sync_range(days: int | None, from_date: date | None, to_date: date | None) -> tuple[date, date]:
    """The inclusive day range to fetch: ``from_date``..``to_date`` (``to_date``
    defaults to today), or the last ``days`` days. Raises 422 on a bad range."""
    today = date.today()
    end = to_date or today
    if from_date is None:
        start = end - timedelta(days=days or 30)
    else:
        start = from_date
    if end > today:
        raise HTTPException(422, "La date de fin ne peut pas être dans le futur.")
    if start > end:
        raise HTTPException(422, "La date de début doit précéder la date de fin.")
    if (end - start).days > MAX_SYNC_DAYS:
        raise HTTPException(422, f"Plage trop longue : {MAX_SYNC_DAYS} jours au maximum.")
    return start, end


@app.get("/api/session")
def xiaomi_session() -> dict:
    """Is a Xiaomi session stored (and since when)? Never returns its secrets."""
    return session_info()


@app.post("/api/login", status_code=202)
def xiaomi_login(response: Response) -> dict:
    """Start a Xiaomi login: returns ``login_url`` to open and approve; poll
    ``GET /api/login``. 409 (with the current state) if one is already waiting."""
    state, started = login_manager.start()
    if not started:
        response.status_code = 409
    return state


@app.get("/api/login")
def xiaomi_login_state() -> dict | None:
    return login_manager.state()


@app.post("/api/sync", status_code=202)
def sync(
    response: Response,
    days: int | None = Query(None, ge=1, le=MAX_SYNC_DAYS),
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
) -> dict:
    """Start a background sync of a day range (``?from=&to=``, or ``?days=N``, default
    30): fetch from the Xiaomi cloud, add the runs not stored yet, analyse them.
    Returns the job state; poll ``GET /api/sync/current``. 409 if one is running."""
    start, end = sync_range(days, from_date, to_date)
    state, started = sync_manager.start(start, end)
    if not started:
        response.status_code = 409
    return state


@app.get("/api/sync/current")
def sync_current() -> dict | None:
    """State of the running sync, or of the last one (``null`` if none since startup)."""
    return sync_manager.current()
