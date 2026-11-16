<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { fmtKm, fmtPace, type Run } from '#lib/api.js';
	import ladderConfig from '#lib/interval-ladder.json';
	import {
		RUNS_PER_WEEK,
		SESSION_LABEL,
		addDays,
		ladderProgress,
		mondayOf,
		plannedOn,
		stepOn,
		today,
		type LadderConfig,
		type Session
	} from '#lib/training.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const WEEKS = 4; // weeks shown at once; the arrows move by this much
	const lo = $derived(Math.round(data.hrMax * 0.7));
	const hi = $derived(Math.round(data.hrMax * 0.85));
	const easy = $derived(Math.round(data.hrMax * 0.75));

	const todayKey = today();
	const ladder = $derived(
		ladderProgress(data.runs, ladderConfig as LadderConfig, data.validations)
	);

	// Hand validation of the current step, or undo of the last one validated by hand.
	let saving = $state(false);
	let saveError = $state('');
	async function setValidated(stepKey: string, on: boolean, runId?: number, day?: string) {
		saving = true;
		saveError = '';
		try {
			const res = on
				? await fetch('/api/ladder/validations', {
						method: 'POST',
						headers: { 'content-type': 'application/json' },
						body: JSON.stringify({ step_key: stepKey, day, run_id: runId })
					})
				: await fetch(`/api/ladder/validations?step_key=${encodeURIComponent(stepKey)}`, {
						method: 'DELETE'
					});
			if (!res.ok) throw new Error(String(res.status));
			await invalidateAll();
		} catch {
			saveError = 'Enregistrement impossible, réessaie.';
		} finally {
			saving = false;
		}
	}
	const next = $derived(
		ladder.steps[Math.min(ladder.current, ladder.steps.length - 1)] as
			(typeof ladder.steps)[number] | undefined
	);
	const recovery = ladderConfig.recovery.replace(':', ' min ');

	const plan = $derived([
		{
			day: 'Lundi',
			session: 'long' as Session,
			points: [
				'60 à 75 min en endurance, à allure facile : tu dois pouvoir parler.',
				`FC sous ${easy} bpm (75 % de ta FC max).`,
				'Allonger de 5 à 10 % par semaine au plus.'
			]
		},
		{
			day: 'Jeudi',
			session: 'intervals' as Session,
			points: [
				next
					? `15 min d’échauffement, puis ${next.label} à ${fmtPace(next.pace_s)} /km.`
					: '15 min d’échauffement, puis les répétitions.',
				`Récupération de ${recovery} en trottinant entre les répétitions.`,
				'10 min de retour au calme.'
			]
		},
		{
			day: 'Samedi',
			session: 'steady' as Session,
			points: [
				`Sortie régulière : 30 à 45 min à allure constante sur le plat, FC entre ${lo} et ${hi} bpm.`,
				'Le premier samedi du mois : 5 km à fond à la place.',
				'C’est la sortie qui nourrit le mieux l’estimation de la VO2max.'
			]
		}
	]);

	const byDay = $derived.by(() => {
		const m = new Map<string, Run[]>();
		for (const r of data.runs) {
			const k = r.start_local.slice(0, 10);
			m.set(k, [...(m.get(k) ?? []), r]);
		}
		return m;
	});

	// Pages of WEEKS weeks; page 0 starts with the current week.
	let page = $state(0);
	const weeks = $derived.by(() => {
		const first = addDays(mondayOf(todayKey), 7 * WEEKS * page);
		return Array.from({ length: WEEKS }, (_, w) => {
			const monday = addDays(first, 7 * w);
			const days = Array.from({ length: 7 }, (_, i) => {
				const day = addDays(monday, i);
				return {
					day,
					planned: plannedOn(day),
					step: stepOn(day, todayKey, ladder),
					runs: byDay.get(day) ?? []
				};
			});
			return { monday, days, done: days.reduce((n, d) => n + d.runs.length, 0) };
		});
	});

	const dayNames = ['L', 'M', 'M', 'J', 'V', 'S', 'D'];
	const weekFmt = new Intl.DateTimeFormat('fr-FR', {
		day: 'numeric',
		month: 'short',
		timeZone: 'UTC'
	});
	const weekLabel = (monday: string) =>
		weekFmt.format(new Date(monday + 'T00:00:00Z')).replace('.', '');
	const dayNum = (day: string) => Number(day.slice(8));
	const shortLabel: Record<Session, string> = {
		long: 'Longue',
		intervals: 'Fract.',
		steady: 'Régul.',
		test: '5 km'
	};
</script>

<svelte:head><title>Entraînement – Runlog</title></svelte:head>

