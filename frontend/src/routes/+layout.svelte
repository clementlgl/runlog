<script lang="ts">
	import './layout.css';
	import { page } from '$app/state';
	import favicon from '#lib/assets/favicon.svg';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	// Always-visible sections; a run's page belongs to "Sorties".
	const sections = [
		{ href: '/', label: 'Accueil', match: (p: string) => p === '/' },
		{
			href: '/sorties',
			label: 'Sorties',
			match: (p: string) => p.startsWith('/sorties') || p.startsWith('/runs/')
		},
		{
			href: '/entrainement',
			label: 'Entraînement',
			match: (p: string) => p.startsWith('/entrainement')
		},
		{ href: '/trophees', label: 'Trophées', match: (p: string) => p.startsWith('/trophees') }
	];
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<nav class="sticky top-0 z-20 border-b border-rule bg-page/90 backdrop-blur" aria-label="Sections">
	<div class="mx-auto flex h-12 max-w-5xl items-center gap-4 px-4 sm:gap-7 sm:px-8">
		<a href="/" class="mr-auto font-semibold tracking-tight">Runlog</a>
		{#each sections as s (s.href)}
			{@const active = s.match(page.url.pathname)}
			<a
				href={s.href}
				aria-current={active ? 'page' : undefined}
				class="-mb-px flex h-12 items-center border-b-2 text-sm font-medium transition-colors {active
					? 'border-ink text-ink'
					: 'border-transparent text-muted hover:text-ink'}">{s.label}</a
			>
		{/each}
	</div>
</nav>

{@render children()}
