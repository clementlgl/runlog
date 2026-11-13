"""Compute and store per-run analysis (workout type, interval segments)."""

from __future__ import annotations

import json

from .db import cursor
from .intervals import analyse

ANALYSIS_VERSION = 2  # bump to force recomputation after an algorithm change


def analyse_runs(run_ids: list[int] | None = None) -> dict:
    """(Re)analyse ``run_ids`` (all running sessions when ``None``)."""
    with cursor() as cur:
        if run_ids is None:
            run_ids = [r[0] for r in cur.execute("SELECT id FROM runs WHERE sport = 'running'").fetchall()]
        counts = {"intervals": 0, "continuous": 0}
        rows = []
        for run_id in run_ids:
            res = cur.execute(
                """SELECT t_s, distance_m, heart_rate_bpm, cadence_spm
                   FROM samples WHERE run_id = ? ORDER BY t_s""",
                [run_id],
            )
            cols = [c[0] for c in res.description]
            samples = [dict(zip(cols, r, strict=True)) for r in res.fetchall()]
            a = analyse(samples)
            kind = "intervals" if a.is_interval else "continuous"
            counts[kind] += 1
            payload = {"version": ANALYSIS_VERSION, **a.as_dict()}
            rows.append((run_id, kind, a.label, json.dumps(payload)))
        cur.execute("BEGIN")
        cur.executemany("INSERT OR REPLACE INTO run_analysis VALUES (?, ?, ?, ?)", rows)
        cur.execute("COMMIT")
    return counts


def ensure_analysed() -> None:
    """Analyse runs that have none, or whose analysis predates ``ANALYSIS_VERSION``."""
    with cursor() as cur:
        stale = [
            r[0]
            for r in cur.execute(
                """SELECT r.id FROM runs r LEFT JOIN run_analysis a ON a.run_id = r.id
                   WHERE r.sport = 'running'
                     AND (a.run_id IS NULL OR coalesce(a.analysis->>'version', '0')::INT < ?)""",
                [ANALYSIS_VERSION],
            ).fetchall()
        ]
    if stale:
        analyse_runs(stale)
