import importlib
from datetime import date

import pytest


@pytest.fixture
def main(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.duckdb"))
    import app.config
    import app.db
    import app.main

    for mod in (app.config, app.db, app.main):
        importlib.reload(mod)
    return app.main


def test_manual_validations(main):
    assert main.ladder_validations() == []
    main.validate_ladder_step(main.LadderValidation(step_key="8 × 400 m@285", day=date(2026, 11, 19), run_id=1))
    main.validate_ladder_step(main.LadderValidation(step_key="8 × 400 m@270", day=date(2026, 11, 26), run_id=2))
    main.validate_ladder_step(
        main.LadderValidation(step_key="8 × 400 m@285", day=date(2026, 11, 20), run_id=3)
    )  # re-dated
    assert main.ladder_validations() == [
        {"step_key": "8 × 400 m@285", "day": "2026-11-20", "run_id": 3},
        {"step_key": "8 × 400 m@270", "day": "2026-11-26", "run_id": 2},
    ]
    main.unvalidate_ladder_step("8 × 400 m@285")
    assert [v["step_key"] for v in main.ladder_validations()] == ["8 × 400 m@270"]
