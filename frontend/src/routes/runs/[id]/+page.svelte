<script lang="ts">
	import { fmtDay, fmtDuration, fmtKm, fmtPace, fmtTime } from '#lib/api.js';
	import RunMap from '#lib/components/RunMap.svelte';
	import SeriesChart from '#lib/components/SeriesChart.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	const run = $derived(data.run);

	// --- per-second series, x = distance (km) ---
	const series = $derived.by(() => {
		const s = data.samples;
		const n = s.length;
		const t = s.map((p) => p.t_s);
		const d: number[] = [];
		let last = 0;
		for (const p of s) d.push((last = p.distance_m ?? last));
		const x = d.map((m) => m / 1000);
		const hr = s.map((p) => p.heart_rate_bpm);
		const cadence = s.map((p) => (p.cadence_spm ? p.cadence_spm : null));
		// Pace over a centred 30 s window: raw per-second pace is too noisy to read.
		const W = 15;
		const pace = s.map((_, i) => {
			const a = Math.max(0, i - W);
			const b = Math.min(n - 1, i + W);
			const dd = d[b] - d[a];
			if (dd < 5) return null;
			const v = ((t[b] - t[a]) / dd) * 1000;
			return v > 900 ? null : v; // slower than 15'/km = stopped / walking
		});
		return { x, hr, cadence, pace };
	});

	// --- HR zones (% of HRmax), ordinal: one hue, darker = harder ---
	const ZONES = [
		{ name: 'Récupération', lo: 0.5, alpha: 0.25 },
		{ name: 'Endurance', lo: 0.6, alpha: 0.42 },
		{ name: 'Tempo', lo: 0.7, alpha: 0.6 },
		{ name: 'Seuil', lo: 0.8, alpha: 0.8 },
		{ name: 'VO2max', lo: 0.9, alpha: 1 }
	];
	const zones = $derived.by(() => {
		const secs = ZONES.map(() => 0);
		for (const h of series.hr) {
			if (!h) continue;
			const r = h / data.hrMax;
			for (let z = ZONES.length - 1; z >= 0; z--)
				if (r >= ZONES[z].lo) {
					secs[z]++;
					break;
				}
		}
		const total = secs.reduce((a, b) => a + b, 0) || 1;
		const max = Math.max(...secs, 1);
		return ZONES.map((z, i) => ({
			...z,
			bpm: Math.round(z.lo * data.hrMax),
			s: secs[i],
			pct: Math.round((secs[i] / total) * 100),
			w: (secs[i] / max) * 100
		}));
	});

	// --- splits ---
	const splitRows = $derived.by(() => {
		const rows = data.splits.map((s) => ({
			...s,
			pace: s.distance_m > 0 ? (s.duration_s / s.distance_m) * 1000 : null
		}));
		const paces = rows.filter((r) => r.pace && r.distance_m >= 900).map((r) => r.pace!);
		const best = Math.min(...paces);
		const worst = Math.max(...paces);
		return rows.map((r, i) => ({
			...r,
			label:
				i === rows.length - 1 && r.distance_m < 995
					? fmtKm(r.distance_m)
					: String(r.km),
			best: r.pace === best,
			// bar = speed relative to the slowest full split, so faster = longer
			w: r.pace ? 35 + 65 * ((worst - r.pace) / Math.max(1, worst - best)) : 0
		}));
	});

	// --- chart hover -> map marker ---
	const trackByT = $derived(new Map(data.track.map((p) => [p[2], [p[0], p[1]] as [number, number]])));
	const coords = $derived(data.track.map((p) => [p[0], p[1]] as [number, number]));
	let hoverIdx = $state<number | null>(null);
	const cursor = $derived.by(() => {
		if (hoverIdx == null) return null;
		const t = data.samples[hoverIdx]?.t_s;
		for (let k = 0; k < 5; k++) {
			const p = trackByT.get(t - k) ?? trackByT.get(t + k);
			if (p) return p;
		}
		return null;
	});
	const hover = (i: number | null) => (hoverIdx = i);

	// --- interval session ---
	const intervals = $derived(data.analysis?.is_interval ? data.analysis : null);
	const indexByT = $derived(new Map(data.samples.map((p, i) => [p.t_s, i])));
	const kmAt = (t: number) => series.x[indexByT.get(t) ?? Math.min(series.x.length - 1, t)] ?? 0;
	const work = $derived(intervals ? intervals.segments.filter((s) => s.kind === 'work') : []);
	const bands = $derived(work.map((s) => [kmAt(s.t0), kmAt(s.t1 - 1)] as [number, number]));
	const highlights = $derived(
		work.map((s) =>
			data.track.filter((p) => p[2] >= s.t0 && p[2] < s.t1).map((p) => [p[0], p[1]] as [number, number])
		)
	);
	const repRows = $derived.by(() => {
		if (!intervals) return [];
		const paces = work.map((s) => s.pace_s_per_km ?? 0).filter(Boolean);
		const best = Math.min(...paces);
		const worst = Math.max(...paces);
		const recs = intervals.segments.filter((s) => s.kind === 'recovery');
		return work.map((s, k) => {
			const rec = recs[k];
			return {
				...s,
				best: s.pace_s_per_km === best,
				w: s.pace_s_per_km ? 35 + 65 * ((worst - s.pace_s_per_km) / Math.max(1, worst - best)) : 0,
				rec,
				hrDrop: rec && s.end_hr_bpm && rec.min_hr_bpm ? s.end_hr_bpm - rec.min_hr_bpm : null
			};
		});
	});
	// Under a minute, a warm-up/cool-down is a detection edge effect, not a phase.
	const edge = (kind: 'warmup' | 'cooldown') =>
		intervals?.segments.find((s) => s.kind === kind && s.duration_s >= 60);
	const pct = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 });

	// Plain-language reading of the session, from the summary numbers.
	const insights = $derived.by(() => {
		if (!intervals) return [];
		const sm = intervals.summary;
		const out: string[] = [];
		const cv = sm.rep_pace_cv_pct ?? 0;
		out.push(
			cv < 4
				? `Répétitions très régulières : l'allure varie de ${pct.format(cv)} % autour de ${fmtPace(sm.rep_pace_mean_s_per_km)}/km.`
				: cv < 7
					? `Répétitions assez régulières : l'allure varie de ${pct.format(cv)} % autour de ${fmtPace(sm.rep_pace_mean_s_per_km)}/km.`
					: `Répétitions irrégulières : l'allure varie de ${pct.format(cv)} %. Vise une allure cible plus constante.`
		);
		const fade = sm.fade_pct;
		if (fade != null)
			out.push(
				fade <= -3
					? `Tu as accéléré au fil de la séance : les dernières répétitions sont ${pct.format(-fade)} % plus rapides que les premières.`
					: fade >= 3
						? `L'allure baisse en fin de séance : les dernières répétitions sont ${pct.format(fade)} % plus lentes que les premières.`
						: `Allure tenue de la première à la dernière répétition.`
			);
		if (sm.rep_hr_first_bpm && sm.rep_hr_last_bpm) {
			const drift = Math.round(sm.rep_hr_last_bpm - sm.rep_hr_first_bpm);
			if (drift > 0) out.push(`La FC moyenne en répétition monte de ${drift} bpm entre la première et la dernière.`);
		}
		if (sm.recovery_hr_drop_mean_bpm && sm.recovery_duration_mean_s)
			out.push(
				`Pendant les récupérations (${fmtDuration(sm.recovery_duration_mean_s)} en moyenne), ta FC redescend de ${Math.round(sm.recovery_hr_drop_mean_bpm)} bpm.`
			);
		return out;
	});

	// Average pace line: of the reps for an interval session (the overall average
	// would mix running with walking recoveries), of the whole run otherwise.
	const refLine = $derived.by(() => {
		const avg = intervals ? intervals.summary.rep_pace_mean_s_per_km : run.pace_s_per_km;
		if (!avg) return null;
		return { value: avg, label: `${intervals ? '' : 'Moyenne '}${fmtPace(avg)}/km` };
	});

	const figures = $derived([
		{ label: 'Distance', value: fmtKm(run.distance_m), unit: 'km' },
		{ label: 'Durée', value: fmtDuration(run.duration_s), unit: '' },
		intervals
			? { label: 'Allure en répétition', value: fmtPace(intervals.summary.rep_pace_mean_s_per_km), unit: '/km' }
			: { label: 'Allure moyenne', value: fmtPace(run.pace_s_per_km), unit: '/km' },
		{ label: 'FC moyenne', value: String(run.avg_hr_bpm ?? '–'), unit: 'bpm' },
		{ label: 'FC max', value: String(run.max_hr_bpm ?? '–'), unit: 'bpm' },
		{ label: 'Cadence', value: String(run.avg_cadence_spm ?? '–'), unit: 'pas/min' }
	]);
