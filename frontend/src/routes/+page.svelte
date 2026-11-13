<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { fmtDay, fmtDuration, fmtKm, fmtPace, fmtShortDay, fmtTime } from '#lib/api.js';
	import RouteGlyph from '#lib/components/RouteGlyph.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const latest = $derived(data.runs[0]);
	const totalM = $derived(data.runs.reduce((a, r) => a + r.distance_m, 0));
	const since = $derived(
		data.runs.length
			? new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long' }).format(
					new Date(data.runs[data.runs.length - 1].start_local)
				)
			: ''
	);

	// Weekly volume with empty weeks filled in, so gaps read as gaps.
	const weeks = $derived.by(() => {
		if (!data.weekly.length) return [];
		const byWeek = new Map(data.weekly.map((w) => [w.week, w]));
		const out: { week: string; km: number; runs: number }[] = [];
		const d = new Date(data.weekly[0].week + 'T00:00:00Z');
		const end = new Date(data.weekly[data.weekly.length - 1].week + 'T00:00:00Z');
		for (; d <= end; d.setUTCDate(d.getUTCDate() + 7)) {
			const key = d.toISOString().slice(0, 10);
			const w = byWeek.get(key);
			out.push({ week: key, km: w?.distance_km ?? 0, runs: w?.runs ?? 0 });
		}
		return out;
	});
	const maxKm = $derived(Math.max(1, ...weeks.map((w) => w.km)));
	const weekLabel = (iso: string) =>
		new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' })
			.format(new Date(iso + 'T00:00:00Z'))
			.replace('.', '');

	let syncing = $state(false);
	let syncMsg = $state('');

	async function sync() {
		syncing = true;
		syncMsg = '';
		try {
			const res = await fetch('/api/sync?days=30', { method: 'POST' });
			const body = await res.json();
			syncMsg = res.ok
				? 'Sorties des 30 derniers jours synchronisées.'
				: `Synchronisation impossible : ${body.detail}. Reconnecte-toi avec mifit login.`;
			await invalidateAll();
		} finally {
			syncing = false;
		}
	}
</script>

<svelte:head><title>Mes courses</title></svelte:head>

