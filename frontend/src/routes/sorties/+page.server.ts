import type { Routes, Run, WeekStat } from '#lib/api.js';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
	const get = <T>(path: string) => fetch(path).then((r) => r.json() as Promise<T>);
	const [runs, weekly, routes] = await Promise.all([
		get<Run[]>('/api/runs?sport=running'),
		get<WeekStat[]>('/api/stats/weekly'),
		get<Routes>('/api/routes?points=120')
	]);
	return { runs, weekly, routes };
};
