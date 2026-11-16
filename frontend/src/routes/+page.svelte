<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { fmtDay, fmtDuration, fmtKm, fmtPace, fmtShortDay, fmtTime } from '#lib/api.js';
	import Medal from '#lib/components/Medal.svelte';
	import RouteGlyph from '#lib/components/RouteGlyph.svelte';
	import SyncPanel from '#lib/components/SyncPanel.svelte';
	import { SESSION_LABEL, addDays, nextPlanned, today } from '#lib/training.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const todayKey = today();
	const latest = $derived(data.runs[0]);
	let syncOpen = $state(false);

	// Next session of the weekly plan.
	const next = $derived(
		nextPlanned(
			todayKey,
			data.runs.some((r) => r.start_local.startsWith(todayKey))
		)
	);
	const when = (day: string) =>
		day === todayKey
			? 'Aujourd’hui'
			: day === addDays(todayKey, 1)
				? 'Demain'
				: fmtShortDay(day + 'T00:00:00');

	// Fitness: latest watch VO2max against about a month earlier, latest estimate.
	const watch = $derived(data.runs.find((r) => r.vo2_max_watch != null));
	const watchBefore = $derived.by(() => {
		if (!watch) return undefined;
		const cutoff = addDays(watch.start_local.slice(0, 10), -30);
		return data.runs.find((r) => r.vo2_max_watch != null && r.start_local.slice(0, 10) <= cutoff);
	});
	const watchDelta = $derived(
		watch && watchBefore ? watch.vo2_max_watch! - watchBefore.vo2_max_watch! : null
	);
	const est = $derived(data.runs.find((r) => r.vo2max_est != null));
	const nf1 = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 });

	// Trophies: the latest unlocked.
	const recent = $derived(
		data.trophies
			.filter((t) => t.unlocked && t.unlocked_at)
			.sort((a, b) => b.unlocked_at!.localeCompare(a.unlocked_at!))
			.slice(0, 3)
	);
	const shortDate = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' });
	const fmtShort = (iso: string) => shortDate.format(new Date(iso)).replace('.', '');
</script>

<svelte:head><title>Runlog</title></svelte:head>

