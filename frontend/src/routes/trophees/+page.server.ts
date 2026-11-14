import type { Trophy } from '#lib/api.js';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
	const trophies = (await fetch('/api/trophies').then((r) => r.json())) as Trophy[];
	return { trophies };
};
