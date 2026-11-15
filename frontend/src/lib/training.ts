// Weekly plan: three runs, long on Monday, intervals on Thursday, steady (or a
// 5 km time trial on the month's first Saturday) on Saturday.

export type Session = 'long' | 'intervals' | 'steady' | 'test';

export const SESSION_LABEL: Record<Session, string> = {
	long: 'Sortie longue',
	intervals: 'Fractionné',
	steady: 'Sortie régulière',
	test: '5 km à fond'
};

export const RUNS_PER_WEEK = 3;

/** Planned session on a ``YYYY-MM-DD`` day, if any. */
export function plannedOn(day: string): Session | null {
	const d = new Date(day + 'T00:00:00Z');
	switch (d.getUTCDay()) {
		case 1:
			return 'long';
		case 4:
			return 'intervals';
		case 6:
			return d.getUTCDate() <= 7 ? 'test' : 'steady';
		default:
			return null;
	}
}

/** ``YYYY-MM-DD`` shifted by ``n`` days (calendar arithmetic, no time zone). */
export function addDays(day: string, n: number): string {
	const d = new Date(day + 'T00:00:00Z');
	d.setUTCDate(d.getUTCDate() + n);
	return d.toISOString().slice(0, 10);
}

/** Monday of the week holding ``day``. */
export function mondayOf(day: string): string {
	const dow = new Date(day + 'T00:00:00Z').getUTCDay();
	return addDays(day, -((dow + 6) % 7));
}

/** Today as ``YYYY-MM-DD`` in the viewer's time zone. */
export function today(): string {
	const d = new Date();
	return [d.getFullYear(), d.getMonth() + 1, d.getDate()]
		.map((n) => String(n).padStart(2, '0'))
		.join('-');
}

// Interval ladder: each Thursday session targets the next step of
// interval-ladder.json (e.g. 8 × 400 m at 4:45, then 4:30, then 4:15...). A step
// is validated by hand, and only with a qualifying session: detected reps that
// match it and a mean rep pace at or under the target (plus ``tolerance_s``).
// Every interval session counts, whatever the day; one session validates one
// step at most.

export type LadderConfig = {
	tolerance_s: number; // seconds per km over the target still accepted
	recovery: string; // ``m:ss`` jogged between reps
	steps: { reps: number; distance_m: number; paces: string[] }[];
};

export type LadderStep = {
	reps: number;
	distance_m: number;
	pace_s: number;
	label: string;
	key: string; // stable id for hand validations, e.g. '8 × 400 m@285'
};

/** A validated step, as stored (``/api/ladder/validations``). */
export type ManualValidation = { step_key: string; day: string; run_id: number };

type IntervalRun = {
	id: number;
	start_local: string;
	workout_label: string | null;
	rep_pace_s_per_km: number | null;
};

export type LadderProgress = {
	steps: LadderStep[];
	/** Session that validated each step, in step order (pace unknown if it's gone). */
	validated: { day: string; runId: number; pace_s: number | null }[];
	/** Index of the step to work on; ``steps.length`` once the ladder is done. */
	current: number;
	/** Earliest unused session that qualifies for the current step, if any. */
	candidate: { day: string; runId: number; pace_s: number } | null;
};

/** ``m:ss`` to seconds. */
export function parsePace(p: string): number {
	const [m, s] = p.split(':').map(Number);
	if (!Number.isFinite(m) || !Number.isFinite(s) || s >= 60) throw new Error(`bad pace: ${p}`);
	return m * 60 + s;
}

/** One step per (block, pace), in file order. */
export function expandLadder(cfg: LadderConfig): LadderStep[] {
	return cfg.steps.flatMap((b) =>
		b.paces.map((p) => {
			// Same format as the backend's interval label.
			const label = `${b.reps} × ${b.distance_m} m`;
			const pace_s = parsePace(p);
			return { reps: b.reps, distance_m: b.distance_m, pace_s, label, key: `${label}@${pace_s}` };
		})
	);
}

/** Does ``run`` meet ``step``'s target? */
export function qualifies(run: IntervalRun, step: LadderStep, tolerance_s: number): boolean {
	return (
		run.workout_label === step.label &&
		run.rep_pace_s_per_km != null &&
		run.rep_pace_s_per_km <= step.pace_s + tolerance_s
	);
}

export function ladderProgress(
	runs: IntervalRun[],
	cfg: LadderConfig,
	manual: ManualValidation[] = []
): LadderProgress {
	const steps = expandLadder(cfg);
	const byId = new Map(runs.map((r) => [r.id, r]));
	const validated: LadderProgress['validated'] = [];
	// Stored validations apply in order; one for another step than the current
	// (the file changed since) is ignored.
	for (const m of [...manual].sort((a, b) => a.day.localeCompare(b.day))) {
		const step = steps[validated.length];
		if (!step) break;
		if (m.step_key === step.key)
			validated.push({
				day: m.day,
				runId: m.run_id,
				pace_s: byId.get(m.run_id)?.rep_pace_s_per_km ?? null
			});
	}
	const step = steps[validated.length];
	const used = new Set(validated.map((v) => v.runId));
	const hit = step
		? runs
				.filter((r) => !used.has(r.id) && qualifies(r, step, cfg.tolerance_s))
				.sort((a, b) => a.start_local.localeCompare(b.start_local))[0]
		: undefined;
	return {
		steps,
		validated,
		current: validated.length,
		candidate: hit
			? { day: hit.start_local.slice(0, 10), runId: hit.id, pace_s: hit.rep_pace_s_per_km! }
			: null
	};
}

/**
 * Step expected on an upcoming interval ``day``: the current step on the next
 * interval day still to run, then one step further each week (the last step
 * repeats once the ladder is done). ``null`` for past days or other sessions.
 */
export function stepOn(day: string, todayKey: string, p: LadderProgress): LadderStep | null {
	if (day < todayKey || plannedOn(day) !== 'intervals' || !p.steps.length) return null;
	const done = new Set(p.validated.map((v) => v.day));
	if (done.has(day)) return null;
	let ahead = 0;
	for (let d = todayKey; d < day; d = addDays(d, 1))
		if (plannedOn(d) === 'intervals' && !done.has(d)) ahead++;
	return p.steps[Math.min(p.current + ahead, p.steps.length - 1)];
}
