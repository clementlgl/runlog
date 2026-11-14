"""Background sync job: fetch from the Xiaomi cloud, import new runs, analyse them.

One job at a time. It runs in a thread and publishes its state, which the API
returns for the UI to poll:

    phase: fetch -> import -> analyse -> done   (or error)

Fetch progress comes from mifit's stderr ("chunk 3/12 ...: 2 record(s)"); a range
shorter than one chunk prints no chunk line, so its fetch progress is unknown.
"""

from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from .config import BACKEND_DIR, DATA_DIR

FETCH_TIMEOUT_S = 30 * 60
_CHUNK = re.compile(r"chunk (\d+)/(\d+) .*?: (\d+) record")
_PLAN = re.compile(r"export: (\d+) chunks")


@dataclass
class Step:
    status: str = "pending"  # pending | running | done | error
    done: int | None = None  # progress counter, when known
    total: int | None = None
    detail: str | None = None


@dataclass
class JobState:
    id: str
    start: str
    end: str
    status: str = "running"  # running | done | error
    phase: str = "fetch"  # fetch | import | analyse | done
    steps: dict[str, Step] = field(default_factory=lambda: {"fetch": Step(), "import": Step(), "analyse": Step()})
    records: int = 0  # workouts fetched so far
    result: dict | None = None
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def parse_progress(line: str) -> tuple[int | None, int | None, int]:
    """``(chunks done, chunks total, records in this line)`` from one mifit stderr line."""
    if m := _CHUNK.search(line):
        return int(m[1]), int(m[2]), int(m[3])
    if m := _PLAN.search(line):
        return 0, int(m[1]), 0
    return None, None, 0


def fetch_command(start: date, end: date, out: Path) -> list[str]:
    """mifit command (through the v7 patch). A ``.partial`` left by an interrupted
    fetch of the same range (e.g. a container restart) is resumed, not redone."""
    cmd = [
        sys.executable,
        "-I",
        str(BACKEND_DIR / "mifit_patch.py"),
        "export",
        "workout_detail",
        "--from",
        str(start),
        "--to",
        str(end),
        "--long",
        "--json",
        str(out),
    ]
    if Path(f"{out}.partial").exists():
        cmd.append("--resume")
    return cmd


def run_fetch(start: date, end: date, out: Path, on_line: Callable[[str], None]) -> None:
    """Run mifit, streaming its stderr lines to ``on_line``."""
    cmd = fetch_command(start, end, out)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    tail: list[str] = []
    deadline = time.time() + FETCH_TIMEOUT_S
    assert proc.stderr is not None
    for line in proc.stderr:
        tail = (tail + [line.rstrip()])[-5:]
        on_line(line)
        if time.time() > deadline:
            proc.kill()
            raise RuntimeError("la récupération a dépassé 30 minutes")
    if proc.wait() != 0:
        raise RuntimeError(f"mifit failed: {' | '.join(tail)[-500:]}")


class SyncManager:
    """Holds the current/last job; starts at most one at a time."""

    def __init__(
        self,
        fetch: Callable[[date, date, Path, Callable[[str], None]], None] = run_fetch,
        ingest: Callable[..., dict] | None = None,
        data_dir: Path = DATA_DIR,
    ) -> None:
        self._fetch = fetch
        self._ingest = ingest
        self._data_dir = data_dir
        self._lock = threading.Lock()
        self.job: JobState | None = None
        self._thread: threading.Thread | None = None

    def current(self) -> dict | None:
        with self._lock:
            return self.job.as_dict() if self.job else None

    def start(self, start: date, end: date) -> tuple[dict, bool]:
        """Start a job; returns ``(state, started)``: ``started`` is False when one is
        already running (its state is returned instead)."""
        with self._lock:
            if self.job and self.job.status == "running":
                return self.job.as_dict(), False
            self.job = JobState(id=uuid.uuid4().hex[:8], start=str(start), end=str(end))
            job = self.job
        self._thread = threading.Thread(target=self._run, args=(job, start, end), daemon=True)
        self._thread.start()
        return self.current() or {}, True

    def wait(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    # ---- job body -------------------------------------------------------------

    def _update(self, fn: Callable[[JobState], None]) -> None:
        with self._lock:
            assert self.job is not None
            fn(self.job)

    def _run(self, job: JobState, start: date, end: date) -> None:
        out = self._data_dir / f"workout_detail_{start}_{end}.json"
        step = "fetch"
        try:
            self._update(lambda j: setattr(j.steps["fetch"], "status", "running"))

            def on_line(line: str) -> None:
                done, total, records = parse_progress(line)

                def apply(j: JobState) -> None:
                    s = j.steps["fetch"]
                    if total is not None:
                        s.done, s.total = done, total
                    j.records += records
                    s.detail = f"{j.records} séance{'s' if j.records > 1 else ''} trouvée{'s' if j.records > 1 else ''}"

                self._update(apply)

            self._fetch(start, end, out, on_line)
            self._update(lambda j: _finish_step(j, "fetch"))

            step = "import"
            self._update(lambda j: _begin_step(j, "import"))

            def on_imported(new_runs: int) -> None:
                def apply(j: JobState) -> None:
                    s = j.steps["import"]
                    s.status, s.done = "done", new_runs
                    s.detail = f"{new_runs} nouvelle{'s' if new_runs > 1 else ''} sortie{'s' if new_runs > 1 else ''}"
                    j.phase = "analyse"
                    j.steps["analyse"].status = "running"
                    j.steps["analyse"].done, j.steps["analyse"].total = 0, new_runs

                self._update(apply)

            def on_analysed(done: int, total: int) -> None:
                def apply(j: JobState) -> None:
                    s = j.steps["analyse"]
                    s.done, s.total = done, total

                self._update(apply)

            ingest = self._ingest
            if ingest is None:
                from .ingest import ingest as ingest  # late import: avoids a cycle at startup
            result = ingest(self._data_dir, on_imported=on_imported, on_analysed=on_analysed)
            step = "analyse"

            def finish(j: JobState) -> None:
                if j.steps["import"].status != "done":  # nothing new: no analyse callback
                    _finish_step(j, "import")
                    j.steps["import"].detail = "aucune nouvelle sortie"
                    j.steps["import"].done = 0
                _finish_step(j, "analyse")
                j.result = {"file": out.name, **result}
                j.status, j.phase, j.finished_at = "done", "done", time.time()

            self._update(finish)
        except Exception as exc:  # surfaced to the UI, never raised in the thread
            message = str(exc)

            def fail(j: JobState) -> None:
                j.steps[step].status = "error"
                j.error = message
                j.status, j.finished_at = "error", time.time()

            self._update(fail)


def _begin_step(j: JobState, name: str) -> None:
    j.phase = name
    j.steps[name].status = "running"


def _finish_step(j: JobState, name: str) -> None:
    s = j.steps[name]
    s.status = "done"
    if s.total is not None:
        s.done = s.total
