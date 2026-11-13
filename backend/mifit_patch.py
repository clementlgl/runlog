"""Local patches for mifit 0.4.x, applied before running its CLI.

Adds the outdoor-run record file format v7 (sport format 22), which Mi Fitness
writes for our watch but mifit does not list yet. v7 uses the same field table
as v8 minus the two v8-only fields (verticalStrideRatio, verticalAmplitude),
which ``selected_fields`` already handles through each field's ``since``.
The validity flag length for v7 (6 bytes) is already in ``binary._RUN_VALIDITY``.

Usage:  python mifit_patch.py <mifit CLI args...>
"""

from __future__ import annotations

import sys

from mifit.fds.ids import RECORD
from mifit.fds.layouts import LAYOUTS, RUN_FIELDS, RUN_SEGMENT, RecordLayout

RUN_FORMAT = 22


def apply() -> None:
    LAYOUTS.setdefault((RUN_FORMAT, RECORD, 7), RecordLayout(RUN_FIELDS, RUN_SEGMENT))


if __name__ == "__main__":
    apply()
    from mifit.cli import main

    sys.exit(main(sys.argv[1:]))