<main class="mx-auto max-w-5xl px-4 pt-8 pb-20 sm:px-8 sm:pt-12">
	<header>
		<h1 class="text-2xl font-semibold tracking-tight">Entraînement</h1>
		<p class="mt-1 max-w-2xl text-muted">
			Objectif : {RUNS_PER_WEEK} sorties par semaine.
		</p>
	</header>

	<section class="mt-10" aria-labelledby="week">
		<h2 id="week" class="text-lg font-semibold">Semaine type</h2>
		<div class="mt-4 grid gap-3 sm:grid-cols-3">
			{#each plan as p (p.day)}
				<div class="rounded-xl bg-surface p-5">
					<p class="flex flex-wrap items-baseline justify-between gap-x-3">
						<span class="font-semibold">{SESSION_LABEL[p.session]}</span>
						<span class="text-sm text-faint">{p.day}</span>
					</p>
					<ul class="mt-3 list-disc space-y-1.5 pl-4 text-sm text-muted">
						{#each p.points as pt (pt)}<li>{pt}</li>{/each}
					</ul>
				</div>
			{/each}
		</div>
	</section>

	<section class="mt-12" aria-labelledby="ladder">
		<h2 id="ladder" class="text-lg font-semibold">Paliers de fractionné</h2>
		<p class="mt-1 max-w-2xl text-sm text-muted">
			Le bouton Valider apparaît quand une séance de fractionné, quel que soit le jour, compte les
			bonnes répétitions et que leur allure moyenne tient la cible (à {ladderConfig.tolerance_s} s/km
			près). Rien n’est validé sans clic.
		</p>
		<ol class="mt-4 grid gap-2 sm:grid-cols-3">
			{#each ladder.steps as st, i (i)}
				{@const v = ladder.validated[i]}
				<li
					class="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 rounded-lg p-3 text-sm {i ===
					ladder.current
						? 'bg-surface ring-1 ring-route'
						: 'bg-surface'}"
				>
					<span class="whitespace-nowrap">
						<span class="font-semibold">{st.label}</span>
						<span class="text-muted">à {fmtPace(st.pace_s)}</span>
					</span>
					{#if v}
						<span class="flex shrink-0 items-baseline gap-2 text-xs whitespace-nowrap">
							<a href="/runs/{v.runId}" class="text-route hover:underline"
								>Validé · {weekLabel(v.day)}{v.pace_s ? ` · ${fmtPace(v.pace_s)}` : ''}</a
							>
							{#if i === ladder.current - 1}
								<button
									class="text-muted underline hover:text-ink disabled:opacity-40"
									disabled={saving}
									onclick={() => setValidated(st.key, false)}>Annuler</button
								>
							{/if}
						</span>
					{:else if i === ladder.current && ladder.candidate}
						{@const c = ladder.candidate}
						<span class="flex shrink-0 items-baseline gap-2 text-xs whitespace-nowrap">
							<a href="/runs/{c.runId}" class="text-muted hover:underline"
								>{weekLabel(c.day)} · {fmtPace(c.pace_s)}</a
							>
							<button
								class="h-7 rounded-full border border-route px-3 font-medium text-route transition-colors hover:bg-route/15 disabled:opacity-40"
								disabled={saving}
								onclick={() => setValidated(st.key, true, c.runId, c.day)}>Valider</button
							>
						</span>
					{:else if i === ladder.current}
						<span class="text-xs font-medium text-route">En cours</span>
					{:else}
						<span class="text-xs text-faint">À venir</span>
					{/if}
				</li>
			{/each}
		</ol>
		{#if saveError}
			<p class="mt-3 text-sm text-[#b42318] dark:text-[#f97066]" role="alert">{saveError}</p>
		{/if}
		{#if ladder.current >= ladder.steps.length}
			<p class="mt-3 text-sm text-muted">
				Tous les paliers sont validés : ajoute les suivants dans
				<code>frontend/src/lib/interval-ladder.json</code>.
			</p>
		{/if}
	</section>

	<section class="mt-12" aria-labelledby="calendar">
		<div class="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
			<div>
				<h2 id="calendar" class="text-lg font-semibold">Calendrier</h2>
				<p class="mt-1 text-sm text-muted" aria-live="polite">
					Du {weekLabel(weeks[0].monday)} au {weekLabel(addDays(weeks[WEEKS - 1].monday, 6))}
				</p>
			</div>
			<div class="flex gap-2">
				<button
					class="grid size-9 place-items-center rounded-full border border-rule bg-surface transition-colors hover:border-ink"
					aria-label="{WEEKS} semaines précédentes"
					onclick={() => page--}
				>
					<svg
						viewBox="0 0 16 16"
						class="size-4"
						fill="none"
						stroke="currentColor"
						stroke-width="1.75"
						stroke-linecap="round"
						stroke-linejoin="round"
						aria-hidden="true"><path d="M10 3 5 8l5 5" /></svg
					>
				</button>
				<button
					class="h-9 rounded-full border border-rule bg-surface px-3 text-sm font-medium transition-colors hover:border-ink disabled:opacity-40 disabled:hover:border-rule"
					disabled={page === 0}
					onclick={() => (page = 0)}>Aujourd’hui</button
				>
				<button
					class="grid size-9 place-items-center rounded-full border border-rule bg-surface transition-colors hover:border-ink"
					aria-label="{WEEKS} semaines suivantes"
					onclick={() => page++}
				>
					<svg
						viewBox="0 0 16 16"
						class="size-4"
						fill="none"
						stroke="currentColor"
						stroke-width="1.75"
						stroke-linecap="round"
						stroke-linejoin="round"
						aria-hidden="true"><path d="m6 3 5 5-5 5" /></svg
					>
				</button>
			</div>
		</div>

		<div class="mt-4 rounded-xl bg-surface p-3 sm:p-5">
			<div
				class="grid grid-cols-[repeat(7,minmax(0,1fr))_2.5rem] gap-1 text-center text-xs text-faint sm:grid-cols-[4rem_repeat(7,minmax(0,1fr))_3rem] sm:gap-1.5"
			>
				<span class="hidden sm:block"></span>
				{#each dayNames as d, i (i)}<span>{d}</span>{/each}
				<span></span>
			</div>

			{#each weeks as w (w.monday)}
				<div
					class="mt-1 grid grid-cols-[repeat(7,minmax(0,1fr))_2.5rem] items-stretch gap-1 sm:mt-1.5 sm:grid-cols-[4rem_repeat(7,minmax(0,1fr))_3rem] sm:gap-1.5"
				>
					<span class="hidden self-center text-xs text-faint sm:block">{weekLabel(w.monday)}</span>
					{#each w.days as d (d.day)}
						{@const future = d.day > todayKey}
						{@const missed = d.planned && !future && d.day !== todayKey && !d.runs.length}
						{#if d.runs.length}
							<a
								href="/runs/{d.runs[0].id}"
								class="flex min-h-14 flex-col justify-between rounded-md bg-route/20 p-1 text-left hover:bg-route/35 sm:p-1.5"
								title="{d.planned ? SESSION_LABEL[d.planned] + ' – ' : ''}{fmtKm(
									d.runs[0].distance_m,
									1
								)} km{d.runs[0].workout_type === 'intervals' ? ', fractionné' : ''}"
							>
								<span class="text-[11px] text-muted">{dayNum(d.day)}</span>
								<span class="text-xs font-semibold sm:text-sm">
									{fmtKm(
										d.runs.reduce((a, r) => a + r.distance_m, 0),
										1
									)}
								</span>
							</a>
						{:else}
							<div
								class="flex min-h-14 flex-col justify-between rounded-md p-1 text-left sm:p-1.5 {d.planned
									? 'border border-dashed ' + (missed ? 'border-rule' : 'border-route/60')
									: ''} {d.day === todayKey ? 'ring-1 ring-ink' : ''}"
								title={d.planned
									? `${SESSION_LABEL[d.planned]}${d.step ? ` – ${d.step.label} à ${fmtPace(d.step.pace_s)}` : ''}${missed ? ' – non faite' : ''}`
									: undefined}
							>
								<span class="text-[11px] {future ? 'text-faint' : 'text-muted'}"
									>{dayNum(d.day)}</span
								>
								{#if d.planned}
									<span
										class="truncate text-[10px] sm:text-xs {missed
											? 'text-faint line-through'
											: 'text-route'}"
									>
										{shortLabel[d.planned]}
									</span>
									{#if d.step}
										<span class="truncate text-[10px] text-muted sm:text-xs"
											>{d.step.distance_m}·{fmtPace(d.step.pace_s)}</span
										>
									{/if}
								{/if}
							</div>
						{/if}
					{/each}
					<span
						class="self-center text-xs font-medium {w.done >= RUNS_PER_WEEK
							? 'text-ink'
							: 'text-faint'}"
					>
						{w.done}/{RUNS_PER_WEEK}
					</span>
				</div>
			{/each}

			<p class="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
				<span
					><span class="mr-1.5 inline-block size-3 rounded-sm bg-route/20 align-middle"
					></span>Sortie faite (km)</span
				>
				<span
					><span
						class="mr-1.5 inline-block size-3 rounded-sm border border-dashed border-route/60 align-middle"
					></span>Prévue</span
				>
				<span
					><span
						class="mr-1.5 inline-block size-3 rounded-sm border border-dashed border-rule align-middle"
					></span>Prévue, non faite</span
				>
			</p>
		</div>
	</section>

	<section class="mt-12" aria-labelledby="conditions">
		<h2 id="conditions" class="text-lg font-semibold">Pour une VO2max fiable</h2>
		<dl class="mt-4 grid gap-6 sm:grid-cols-3">
			<div>
				<dt class="font-semibold">5 km à fond</dt>
				<dd class="mt-1 text-sm text-muted">
					Sur piste ou parcours plat, sprint sur les 500 derniers mètres. Il mesure ta vraie FC max,
					qui entre dans chaque estimation : si elle dépasse {data.hrMax}, toutes remontent.
					Seulement en forme et sans souci cardiaque connu.
				</dd>
			</div>
			<div>
				<dt class="font-semibold">Conditions</dt>
				<dd class="mt-1 text-sm text-muted">
					Temps frais, sans fatigue de la veille, montre bien serrée. Une ceinture cardio est plus
					précise que le capteur au poignet.
				</dd>
			</div>
			<div>
				<dt class="font-semibold">À éviter</dt>
				<dd class="mt-1 text-sm text-muted">
					Pour l’estimation : le fractionné (non estimé), les parcours vallonnés et les arrêts aux
					feux.
				</dd>
			</div>
		</dl>
	</section>
</main>