<main class="mx-auto max-w-5xl px-4 pt-10 pb-20 sm:px-8 sm:pt-14">
	<header class="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
		<div>
			<h1 class="text-2xl font-semibold tracking-tight">Mes courses</h1>
			<p class="mt-1 text-muted">
				{data.runs.length} sorties et {fmtKm(totalM, 1)} km depuis le {since}
			</p>
		</div>
		<div class="flex flex-col items-end gap-2">
			<button
				class="rounded-full border border-rule bg-surface px-4 py-2 text-sm font-medium transition-colors hover:border-ink disabled:cursor-wait disabled:opacity-60"
				onclick={sync}
				disabled={syncing}
			>
				{syncing ? 'Synchronisation…' : 'Synchroniser'}
			</button>
			{#if syncMsg}<p class="max-w-64 text-right text-xs text-muted" role="status">{syncMsg}</p>{/if}
		</div>
	</header>

	{#if latest}
		<a
			href="/runs/{latest.id}"
			class="group mt-10 grid items-center gap-6 rounded-2xl bg-surface p-6 sm:grid-cols-[minmax(0,15rem)_1fr] sm:gap-10 sm:p-8"
		>
			<RouteGlyph
				points={data.routes[latest.id]}
				size={240}
				stroke={2.5}
				class="mx-auto h-auto w-40 text-route sm:w-full"
			/>
			<div>
				<p class="text-muted">Dernière sortie</p>
				<h2 class="mt-1 text-xl font-semibold group-hover:underline">
					{fmtDay(latest.start_local)}, {fmtTime(latest.start_local)}
				</h2>
				<dl class="mt-6 grid grid-cols-2 gap-x-8 gap-y-5 sm:flex sm:flex-wrap sm:gap-x-10">
					<div>
						<dt class="text-sm text-muted">Distance</dt>
						<dd class="figure mt-1 text-figure">{fmtKm(latest.distance_m)}<span class="ml-1 text-lg text-muted">km</span></dd>
					</div>
					<div>
						<dt class="text-sm text-muted">Durée</dt>
						<dd class="figure mt-1 text-figure">{fmtDuration(latest.duration_s)}</dd>
					</div>
					<div>
						<dt class="text-sm text-muted">Allure</dt>
						<dd class="figure mt-1 text-figure">{fmtPace(latest.pace_s_per_km)}<span class="ml-1 text-lg text-muted">/km</span></dd>
					</div>
					<div>
						<dt class="text-sm text-muted">FC moyenne</dt>
						<dd class="figure mt-1 text-figure">{latest.avg_hr_bpm ?? '–'}<span class="ml-1 text-lg text-muted">bpm</span></dd>
					</div>
				</dl>
			</div>
		</a>
	{/if}

	<section class="mt-14" aria-labelledby="weeks">
		<h2 id="weeks" class="text-lg font-semibold">Kilomètres par semaine</h2>
		<div class="mt-6 flex h-44 items-end gap-1.5 sm:gap-3">
			{#each weeks as w, i (w.week)}
				{@const last = i === weeks.length - 1}
				<div
					class="group flex h-full flex-1 flex-col items-center justify-end gap-1.5"
					title="Semaine du {weekLabel(w.week)} : {fmtKm(w.km * 1000, 1)} km en {w.runs} sortie{w.runs > 1 ? 's' : ''}"
				>
					<span class="text-xs {last ? 'font-semibold text-ink' : 'text-muted'}">
						{w.km ? Math.round(w.km) : ''}
					</span>
					<div
						class="w-full max-w-12 rounded-t-[4px] {last ? 'bg-route' : 'bg-route/35 group-hover:bg-route/60'}"
						style="height: {(w.km / maxKm) * 100}%; min-height: {w.km ? 2 : 0}px"
					></div>
				</div>
			{/each}
		</div>
		<div class="mt-2 flex gap-1.5 border-t border-rule pt-2 sm:gap-3">
			{#each weeks as w, i (w.week)}
				<span class="flex-1 text-center text-[11px] text-faint">
					{i % 2 === 0 || i === weeks.length - 1 ? weekLabel(w.week) : ''}
				</span>
			{/each}
		</div>
	</section>

	<section class="mt-14" aria-labelledby="all">
		<h2 id="all" class="text-lg font-semibold">Toutes les sorties</h2>
		<ol class="mt-4">
			{#each data.runs as r (r.id)}
				<li class="border-t border-rule first:border-t-0">
					<a
						href="/runs/{r.id}"
						class="grid grid-cols-[2.5rem_1fr_auto] items-center gap-x-4 rounded-lg px-2 py-3 hover:bg-surface sm:grid-cols-[2.5rem_1fr_6rem_5rem_6rem_4rem]"
					>
						<RouteGlyph points={data.routes[r.id]} size={40} stroke={1.25} class="text-route" />
						<span>
							<span class="font-medium">{fmtShortDay(r.start_local)}</span>
							<span class="ml-2 text-sm text-faint">{fmtTime(r.start_local)}</span>
						</span>
						<span class="text-right">
							<span class="figure text-lg">{fmtKm(r.distance_m)}</span>
							<span class="text-sm text-muted">km</span>
						</span>
						<span class="hidden text-right text-muted sm:block">{fmtDuration(r.duration_s)}</span>
						<span class="hidden text-right sm:block">{fmtPace(r.pace_s_per_km)}<span class="ml-0.5 text-sm text-muted">/km</span></span>
						<span class="hidden text-right text-muted sm:block">{r.avg_hr_bpm ?? '–'}<span class="ml-1 text-xs">bpm</span></span>
					</a>
				</li>
			{:else}
				<li class="py-10 text-muted">
					Aucune sortie pour l'instant. Synchronise ta montre pour récupérer tes courses.
				</li>
			{/each}
		</ol>
	</section>
</main>
