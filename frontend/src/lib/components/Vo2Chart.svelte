<script lang="ts">
	// VO2max over time: the watch's value and our estimate, one point per run.
	import type { Run } from '#lib/api.js';

	let { runs }: { runs: Run[] } = $props();

	const W = 640;
	const H = 200;
	const pad = { l: 28, r: 8, t: 10, b: 22 };

	const pts = $derived(
		runs
			.filter((r) => r.vo2_max_watch || r.vo2max_est)
			.map((r) => ({
				t: new Date(r.start_local).getTime(),
				watch: r.vo2_max_watch,
				est: r.vo2max_est
			}))
			.sort((a, b) => a.t - b.t)
	);
	const values = $derived(
		pts.flatMap((p) => [p.watch, p.est]).filter((v): v is number => v != null)
	);
	const yMin = $derived(Math.floor((Math.min(...values) - 2) / 5) * 5);
	const yMax = $derived(Math.ceil((Math.max(...values) + 2) / 5) * 5);
	const t0 = $derived(pts[0]?.t ?? 0);
	const t1 = $derived(pts[pts.length - 1]?.t ?? 1);

	const x = (t: number) => pad.l + ((t - t0) / Math.max(1, t1 - t0)) * (W - pad.l - pad.r);
	const y = (v: number) => pad.t + (1 - (v - yMin) / (yMax - yMin)) * (H - pad.t - pad.b);
	const ticks = $derived(Array.from({ length: (yMax - yMin) / 5 + 1 }, (_, i) => yMin + i * 5));
	const line = (key: 'watch' | 'est') =>
		pts
			.filter((p) => p[key] != null)
			.map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)},${y(p[key]!).toFixed(1)}`)
			.join('');
	const monthFmt = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' });
	const xTicks = $derived(t1 > t0 ? [t0, (t0 + t1) / 2, t1] : [t0]);
</script>

{#if pts.length}
	<svg viewBox="0 0 {W} {H}" class="h-auto w-full" role="img" aria-label="VO2max par sortie">
		{#each ticks as v (v)}
			<line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} stroke="var(--rule)" />
			<text x={pad.l - 6} y={y(v) + 4} text-anchor="end" font-size="11" fill="var(--faint)"
				>{v}</text
			>
		{/each}
		{#each xTicks as t, i (t)}
			<text
				x={x(t)}
				y={H - 4}
				font-size="11"
				fill="var(--faint)"
				text-anchor={i === 0 ? 'start' : i === xTicks.length - 1 ? 'end' : 'middle'}
			>
				{monthFmt.format(new Date(t)).replace('.', '')}
			</text>
		{/each}
		<path
			d={line('est')}
			fill="none"
			stroke="var(--muted)"
			stroke-width="1.5"
			stroke-dasharray="4 3"
		/>
		<path d={line('watch')} fill="none" stroke="var(--route)" stroke-width="2" />
		{#each pts as p (p.t)}
			{#if p.est != null}
				<circle
					cx={x(p.t)}
					cy={y(p.est)}
					r="3"
					fill="var(--surface)"
					stroke="var(--muted)"
					stroke-width="1.5"
				>
					<title>Estimée : {p.est}</title>
				</circle>
			{/if}
			{#if p.watch != null}
				<circle cx={x(p.t)} cy={y(p.watch)} r="3" fill="var(--route)">
					<title>Montre : {p.watch}</title>
				</circle>
			{/if}
		{/each}
	</svg>
	<p class="mt-2 flex flex-wrap gap-x-5 text-xs text-muted">
		<span><span class="mr-1.5 inline-block h-0.5 w-4 bg-route align-middle"></span>Montre</span>
		<span>
			<span class="mr-1.5 inline-block w-4 border-t-[1.5px] border-dashed border-muted align-middle"
			></span>Estimée (allure et FC, hors fractionnés)
		</span>
	</p>
{/if}
