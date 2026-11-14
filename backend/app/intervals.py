"""Interval-session detection from per-second distance and cadence samples.

Pipeline (all durations in *active* seconds: watch pauses don't count):
1. Speed smoothed over 21 s (finds efforts) and over 5 s (places their edges).
2. Run/walk split: when cadence is clearly two-level (running ~170, walking ~105,
   threshold ``WALK_RUN_CADENCE``), running blocks come from cadence: crisp,
   GPS-free boundaries. Otherwise (jogged recoveries, no cadence) an Otsu
   threshold on speed splits fast/slow. Runs under ``MIN_SEG_S`` are merged away.
3. Inside each running block, the rep core is the stretch at rep pace (>= 90 % of
   the reference rep speed). A warm-up flowing into rep 1, or the jog into and out
   of each effort, stays outside it.
4. The session counts as intervals with >= ``MIN_REPS`` reps, recoveries of at
   least ``MIN_RECOVERY_S``, and a clear contrast between reps and recoveries in
   speed, or in cadence backed by a smaller speed gap.
5. All reps cover the same distance: the target is the cores' median distance,
   and each rep becomes the quickest window of that distance inside its running
   block (cadence path) or around it (speed path, ``equalise_reps``). The label
   and rep paces use the nominal distance (400 m, 500 m...), so GPS error doesn't
   skew one rep's pace against another.
"""

from __future__ import annotations

import statistics as st
from dataclasses import asdict, dataclass, field

SMOOTH_HALF_S = 10  # centred window = 21 s
EDGE_SMOOTH_HALF_S = 2  # 5 s window to place rep edges
MIN_SEG_S = 20  # shorter fast/slow runs are noise
MIN_REPS = 3
MIN_CONTRAST = 1.3  # median rep speed / median recovery speed
MIN_RECOVERY_S = 40  # shorter pauses are stops (traffic lights), not recoveries
REP_PACE_TOLERANCE = 0.9  # a rep holds >= 90 % of the reference rep speed
EDGE_REP_MIN_RATIO = 0.4  # first/last 'rep' shorter than 40 % of the median is warm-up/cool-down
MAX_REP_S = 20 * 60
PACE_GAP_S = 30  # dips below rep pace shorter than this stay inside the rep

# Cadence (steps/min): running ~160-180, walking ~95-115, and it switches within a
# second, without GPS noise.
CADENCE_HALF_S = 3  # rolling median over 7 s
WALK_RUN_CADENCE = 135  # below: walking, above: running
MIN_WALK_SHARE = 0.1  # walking must be >= 10 % of the session to use cadence segmentation
MIN_CADENCE_GAP = 35  # run and walk cadence levels at least this far apart
MIN_CADENCE_CONTRAST = 1.3  # rep cadence / recovery cadence (walked recoveries ~1.6)
MIN_CONTRAST_WITH_CADENCE = 1.15  # speed contrast still required alongside cadence

# Equal-distance realignment: every rep of a session covers the same distance.
MERGE_GAP_RATIO = 0.5  # a "recovery" under half the median one splits a single rep
FRAGMENT_RATIO = 0.6  # reps under 60 % of the median distance don't vote for the target
KEEP_SPEED_RATIO = 0.85  # a realigned window slower than 85 % of the median one isn't a rep
STANDARD_DISTANCES = (100, 150, 200, 250, 300, 400, 500, 600, 800, 1000, 1200, 1500, 1600, 2000, 3000)
SNAP_TOLERANCE = 0.1  # label snaps to a standard distance within ±10 %


@dataclass
class Segment:
    kind: str  # warmup | work | recovery | cooldown
    index: int  # 1-based within its kind (rep 1, rep 2...), 0 for warm-up/cool-down
    t0: int
    t1: int  # exclusive
    distance_m: float  # nominal for reps, GPS-measured otherwise
    gps_distance_m: float
    duration_s: int
    pace_s_per_km: float | None
    avg_hr_bpm: float | None
    max_hr_bpm: int | None
    min_hr_bpm: int | None
    end_hr_bpm: int | None
    avg_cadence_spm: float | None


