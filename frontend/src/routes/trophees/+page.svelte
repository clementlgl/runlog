<script lang="ts">
	import { fmtDay, fmtDuration, fmtKm, fmtPace, type Trophy } from '#lib/api.js';
	import Medal from '#lib/components/Medal.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const sections = [
		{ id: 'distance', title: 'Distance sur une sortie', families: ['distance'] },
		{ id: 'volume', title: 'Volume cumulé', families: ['volume', 'month'] },
		{ id: 'records', title: 'Records perso', families: ['record', 'chrono'] }
	] as const;

	const unlocked = $derived(data.trophies.filter((t) => t.unlocked).length);
	const tierName = { bronze: 'Bronze', argent: 'Argent', or: 'Or', platine: 'Platine', record: '' };
	const progressLabel = (t: Trophy) =>
		t.family === 'distance'
			? 'Plus longue sortie'
			: t.family === 'month'
				? 'Meilleur mois'
				: 'Total';
</script>

<svelte:head><title>Trophées – Runlog</title></svelte:head>

<main class="mx-auto max-w-5xl px-4 pt-8 pb-20 sm:px-8 sm:pt-12">
	<a href="/" class="text-sm text-muted hover:text-ink hover:underline">Toutes les sorties</a>

	<header class="mt-4">
		<h1 class="text-2xl font-semibold tracking-tight">Trophées</h1>
		<p class="mt-1 text-muted">{unlocked} débloqués sur {data.trophies.length}</p>
	</header>

	{#each sections as s (s.id)}
		<section class="mt-12" aria-labelledby={s.id}>
			<h2 id={s.id} class="text-lg font-semibold">{s.title}</h2>
			<ul class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
				{#each data.trophies.filter( (t) => (s.families as readonly string[]).includes(t.family) ) as t (t.id)}
					<li class="flex gap-4 rounded-xl bg-surface p-5">
						<Medal tier={t.tier} unlocked={t.unlocked} class="h-12 w-10 shrink-0" />
						<div class="min-w-0 flex-1">
							<p class="flex items-baseline gap-2">
								<span class="font-semibold {t.unlocked ? '' : 'text-muted'}">{t.title}</span>
								<span class="text-xs text-faint">{tierName[t.tier]}</span>
								{#if (t.times ?? 0) > 1}
									<span class="ml-auto text-sm font-medium">×{t.times}</span>
								{/if}
							</p>
							<p class="mt-0.5 text-sm text-muted">{t.description}</p>
							{#if t.family === 'record' && t.unlocked && t.time_s}
								<p class="mt-3">
									<span class="figure text-xl">{fmtDuration(t.time_s)}</span>
									<span class="ml-1 text-sm text-muted"
										>{fmtPace(t.time_s / (t.target_m / 1000))}/km</span
									>
								</p>
								<a href="/runs/{t.run_id}" class="mt-1 block text-sm hover:underline">
									{fmtDay(t.unlocked_at!)}
								</a>
								{#if (t.history?.length ?? 0) > 1}
									<p class="mt-1.5 text-xs text-faint">
										Précédents : {t
											.history!.slice(0, -1)
											.reverse()
											.map((h) => fmtDuration(h.time_s))
											.join(', ')}
									</p>
								{/if}
							{:else if t.unlocked && t.run_id}
								<a href="/runs/{t.run_id}" class="mt-3 block text-sm hover:underline">
									{fmtDay(t.unlocked_at!)}
								</a>
							{:else if t.family === 'record' || t.family === 'chrono'}
								<p class="mt-3 text-xs text-faint">
									{#if t.time_s}
										Meilleur temps : {fmtDuration(t.time_s)} / {fmtDuration(t.target_s!)}
									{:else}
										Aucune sortie de {t.target_m / 1000} km pour l'instant
									{/if}
								</p>
							{:else}
								<p class="mt-3 text-xs text-faint">
									{progressLabel(t)} : {fmtKm(t.progress_m, 1)} / {fmtKm(t.target_m, 1)} km
								</p>
							{/if}
						</div>
					</li>
				{/each}
			</ul>
		</section>
	{/each}
</main>
