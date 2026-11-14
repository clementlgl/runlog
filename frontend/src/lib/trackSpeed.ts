// Speed along the GPS track, from the per-second distance samples.

/** Slow to fast. Blue / yellow / red stays readable with the common colour-vision deficiencies. */
export const SPEED_COLORS = ['#2c7bb6', '#fdd94a', '#d7191c'] as const;

type DistSample = { t_s: number; distance_m: number | null };

/** Distance (m) at time ``t`` (s), interpolated between samples; clamped to the ends. */
function distanceAt(t: number[], d: number[], at: number): number {
	if (at <= t[0]) return d[0];
	if (at >= t[t.length - 1]) return d[d.length - 1];
	let lo = 0;
	let hi = t.length - 1;
	while (hi - lo > 1) {
		const mid = (lo + hi) >> 1;
		if (t[mid] <= at) lo = mid;
		else hi = mid;
	}
	return d[lo] + ((d[hi] - d[lo]) * (at - t[lo])) / (t[hi] - t[lo] || 1);
}

/**
 * Speed (m/s) at each of ``times``, averaged over ``±halfWindow`` seconds so GPS
 * jitter does not show as constant speed changes. ``null`` without distance data.
 */
export function speedsAt(
	samples: DistSample[],
	times: number[],
	halfWindow = 15
): (number | null)[] {
	const pts = samples.filter((s) => s.distance_m != null);
	if (pts.length < 2) return times.map(() => null);
	const t = pts.map((s) => s.t_s);
	const d = pts.map((s) => s.distance_m!);
	return times.map((at) => {
		const a = Math.max(t[0], at - halfWindow);
		const b = Math.min(t[t.length - 1], at + halfWindow);
		return b > a ? (distanceAt(t, d, b) - distanceAt(t, d, a)) / (b - a) : null;
	});
}

/** Colour scale bounds: 5th and 95th percentiles of moving speeds, so a stop or a
 * GPS spike does not flatten the rest of the run. */
export function speedRange(speeds: (number | null)[], minMoving = 0.5): [number, number] | null {
	const v = speeds.filter((s): s is number => s != null && s >= minMoving).sort((a, b) => a - b);
	if (v.length < 2) return null;
	const q = (p: number) => v[Math.min(v.length - 1, Math.floor(p * v.length))];
	const [lo, hi] = [q(0.05), q(0.95)];
	return hi > lo ? [lo, hi] : null;
}
