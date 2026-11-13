from datetime import date

from app.sync_job import SyncManager, parse_progress


def test_parse_progress_lines():
    assert parse_progress("export: 7 chunks of up to 7 days, read one at a time.") == (0, 7, 0)
    assert parse_progress("chunk 2/7 2026-11-05..2026-11-11: 3 record(s)") == (2, 7, 3)
    assert parse_progress("something else") == (None, None, 0)


def fake_fetch(start, end, out, on_line):
    for line in ["export: 2 chunks of up to 7 days", "chunk 1/2 a..b: 2 record(s)", "chunk 2/2 c..d: 1 record(s)"]:
        on_line(line)


def fake_ingest(data_dir, on_imported=None, on_analysed=None):
    on_imported(2)
    on_analysed(1, 2)
    on_analysed(2, 2)
    return {"new_runs": 2, "already_stored": 20}


def test_job_goes_through_fetch_import_analyse(tmp_path):
    m = SyncManager(fetch=fake_fetch, ingest=fake_ingest, data_dir=tmp_path)
    state, started = m.start(date(2026, 11, 1), date(2026, 11, 13))
    assert started and state["status"] in ("running", "done")
    m.wait(5)
    s = m.current()
    assert s["status"] == "done" and s["phase"] == "done"
    assert s["steps"]["fetch"] == {"status": "done", "done": 2, "total": 2, "detail": "3 séances trouvées"}
    assert s["steps"]["import"]["done"] == 2
    assert s["steps"]["analyse"]["done"] == 2 and s["steps"]["analyse"]["status"] == "done"
    assert s["result"]["new_runs"] == 2


def test_nothing_new_still_finishes(tmp_path):
    m = SyncManager(fetch=fake_fetch, ingest=lambda *a, **k: {"new_runs": 0}, data_dir=tmp_path)
    m.start(date(2026, 11, 1), date(2026, 11, 13))
    m.wait(5)
    s = m.current()
    assert s["status"] == "done"
    assert s["steps"]["import"]["detail"] == "aucune nouvelle sortie"


def test_fetch_failure_is_reported_on_its_step(tmp_path):
    def boom(*_):
        raise RuntimeError("mifit failed: session expired")

    m = SyncManager(fetch=boom, ingest=fake_ingest, data_dir=tmp_path)
    m.start(date(2026, 11, 1), date(2026, 11, 13))
    m.wait(5)
    s = m.current()
    assert s["status"] == "error" and s["steps"]["fetch"]["status"] == "error"
    assert "session expired" in s["error"]


def test_only_one_job_at_a_time(tmp_path):
    import threading

    gate = threading.Event()

    def slow(start, end, out, on_line):
        gate.wait(5)

    m = SyncManager(fetch=slow, ingest=fake_ingest, data_dir=tmp_path)
    _, first = m.start(date(2026, 11, 1), date(2026, 11, 13))
    _, second = m.start(date(2026, 11, 1), date(2026, 11, 13))
    gate.set()
    m.wait(5)
    assert first and not second


def test_interrupted_fetch_is_resumed(tmp_path):
    from app.sync_job import fetch_command

    out = tmp_path / "workout_detail_2026-11-01_2026-11-13.json"
    assert "--resume" not in fetch_command(date(2026, 11, 1), date(2026, 11, 13), out)
    (tmp_path / "workout_detail_2026-11-01_2026-11-13.json.partial").write_text("{}")
    assert fetch_command(date(2026, 11, 1), date(2026, 11, 13), out)[-1] == "--resume"
