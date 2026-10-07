/**
 * Ports the assertions from tools/test_vwap_core.py, which executes the real
 * VwapCore.mqh under gcc. Same synthetic series, same expected behaviour, so a
 * divergence between the MT5 indicator and this browser engine fails here.
 *
 * Run: cd web && npm test
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  ANCHOR, ENTRY_MODE, AMBIG,
  typicalPrice, vwapSessionStart, computeVwap, computeEma, atrAt,
  signalAt, evaluateOutcome, buildSignals, summarise,
} from '../src/engine.js';

// 2024-01-08 00:00 UTC is a Monday. 30 hourly bars from there.
const T0 = 1704672000;
const N = 30;

function makeBars() {
  const bars = [];
  for (let i = 0; i < N; i++) {
    const open = 100.0 + i * 0.5;
    bars.push({
      time: T0 + i * 3600,
      open,
      high: open + 1.0,
      low: open - 1.0,
      close: open + 0.25,
      volume: 10 + ((i * 7) % 13),
    });
  }
  return bars;
}

/** Independent textbook VWAP over an explicit window - shares no code with
 *  computeVwap, so it is a genuine cross-check. */
function naiveVwap(bars, a, b) {
  let pv = 0, vv = 0;
  for (let i = a; i <= b; i++) {
    const bar = bars[i];
    pv += ((bar.open + bar.high + bar.low + bar.close) / 4) * bar.volume;
    vv += bar.volume;
  }
  return vv > 0 ? pv / vv : 0;
}

test('1. typical price is (O+H+L+C)/4', () => {
  const b = makeBars()[0];
  assert.equal(typicalPrice(b), (b.open + b.high + b.low + b.close) / 4);
  assert.ok(Math.abs(typicalPrice(b) - 100.0625) < 1e-12);
});

test('2. session anchors', () => {
  const bars = makeBars();

  // bar 0 = Mon 00:00; bar 23 = Mon 23:00 -> same daily session.
  assert.equal(vwapSessionStart(bars[0].time, ANCHOR.DAILY_MIDNIGHT), T0);
  assert.equal(vwapSessionStart(bars[23].time, ANCHOR.DAILY_MIDNIGHT), T0);

  // Session start 13:00. bar 10 is Mon 10:00, before 13:00, so it belongs to
  // the previous day's session (Sun 13:00).
  assert.equal(
    vwapSessionStart(bars[10].time, ANCHOR.DAILY_CUSTOM, 13, 0),
    T0 - 86400 + 13 * 3600,
  );
  // bar 13 is Mon 13:00 exactly -> its own session start.
  assert.equal(vwapSessionStart(bars[13].time, ANCHOR.DAILY_CUSTOM, 13, 0), bars[13].time);
  // bar 20 is Mon 20:00 -> same session as bar 13.
  assert.equal(vwapSessionStart(bars[20].time, ANCHOR.DAILY_CUSTOM, 13, 0), bars[13].time);

  // Weekly: the whole Monday anchors to Monday 00:00.
  assert.equal(vwapSessionStart(bars[0].time, ANCHOR.WEEKLY), T0);
  assert.equal(vwapSessionStart(bars[23].time, ANCHOR.WEEKLY), T0);
  // A Wednesday 09:00 rolls back to that same Monday.
  const wed = T0 + 2 * 86400 + 9 * 3600;
  assert.equal(vwapSessionStart(wed, ANCHOR.WEEKLY), T0);
  // A Sunday belongs to the PREVIOUS Monday.
  const sun = T0 - 86400 + 12 * 3600;
  assert.equal(vwapSessionStart(sun, ANCHOR.WEEKLY), T0 - 7 * 86400);
});

test('3. daily VWAP accumulates over the session', () => {
  const bars = makeBars();
  const vwap = computeVwap(bars, { anchor: ANCHOR.DAILY_MIDNIGHT });

  // bars 0..23 are Monday -> one accumulating session.
  for (let i = 0; i < 24; i++) {
    assert.ok(Math.abs(vwap[i] - naiveVwap(bars, 0, i)) < 1e-9, `bar ${i}`);
  }
  // bars 24..29 are Tuesday -> a fresh session.
  for (let i = 24; i < N; i++) {
    assert.ok(Math.abs(vwap[i] - naiveVwap(bars, 24, i)) < 1e-9, `bar ${i}`);
  }
});

