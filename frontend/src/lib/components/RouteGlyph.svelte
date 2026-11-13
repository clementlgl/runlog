<script lang="ts">
	// A run's GPS shape as a single stroke, fitted into a square. Purely decorative
	// next to the data it accompanies, so hidden from assistive tech.
	type Props = { points: [number, number][] | undefined; size?: number; stroke?: number; class?: string };
	let { points, size = 40, stroke = 1.75, class: cls = '' }: Props = $props();

	const d = $derived.by(() => {
		if (!points || points.length < 2) return '';
		// Equirectangular projection, longitudes shrunk by cos(lat).
		const lat0 = (points.reduce((a, p) => a + p[1], 0) / points.length) * (Math.PI / 180);
		const xy = points.map(([lon, lat]) => [lon * Math.cos(lat0), -lat]);
		const xs = xy.map((p) => p[0]);
		const ys = xy.map((p) => p[1]);
		const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
		const span = Math.max(x1 - x0, y1 - y0) || 1;
		const pad = stroke * 1.5;
		const k = (size - 2 * pad) / span;
		const ox = pad + (size - 2 * pad - (x1 - x0) * k) / 2;
		const oy = pad + (size - 2 * pad - (y1 - y0) * k) / 2;
		return xy
			.map(([x, y], i) => `${i ? 'L' : 'M'}${(ox + (x - x0) * k).toFixed(1)} ${(oy + (y - y0) * k).toFixed(1)}`)
			.join('');
	});
</script>

<svg
	viewBox="0 0 {size} {size}"
	width={size}
	height={size}
	class={cls}
	aria-hidden="true"
	fill="none"
	stroke="currentColor"
	stroke-width={stroke}
	stroke-linejoin="round"
	stroke-linecap="round"
>
	{#if d}<path {d} />{/if}
</svg>
