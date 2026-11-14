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
		bands?: [number, number][]; // x ranges (km) to shade, e.g. interval reps
		refLine?: { value: number; label: string } | null; // horizontal reference, e.g. average
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
		incrs,
		bands = [],
		refLine = null
	}: Props = $props();

	let el: HTMLDivElement;
	let readout = $state<string>('');
	const kmFmt = new Intl.NumberFormat('fr-FR', {
		maximumFractionDigits: 2,
		minimumFractionDigits: 2
	});

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
						{
							...axis,
							size: 52,
							...(incrs ? { incrs } : {}),
							values: (_, v) => v.map((n) => format(sign * n))
						}
					],
					series: [{}, { label: title, stroke: c.route, width: 2, points: { show: false } }],
					hooks: {
						// Shade bands under the series (drawClear runs before axes and series).
						drawClear: [
							(u) => {
								if (!bands.length) return;
								const ctx = u.ctx;
								ctx.save();
								ctx.fillStyle = c.routeSoft;
								const { top, height: h } = u.bbox;
								for (const [a, b] of bands) {
									const x0 = u.valToPos(a, 'x', true);
									const x1 = u.valToPos(b, 'x', true);
									ctx.fillRect(x0, top, Math.max(1, x1 - x0), h);
								}
								ctx.restore();
							}
						],
						// Reference line (e.g. average) over the series, labelled at the left.
						draw: [
							(u) => {
								if (!refLine) return;
								const y = u.valToPos(sign * refLine.value, 'y', true);
								const { left, top, width, height: h } = u.bbox;
								if (y < top || y > top + h) return;
								const ctx = u.ctx;
								const dpr = devicePixelRatio || 1;
								ctx.save();
								ctx.strokeStyle = c.ink;
								ctx.lineWidth = 1.5 * dpr;
								ctx.setLineDash([6 * dpr, 4 * dpr]);
								ctx.beginPath();
								ctx.moveTo(left, y);
								ctx.lineTo(left + width, y);
								ctx.stroke();
								ctx.setLineDash([]);
								ctx.font = `${600} ${12 * dpr}px "IBM Plex Sans Variable", sans-serif`;
								ctx.textAlign = 'right'; // uPlot leaves the axes' alignment set: be explicit
								ctx.textBaseline = 'bottom';
								const text = refLine.label;
								const tw = ctx.measureText(text).width;
								const pad = 4 * dpr;
								const tx = left + width - 6 * dpr;
								const ty = y - 4 * dpr;
								ctx.fillStyle = c.surface;
								ctx.fillRect(tx - tw - pad, ty - 15 * dpr, tw + 2 * pad, 15 * dpr);
								ctx.fillStyle = c.ink;
								ctx.fillText(text, tx, ty);
								ctx.restore();
							}
						],
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
