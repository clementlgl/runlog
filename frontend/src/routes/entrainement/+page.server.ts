import type { Run } from '#lib/api.js';
import type { ManualValidation } from '#lib/training.js';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
	const [runs, validations] = (await Promise.all([
		fetch('/api/runs?sport=running').then((r) => r.json()),
		fetch('/api/ladder/validations').then((r) => r.json())
	])) as [Run[], ManualValidation[]];
	return {
		runs,
		validations,
		// Highest HR recorded while running, as in the VO2max estimate.
		hrMax: Math.max(0, ...runs.map((r) => r.max_hr_bpm ?? 0))
	};
};
