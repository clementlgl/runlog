<script lang="ts">
	// Xiaomi account status, and login through Xiaomi's own page (QR login flow):
	// the backend gets a login URL, we open it, the user signs in and approves there.
	import { onMount } from 'svelte';

	type Info = { connected: boolean; region?: string; logged_in_at?: string; renewed_at?: string | null };
	type Login = {
		status: 'waiting' | 'done' | 'error';
		login_url: string | null;
		link_count: number;
		notification_url: string | null;
		error: string | null;
	};

	let info = $state<Info | null>(null);
	let login = $state<Login | null>(null);
	let timer: ReturnType<typeof setTimeout> | undefined;

	const dateFmt = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
	const since = $derived(info?.logged_in_at ? dateFmt.format(new Date(info.logged_in_at)) : '');

	async function refresh() {
		try {
			info = await (await fetch('/api/session')).json();
		} catch {
			info = null;
		}
	}

	async function poll() {
		try {
			login = await (await fetch('/api/login')).json();
		} catch {
			// transient: retry next tick
		}
		if (login?.status === 'waiting') {
			timer = setTimeout(poll, 2000);
			return;
		}
		await refresh();
	}

	async function connect() {
		// Open the tab now, inside the click: opened after the request it would be
		// treated as a popup and blocked.
		const tab = window.open('', '_blank');
		try {
			const res = await fetch('/api/login', { method: 'POST' });
			login = await res.json();
		} catch {
			tab?.close();
			login = { status: 'error', login_url: null, link_count: 0, notification_url: null, error: 'le serveur ne répond pas.' };
			return;
		}
		if (login?.login_url && tab) {
			tab.opener = null;
			tab.location.href = login.login_url;
		} else {
			tab?.close(); // popup blocked: the link shown below still works
		}
		poll();
	}

	onMount(() => {
		refresh();
		(async () => {
			try {
				const current: Login | null = await (await fetch('/api/login')).json();
				if (current?.status === 'waiting') {
					login = current;
					poll();
				}
			} catch {
				// ignore
			}
		})();
		return () => clearTimeout(timer);
	});
</script>

<div class="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-rule pb-4">
	<div class="text-sm">
		<span class="font-medium">Compte Xiaomi</span>
		<span class="ml-2 text-muted">
			{#if login?.status === 'waiting'}
				En attente de ta validation sur la page Xiaomi…
			{:else if info?.connected}
				Connecté depuis le {since}, région {info.region}
			{:else if info}
				Non connecté : connecte-toi pour synchroniser.
			{/if}
		</span>
	</div>
	<button
		type="button"
		class="rounded-full border px-4 py-1.5 text-sm font-medium transition-colors disabled:cursor-wait disabled:opacity-60 {info?.connected
			? 'border-rule hover:border-ink'
			: 'border-ink bg-ink text-surface hover:opacity-85'}"
		onclick={connect}
		disabled={login?.status === 'waiting'}
	>
		{info?.connected ? 'Se reconnecter' : 'Se connecter à Xiaomi'}
	</button>

	{#if login?.status === 'waiting'}
		<div class="w-full space-y-1.5 text-sm text-muted">
			<p>
				Dans l'onglet Xiaomi, valide la connexion. Si la page te demande de te connecter, fais-le : le lien se
				renouvelle tout seul s'il expire, pendant 10 minutes.
			</p>
			<p>
				Plus rapide : sois déjà connecté sur
				<a class="font-medium text-ink underline" href="https://account.xiaomi.com" target="_blank" rel="noopener noreferrer">account.xiaomi.com</a>
				dans ce navigateur, la validation ne prend alors qu'un clic.
			</p>
			{#if login.login_url}
				<p>
					{#if login.link_count > 1}<span class="text-ink">Le lien précédent a expiré.</span>{/if}
					<a class="font-medium text-ink underline" href={login.login_url} target="_blank" rel="noopener noreferrer">
						{login.link_count > 1 ? 'Ouvrir le nouveau lien de connexion' : 'Ouvrir la page de connexion Xiaomi'}
					</a>
				</p>
			{/if}
		</div>
	{:else if login?.status === 'done'}
		<p class="w-full text-sm text-muted" role="status">Connexion réussie.</p>
	{:else if login?.status === 'error'}
		<p class="w-full text-sm text-[#b42318] dark:text-[#f97066]" role="status">
			Connexion impossible : {login.error}
			{#if login.notification_url}
				<a class="ml-1 font-medium underline" href={login.notification_url} target="_blank" rel="noopener noreferrer">
					Ouvrir la confirmation de sécurité
				</a>
			{/if}
		</p>
	{/if}
</div>
