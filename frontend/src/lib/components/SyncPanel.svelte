<script lang="ts">
	// Choose the day range to fetch from the Xiaomi cloud, then run the sync.
	import { onMount, untrack } from 'svelte';

	type Props = { lastRun?: string; onsynced?: () => Promise<void> | void };
	let { lastRun, onsynced }: Props = $props();

	const iso = (d: Date) => {
		const z = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
		return z.toISOString().slice(0, 10);
	};
	const daysAgo = (n: number) => iso(new Date(Date.now() - n * 86400000));
	const today = iso(new Date());

	type Preset = { id: string; label: string; from: () => string };
	// Presets are fixed when the panel opens: the latest run doesn't move while it is open.
	const last = untrack(() => lastRun);
	const presets: Preset[] = [
		...(last ? [{ id: 'last', label: 'Depuis la dernière sortie', from: () => last.slice(0, 10) }] : []),
		{ id: '30', label: '30 jours', from: () => daysAgo(30) },
		{ id: '90', label: '3 mois', from: () => daysAgo(90) },
		{ id: '365', label: '1 an', from: () => daysAgo(365) }
	];

	let preset = $state<string>(presets[0].id);
	let from = $state(presets[0].from());
	let to = $state(today);
	let syncing = $state(false);
	let message = $state('');
	let failed = $state(false);

	const MAX_DAYS = 730;
	const span = $derived(Math.round((Date.parse(to) - Date.parse(from)) / 86400000));
	const error = $derived(
		!from || !to
			? 'Choisis une date de début et de fin.'
			: span < 0
				? 'La date de début doit précéder la date de fin.'
				: span > MAX_DAYS
					? `Plage trop longue : ${MAX_DAYS} jours au maximum.`
					: ''
	);

	const longFmt = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
	const fmt = (d: string) => longFmt.format(new Date(d + 'T12:00:00'));

	function pick(p: Preset) {
		preset = p.id;
		from = p.from();
		to = today;
	}

	type Step = { status: 'pending' | 'running' | 'done' | 'error'; done: number | null; total: number | null; detail: string | null };
	type Job = {
		id: string;
		start: string;
		end: string;
		status: 'running' | 'done' | 'error';
		phase: string;
		steps: { fetch: Step; import: Step; analyse: Step };
		result: { new_runs?: number } | null;
		error: string | null;
	};
	let job = $state<Job | null>(null);
	let timer: ReturnType<typeof setTimeout> | undefined;

	const STEPS = [
		{ key: 'fetch', label: 'Récupération depuis Xiaomi' },
		{ key: 'import', label: 'Ajout des nouvelles sorties' },
		{ key: 'analyse', label: 'Analyse des séances' }
	] as const;

	const errorText = (e: string | null) =>
		!e
			? 'erreur inconnue'
			: e.startsWith('mifit failed')
				? 'la session Xiaomi a expiré ou est invalide. Reconnecte-toi avec mifit login.'
				: e;

	// Poll the job until it ends; refresh the page data once it's done.
	async function poll() {
		try {
			const res = await fetch('/api/sync/current');
			job = await res.json();
		} catch {
			// transient: try again on the next tick
		}
		if (job?.status === 'running') {
			timer = setTimeout(poll, 1000);
			return;
		}
		syncing = false;
		if (job?.status === 'done') {
			const n = job.result?.new_runs ?? 0;
			message =
				n === 0
					? `Aucune nouvelle sortie entre le ${fmt(job.start)} et le ${fmt(job.end)}.`
					: `${n} nouvelle${n > 1 ? 's' : ''} sortie${n > 1 ? 's' : ''} ajoutée${n > 1 ? 's' : ''}.`;
			await onsynced?.();
		} else if (job?.status === 'error') {
			failed = true;
			message = `Synchronisation impossible : ${errorText(job.error)}`;
		}
	}

	async function run() {
		if (error) return;
		syncing = true;
		message = '';
		failed = false;
		try {
			const res = await fetch(`/api/sync?from=${from}&to=${to}`, { method: 'POST' });
			const body = await res.json();
			if (res.status === 202 || res.status === 409) {
				job = body; // 409: a sync is already running, follow that one
				poll();
			} else {
				syncing = false;
				failed = true;
				message = `Synchronisation impossible : ${typeof body.detail === 'string' ? body.detail : 'erreur inconnue'}`;
			}
		} catch {
			syncing = false;
			failed = true;
			message = 'Synchronisation impossible : le serveur ne répond pas.';
		}
	}

	// Reopening the panel (or reloading the page) during a sync shows its progress.
	onMount(() => {
		(async () => {
			try {
				const current: Job | null = await (await fetch('/api/sync/current')).json();
				if (current?.status === 'running') {
					job = current;
					syncing = true;
					poll();
				}
			} catch {
				// no job info: the form stays usable
			}
		})();
		return () => clearTimeout(timer);
	});

	const stepText = (s: Step, key: string) => {
		if (s.status === 'pending') return 'En attente';
		if (s.status === 'error') return 'Échec';
		if (key === 'fetch') {
			const chunks = s.total ? `bloc ${s.done ?? 0} sur ${s.total}` : s.status === 'running' ? 'en cours' : '';
			return [chunks, s.detail].filter(Boolean).join(', ') || 'Terminé';
		}
		if (key === 'analyse' && s.total) return `${s.done ?? 0} sur ${s.total}`;
		if (s.detail) return s.detail;
		return s.status === 'running' ? 'En cours' : 'Terminé';
	};
