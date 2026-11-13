"""DuckDB connection and schema."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

import duckdb

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            BIGINT PRIMARY KEY,   -- start epoch (s), stable across exports
    start_utc     TIMESTAMP NOT NULL,
    utc_offset_s  INTEGER,
    sport         VARCHAR,
    sport_code    INTEGER,
    duration_s    INTEGER,
    distance_m    DOUBLE,
    active_kcal   INTEGER,
    total_kcal    INTEGER,
    avg_hr_bpm    INTEGER,
    max_hr_bpm    INTEGER,
    steps         INTEGER
);
CREATE TABLE IF NOT EXISTS samples (
    run_id         BIGINT NOT NULL,
    t_s            INTEGER NOT NULL,    -- seconds since run start
    epoch_s        BIGINT NOT NULL,
    heart_rate_bpm SMALLINT,
    distance_m     DOUBLE,
    steps          INTEGER,
    cadence_spm    SMALLINT,
    pace_s_per_km  INTEGER,
    speed_mps      DOUBLE
);
CREATE TABLE IF NOT EXISTS track (
    run_id   BIGINT NOT NULL,
    epoch_s  BIGINT NOT NULL,
    lat      DOUBLE NOT NULL,
    lon      DOUBLE NOT NULL
);
-- Derived per-run analysis (see analysis.py); recomputed from samples.
CREATE TABLE IF NOT EXISTS run_analysis (
    run_id        BIGINT PRIMARY KEY,
    workout_type  VARCHAR NOT NULL,   -- 'intervals' | 'continuous'
    label         VARCHAR,            -- e.g. '8 × 400 m'
    analysis      JSON NOT NULL
);
"""

_lock = threading.Lock()
_conn: duckdb.DuckDBPyConnection | None = None


def connection() -> duckdb.DuckDBPyConnection:
    """Process-wide connection; DuckDB allows one writer process per file."""
    global _conn
    with _lock:
        if _conn is None:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            _conn = duckdb.connect(str(DB_PATH))
            _conn.execute(SCHEMA)
        return _conn


@contextmanager
def cursor() -> Iterator[duckdb.DuckDBPyConnection]:
    cur = connection().cursor()
    try:
        yield cur
    finally:
        cur.close()
