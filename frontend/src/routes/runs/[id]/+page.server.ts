import { error } from '@sveltejs/kit';
import type { Analysis, Run, Sample, Split, TrackPoint } from '#lib/api.js';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, fetch }) => {
	const runRes = await fetch(`/api/runs/${params.id}`);
	if (!runRes.ok) error(runRes.status, 'Séance introuvable');
	const get = <T>(path: string) => fetch(path).then((r) => r.json() as Promise<T>);
	const [run, samples, track, splits, runs, analysis] = await Promise.all([
		runRes.json() as Promise<Run>,
		get<Sample[]>(`/api/runs/${params.id}/samples`),
		get<TrackPoint[]>(`/api/runs/${params.id}/track`),
		get<Split[]>(`/api/runs/${params.id}/splits`),
		get<Run[]>('/api/runs'),
		fetch(`/api/runs/${params.id}/analysis`).then((r) =>
			r.ok ? (r.json() as Promise<Analysis>) : null
		)
	]);
	// HRmax for zones: highest max HR recorded across all sessions.
	const hrMax = Math.max(...runs.map((r) => r.max_hr_bpm ?? 0));
	return { run, samples, track, splits, hrMax, analysis };
};
