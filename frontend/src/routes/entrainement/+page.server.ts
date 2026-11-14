import type { Run } from '#lib/api.js';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
	const runs = (await fetch('/api/runs?sport=running').then((r) => r.json())) as Run[];
	// Highest HR recorded while running, as in the VO2max estimate.
	return { hrMax: Math.max(0, ...runs.map((r) => r.max_hr_bpm ?? 0)) };
};
