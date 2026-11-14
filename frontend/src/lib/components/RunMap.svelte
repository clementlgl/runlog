<script lang="ts">
	// GPS track on OpenFreeMap tiles (no API key). `cursor` = [lon, lat] marker synced with charts.
	import { onMount } from 'svelte';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import type { Map as MapType, Marker } from 'maplibre-gl';
	import { onSchemeChange, prefersDark, readPalette } from '#lib/theme.js';
	import { SPEED_COLORS } from '#lib/trackSpeed.js';

	type Props = {
		track: [number, number][];
		cursor?: [number, number] | null;
		highlights?: [number, number][][]; // e.g. interval reps; the rest of the track is muted
		speeds?: (number | null)[]; // m/s at each track point, for colouring by speed
		speedRange?: [number, number] | null; // m/s mapped to the slow and fast ends of the scale
		bySpeed?: boolean; // colour the track by speed instead of the plain route
	};
	let {
		track,
		cursor = null,
		highlights = [],
		speeds = [],
		speedRange = null,
		bySpeed = false
	}: Props = $props();

	let el: HTMLDivElement;
	let map: MapType | undefined;
	let marker: Marker | undefined;

	const styleUrl = () =>
		`https://tiles.openfreemap.org/styles/${prefersDark() ? 'dark' : 'positron'}`;

	// One two-point segment per stretch of track, carrying its average speed.
	function speedSegments() {
		const features = [];
		for (let i = 1; i < track.length; i++) {
			const a = speeds[i - 1];
			const b = speeds[i];
			if (a == null || b == null) continue;
			features.push({
				type: 'Feature' as const,
				properties: { v: (a + b) / 2 },
				geometry: { type: 'LineString' as const, coordinates: [track[i - 1], track[i]] }
			});
		}
		return { type: 'FeatureCollection' as const, features };
	}

	function applyMode(m: MapType) {
		const speed = bySpeed && !!speedRange;
		const vis = (on: boolean) => (on ? 'visible' : 'none');
		for (const id of ['track', 'highlights'])
			if (m.getLayer(id)) m.setLayoutProperty(id, 'visibility', vis(!speed));
		if (m.getLayer('track-speed')) m.setLayoutProperty('track-speed', 'visibility', vis(speed));
	}

	function addTrack(m: MapType) {
		const c = readPalette();
		if (!m.getSource('track'))
			m.addSource('track', {
				type: 'geojson',
				data: {
					type: 'Feature',
					properties: {},
					geometry: { type: 'LineString', coordinates: track }
				}
			});
		const layout = { 'line-join': 'round', 'line-cap': 'round' } as const;
		// Surface-coloured casing keeps the route legible over busy tiles.
		m.addLayer({
			id: 'track-casing',
			type: 'line',
			source: 'track',
			layout,
			paint: { 'line-color': c.surface, 'line-width': 7 }
		});
		const hl = highlights.length > 0;
		m.addLayer({
			id: 'track',
			type: 'line',
			source: 'track',
			layout,
			paint: { 'line-color': hl ? c.faint : c.route, 'line-width': hl ? 2.5 : 3.5 }
		});
		if (hl) {
			if (!m.getSource('highlights'))
				m.addSource('highlights', {
					type: 'geojson',
					data: {
						type: 'Feature',
						properties: {},
						geometry: { type: 'MultiLineString', coordinates: highlights }
					}
				});
			m.addLayer({
				id: 'highlights',
				type: 'line',
				source: 'highlights',
				layout,
				paint: { 'line-color': c.route, 'line-width': 4 }
			});
		}
		if (speedRange) {
			const [lo, hi] = speedRange;
			if (!m.getSource('speed')) m.addSource('speed', { type: 'geojson', data: speedSegments() });
			m.addLayer({
				id: 'track-speed',
				type: 'line',
				source: 'speed',
				layout,
				paint: {
					'line-width': 4,
					'line-color': [
						'interpolate',
						['linear'],
						['get', 'v'],
						lo,
						SPEED_COLORS[0],
						(lo + hi) / 2,
						SPEED_COLORS[1],
						hi,
						SPEED_COLORS[2]
					]
				}
			});
		}
		applyMode(m);
	}

	const pin = (label: string, title: string) => {
		const d = document.createElement('div');
		d.className =
			'grid size-6 place-items-center rounded-full border-2 border-surface bg-ink text-[11px] font-semibold text-surface';
		d.textContent = label;
		d.title = title;
		return d;
	};

	onMount(() => {
		let off = () => {};
		(async () => {
			const [maplibre, { default: workerUrl }] = await Promise.all([
				import('maplibre-gl'),
				// Bundling moves the ESM build away from its worker file: point at it explicitly.
				import('maplibre-gl/dist/maplibre-gl-worker.mjs?url')
			]);
			maplibre.setWorkerUrl(workerUrl);
			const lons = track.map((p) => p[0]);
			const lats = track.map((p) => p[1]);
			map = new maplibre.Map({
				container: el,
				style: styleUrl(),
				bounds: [
					[Math.min(...lons), Math.min(...lats)],
					[Math.max(...lons), Math.max(...lats)]
				],
				fitBoundsOptions: { padding: 40 },
				cooperativeGestures: true, // page scroll stays page scroll
				attributionControl: { compact: true }
			});
			map.addControl(new maplibre.NavigationControl({ showCompass: false }), 'top-right');
			map.on('style.load', () => addTrack(map!));
			new maplibre.Marker({ element: pin('D', 'Départ') }).setLngLat(track[0]).addTo(map);
			new maplibre.Marker({ element: pin('A', 'Arrivée') })
				.setLngLat(track[track.length - 1])
				.addTo(map);
			const c = document.createElement('div');
			c.className = 'size-4 rounded-full border-2 border-surface bg-route';
			marker = new maplibre.Marker({ element: c });
			off = onSchemeChange(() => map?.setStyle(styleUrl()));
		})();
		return () => {
			off();
			map?.remove();
		};
	});

	$effect(() => {
		void bySpeed; // re-run when the mode changes
		if (map?.isStyleLoaded()) applyMode(map);
	});

	$effect(() => {
		const c = cursor; // read first: Svelte only tracks what the effect reads
		if (!map || !marker) return;
		if (c) marker.setLngLat(c).addTo(map);
		else marker.remove();
	});
</script>

<div
	bind:this={el}
	class="h-80 w-full overflow-hidden rounded-2xl bg-surface sm:h-[26rem]"
	role="img"
	aria-label="Carte du parcours"
></div>
