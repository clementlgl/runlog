import pytest

from app.vo2max import estimate, oxygen_cost, vo2max_share


def test_reference_values():
    # ACSM: 250 m/min (4:00/km) takes 3.5 + 0.2 * 250 = 53.5 ml/kg/min.
    assert oxygen_cost(250) == pytest.approx(53.5)
    assert vo2max_share(192, 192) == pytest.approx(1.0, abs=0.01)  # relation is fitted, not exact


def test_estimate_easy_run():
    # 10 km in 55:00 (181.8 m/min, uptake 39.86) at 150 bpm of 190 (share 0.705).
    assert estimate(10_000, 3300, 150, 190) == pytest.approx(56.6, abs=0.05)


def test_harder_effort_at_same_pace_lowers_estimate():
    assert estimate(10_000, 3300, 170, 190) < estimate(10_000, 3300, 150, 190)


@pytest.mark.parametrize(
    "args",
    [
        (10_000, 3300, 150, 190, "intervals"),  # recoveries skew the averages
        (1_500, 3300, 150, 190, None),  # too short
        (10_000, 600, 150, 190, None),  # too short
        (10_000, 3300, None, 190, None),  # no heart rate
        (10_000, 3300, 90, 190, None),  # near rest
    ],
)
def test_runs_left_out(args):
    assert estimate(*args) is None
