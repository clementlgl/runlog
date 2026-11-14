// Run with: pnpm test
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { addDays, mondayOf, plannedOn } from './training.ts';

test('weekly plan', () => {
	assert.equal(plannedOn('2026-11-09'), 'long'); // Monday
	assert.equal(plannedOn('2026-11-12'), 'intervals'); // Thursday
	assert.equal(plannedOn('2026-11-07'), 'test'); // first Saturday of November
	assert.equal(plannedOn('2026-11-14'), 'steady'); // second Saturday
	assert.equal(plannedOn('2026-11-10'), null); // Tuesday
});

test('week arithmetic', () => {
	assert.equal(mondayOf('2026-11-15'), '2026-11-09'); // Sunday
	assert.equal(mondayOf('2026-11-09'), '2026-11-09');
	assert.equal(addDays('2026-10-31', 1), '2026-11-01');
	assert.equal(addDays('2026-03-29', 1), '2026-03-30'); // across the DST change
});
