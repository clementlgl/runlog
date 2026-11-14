// Run with: pnpm test
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { speedRange, speedsAt } from './trackSpeed.ts';

// 60 s at 3 m/s, then 60 s at 4 m/s, one sample per second.
const samples = Array.from({ length: 121 }, (_, t) => ({
	t_s: t,
	distance_m: t <= 60 ? t * 3 : 180 + (t - 60) * 4
}));

test('speed follows the samples', () => {
	const [slow, fast] = speedsAt(samples, [20, 100]);
	assert.equal(slow, 3);
	assert.equal(fast, 4);
});

test('speed is averaged across a change and clamped at the ends', () => {
	assert.equal(speedsAt(samples, [60])[0], 3.5);
	assert.equal(speedsAt(samples, [0])[0], 3);
});

test('missing distances are skipped, none at all gives null', () => {
	const gappy = samples.map((s) => (s.t_s % 2 ? { ...s, distance_m: null } : s));
	assert.equal(speedsAt(gappy, [20])[0], 3);
	assert.deepEqual(speedsAt([{ t_s: 0, distance_m: null }], [0]), [null]);
});

test('range ignores stops and outliers', () => {
	const v = [0, 0.1, ...Array.from({ length: 100 }, (_, i) => 3 + i / 100), 25];
	const [lo, hi] = speedRange(v)!;
	assert.ok(lo >= 3 && lo < 3.1);
	assert.ok(hi > 3.9 && hi < 4);
	assert.equal(speedRange([3, 3, 3]), null);
});
