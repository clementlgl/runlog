import math
import random

from app.intervals import analyse


def build(blocks: list[tuple[int, float]], seed: int = 0) -> list[dict]:
    """Samples from (duration_s, speed_mps) blocks, with GPS-like speed noise."""
    rng = random.Random(seed)
    out, t, d = [], 0, 0.0
    for dur, v in blocks:
        for _ in range(dur):
            d += max(0.0, v + rng.gauss(0, 0.25))
            out.append({"t_s": t, "distance_m": d, "heart_rate_bpm": 150, "cadence_spm": 170})
            t += 1
    return out


def test_steady_run_is_continuous():
    a = analyse(build([(2400, 3.0)]))
    assert not a.is_interval


def test_steady_run_with_traffic_light_stops_is_continuous():
    blocks = []
    for _ in range(6):
        blocks += [(360, 3.0), (25, 0.0)]
    assert not analyse(build(blocks)).is_interval


def test_walked_recoveries_warmup_flowing_into_first_rep():
    blocks = [(420, 2.9)]  # warm-up runs straight into rep 1
    for k in range(8):
        blocks.append((100, 4.0))
        if k < 7:
            blocks.append((90, 1.3))
    blocks.append((300, 2.6))
    a = analyse(build(blocks))
    assert a.is_interval
    assert a.summary["reps"] == 8
    assert a.label == "8 × 400 m"
    kinds = [s.kind for s in a.segments]
    assert kinds[0] == "warmup" and kinds[-1] == "cooldown"
    warmup = a.segments[0]
    assert math.isclose(warmup.duration_s, 420, abs_tol=25)


def test_jogged_recoveries():
    blocks = [(600, 2.8)]
    for _ in range(5):
        blocks += [(180, 4.2), (120, 2.6)]
    a = analyse(build(blocks, seed=3))
    assert a.is_interval
    assert a.summary["reps"] == 5
    assert a.label == "5 × 3'00" or a.label.startswith("5 × ")


def test_rep_split_by_a_short_slowdown_is_merged_and_reps_equalised():
    blocks = [(420, 2.8)]
    for k in range(6):
        if k == 2:  # rep 3 broken by a 25 s slowdown: two fast pieces
            blocks += [(50, 4.0), (25, 1.5), (50, 4.0)]
        else:
            blocks.append((100, 4.0))
        if k < 5:
            blocks.append((120, 1.3))
    blocks.append((240, 2.6))
    a = analyse(build(blocks, seed=7))
    assert a.is_interval
    work = [s for s in a.segments if s.kind == "work"]
    assert len(work) == 6
    dists = [s.distance_m for s in work]
    assert max(dists) - min(dists) <= 10
    assert a.label == "6 × 400 m"


def test_label_snaps_to_standard_distance():
    from app.intervals import nominal_distance

    assert nominal_distance(485) == 500
    assert nominal_distance(375) == 400
    assert nominal_distance(448) == 450  # 12 % from 400 and 500: no snap
