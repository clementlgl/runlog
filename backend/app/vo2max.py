"""VO2max estimated from one run: pace and heart rate only (Runalyze's "effective VO2max").

The oxygen cost of the run's average speed (Jack Daniels' formula) is divided by
the share of VO2max it took, inferred from the average heart rate as a share of
HRmax. Only HRmax is needed (no resting HR, weight or age), but the estimate
assumes steady effort on flat ground: interval sessions, with their walked or
jogged recoveries, are left out, and hills or heat push it down.
"""

from __future__ import annotations

# Below this, a run is too short for the average heart rate to settle.
MIN_DURATION_S = 15 * 60
MIN_DISTANCE_M = 2_000


def oxygen_cost(speed_m_per_min: float) -> float:
    """ml/kg/min needed to run at this speed (Daniels & Gilbert)."""
    v = speed_m_per_min
    return -4.60 + 0.182258 * v + 0.000104 * v * v


def vo2max_share(hr: float, hr_max: float) -> float:
    """Share of VO2max used at ``hr`` (linear %HRmax to %VO2max relation)."""
    return (hr / hr_max - 0.2812) / 0.7213


def estimate(
    distance_m: float | None,
    duration_s: float | None,
    avg_hr_bpm: float | None,
    hr_max: float | None,
    workout_type: str | None = None,
) -> float | None:
    """Estimated VO2max (ml/kg/min, one decimal) of a run, or ``None`` when the
    run does not lend itself to it (intervals, too short, missing heart rate)."""
    if workout_type == "intervals" or not (distance_m and duration_s and avg_hr_bpm and hr_max):
        return None
    if duration_s < MIN_DURATION_S or distance_m < MIN_DISTANCE_M:
        return None
    share = vo2max_share(avg_hr_bpm, hr_max)
    if share <= 0.4:  # barely above rest: the relation no longer holds
        return None
    return round(oxygen_cost(distance_m / duration_s * 60) / share, 1)