<main class="mx-auto max-w-5xl px-4 pt-8 pb-20 sm:px-8 sm:pt-12">
	<header class="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
		<div>
			<h1 class="text-2xl font-semibold tracking-tight">{fmtDay(todayKey + 'T00:00:00')}</h1>
			<p class="mt-1 text-muted">Tes dernières nouvelles de course.</p>
		</div>
		<button
			class="rounded-full border border-rule bg-surface px-4 py-2 text-sm font-medium transition-colors hover:border-ink"
			aria-expanded={syncOpen}
			aria-controls="sync-panel"
			onclick={() => (syncOpen = !syncOpen)}
		>
			{syncOpen ? 'Fermer' : 'Synchroniser'}
		</button>
	</header>

	{#if syncOpen}
		<div id="sync-panel" class="mt-6">
			<SyncPanel lastRun={latest?.start_local} onsynced={invalidateAll} />
		</div>
	{/if}

	{#if latest}
		<a
			href="/runs/{latest.id}"
			class="group mt-8 grid items-center gap-6 rounded-2xl bg-surface p-6 sm:grid-cols-[minmax(0,15rem)_1fr] sm:gap-10 sm:p-8"
		>
			<RouteGlyph
				points={data.routes[latest.id]}
				size={240}
				stroke={2.5}
				class="mx-auto h-auto w-40 text-route sm:w-full"
			/>
			<div>
				<p class="text-muted">
					Dernière sortie{#if latest.workout_type === 'intervals'}, fractionné {latest.workout_label}{/if}
				</p>
				<h2 class="mt-1 text-xl font-semibold group-hover:underline">
					{fmtDay(latest.start_local)}, {fmtTime(latest.start_local)}
				</h2>
				<dl class="mt-6 grid grid-cols-2 gap-x-8 gap-y-5 sm:flex sm:flex-wrap sm:gap-x-10">
					<div>
						<dt class="text-sm text-muted">Distance</dt>
						<dd class="mt-1 figure text-figure">
							{fmtKm(latest.distance_m)}<span class="ml-1 text-lg text-muted">km</span>
						</dd>
					</div>
					<div>
						<dt class="text-sm text-muted">Durée</dt>
						<dd class="mt-1 figure text-figure">{fmtDuration(latest.duration_s)}</dd>
					</div>
					<div>
						<dt class="text-sm text-muted">
							{latest.workout_type === 'intervals' ? 'Allure des reps' : 'Allure'}
						</dt>
						<dd class="mt-1 figure text-figure">
							{fmtPace(
								latest.workout_type === 'intervals'
									? latest.rep_pace_s_per_km
									: latest.pace_s_per_km
							)}<span class="ml-1 text-lg text-muted">/km</span>
						</dd>
					</div>
					<div>
						<dt class="text-sm text-muted">FC moyenne</dt>
						<dd class="mt-1 figure text-figure">
							{latest.avg_hr_bpm ?? '–'}<span class="ml-1 text-lg text-muted">bpm</span>
						</dd>
					</div>
				</dl>
			</div>
		</a>
	{:else}
		<p class="mt-8 rounded-2xl bg-surface p-6 text-muted">
			Aucune sortie pour l’instant. Synchronise ta montre pour récupérer tes courses.
		</p>
	{/if}

	<div class="mt-4 grid gap-4 md:grid-cols-3">
		<a
			href="/entrainement"
			class="group flex flex-col rounded-2xl bg-surface p-6 transition-colors hover:bg-route/10"
		>
			<p class="text-sm text-muted">Prochaine séance</p>
			<h2 class="mt-1 text-lg font-semibold group-hover:underline">
				{SESSION_LABEL[next.session]}
			</h2>
			<p class="mt-3 figure text-2xl text-route">{when(next.day)}</p>
		</a>

		<a
			href="/sorties#vo2"
			class="group flex flex-col rounded-2xl bg-surface p-6 transition-colors hover:bg-route/10"
		>
			<p class="text-sm text-muted">Forme</p>
			<h2 class="mt-1 text-lg font-semibold group-hover:underline">VO2max</h2>
			<dl class="mt-3 grid grid-cols-2 gap-4">
				<div>
					<dt class="text-xs text-muted">Montre</dt>
					<dd class="mt-1 figure text-2xl">
						{watch?.vo2_max_watch ?? '–'}
						{#if watchDelta}
							<span class="ml-1 text-sm {watchDelta > 0 ? 'text-route' : 'text-muted'}"
								>{watchDelta > 0 ? '+' : ''}{watchDelta}</span
							>
						{/if}
					</dd>
				</div>
				<div>
					<dt class="text-xs text-muted">Estimée</dt>
					<dd class="mt-1 figure text-2xl">{est ? nf1.format(est.vo2max_est!) : '–'}</dd>
				</div>
			</dl>
			<p class="mt-auto pt-4 text-xs text-faint">
				ml/kg/min{#if watchDelta != null}, écart montre sur un mois{/if}{#if est}, estimée le
					{fmtShort(est.start_local)}{/if}
			</p>
		</a>

		<a
			href="/trophees"
			class="group flex flex-col rounded-2xl bg-surface p-6 transition-colors hover:bg-route/10"
		>
			<p class="text-sm text-muted">Trophées</p>
			<h2 class="mt-1 text-lg font-semibold group-hover:underline">Derniers débloqués</h2>
			<ul class="mt-3 space-y-2">
				{#each recent as t (t.id)}
					<li class="flex items-center gap-2 text-sm">
						<Medal tier={t.tier} unlocked class="h-6 w-5 shrink-0" />
						<span class="min-w-0 flex-1 truncate">{t.title}</span>
						<span class="text-xs text-faint">{fmtShort(t.unlocked_at!)}</span>
					</li>
				{:else}
					<li class="text-sm text-muted">Aucun pour l’instant.</li>
				{/each}
			</ul>
		</a>
	</div>
</main>