@dataclass
class Analysis:
    is_interval: bool
    label: str | None = None
    segments: list[Segment] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "is_interval": self.is_interval,
            "label": self.label,
            "segments": [asdict(s) for s in self.segments],
            "summary": self.summary,
        }


# --------------------------------------------------------------------------- helpers


def _forward_fill(values: list[float | None]) -> list[float]:
    out, last = [], 0.0
    for v in values:
        last = v if v is not None else last
        out.append(last)
    return out


def smoothed_speed(t: list[int], d: list[float], half: int = SMOOTH_HALF_S) -> list[float]:
    n = len(d)
    out = []
    for i in range(n):
        a, b = max(0, i - half), min(n - 1, i + half)
        dt = t[b] - t[a]
        out.append((d[b] - d[a]) / dt if dt > 0 else 0.0)
    return out


def otsu(values: list[float], bins: int = 64) -> float:
    """Threshold maximising between-class variance."""
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return hi
    width = (hi - lo) / bins
    hist = [0] * bins
    for v in values:
        hist[min(bins - 1, int((v - lo) / width))] += 1
    total = len(values)
    sum_all = sum((lo + (i + 0.5) * width) * h for i, h in enumerate(hist))
    w0 = sum0 = 0.0
    best, best_t = -1.0, lo
    for i, h in enumerate(hist):
        w0 += h
        if w0 == 0 or w0 == total:
            continue
        sum0 += (lo + (i + 0.5) * width) * h
        m0, m1 = sum0 / w0, (sum_all - sum0) / (total - w0)
        var = w0 * (total - w0) * (m0 - m1) ** 2
        if var > best:
            best, best_t = var, lo + (i + 1) * width
    return best_t


def _runs(flags: list[bool]) -> list[list]:
    """[[flag, start, end_exclusive], ...]"""
    runs: list[list] = []
    for i, f in enumerate(flags):
        if runs and runs[-1][0] == f:
            runs[-1][2] = i + 1
        else:
            runs.append([f, i, i + 1])
    return runs


def _merge_short(runs: list[list], min_len: int) -> list[list]:
    """Absorb the shortest run below ``min_len`` into its neighbours until none is left."""
    runs = [r[:] for r in runs]
    while len(runs) > 1:
        k = min(range(len(runs)), key=lambda j: runs[j][2] - runs[j][1])
        if runs[k][2] - runs[k][1] >= min_len:
            break
        if k == 0:
            runs[1][1] = runs[0][1]
            del runs[0]
        elif k == len(runs) - 1:
            runs[-2][2] = runs[-1][2]
            del runs[-1]
        else:  # flip it: it joins both neighbours (same flag)
            runs[k - 1][2] = runs[k + 1][2]
            del runs[k : k + 2]
    return runs


def smoothed_cadence(cad: list[int | None]) -> list[float | None]:
    """Rolling median over ``CADENCE_HALF_S`` each side; 0 counts as missing."""
    out: list[float | None] = []
    for i in range(len(cad)):
        w = [c for c in cad[max(0, i - CADENCE_HALF_S) : i + CADENCE_HALF_S + 1] if c]
        out.append(st.median(w) if w else None)
    return out


def cadence_walk_threshold(cad_s: list[float | None]) -> float | None:
    """``WALK_RUN_CADENCE`` when the session clearly has both walking and running,
    else ``None``.

    Needs enough cadence data, a walking share of at least ``MIN_WALK_SHARE``, and
    walking and running levels at least ``MIN_CADENCE_GAP`` apart. The threshold is
    physiological rather than fitted: a fitted one drifted into the walking cluster.
    """
    vals = [c for c in cad_s if c]
    if len(vals) < 0.5 * len(cad_s) or len(vals) < 120:
        return None
    low = [c for c in vals if c < WALK_RUN_CADENCE]
    high = [c for c in vals if c >= WALK_RUN_CADENCE]
    if len(low) < MIN_WALK_SHARE * len(vals) or not high:
        return None
    if st.median(high) - st.median(low) < MIN_CADENCE_GAP:
        return None
    return WALK_RUN_CADENCE


