<script lang="ts">
	// One measure per chart (no dual axis). Charts sharing `syncKey` share the crosshair.
	import { onMount } from 'svelte';
	import 'uplot/dist/uPlot.min.css';
	import type uPlotType from 'uplot';
	import { onSchemeChange, readPalette } from '#lib/theme.js';

	type Props = {
		title: string;
		x: number[]; // km
		y: (number | null)[];
		unit: string;
		format?: (v: number) => string;
		invert?: boolean; // e.g. pace: faster (lower) is up
		syncKey?: string;
		onhover?: (idx: number | null) => void;
		height?: number;
		incrs?: number[]; // allowed y tick steps (e.g. 30 s / 60 s for pace)
	};

	let {
		title,
		x,
		y,
		unit,
		format = (v) => String(Math.round(v)),
		invert = false,
		syncKey = 'run',
		onhover,
		height = 150,
		incrs
	}: Props = $props();

	let el: HTMLDivElement;
	let readout = $state<string>('');
	const kmFmt = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2, minimumFractionDigits: 2 });

	onMount(() => {
		let plot: uPlotType | undefined;
		let ro: ResizeObserver | undefined;
		let uPlot: typeof uPlotType;

		// Inverted measures are plotted negated so ticks stay regular (uPlot's dir:-1 drops labels).
		const sign = invert ? -1 : 1;
		const build = () => {
			plot?.destroy();
			const c = readPalette();
			const axis = {
				stroke: c.muted,
				font: '12px "IBM Plex Sans Variable", sans-serif',
				grid: { stroke: c.rule, width: 1 },
				ticks: { show: false },
				border: { show: false }
			};
			plot = new uPlot(
				{
					width: el.clientWidth,
					height,
					legend: { show: false },
					padding: [8, 8, 0, 0],
					cursor: {
						sync: { key: syncKey, setSeries: false },
						points: { size: 9, fill: c.route, stroke: c.surface, width: 2 },
						drag: { x: false, y: false }
					},
					scales: { x: { time: false } },
					axes: [
						{ ...axis, values: (_, v) => v.map((n) => `${n} km`) },
						{ ...axis, size: 52, ...(incrs ? { incrs } : {}), values: (_, v) => v.map((n) => format(sign * n)) }
					],
					series: [{}, { label: title, stroke: c.route, width: 2, points: { show: false } }],
					hooks: {
						setCursor: [
							(u) => {
								const i = u.cursor.idx;
								if (i == null) {
									readout = '';
									onhover?.(null);
									return;
								}
								const v = y[i];
								readout = `${v == null ? '–' : `${format(v)} ${unit}`} à ${kmFmt.format(x[i])} km`;
								onhover?.(i);
							}
						]
					}
				},
				[x, (invert ? y.map((v) => (v == null ? null : -v)) : y) as number[]],
				el
			);
		};

		(async () => {
			uPlot = (await import('uplot')).default;
			await document.fonts.ready;
			build();
			ro = new ResizeObserver(() => plot?.setSize({ width: el.clientWidth, height }));
			ro.observe(el);
		})();
		const off = onSchemeChange(() => uPlot && build());
		return () => {
			off();
			ro?.disconnect();
			plot?.destroy();
		};
	});
</script>

<figure>
	<figcaption class="mb-1 flex flex-wrap items-baseline justify-between gap-x-4">
		<span class="font-medium">{title}</span>
		<span class="text-sm text-muted" aria-live="polite">{readout || unit}</span>
	</figcaption>
	<div bind:this={el} class="w-full" style="height:{height}px"></div>
</figure>