test('4. custom 13:00 session resets mid-series', () => {
  const bars = makeBars();
  const vwap = computeVwap(bars, { anchor: ANCHOR.DAILY_CUSTOM, startHour: 13 });

  for (let i = 0; i < 13; i++) {
    assert.ok(Math.abs(vwap[i] - naiveVwap(bars, 0, i)) < 1e-9, `bar ${i} from bar0`);
  }
  for (let i = 13; i < N; i++) {
    assert.ok(Math.abs(vwap[i] - naiveVwap(bars, 13, i)) < 1e-9, `bar ${i} resets at bar13`);
  }
});

test('5. weekly VWAP never resets inside the week', () => {
  const bars = makeBars();
  const vwap = computeVwap(bars, { anchor: ANCHOR.WEEKLY });
  for (let i = 0; i < N; i++) {
    assert.ok(Math.abs(vwap[i] - naiveVwap(bars, 0, i)) < 1e-9, `bar ${i}`);
  }
});

test('6. rolling window of 5 bars', () => {
  const bars = makeBars();
  const vwap = computeVwap(bars, { anchor: ANCHOR.ROLLING, rollingBars: 5 });
  for (let i = 0; i < N; i++) {
    const a = Math.max(0, i - 4);
    assert.ok(Math.abs(vwap[i] - naiveVwap(bars, a, i)) < 1e-9, `bar ${i} window ${a}..${i}`);
  }
});

test('7. zero-volume bars do not break the line', () => {
  const bars = makeBars();

  const allZero = bars.map((b) => ({ ...b, volume: 0 }));
  const vwapZero = computeVwap(allZero, { anchor: ANCHOR.DAILY_MIDNIGHT });
  for (let i = 0; i < 3; i++) {
    assert.ok(Math.abs(vwapZero[i] - typicalPrice(bars[i])) < 1e-12, `bar ${i} falls back to TP`);
  }

  // A single zero-volume bar inside a live session is simply skipped.
  const partial = bars.map((b, i) => (i === 2 ? { ...b, volume: 0 } : b));
  const vwap = computeVwap(partial, { anchor: ANCHOR.DAILY_MIDNIGHT });
  let pv = 0, vv = 0;
  for (let i = 0; i <= 5; i++) {
    if (partial[i].volume > 0) {
      pv += typicalPrice(partial[i]) * partial[i].volume;
      vv += partial[i].volume;
    }
  }
  assert.ok(Math.abs(vwap[5] - pv / vv) < 1e-9);
});

// --- outcome marking: mirrors group 9 of test_vwap_core.py ---

function flatBars(n = 10, high = 101.0, low = 99.0) {
  return Array.from({ length: n }, () => ({ high, low }));
}