def _median_present(xs: list[float | None], spans: list[tuple[int, int]]) -> float | None:
    vals = [x for a, b in spans for x in xs[a:b] if x]
    return st.median(vals) if vals else None


def _fastest_window(
    t: list[int],
    d: list[float],
    lo: int,
    hi: int,
    dist: float,
) -> tuple[int, int] | None:
    """Indices ``(i, j)`` in ``[lo, hi)`` with ``d[j] - d[i] >= dist`` and the least
    ``t[j] - t[i]``: the quickest ``dist`` metres in that range (two pointers, O(n)).
    """
    best: tuple[int, int] | None = None
    j = lo
    for i in range(lo, hi):
        j = max(j, i)
        while j < hi and d[j] - d[i] < dist:
            j += 1
        if j >= hi:
            break
        if best is None or t[j] - t[i] < t[best[1]] - t[best[0]]:
            best = (i, j)
    return best


def _reps_from_speed(
    v: list[float], fast: list[list], seg_speed, v_edge: list[float] | None = None
) -> list[tuple[int, int]]:
    """Reps from speed alone (no usable cadence, or jogged recoveries).

    ``v`` (heavily smoothed) finds the reps; ``v_edge`` (lightly smoothed) then
    places their edges, since heavy smoothing pulls a sharp start/stop inwards.
    """
    # Rep pace reference: the faster half of the fast segments, so warm-up jogs
    # broken up by walking breaks don't drag it down.
    speeds = sorted(seg_speed(a, b) for _, a, b in fast)
    ref = st.median(speeds[len(speeds) // 2 :])

    # Inside each fast segment, the rep spans from the first to the last stretch at
    # rep pace (dips shorter than PACE_GAP_S ignored). A slower lead-in (warm-up
    # flowing into rep 1) or tail (cool-down) is left out; a fast segment never at
    # rep pace (warm-up jog between walking breaks) is not a rep.
    at_pace = [x >= REP_PACE_TOLERANCE * ref for x in v]
    reps: list[tuple[int, int]] = []
    for _, a, b in fast:
        sub = [r for r in _merge_short(_runs(at_pace[a:b]), PACE_GAP_S) if r[0]]
        if not sub:
            continue
        # Gap tolerance fills dips inside a rep, not its edges: trim to the first
        # and last samples really at pace.
        lo, hi = a + sub[0][1], a + sub[-1][2]
        while lo < hi and not at_pace[lo]:
            lo += 1
        while hi > lo and not at_pace[hi - 1]:
            hi -= 1
        if v_edge is not None:
            edge_thr = REP_PACE_TOLERANCE * ref
            while lo > a and v_edge[lo - 1] >= edge_thr:
                lo -= 1
            while hi < b and v_edge[hi] >= edge_thr:
                hi += 1
        if hi - lo >= MIN_SEG_S:
            reps.append((lo, hi))
    # A short first/last fragment is the tail of the warm-up or the start of the cool-down.
    while len(reps) > MIN_REPS:
        med = st.median(b - a for a, b in reps)
        if reps[0][1] - reps[0][0] < EDGE_REP_MIN_RATIO * med:
            reps.pop(0)
        elif reps[-1][1] - reps[-1][0] < EDGE_REP_MIN_RATIO * med:
            reps.pop()
        else:
            break
    return reps


def reps_from_cadence(
    t: list[int], d: list[float], v: list[float], runs: list[list], seg_speed, v_edge: list[float]
) -> tuple[list[tuple[int, int]], float]:
    """Reps for walked recoveries: one rep per cadence running block.

    A running block (between two walks) also holds the jog into and out of the
    effort, so it is the *search region*, not the rep: the rep core is found by
    speed inside it, the target distance is the cores' median, and each rep is the
    quickest window of that distance inside its block. Reps can't contain walking.

    Returns the rep spans and the target (measured) distance.
    """
    blocks = [(a, b) for f, a, b in runs if f]
    if len(blocks) < MIN_REPS:
        return [], 0.0
    gaps = [t[blocks[k + 1][0]] - t[blocks[k][1] - 1] for k in range(len(blocks) - 1)]
    med_gap = st.median(gaps)
    merged = [blocks[0]]
    for k, gap in enumerate(gaps):
        if gap < MERGE_GAP_RATIO * med_gap:  # a short walk splitting one rep
            merged[-1] = (merged[-1][0], blocks[k + 1][1])
        else:
            merged.append(blocks[k + 1])

    cores = _reps_from_speed(v, [[True, a, b] for a, b in merged], seg_speed, v_edge)
    if len(cores) < MIN_REPS:
        return [], 0.0
    dist = lambda a, b: d[b - 1] - d[a]  # noqa: E731
    med = st.median(dist(a, b) for a, b in cores)
    target = st.median(x for x in (dist(a, b) for a, b in cores) if x >= FRAGMENT_RATIO * med)

    windows: list[tuple[int, int]] = []
    for a, b in cores:
        ba, bb = next((x for x in merged if x[0] <= a and b <= x[1]), (a, b))
        w = _fastest_window(t, d, ba, bb, target)
        windows.append((w[0], w[1] + 1) if w else (ba, bb))
    # A window clearly slower than the others is a warm-up/cool-down block, not a rep.
    speed = lambda a, b: dist(a, b) / max(1, t[b - 1] - t[a])  # noqa: E731
    med_speed = st.median(speed(a, b) for a, b in windows)
    reps = [w for w in windows if speed(*w) >= KEEP_SPEED_RATIO * med_speed]
    return reps, target


def equalise_reps(
    t: list[int],
    d: list[float],
    reps: list[tuple[int, int]],
) -> tuple[list[tuple[int, int]], float]:
    """Realign ``reps`` (``[a, b)`` index spans) so they all cover the same distance.

    1. Merge reps split by a pause much shorter than the usual recovery.
    2. Target distance = median distance of the full-length reps.
    3. Each rep becomes the quickest window of exactly that distance between the
       previous and the next rep (it may reach into the recoveries around it).
    4. Windows clearly slower than the others are dropped; overlapping ones dedupe.

    Returns the new spans and the target distance (metres, as measured by the watch).
    """
    if len(reps) < 2:
        return reps, 0.0
    dist = lambda a, b: d[b - 1] - d[a]  # noqa: E731

    gaps = [t[reps[k + 1][0]] - t[reps[k][1] - 1] for k in range(len(reps) - 1)]
    med_gap = st.median(gaps)
    merged = [reps[0]]
    for k, gap in enumerate(gaps):
        if gap < MERGE_GAP_RATIO * med_gap:
            merged[-1] = (merged[-1][0], reps[k + 1][1])
        else:
            merged.append(reps[k + 1])

    med = st.median(dist(a, b) for a, b in merged)
    full = [dist(a, b) for a, b in merged if dist(a, b) >= FRAGMENT_RATIO * med]
    target = st.median(full)

    windows: list[tuple[int, int]] = []
    for k, (a, b) in enumerate(merged):
        lo = merged[k - 1][1] if k else 0
        hi = merged[k + 1][0] if k + 1 < len(merged) else len(d)
        w = _fastest_window(t, d, lo, hi, target)
        windows.append((w[0], w[1] + 1) if w else (a, b))

    speed = lambda a, b: dist(a, b) / max(1, t[b - 1] - t[a])  # noqa: E731
    med_speed = st.median(speed(a, b) for a, b in windows)
    kept: list[tuple[int, int]] = []
    for w in sorted(windows):
        if speed(*w) < KEEP_SPEED_RATIO * med_speed:
            continue
        if kept and w[0] < kept[-1][1]:  # overlap: keep the quicker one
            if speed(*w) > speed(*kept[-1]):
                kept[-1] = w
            continue
        kept.append(w)
    return kept, target


def nominal_distance(measured: float) -> int:
    """Label distance: the nearest standard distance within ±10 %, else rounded."""
    best = min(STANDARD_DISTANCES, key=lambda s: abs(s - measured))
    if abs(best - measured) <= SNAP_TOLERANCE * best:
        return best
    return _round_distance(measured)


def _round_distance(m: float) -> int:
    step = 50 if m < 1000 else 100
    return int(round(m / step) * step)


# --------------------------------------------------------------------------- main


def analyse(samples: list[dict]) -> Analysis:
    """``samples``: dicts with t_s, distance_m, heart_rate_bpm, cadence_spm, ordered by t_s."""
    if len(samples) < 5 * 60:
        return Analysis(False)
    t_wall = [s["t_s"] for s in samples]  # wall-clock offsets, for output only
    # Computations run on active time: one sample per second, so watch pauses
    # (gaps in t_s) don't count as slow running.
    t = list(range(len(samples)))
    d = _forward_fill([s.get("distance_m") for s in samples])
    hr = [s.get("heart_rate_bpm") for s in samples]
    cad = [s.get("cadence_spm") for s in samples]
    v = smoothed_speed(t, d)
    v_edge = smoothed_speed(t, d, EDGE_SMOOTH_HALF_S)

    moving = [x for x in v if x > 0.3]
    if len(moving) < 60:
        return Analysis(False)
    thr = otsu(moving)

    # Running vs walking from cadence when it is clearly two-level: crisp, GPS-free
    # boundaries. Otherwise (jogged recoveries, no cadence) fall back to speed.
    cad_s = smoothed_cadence(cad)
    walk_thr = cadence_walk_threshold(cad_s)
    if walk_thr is not None:
        running = [c is not None and c >= walk_thr for c in cad_s]
    else:
        running = [x > thr for x in v]
    runs = _merge_short(_runs(running), MIN_SEG_S)

    fast = [r for r in runs if r[0]]
    if len(fast) < MIN_REPS:
        return Analysis(False)

    def seg_speed(a: int, b: int) -> float:
        return (d[b - 1] - d[a]) / max(1, t[b - 1] - t[a])

    if walk_thr is not None:
        reps, target_m = reps_from_cadence(t, d, v, runs, seg_speed, v_edge)
    else:
        reps, target_m = _reps_from_speed(v, fast, seg_speed, v_edge), 0.0

    recs = [(reps[k][1], reps[k + 1][0]) for k in range(len(reps) - 1)]

    if len(reps) < MIN_REPS or not recs:
        return Analysis(False)
    rep_v = st.median(seg_speed(a, b) for a, b in reps)
    rec_v = st.median(seg_speed(a, b) for a, b in recs)
    rep_dur = st.median(t[b - 1] - t[a] for a, b in reps)
    rec_dur = st.median(t[b - 1] - t[a] for a, b in recs)
    # Contrast evidence: speed, or cadence (run vs walk) backed by a smaller speed gap.
    speed_ratio = rep_v / rec_v if rec_v > 0 else float("inf")
    rep_c = _median_present(cad_s, reps)
    rec_c = _median_present(cad_s, recs)
    cad_ratio = rep_c / rec_c if rep_c and rec_c else 1.0
    contrast = speed_ratio >= MIN_CONTRAST or (
        cad_ratio >= MIN_CADENCE_CONTRAST and speed_ratio >= MIN_CONTRAST_WITH_CADENCE
    )
    if not contrast or rep_dur > MAX_REP_S or rec_dur < MIN_RECOVERY_S:
        return Analysis(False)

    # It is an interval session. Without cadence, snap every rep to the same distance
    # (cadence blocks already give exact reps).
    if walk_thr is None:
        reps, target_m = equalise_reps(t, d, reps)
        if len(reps) < MIN_REPS:
            return Analysis(False)
        recs = [(reps[k][1], reps[k + 1][0]) for k in range(len(reps) - 1)]
    nominal_m = nominal_distance(target_m)

    def make(kind: str, idx: int, a: int, b: int) -> Segment:
        h = [x for x in hr[a:b] if x]
        c = [x for x in cad[a:b] if x]
        gps = d[b - 1] - d[a]
        # Reps all cover the nominal distance; GPS error would otherwise skew their pace.
        dist = float(nominal_m) if kind == "work" else gps
        dur = b - a  # active seconds
        return Segment(
            kind=kind,
            index=idx,
            t0=t_wall[a],
            t1=t_wall[b - 1] + 1,
            distance_m=round(dist, 1),
            gps_distance_m=round(gps, 1),
            duration_s=dur,
            pace_s_per_km=round(dur / dist * 1000, 1) if dist > 1 else None,
            avg_hr_bpm=round(st.mean(h), 1) if h else None,
            max_hr_bpm=max(h) if h else None,
            min_hr_bpm=min(h) if h else None,
            end_hr_bpm=next((x for x in reversed(hr[a:b]) if x), None),
            avg_cadence_spm=round(st.mean(c), 1) if c else None,
        )

    segments: list[Segment] = []
    if reps[0][0] > 0:
        segments.append(make("warmup", 0, 0, reps[0][0]))
    for k, (a, b) in enumerate(reps):
        segments.append(make("work", k + 1, a, b))
        if k < len(recs):
            segments.append(make("recovery", k + 1, *recs[k]))
    if reps[-1][1] < len(t):
        segments.append(make("cooldown", 0, reps[-1][1], len(t)))

    work = [s for s in segments if s.kind == "work"]
    rec = [s for s in segments if s.kind == "recovery"]
    dists = [s.distance_m for s in work]
    durs = [s.duration_s for s in work]
    paces = [s.pace_s_per_km for s in work if s.pace_s_per_km]

    # Reps are equal-distance by construction: label by the nominal distance.
    cv = lambda xs: st.pstdev(xs) / st.mean(xs) if len(xs) > 1 and st.mean(xs) else 0.0  # noqa: E731
    label = f"{len(work)} × {nominal_m} m"

    n2 = min(2, len(paces) // 2) or 1
    fade = (st.mean(paces[-n2:]) / st.mean(paces[:n2]) - 1) * 100 if paces else None
    rep_hr = [s.avg_hr_bpm for s in work if s.avg_hr_bpm]
    hr_drops = [
        work[k].end_hr_bpm - rec[k].min_hr_bpm for k in range(len(rec)) if work[k].end_hr_bpm and rec[k].min_hr_bpm
    ]
    summary = {
        "reps": len(work),
        "work_distance_m": round(sum(dists)),
        "work_duration_s": sum(durs),
        "rep_pace_mean_s_per_km": round(st.mean(paces), 1) if paces else None,
        "rep_pace_best_s_per_km": min(paces) if paces else None,
        "rep_pace_cv_pct": round(cv(paces) * 100, 1),
        "fade_pct": round(fade, 1) if fade is not None else None,  # > 0 = slower at the end
        "rep_hr_first_bpm": rep_hr[0] if rep_hr else None,
        "rep_hr_last_bpm": rep_hr[-1] if rep_hr else None,
        "recovery_duration_mean_s": round(st.mean(s.duration_s for s in rec)) if rec else None,
        "recovery_hr_drop_mean_bpm": round(st.mean(hr_drops), 1) if hr_drops else None,
        "speed_threshold_mps": round(thr, 2),
        "rep_target_m": round(target_m, 1),  # measured (watch) distance every rep is aligned to
        "rep_nominal_m": nominal_m,
        "segmentation": "cadence" if walk_thr is not None else "speed",
    }
    return Analysis(True, label, segments, summary)
