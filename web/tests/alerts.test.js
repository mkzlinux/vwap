/**
 * Tests for the alert path - detectNewSignals(), which App.jsx calls to decide
 * what to raise.
 *
 * Alerts are a headline feature and were previously untested: the logic was
 * inline in a useEffect, so the only way to exercise it was to mount the whole
 * app. It now lives in engine.js and both the component and these tests call it.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { detectNewSignals } from '../src/engine.js';

const INSTRUMENTS = [
  { symbol: 'EURUSD', digits: 5 },
  { symbol: 'GER30', digits: 1 },
];

function sig(time, dir = 1) {
  return { time, dir, entry: 1.1, sl: 1.09, tp: 1.13, index: 1 };
}

function computedWith(entries) {
  const m = new Map();
  for (const [symbol, signals] of Object.entries(entries)) {
    m.set(symbol, { signals });
  }
  return m;
}

test('the first pass absorbs history and raises nothing', () => {
  const seen = new Map();
  const { alerts, primedNow } = detectNewSignals(
    INSTRUMENTS,
    computedWith({ EURUSD: [sig(100), sig(200), sig(300)], GER30: [sig(150)] }),
    seen,
    false, // not primed
  );

  assert.deepEqual(alerts, [], 'no alerts on the priming pass');
  assert.equal(primedNow, true, 'the pass marks the detector primed');

  // but the history is recorded, so it will not be re-raised later
  assert.equal(seen.get('EURUSD').size, 3);
  assert.equal(seen.get('GER30').size, 1);
});

test('a second pass raises only the signals that are new', () => {
  const seen = new Map();

  detectNewSignals(INSTRUMENTS, computedWith({ EURUSD: [sig(100), sig(200)] }), seen, false);

  const { alerts } = detectNewSignals(
    INSTRUMENTS,
    computedWith({ EURUSD: [sig(100), sig(200), sig(300)], GER30: [sig(250)] }),
    seen,
    true,
  );

  assert.equal(alerts.length, 2, 'one new EURUSD signal and one new GER30 signal');
  const times = alerts.map((a) => a.time).sort((a, b) => a - b);
  assert.deepEqual(times, [250, 300], 'exactly the unseen bar times');
});

test('a signal already alerted is never raised twice', () => {
  const seen = new Map();
  detectNewSignals(INSTRUMENTS, computedWith({ EURUSD: [sig(100)] }), seen, false);

  // same signal present across three further passes
  for (let i = 0; i < 3; i++) {
    const { alerts } = detectNewSignals(
      INSTRUMENTS,
      computedWith({ EURUSD: [sig(100)] }),
      seen,
      true,
    );
    assert.deepEqual(alerts, [], `pass ${i + 1} does not re-raise bar 100`);
  }
});

test('the alert payload carries what the UI renders', () => {
  const seen = new Map();
  detectNewSignals(INSTRUMENTS, computedWith({ EURUSD: [] }), seen, false);

  const s = { time: 400, dir: -1, entry: 18250.5, sl: 18290.0, tp: 18132.0, index: 7 };
  const { alerts } = detectNewSignals(
    INSTRUMENTS,
    computedWith({ GER30: [s] }),
    seen,
    true,
  );

  assert.equal(alerts.length, 1);
  const a = alerts[0];
  assert.equal(a.symbol, 'GER30');
  assert.equal(a.dir, -1, 'direction preserved');
  assert.equal(a.digits, 1, 'digits come from the instrument, not the signal');
  assert.equal(a.entry, 18250.5);
  assert.equal(a.sl, 18290.0);
  assert.equal(a.tp, 18132.0);
  assert.equal(a.id, 'GER30-400', 'id is unique per symbol and bar');
  assert.equal(a.time, 400);

  // the body string App.jsx builds for a browser notification must not throw
  const body = `entry ${a.entry.toFixed(a.digits)}  SL ${a.sl.toFixed(a.digits)}  TP ${a.tp.toFixed(a.digits)}`;
  assert.ok(body.includes('18250.5'), body);
});

test('ids do not collide across instruments on the same bar', () => {
  const seen = new Map();
  detectNewSignals(INSTRUMENTS, computedWith({}), seen, false);

  const { alerts } = detectNewSignals(
    INSTRUMENTS,
    computedWith({ EURUSD: [sig(500)], GER30: [sig(500)] }),
    seen,
    true,
  );

  assert.equal(alerts.length, 2);
  assert.notEqual(alerts[0].id, alerts[1].id, 'same bar time, different ids');
});

test('instruments with no signals are skipped without error', () => {
  const seen = new Map();
  const { alerts } = detectNewSignals(
    INSTRUMENTS,
    computedWith({ EURUSD: [], GER30: [] }),
    seen,
    true,
  );
  assert.deepEqual(alerts, []);

  // and an instrument missing from the computed map entirely
  const { alerts: a2 } = detectNewSignals(INSTRUMENTS, new Map(), seen, true);
  assert.deepEqual(a2, []);
});