test('8. outcome marking: which level price reaches first', () => {
  // long: entry 100, stop 98, target 106
  let bars = flatBars();
  let r = evaluateOutcome({ dir: 1, sigBar: 0, lastClosed: 9, sl: 98, tp: 106, bars });
  assert.deepEqual(r, { outcome: 0, hitBar: 0 }, 'no level touched -> still open');

  bars[4].high = 106.5;
  r = evaluateOutcome({ dir: 1, sigBar: 0, lastClosed: 9, sl: 98, tp: 106, bars });
  assert.deepEqual(r, { outcome: 1, hitBar: 4 }, 'high >= TP on bar 4');
  bars[4].high = 101.0;

  bars[6].low = 97.5;
  r = evaluateOutcome({ dir: 1, sigBar: 0, lastClosed: 9, sl: 98, tp: 106, bars });
  assert.deepEqual(r, { outcome: -1, hitBar: 6 }, 'low <= SL on bar 6');

  bars[8].high = 106.5; // l[6] still low: stop came first
  r = evaluateOutcome({ dir: 1, sigBar: 0, lastClosed: 9, sl: 98, tp: 106, bars });
  assert.deepEqual(r, { outcome: -1, hitBar: 6 }, 'SL on 6 before TP on 8');
  bars[6].low = 99.0;
  bars[8].high = 101.0;

  bars[3].high = 106.5;
  bars[7].low = 97.5; // target came first
  r = evaluateOutcome({ dir: 1, sigBar: 0, lastClosed: 9, sl: 98, tp: 106, bars });
  assert.deepEqual(r, { outcome: 1, hitBar: 3 }, 'TP on 3 before SL on 7');

  bars[3].high = 101.0;
  bars[7].low = 99.0;
  bars[9].high = 106.5;
  r = evaluateOutcome({ dir: 1, sigBar: 0, lastClosed: 8, sl: 98, tp: 106, bars });
  assert.deepEqual(r, { outcome: 0, hitBar: 0 }, 'TP only on bar 9 but lastClosed=8');
  bars[9].high = 101.0;

  bars[0].high = 110.0;
  bars[0].low = 90.0; // the signal bar itself spans both
  r = evaluateOutcome({ dir: 1, sigBar: 0, lastClosed: 9, sl: 98, tp: 106, bars });
  assert.deepEqual(r, { outcome: 0, hitBar: 0 }, 'signal bar spans both -> not a hit');

  // short: entry 100, stop 102, target 94
  bars = flatBars();
  bars[5].low = 93.5;
  r = evaluateOutcome({ dir: -1, sigBar: 0, lastClosed: 9, sl: 102, tp: 94, bars });
  assert.deepEqual(r, { outcome: 1, hitBar: 5 }, 'short low <= TP');
  bars[5].low = 99.0;

  bars[5].high = 102.5;
  r = evaluateOutcome({ dir: -1, sigBar: 0, lastClosed: 9, sl: 102, tp: 94, bars });
  assert.deepEqual(r, { outcome: -1, hitBar: 5 }, 'short high >= SL');

  // one bar spanning both levels: the assumption decides
  bars[2].high = 106.5;
  bars[2].low = 97.5;
  r = evaluateOutcome({ dir: 1, sigBar: 0, lastClosed: 9, sl: 98, tp: 106, bars, ambiguous: AMBIG.SL_FIRST });
  assert.deepEqual(r, { outcome: -1, hitBar: 2 }, 'ambiguous, SL-first');
  r = evaluateOutcome({ dir: 1, sigBar: 0, lastClosed: 9, sl: 98, tp: 106, bars, ambiguous: AMBIG.TP_FIRST });
  assert.deepEqual(r, { outcome: 1, hitBar: 2 }, 'ambiguous, TP-first');
});

test('9. exact-touch boundary counts as a hit', () => {
  let bars = flatBars();
  bars[4].low = 98.0; // low == stop exactly
  let r = evaluateOutcome({ dir: 1, sigBar: 0, lastClosed: 9, sl: 98, tp: 106, bars });
  assert.deepEqual(r, { outcome: -1, hitBar: 4 }, 'low exactly == SL');
  bars[4].low = 99.0;

  bars[4].high = 106.0; // high == target exactly
  r = evaluateOutcome({ dir: 1, sigBar: 0, lastClosed: 9, sl: 98, tp: 106, bars });
  assert.deepEqual(r, { outcome: 1, hitBar: 4 }, 'high exactly == TP');
  bars[4].high = 101.0;

  bars[4].low = 98.0000001; // one tick short
  r = evaluateOutcome({ dir: 1, sigBar: 0, lastClosed: 9, sl: 98, tp: 106, bars });
  assert.deepEqual(r, { outcome: 0, hitBar: 0 }, 'a tick above SL -> still open');

  bars = flatBars();
  bars[3].high = 102.0; // short: high == stop exactly
  r = evaluateOutcome({ dir: -1, sigBar: 0, lastClosed: 9, sl: 102, tp: 94, bars });
  assert.equal(r.outcome, -1, 'short high exactly == SL');

  bars[3].high = 101.0;
  bars[3].low = 94.0; // short: low == target exactly
  r = evaluateOutcome({ dir: -1, sigBar: 0, lastClosed: 9, sl: 102, tp: 94, bars });
  assert.equal(r.outcome, 1, 'short low exactly == TP');
});

