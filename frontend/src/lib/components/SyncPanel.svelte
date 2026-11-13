<script lang="ts">
	// Choose the day range to fetch from the Xiaomi cloud, then run the sync.
	import { untrack } from 'svelte';

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

	async function run() {
		if (error) return;
		syncing = true;
		message = '';
		failed = false;
		try {
			const res = await fetch(`/api/sync?from=${from}&to=${to}`, { method: 'POST' });
			const body = await res.json();
			if (res.ok) {
				const n = body.new_runs ?? 0;
				message =
					n === 0
						? `Aucune nouvelle sortie entre le ${fmt(from)} et le ${fmt(to)}.`
						: `${n} nouvelle${n > 1 ? 's' : ''} sortie${n > 1 ? 's' : ''} ajoutée${n > 1 ? 's' : ''}.`;
				await onsynced?.();
			} else {
				failed = true;
				const detail = typeof body.detail === 'string' ? body.detail : 'erreur inconnue';
				message = detail.startsWith('mifit failed')
					? 'Synchronisation impossible : la session Xiaomi a expiré ou est invalide. Reconnecte-toi avec mifit login.'
					: `Synchronisation impossible : ${detail}`;
			}
		} catch {
			failed = true;
			message = 'Synchronisation impossible : le serveur ne répond pas.';
		} finally {
			syncing = false;
		}
	}
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

	<p class="mt-3 min-h-5 text-sm {error || failed ? 'text-[#b42318] dark:text-[#f97066]' : 'text-muted'}" role="status" aria-live="polite">
		{#if error}{error}{:else if syncing}Récupération du {fmt(from)} au {fmt(to)} ({span + 1} jours)…{:else}{message}{/if}
	</p>
</section>
