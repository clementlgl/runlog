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
