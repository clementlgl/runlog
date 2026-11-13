"""Interval-session detection from per-second distance samples.

Pipeline:
1. Speed smoothed over a centred 20 s window (raw 1 Hz distance is too noisy).
2. Otsu threshold on that speed splits the run into fast / slow; runs shorter than
   ``MIN_SEG_S`` are merged into their neighbours (traffic lights, GPS jitter).
3. Fast segments are repetition candidates and slow segments between them are
   recoveries. Both work for walked recoveries (fast = running) and jogged ones
   (fast = reps, warm-up then sits in the first slow segment).
4. A warm-up that flows straight into rep 1 (no pause) shares its fast segment:
   it is split off where speed reaches the reps' pace. Same for a cool-down.
5. The session counts as intervals when it has >= ``MIN_REPS`` reps with a clear
   speed contrast to the recoveries.
6. All reps of a session cover the same distance: pieces of a rep split by a short
   slowdown are merged, then each rep is realigned to the quickest window of the
   session's target distance (``equalise_reps``). The label snaps that distance to
   a standard one (400 m, 500 m...).

Pure Python on purpose: a run is a few thousand points.
"""

from __future__ import annotations

import statistics as st
from dataclasses import asdict, dataclass, field

SMOOTH_HALF_S = 10  # centred window = 21 s
MIN_SEG_S = 20  # shorter fast/slow runs are noise
MIN_REPS = 3
MIN_CONTRAST = 1.3  # median rep speed / median recovery speed
MIN_RECOVERY_S = 40  # shorter pauses are stops (traffic lights), not recoveries
REP_PACE_TOLERANCE = 0.9  # a rep holds >= 90 % of the reference rep speed
EDGE_REP_MIN_RATIO = 0.4  # first/last 'rep' shorter than 40 % of the median is warm-up/cool-down
MAX_REP_S = 20 * 60
PACE_GAP_S = 30  # dips below rep pace shorter than this stay inside the rep

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
    distance_m: float
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


def smoothed_speed(t: list[int], d: list[float]) -> list[float]:
    n = len(d)
    out = []
    for i in range(n):
        a, b = max(0, i - SMOOTH_HALF_S), min(n - 1, i + SMOOTH_HALF_S)
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


def _fastest_window(t: list[int], d: list[float], lo: int, hi: int, dist: float) -> tuple[int, int] | None:
    """Indices ``(i, j)`` in ``[lo, hi)`` with ``d[j] - d[i] >= dist`` and the least
    ``t[j] - t[i]``: the quickest ``dist`` metres in that range (two pointers, O(n))."""
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


def equalise_reps(
    t: list[int], d: list[float], reps: list[tuple[int, int]]
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
    t = [s["t_s"] for s in samples]
    d = _forward_fill([s.get("distance_m") for s in samples])
    hr = [s.get("heart_rate_bpm") for s in samples]
    cad = [s.get("cadence_spm") for s in samples]
    v = smoothed_speed(t, d)

    moving = [x for x in v if x > 0.3]
    if len(moving) < 60:
        return Analysis(False)
    thr = otsu(moving)
    runs = _merge_short(_runs([x > thr for x in v]), MIN_SEG_S)

    fast = [r for r in runs if r[0]]
    if len(fast) < MIN_REPS:
        return Analysis(False)

    def seg_speed(a: int, b: int) -> float:
        return (d[b - 1] - d[a]) / max(1, t[b - 1] - t[a])

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
        if sub and sub[-1][2] - sub[0][1] >= MIN_SEG_S:
            reps.append((a + sub[0][1], a + sub[-1][2]))
    # A short first/last fragment is the tail of the warm-up or the start of the cool-down.
    while len(reps) > MIN_REPS:
        med = st.median(b - a for a, b in reps)
        if reps[0][1] - reps[0][0] < EDGE_REP_MIN_RATIO * med:
            reps.pop(0)
        elif reps[-1][1] - reps[-1][0] < EDGE_REP_MIN_RATIO * med:
            reps.pop()
        else:
            break
    recs = [(reps[k][1], reps[k + 1][0]) for k in range(len(reps) - 1)]

    if len(reps) < MIN_REPS or not recs:
        return Analysis(False)
    rep_v = st.median(seg_speed(a, b) for a, b in reps)
    rec_v = st.median(seg_speed(a, b) for a, b in recs)
    rep_dur = st.median(t[b - 1] - t[a] for a, b in reps)
    rec_dur = st.median(t[b - 1] - t[a] for a, b in recs)
    if rec_v <= 0 or rep_v / rec_v < MIN_CONTRAST or rep_dur > MAX_REP_S or rec_dur < MIN_RECOVERY_S:
        return Analysis(False)

    # It is an interval session: now snap every rep to the same distance.
    reps, target_m = equalise_reps(t, d, reps)
    if len(reps) < MIN_REPS:
        return Analysis(False)
    recs = [(reps[k][1], reps[k + 1][0]) for k in range(len(reps) - 1)]

    def make(kind: str, idx: int, a: int, b: int) -> Segment:
        h = [x for x in hr[a:b] if x]
        c = [x for x in cad[a:b] if x]
        dist = d[b - 1] - d[a]
        dur = t[b - 1] - t[a] + 1
        return Segment(
            kind=kind,
            index=idx,
            t0=t[a],
            t1=t[b - 1] + 1,
            distance_m=round(dist, 1),
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
    label = f"{len(work)} × {nominal_distance(target_m)} m"

    n2 = min(2, len(paces) // 2) or 1
    fade = (st.mean(paces[-n2:]) / st.mean(paces[:n2]) - 1) * 100 if paces else None
    rep_hr = [s.avg_hr_bpm for s in work if s.avg_hr_bpm]
    hr_drops = [
        work[k].end_hr_bpm - rec[k].min_hr_bpm
        for k in range(len(rec))
        if work[k].end_hr_bpm and rec[k].min_hr_bpm
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
        "rep_nominal_m": nominal_distance(target_m),
    }
    return Analysis(True, label, segments, summary)