</script>

<svelte:head><title>{fmtDay(run.start_local)}, course</title></svelte:head>

<main class="mx-auto max-w-5xl px-4 pt-8 pb-20 sm:px-8 sm:pt-12">
	<a href="/" class="text-sm text-muted hover:text-ink hover:underline">Toutes les sorties</a>

	<header class="mt-4">
		<h1 class="text-2xl font-semibold tracking-tight">{fmtDay(run.start_local)}</h1>
		<p class="mt-1 text-muted">
			{#if intervals}<span class="font-medium text-ink">Fractionné, {intervals.label}.</span>{/if}
			Départ à {fmtTime(run.start_local)}, {run.total_kcal ?? '–'} kcal
		</p>
	</header>

	<dl class="mt-8 grid grid-cols-2 gap-x-6 gap-y-6 sm:grid-cols-3 lg:grid-cols-6">
		{#each figures as f (f.label)}
			<div>
				<dt class="text-sm text-muted">{f.label}</dt>
				<dd class="figure mt-1 text-[2.25rem] sm:text-figure">
					{f.value}{#if f.unit}<span class="ml-1 text-base font-medium text-muted">{f.unit}</span>{/if}
				</dd>
			</div>
		{/each}
	</dl>

	{#if coords.length > 1}
		<div class="mt-10"><RunMap track={coords} {cursor} {highlights} /></div>
	{/if}

	<section class="mt-4 space-y-6 rounded-2xl bg-surface p-5 sm:p-6" aria-label="Courbes de la sortie">
		<SeriesChart
			title="Allure"
			unit="/km"
			x={series.x}
			y={series.pace}
			invert
			format={fmtPace}
			incrs={[30, 60, 120, 180, 300]}
			{bands}
			{refLine}
			onhover={hover}
		/>
		<SeriesChart title="Fréquence cardiaque" unit="bpm" x={series.x} y={series.hr} {bands} onhover={hover} />
		<SeriesChart title="Cadence" unit="pas/min" x={series.x} y={series.cadence} {bands} onhover={hover} />
		{#if intervals}
			<p class="flex items-center gap-2 text-sm text-muted">
				<span class="inline-block h-3 w-5 rounded-[3px] bg-route-soft"></span> Répétitions
			</p>
		{/if}
	</section>

	{#if intervals}
		<section class="mt-14" aria-labelledby="reps">
			<h2 id="reps" class="text-lg font-semibold">Les répétitions</h2>
			<ul class="mt-3 max-w-[70ch] space-y-1.5">
				{#each insights as line (line)}<li>{line}</li>{/each}
			</ul>
			<div class="mt-6 overflow-x-auto">
				<table class="w-full min-w-[36rem]">
					<thead class="text-left text-sm text-muted">
						<tr>
							<th class="pb-2 font-normal">Rép.</th>
							<th class="pb-2 text-right font-normal">Distance</th>
							<th class="pb-2 text-right font-normal">Durée</th>
							<th class="pb-2 pl-6 font-normal">Allure</th>
							<th class="pb-2 text-right font-normal">FC moy. / max</th>
							<th class="pb-2 text-right font-normal">Récupération</th>
						</tr>
					</thead>
					<tbody>
						{#if edge('warmup')}
							{@const w = edge('warmup')!}
							<tr class="border-t border-rule text-muted">
								<td class="py-2">Échauffement</td>
								<td class="py-2 text-right">{fmtKm(w.distance_m)} km</td>
								<td class="py-2 text-right">{fmtDuration(w.duration_s)}</td>
								<td class="py-2 pl-6">{fmtPace(w.pace_s_per_km)}</td>
								<td class="py-2 text-right">{w.avg_hr_bpm ? Math.round(w.avg_hr_bpm) : '–'}</td>
								<td></td>
							</tr>
						{/if}
						{#each repRows as r (r.index)}
							<tr class="border-t border-rule">
								<td class="py-2 font-medium">{r.index}</td>
								<td class="py-2 text-right" title={r.gps_distance_m ? `Mesuré par GPS : ${Math.round(r.gps_distance_m)} m` : undefined}>
									{Math.round(r.distance_m)} m
								</td>
								<td class="py-2 text-right">{fmtDuration(r.duration_s)}</td>
								<td class="py-2 pl-6">
									<div class="flex items-center gap-3">
										<div class="h-2 rounded-r-[4px] bg-route" style="width:{r.w * 0.5}%"></div>
										<span class={r.best ? 'font-semibold' : ''}>{fmtPace(r.pace_s_per_km)}</span>
									</div>
								</td>
								<td class="py-2 text-right">
									{r.avg_hr_bpm ? Math.round(r.avg_hr_bpm) : '–'}<span class="text-muted"> / {r.max_hr_bpm ?? '–'}</span>
								</td>
								<td class="py-2 text-right text-muted">
									{#if r.rec}{fmtDuration(r.rec.duration_s)}{#if r.hrDrop}, FC −{r.hrDrop}{/if}{/if}
								</td>
							</tr>
						{/each}
						{#if edge('cooldown')}
							{@const c = edge('cooldown')!}
							<tr class="border-t border-rule text-muted">
								<td class="py-2">Retour au calme</td>
								<td class="py-2 text-right">{fmtKm(c.distance_m)} km</td>
								<td class="py-2 text-right">{fmtDuration(c.duration_s)}</td>
								<td class="py-2 pl-6">{fmtPace(c.pace_s_per_km)}</td>
								<td class="py-2 text-right">{c.avg_hr_bpm ? Math.round(c.avg_hr_bpm) : '–'}</td>
								<td></td>
							</tr>
						{/if}
					</tbody>
				</table>
			</div>
		</section>
	{/if}

	<div class="mt-14 grid gap-14 lg:grid-cols-2 lg:gap-12">
		{#if !intervals}
		<section aria-labelledby="splits">
			<h2 id="splits" class="text-lg font-semibold">Kilomètre par kilomètre</h2>
			<table class="mt-4 w-full">
				<thead class="text-left text-sm text-muted">
					<tr>
						<th class="pb-2 font-normal">km</th>
						<th class="pb-2 font-normal">Allure</th>
						<th class="pb-2 text-right font-normal">FC</th>
						<th class="pb-2 text-right font-normal">Cadence</th>
					</tr>
				</thead>
				<tbody>
					{#each splitRows as s (s.km)}
						<tr class="border-t border-rule">
							<td class="w-12 py-2 text-muted">{s.label}</td>
							<td class="py-2">
								<div class="flex items-center gap-3">
									<div class="h-2 rounded-r-[4px] bg-route" style="width:{s.w * 0.6}%"></div>
									<span class={s.best ? 'font-semibold' : ''}>{fmtPace(s.pace)}</span>
								</div>
							</td>
							<td class="py-2 text-right">{s.avg_hr_bpm ?? '–'}</td>
							<td class="py-2 text-right text-muted">{s.avg_cadence_spm ?? '–'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</section>

		{/if}
		<section aria-labelledby="zones" class={intervals ? 'lg:col-span-2 lg:max-w-[calc(50%-1.5rem)]' : ''}>
			<h2 id="zones" class="text-lg font-semibold">Temps par zone cardiaque</h2>
			<p class="mt-1 text-sm text-muted">Calculé sur ta FC max enregistrée, {data.hrMax} bpm.</p>
			<ul class="mt-5 space-y-4">
				{#each zones as z (z.name)}
					<li>
						<div class="flex items-baseline justify-between gap-4">
							<span>{z.name} <span class="text-sm text-faint">dès {z.bpm} bpm</span></span>
							<span class="text-sm"><span class="font-medium">{fmtDuration(z.s)}</span> <span class="text-muted">({z.pct} %)</span></span>
						</div>
						<div class="mt-1.5 h-2 w-full rounded-[4px] bg-rule/60">
							<div
								class="h-2 rounded-[4px] bg-route"
								style="width:{z.w}%; opacity:{z.alpha}"
							></div>
						</div>
					</li>
				{/each}
			</ul>
		</section>
	</div>
</main>
