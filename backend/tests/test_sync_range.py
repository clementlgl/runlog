from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from app.main import MAX_SYNC_DAYS, sync_range


def test_default_is_last_30_days():
    start, end = sync_range(None, None, None)
    assert end == date.today() and (end - start).days == 30


def test_explicit_range():
    assert sync_range(None, date(2026, 9, 1), date(2026, 9, 30)) == (date(2026, 9, 1), date(2026, 9, 30))


@pytest.mark.parametrize(
    "frm,to",
    [
        (date(2026, 9, 30), date(2026, 9, 1)),  # reversed
        (None, date.today() + timedelta(days=1)),  # future
        (date.today() - timedelta(days=MAX_SYNC_DAYS + 1), date.today()),  # too long
    ],
)
def test_bad_ranges_are_rejected(frm, to):
    with pytest.raises(HTTPException) as e:
        sync_range(None, frm, to)
    assert e.value.status_code == 422
