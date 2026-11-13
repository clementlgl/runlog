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

	const figures = $derived([
		{ label: 'Distance', value: fmtKm(run.distance_m), unit: 'km' },
		{ label: 'Durée', value: fmtDuration(run.duration_s), unit: '' },
		{ label: 'Allure moyenne', value: fmtPace(run.pace_s_per_km), unit: '/km' },
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
		<div class="mt-10"><RunMap track={coords} {cursor} /></div>
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
			onhover={hover}
		/>
		<SeriesChart title="Fréquence cardiaque" unit="bpm" x={series.x} y={series.hr} onhover={hover} />
		<SeriesChart title="Cadence" unit="pas/min" x={series.x} y={series.cadence} onhover={hover} />
	</section>

	<div class="mt-14 grid gap-14 lg:grid-cols-2 lg:gap-12">
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

		<section aria-labelledby="zones">
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
