from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BACKEND_DIR.parent / "data")).resolve()
DB_PATH = Path(os.environ.get("DB_PATH", DATA_DIR / "runs.duckdb")).resolve()
