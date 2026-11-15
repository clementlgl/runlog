// Run with: pnpm test
import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
	addDays,
	expandLadder,
	ladderProgress,
	mondayOf,
	parsePace,
	plannedOn,
	stepOn
} from './training.ts';

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

const ladder = {
	tolerance_s: 3,
	recovery: '1:30',
	steps: [
		{ reps: 8, distance_m: 400, paces: ['4:45', '4:30', '4:15'] },
		{ reps: 8, distance_m: 500, paces: ['4:45', '4:30', '4:15'] }
	]
};
const run = (id: number, day: string, label: string, pace: number) => ({
	id,
	start_local: day + 'T18:00:00',
	workout_label: label,
	rep_pace_s_per_km: pace
});

test('ladder expansion', () => {
	const steps = expandLadder(ladder);
	assert.equal(steps.length, 6);
	assert.deepEqual(steps[3], {
		reps: 8,
		distance_m: 500,
		pace_s: 285,
		label: '8 × 500 m',
		key: '8 × 500 m@285'
	});
	assert.throws(() => parsePace('4.45'));
});

test('ladder progress', () => {
	const runs = [
		run(1, '2026-11-12', '8 × 400 m', 290), // misses 4:45 by more than 3 s
		run(2, '2026-11-19', '8 × 400 m', 287), // within tolerance of 4:45
		run(3, '2026-11-26', '8 × 400 m', 250), // beats 4:30
		run(4, '2026-12-03', '8 × 500 m', 250), // wrong distance for 4:15
		run(5, '2026-11-02', '8 × 400 m', 240) // a Monday, before run 2
	];
	let p = ladderProgress(runs, ladder);
	assert.equal(p.current, 0); // nothing validated without a click
	assert.equal(p.candidate?.runId, 5); // earliest qualifying session, any day

	p = ladderProgress(runs, ladder, [{ step_key: '8 × 400 m@285', day: '2026-11-19', run_id: 2 }]);
	assert.deepEqual(p.validated, [{ day: '2026-11-19', runId: 2, pace_s: 287 }]);
	assert.equal(p.candidate?.runId, 5); // older sessions still count

	p = ladderProgress(runs, ladder, [
		{ step_key: '8 × 400 m@285', day: '2026-11-19', run_id: 2 },
		{ step_key: '8 × 400 m@270', day: '2026-11-26', run_id: 3 },
		{ step_key: '8 × 400 m@255', day: '2026-11-27', run_id: 5 },
		{ step_key: '8 × 500 m@270', day: '2026-12-03', run_id: 4 } // not current: ignored
	]);
	assert.equal(p.current, 3);
	assert.equal(p.candidate?.runId, 4); // 8 × 500 m at 4:10 qualifies for 4:45

	p = ladderProgress(runs, ladder, [
		{ step_key: '8 × 400 m@285', day: '2026-11-19', run_id: 2 },
		{ step_key: '8 × 400 m@270', day: '2026-11-26', run_id: 3 },
		{ step_key: '8 × 400 m@255', day: '2026-11-27', run_id: 5 },
		{ step_key: '8 × 500 m@285', day: '2026-12-03', run_id: 4 }
	]);
	assert.equal(p.current, 4);
	assert.equal(p.candidate, null); // run 4 already used
});

test('upcoming steps', () => {
	const p = ladderProgress([run(2, '2026-11-19', '8 × 400 m', 280)], ladder, [
		{ step_key: '8 × 400 m@285', day: '2026-11-19', run_id: 2 }
	]);
	assert.equal(stepOn('2026-11-19', '2026-11-19', p), null); // done today
	assert.equal(stepOn('2026-11-26', '2026-11-20', p)?.pace_s, 270);
	assert.equal(stepOn('2026-12-03', '2026-11-20', p)?.pace_s, 255);
	assert.equal(stepOn('2026-12-10', '2026-11-20', p)?.label, '8 × 500 m');
	assert.equal(stepOn('2027-06-03', '2026-11-20', p)?.pace_s, 255); // last step repeats
	assert.equal(stepOn('2026-11-27', '2026-11-20', p), null); // Friday
});
