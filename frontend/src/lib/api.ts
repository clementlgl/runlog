export type Run = {
	id: number;
	start_local: string;
	sport: string | null;
	duration_s: number;
	distance_m: number;
	avg_hr_bpm: number | null;
	max_hr_bpm: number | null;
	steps: number | null;
	total_kcal: number | null;
	pace_s_per_km: number | null;
	avg_cadence_spm: number | null;
};

export type WeekStat = {
	week: string;
	runs: number;
	distance_km: number;
	duration_s: number;
	avg_hr_bpm: number | null;
};

export type Sample = {
	t_s: number;
	heart_rate_bpm: number | null;
	distance_m: number | null;
	steps: number | null;
	cadence_spm: number | null;
	pace_s_per_km: number | null;
};

export type TrackPoint = [lon: number, lat: number, t_s: number];
export type Routes = Record<string, [number, number][]>;

export type Split = {
	km: number;
	duration_s: number;
	distance_m: number;
	avg_hr_bpm: number | null;
	avg_cadence_spm: number | null;
};

const nf = (digits: number) =>
	new Intl.NumberFormat('fr-FR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
const nf1 = nf(1);
const nf2 = nf(2);

/** 5980 -> "5,98" */
export const fmtKm = (m: number, digits: 1 | 2 = 2) => (digits === 1 ? nf1 : nf2).format(m / 1000);

/** 2232 -> "37:12", 4195 -> "1:09:55" */
export const fmtDuration = (s: number) => {
	const h = Math.floor(s / 3600);
	const m = Math.floor((s % 3600) / 60);
	const sec = Math.round(s % 60);
	const mm = h ? String(m).padStart(2, '0') : String(m);
	return `${h ? `${h}:` : ''}${mm}:${String(sec).padStart(2, '0')}`;
};

/** 373 -> "6'13" */
export const fmtPace = (s: number | null | undefined) =>
	s ? `${Math.floor(s / 60)}'${String(Math.round(s % 60)).padStart(2, '0')}` : '–';

const dayFmt = new Intl.DateTimeFormat('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
const shortFmt = new Intl.DateTimeFormat('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' });
const timeFmt = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' });
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export const fmtDay = (iso: string) => cap(dayFmt.format(new Date(iso)));
export const fmtShortDay = (iso: string) => cap(shortFmt.format(new Date(iso)).replace(/\./g, ''));
export const fmtTime = (iso: string) => timeFmt.format(new Date(iso)).replace(':', ' h '); // non-breaking: "10 h 01" never splits
