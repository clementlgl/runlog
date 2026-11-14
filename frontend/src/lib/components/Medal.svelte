<script lang="ts">
	import type { TrophyTier } from '#lib/api.js';

	let { tier, unlocked, class: klass = '' }: { tier: TrophyTier; unlocked: boolean; class?: string } =
		$props();
</script>

<!-- Ribbon + disc; locked medals are drawn as an outline in the rule colour. -->
<svg
	viewBox="0 0 40 48"
	class={klass}
	style="--medal: var(--{unlocked ? tier : 'rule'})"
	aria-hidden="true"
>
	<path d="M12 2h7l-4 18h-7z M28 2h-7l4 18h7z" fill="var(--medal)" opacity={unlocked ? 0.55 : 1} />
	<circle
		cx="20"
		cy="31"
		r="14"
		fill={unlocked ? 'var(--medal)' : 'var(--surface)'}
		stroke="var(--medal)"
		stroke-width="2"
	/>
	<circle cx="20" cy="31" r="9.5" fill="none" stroke={unlocked ? 'var(--surface)' : 'var(--rule)'} stroke-width="1.5" opacity="0.6" />
</svg>
