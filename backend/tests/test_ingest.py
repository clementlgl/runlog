import importlib
import json

import pytest


def workout(start: int, distance_m: int, n: int = 600) -> dict:
    return {
        "workout": {
            "start_epoch_s": start,
            "utc_offset_s": 3600,
            "sport": "running",
            "source_sport_code": 1,
            "duration_s": n,
            "distance_m": distance_m,
            "avg_hr_bpm": 150,
            "max_hr_bpm": 170,
            "steps": 1500,
        },
        "samples": [
            {"epoch_s": start + i, "heart_rate_bpm": 150, "distance_m": i * 3.0, "steps": i * 3, "cadence_spm": 170}
            for i in range(n)
        ],
        "track": [{"epoch_s": start + i, "latitude_deg": 44.8, "longitude_deg": -0.6} for i in range(n)],
    }


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    """Fresh modules bound to a temporary data dir and DuckDB file."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.duckdb"))
    import app.analysis
    import app.config
    import app.db
    import app.ingest

    for mod in (app.config, app.db, app.analysis, app.ingest):
        importlib.reload(mod)
    yield tmp_path, app.ingest, app.db
    app.db._conn.close()
    app.db._conn = None


def write(path, records):
    path.write_text(json.dumps({"records": records}))


def counts(db):
    with db.cursor() as cur:
        return tuple(cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("runs", "samples", "track"))


def test_resync_same_data_adds_nothing(app_env):
    data, ingest, db = app_env
    write(data / "workout_detail_a.json", [workout(1000, 1800), workout(5000, 1800)])

    first = ingest.ingest(data)
    assert first["new_runs"] == 2
    before = counts(db)

    again = ingest.ingest(data)
    assert again["new_runs"] == 0 and again["already_stored"] == 2
    assert counts(db) == before


def test_stored_run_is_never_overwritten_and_new_one_is_added(app_env):
    data, ingest, db = app_env
    write(data / "workout_detail_a.json", [workout(1000, 1800)])
    ingest.ingest(data)

    # A later export holds the same run with other values, plus a new run.
    write(data / "workout_detail_b.json", [workout(1000, 9999), workout(9000, 2000)])
    res = ingest.ingest(data)

    assert res["new_runs"] == 1
    with db.cursor() as cur:
        assert cur.execute("SELECT distance_m FROM runs WHERE id = 1000").fetchone()[0] == 1800
        assert cur.execute("SELECT count(*) FROM runs").fetchone()[0] == 2
