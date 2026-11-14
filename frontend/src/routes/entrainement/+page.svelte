<script lang="ts">
	// Which runs make the VO2max estimates (watch and ours) more reliable.
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const lo = $derived(Math.round(data.hrMax * 0.7));
	const hi = $derived(Math.round(data.hrMax * 0.85));

	const workouts = $derived([
		{
			title: 'Sortie régulière sur le plat',
			when: 'Chaque semaine',
			points: [
				'30 à 45 min à allure constante, sans arrêt, idéalement toujours sur la même boucle plate.',
				`FC entre ${lo} et ${hi} bpm (70 à 85 % de ta FC max de ${data.hrMax}).`,
				"10 min d'échauffement tranquille avant de tenir l'allure."
			],
			why: "C'est l'effort que suppose l'estimation, et celui que la montre exploite le mieux."
		},
		{
			title: '5 km à fond',
			when: 'Tous les 1 à 2 mois',
			points: [
				'Sur piste ou parcours plat, effort maximal du début à la fin.',
				'Sprint sur les 500 derniers mètres pour atteindre ta vraie FC max.',
				'Seulement en forme et sans souci cardiaque connu.'
			],
			why: `Mesure ta vraie FC max, qui entre dans chaque estimation : si elle dépasse ${data.hrMax}, toutes remontent. Proche de ta FC max, la sortie donne aussi une estimation fiable.`
		}
	]);
</script>

<svelte:head><title>Entraînement – Runlog</title></svelte:head>

<main class="mx-auto max-w-5xl px-4 pt-8 pb-20 sm:px-8 sm:pt-12">
	<a href="/" class="text-sm text-muted hover:text-ink hover:underline">Toutes les sorties</a>

	<header class="mt-4">
		<h1 class="text-2xl font-semibold tracking-tight">Entraînement</h1>
		<p class="mt-1 max-w-2xl text-muted">
			Les sorties qui rendent l'estimation, celle de la montre comme celle de Runlog, plus fiable.
		</p>
	</header>

	<div class="mt-10 grid gap-3 sm:grid-cols-2">
		{#each workouts as w (w.title)}
			<section class="rounded-xl bg-surface p-5 sm:p-6">
				<p class="flex flex-wrap items-baseline justify-between gap-x-3">
					<span class="text-lg font-semibold">{w.title}</span>
					<span class="text-sm text-faint">{w.when}</span>
				</p>
				<ul class="mt-3 list-disc space-y-1.5 pl-4 text-muted">
					{#each w.points as p (p)}<li>{p}</li>{/each}
				</ul>
				<p class="mt-4">{w.why}</p>
			</section>
		{/each}
	</div>

	<dl class="mt-10 grid gap-6 sm:grid-cols-2">
		<div>
			<dt class="font-semibold">Conditions</dt>
			<dd class="mt-1 text-muted">
				Temps frais, sans fatigue de la veille, montre bien serrée. Une ceinture cardio est plus
				précise que le capteur au poignet.
			</dd>
		</div>
		<div>
			<dt class="font-semibold">À éviter</dt>
			<dd class="mt-1 text-muted">
				Le fractionné (non estimé), les parcours vallonnés et les arrêts aux feux.
			</dd>
		</div>
	</dl>
</main>
