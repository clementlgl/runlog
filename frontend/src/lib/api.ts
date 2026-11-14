export type Run = {
	id: number;
	workout_type: 'intervals' | 'continuous' | null;
	workout_label: string | null;
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
	vo2_max_watch: number | null; // ml/kg/min, as the watch reported it after the run
	vo2max_est: number | null; // ml/kg/min, estimated from pace and HR (continuous runs only)
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

export type IntervalSegment = {
	kind: 'warmup' | 'work' | 'recovery' | 'cooldown';
	index: number;
	t0: number;
	t1: number;
	distance_m: number; // nominal for reps, GPS-measured otherwise
	gps_distance_m?: number;
	duration_s: number;
	pace_s_per_km: number | null;
	avg_hr_bpm: number | null;
	max_hr_bpm: number | null;
	min_hr_bpm: number | null;
	end_hr_bpm: number | null;
	avg_cadence_spm: number | null;
};

export type Analysis = {
	is_interval: boolean;
	label: string | null;
	segments: IntervalSegment[];
	summary: {
		reps?: number;
		work_distance_m?: number;
		work_duration_s?: number;
		rep_pace_mean_s_per_km?: number | null;
		rep_pace_best_s_per_km?: number | null;
		rep_pace_cv_pct?: number;
		fade_pct?: number | null;
		rep_hr_first_bpm?: number | null;
		rep_hr_last_bpm?: number | null;
		recovery_duration_mean_s?: number | null;
		recovery_hr_drop_mean_bpm?: number | null;
	};
};

export type TrophyTier = 'bronze' | 'argent' | 'or' | 'platine' | 'record';

export type Trophy = {
	id: string;
	family: 'distance' | 'volume' | 'month' | 'record' | 'chrono';
	tier: TrophyTier;
	title: string;
	description: string;
	target_m: number;
	progress_m: number; // best single run, total, or best month (capped at target once unlocked)
	unlocked: boolean;
	unlocked_at: string | null;
	run_id: number | null;
	times?: number; // 'month' only: months that reached the target
	time_s?: number | null; // 'record' / 'chrono': best time over target_m
	target_s?: number; // 'chrono' only: time to beat
	history?: { run_id: number; at: string; time_s: number }[]; // 'record' only, oldest first
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
const shortFmt = new Intl.DateTimeFormat('fr-FR', {
	weekday: 'short',
	day: 'numeric',
	month: 'short'
});
const timeFmt = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' });
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export const fmtDay = (iso: string) => cap(dayFmt.format(new Date(iso)));
export const fmtShortDay = (iso: string) => cap(shortFmt.format(new Date(iso)).replace(/\./g, ''));
export const fmtTime = (iso: string) => timeFmt.format(new Date(iso)).replace(':', ' h '); // non-breaking: "10 h 01" never splits
