// Canvas/WebGL libraries can't read CSS variables: resolve them, and re-resolve on scheme change.

export type Palette = { route: string; ink: string; muted: string; faint: string; rule: string; surface: string };

export function readPalette(): Palette {
	const css = getComputedStyle(document.documentElement);
	const v = (name: string) => css.getPropertyValue(`--${name}`).trim();
	return { route: v('route'), ink: v('ink'), muted: v('muted'), faint: v('faint'), rule: v('rule'), surface: v('surface') };
}

export const prefersDark = () => matchMedia('(prefers-color-scheme: dark)').matches;

/** Calls `fn` whenever the colour scheme flips; returns an unsubscribe. */
export function onSchemeChange(fn: () => void): () => void {
	const mq = matchMedia('(prefers-color-scheme: dark)');
	mq.addEventListener('change', fn);
	return () => mq.removeEventListener('change', fn);
}
