from datetime import datetime

from app.trophies import compute


def run(id_: int, day: str, km: float) -> dict:
    return {"id": id_, "start_local": datetime.fromisoformat(day), "distance_m": km * 1000}


def by_id(runs: list[dict]) -> dict[str, dict]:
    return {t["id"]: t for t in compute(runs)}


def test_no_runs_locks_everything():
    ts = compute([])
    assert ts and all(not t["unlocked"] and t["progress_m"] == 0 for t in ts)


def test_distance_unlocked_by_first_qualifying_run():
    t = by_id([run(2, "2026-10-02T08:00", 10.2), run(1, "2026-10-01T08:00", 5.1)])
    assert t["distance-5k"]["run_id"] == 1
    assert t["distance-10k"]["run_id"] == 2
    assert t["distance-10k"]["unlocked_at"] == datetime(2026, 10, 2, 8)
    assert not t["distance-15k"]["unlocked"]
    assert t["distance-15k"]["progress_m"] == 10_200


def test_distance_tolerates_short_gps():
    assert by_id([run(1, "2026-10-01T08:00", 9.95)])["distance-10k"]["unlocked"]
    assert not by_id([run(1, "2026-10-01T08:00", 9.85)])["distance-10k"]["unlocked"]


def test_volume_unlocked_by_run_crossing_threshold():
    runs = [run(i, f"2026-{9 + i // 20:02d}-{1 + i % 20:02d}T08:00", 10) for i in range(12)]
    t = by_id(runs)
    assert t["volume-100k"]["run_id"] == 9  # 10th run reaches 100 km
    assert t["volume-100k"]["progress_m"] == 100_000
    assert t["volume-250k"]["progress_m"] == 120_000


def test_month_counts_each_calendar_month():
    runs = [run(i, f"2026-09-{i + 1:02d}T08:00", 20) for i in range(5)]  # 100 km in Sept
    runs += [run(10 + i, f"2026-10-{i + 1:02d}T08:00", 20) for i in range(4)]  # 80 km in Oct
    runs += [run(20, "2026-11-01T08:00", 20)]  # Oct + Nov never sum
    t = by_id(runs)["month-100k"]
    assert t["unlocked"] and t["run_id"] == 4 and t["times"] == 1
