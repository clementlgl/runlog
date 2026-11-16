import type { Routes, Run, Trophy } from '#lib/api.js';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
	const get = <T>(path: string) => fetch(path).then((r) => r.json() as Promise<T>);
	const [runs, routes, trophies] = await Promise.all([
		get<Run[]>('/api/runs?sport=running'),
		get<Routes>('/api/routes?points=120'),
		get<Trophy[]>('/api/trophies')
	]);
	return { runs, routes, trophies };
};