</script>

<section class="rounded-2xl bg-surface p-5 sm:p-6" aria-labelledby="sync-title">
	<h2 id="sync-title" class="font-semibold">Récupérer mes sorties</h2>
	<p class="mt-1 text-sm text-muted">
		Seules les sorties absentes de l'application sont ajoutées. Une longue période peut prendre plusieurs minutes.
	</p>

	<div class="mt-4 flex flex-wrap gap-2" role="group" aria-label="Période prédéfinie">
		{#each presets as p (p.id)}
			<button
				type="button"
				class="rounded-full border px-3 py-1.5 text-sm transition-colors {preset === p.id
					? 'border-route bg-route-soft font-medium text-ink'
					: 'border-rule text-muted hover:border-ink hover:text-ink'}"
				aria-pressed={preset === p.id}
				onclick={() => pick(p)}
				disabled={syncing}
			>
				{p.label}
			</button>
		{/each}
	</div>

	<form
		class="mt-4 flex flex-wrap items-end gap-x-4 gap-y-3"
		onsubmit={(e) => {
			e.preventDefault();
			run();
		}}
	>
		<label class="flex flex-col gap-1 text-sm">
			<span class="text-muted">Du</span>
			<input
				type="date"
				class="rounded-lg border border-rule bg-page px-3 py-2 text-ink"
				bind:value={from}
				max={to || today}
				oninput={() => (preset = '')}
				disabled={syncing}
				required
			/>
		</label>
		<label class="flex flex-col gap-1 text-sm">
			<span class="text-muted">Au</span>
			<input
				type="date"
				class="rounded-lg border border-rule bg-page px-3 py-2 text-ink"
				bind:value={to}
				min={from}
				max={today}
				oninput={() => (preset = '')}
				disabled={syncing}
				required
			/>
		</label>
		<button
			type="submit"
			class="rounded-full bg-ink px-5 py-2 text-sm font-medium text-surface transition-opacity hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-50"
			disabled={syncing || !!error}
		>
			{syncing ? 'Synchronisation…' : 'Synchroniser'}
		</button>
	</form>

	{#if job && (syncing || job.status !== 'running')}
		<ol class="mt-5 space-y-3" aria-label="Progression de la synchronisation">
			{#each STEPS as st (st.key)}
				{@const s = job.steps[st.key]}
				<li>
					<div class="flex items-baseline justify-between gap-4 text-sm">
						<span class="flex items-center gap-2 {s.status === 'pending' ? 'text-faint' : ''}">
							<span
								class="inline-block size-2.5 rounded-full {s.status === 'done'
									? 'bg-route'
									: s.status === 'running'
										? 'animate-pulse bg-route motion-reduce:animate-none'
										: s.status === 'error'
											? 'bg-[#b42318] dark:bg-[#f97066]'
											: 'border border-rule'}"
								aria-hidden="true"
							></span>
							{st.label}
						</span>
						<span class="text-muted">{stepText(s, st.key)}</span>
					</div>
					{#if s.status === 'running' && s.total}
						<div class="mt-1.5 h-1.5 rounded-full bg-rule/60" role="progressbar" aria-valuemin="0" aria-valuemax={s.total} aria-valuenow={s.done ?? 0} aria-label={st.label}>
							<div class="h-1.5 rounded-full bg-route transition-[width] duration-500" style="width:{((s.done ?? 0) / s.total) * 100}%"></div>
						</div>
					{/if}
				</li>
			{/each}
		</ol>
	{/if}

	<p class="mt-3 min-h-5 text-sm {error || failed ? 'text-[#b42318] dark:text-[#f97066]' : 'text-muted'}" role="status" aria-live="polite">
		{#if error}{error}{:else if syncing && job}Récupération du {fmt(job.start)} au {fmt(job.end)}…{:else}{message}{/if}
	</p>
</section>