test('10. EMA is SMA-seeded and converges', () => {
  const bars = makeBars();
  const ema = computeEma(bars, 9, 'close');

  // warm-up bars carry no value
  for (let i = 0; i < 8; i++) assert.equal(ema[i], null, `bar ${i}`);
  // first value is the SMA of the first 9 closes
  let sum = 0;
  for (let i = 0; i < 9; i++) sum += bars[i].close;
  assert.ok(Math.abs(ema[8] - sum / 9) < 1e-12, 'SMA seed');

  // recursion holds after the seed
  const k = 2 / 10;
  for (let i = 9; i < N; i++) {
    assert.ok(Math.abs(ema[i] - (ema[i - 1] + k * (bars[i].close - ema[i - 1]))) < 1e-12, `bar ${i}`);
  }

  // typical-price source differs from close source
  const emaTyp = computeEma(bars, 9, 'typical');
  assert.notEqual(emaTyp[N - 1], ema[N - 1]);
});

test('11. ATR averages true range and skips the first bar', () => {
  const bars = makeBars();
  // every bar has range 2.0 and the previous close is 0.5 away, so TR is 2.0
  assert.ok(Math.abs(atrAt(bars, 20, 14) - 2.0) < 1e-12);
  assert.equal(atrAt(bars, 0, 14), 0, 'bar 0 has no previous close');
});

test('12. entry modes fire on the expected bars', () => {
  // A series that crosses VWAP cleanly: falling then rising.
  const bars = [];
  for (let i = 0; i < 60; i++) {
    const drift = i < 30 ? -0.05 : 0.05;
    const open = 100 + drift * i;
    bars.push({
      time: T0 + i * 3600,
      open,
      high: open + 0.4,
      low: open - 0.4,
      close: open + (i < 30 ? -0.1 : 0.1),
      volume: 100,
    });
  }

  const vwap = computeVwap(bars, { anchor: ANCHOR.WEEKLY });
  const ema = computeEma(bars, 9, 'close');

  const crosses = [];
  for (let i = 1; i < bars.length; i++) {
    const s = signalAt(i, bars, vwap, ema, { mode: ENTRY_MODE.EMA_CROSS_VWAP, point: 0.00001 });
    if (s !== 0) crosses.push({ i, s });
  }
  assert.ok(crosses.length >= 1, 'a cross occurs');
  assert.ok(crosses.some((c) => c.s === 1), 'a long cross occurs on the rally');
});

test('13. buildSignals and summarise agree with the manual tally', () => {
  const bars = makeBars();
  const { signals, lastClosed } = buildSignals(bars, {
    anchor: ANCHOR.DAILY_MIDNIGHT,
    emaPeriod: 9,
    atrPeriod: 14,
    slAtrMult: 1.5,
    rewardR: 3,
    point: 0.01,
  });

  assert.equal(lastClosed, bars.length - 2);
  for (const s of signals) {
    // entry is the signal bar's close
    assert.equal(s.entry, bars[s.index].close);
    // target is exactly rewardR times the stop distance
    const risk = Math.abs(s.entry - s.sl);
    assert.ok(Math.abs(Math.abs(s.tp - s.entry) - risk * 3) < 1e-9, 'R:R is 1:3');
    // outcome only ever resolves on a bar after the signal
    if (s.outcome !== 0) assert.ok(s.hitBar > s.index, 'hit bar is after the signal');
    else assert.equal(s.hitBar, 0);
  }

  const sum = summarise(signals, 3);
  assert.equal(sum.tp + sum.sl + sum.open, signals.length);
  if (sum.resolved > 0) {
    assert.ok(Math.abs(sum.hitRate - sum.tp / sum.resolved) < 1e-12);
    assert.ok(Math.abs(sum.expectancy - (sum.tp * 3 - sum.sl) / sum.resolved) < 1e-12);
  }
});
