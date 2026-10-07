/**
 * Runtime tests for the parts of the dashboard that are not the pure engine:
 * the feed, and the box primitive's canvas geometry.
 *
 * These exercise the shipped modules directly. The canvas is mocked so the
 * primitive's drawing maths runs in Node without a browser, and every path
 * operation it issues is recorded and asserted on.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { SimulatedFeed, INSTRUMENTS, pointFor, applyFeedEvent } from '../src/feed.js';
import { buildSignals, summarise, ANCHOR } from '../src/engine.js';
import { BoxesPrimitive } from '../src/BoxesPrimitive.js';

test('simulated feed produces rolling bars for every instrument', () => {
  const feed = new SimulatedFeed({ barMs: 5000, history: 40, seed: 7 });
  const events = [];
  feed.subscribe((e) => events.push(e));
  feed.start();

  // a throwing assertion must not leave the interval running, or the whole
  // test runner hangs waiting on an event loop that never drains
  try {
  assert.ok(events.some((e) => e.type === 'ready'), 'emits ready');

  for (const inst of INSTRUMENTS) {
    const s = feed.series(inst.symbol);
    assert.ok(s.length >= 40, `${inst.symbol} has history, got ${s.length}`);

    // times strictly increasing, and each bar is internally consistent
    for (let i = 1; i < s.length; i++) {
      assert.ok(s[i].time > s[i - 1].time, `${inst.symbol} time ordering at ${i}`);
    }
    for (const b of s) {
      assert.ok(b.high >= Math.max(b.open, b.close), `${inst.symbol} high >= o/c`);
      assert.ok(b.low <= Math.min(b.open, b.close), `${inst.symbol} low <= o/c`);
      assert.ok(b.volume >= 0, `${inst.symbol} volume >= 0`);
      assert.ok(Number.isFinite(b.close), `${inst.symbol} close finite`);
    }
  }

  // prices stay in a sane neighbourhood of the configured base
  const eur = feed.series('EURUSD');
  const last = eur[eur.length - 1].close;
  assert.ok(Math.abs(last - 1.085) < 0.05, `EURUSD near base, got ${last}`);
  } finally {
    feed.stop();
  }
  assert.equal(feed.connected, false, 'stop disconnects');
});

/**
 * Regression test. The feed originally never emitted 'history', so App.jsx
 * seeded its bar store with a single bar and gained one per tick - the chart
 * opened with one candle. The earlier test missed it by calling feed.series()
 * directly, which bypasses the event path the app actually consumes.
 *
 * This drives the real feed through the real reducer.
 */
test('the app receives the full history through the event path', () => {
  const feed = new SimulatedFeed({ barMs: 5000, history: 260, seed: 3 });
  const store = new Map();
  let sawHistory = 0;
  feed.subscribe((evt) => {
    if (applyFeedEvent(store, evt) && evt.type === 'history') sawHistory++;
  });

  try {
    feed.start();

    assert.equal(sawHistory, INSTRUMENTS.length, 'one history payload per instrument');
    assert.equal(store.size, INSTRUMENTS.length, 'every instrument seeded');

    for (const inst of INSTRUMENTS) {
      const inFeed = feed.series(inst.symbol).length;
      const inApp = store.get(inst.symbol).length;
      // the defect: this was 1 while inFeed was 261
      assert.equal(inApp, inFeed, `${inst.symbol}: app has what the feed has`);
      assert.ok(inApp >= 260, `${inst.symbol} seeded with real history, got ${inApp}`);

      const t = store.get(inst.symbol).map((b) => b.time);
      assert.ok(
        t.every((v, i) => i === 0 || v > t[i - 1]),
        `${inst.symbol} times strictly ascending (chart requirement)`,
      );
    }
  } finally {
    feed.stop();
  }
});

test('applyFeedEvent folds bar updates without duplicating or skipping', () => {
  const store = new Map();

  applyFeedEvent(store, { type: 'history', symbol: 'X', bars: [{ time: 1 }, { time: 2 }] });
  assert.equal(store.get('X').length, 2);

  // same bar still forming -> replace in place, do not append
  applyFeedEvent(store, { type: 'bar', symbol: 'X', bar: { time: 2, close: 9 }, closed: false });
  assert.equal(store.get('X').length, 2, 'no duplicate for the forming bar');
  assert.equal(store.get('X')[1].close, 9, 'forming bar updated in place');

  // bar closes -> overwrite the placeholder
  applyFeedEvent(store, { type: 'bar', symbol: 'X', bar: { time: 2, close: 10 }, closed: true });
  assert.equal(store.get('X').length, 2, 'closing does not append');
  assert.equal(store.get('X')[1].close, 10, 'closed bar replaces the placeholder');

  // a new bar opens -> append
  applyFeedEvent(store, { type: 'bar', symbol: 'X', bar: { time: 3 }, closed: false });
  assert.equal(store.get('X').length, 3, 'new bar appends');

  // first event for an unknown symbol must not throw
  applyFeedEvent(store, { type: 'bar', symbol: 'NEW', bar: { time: 5 }, closed: false });
  assert.deepEqual(store.get('NEW'), [{ time: 5 }]);

  // non-data events report no change
  assert.equal(applyFeedEvent(store, { type: 'ready' }), false);
  assert.equal(applyFeedEvent(store, { type: 'error', message: 'x' }), false);
  assert.equal(applyFeedEvent(store, { type: 'history', symbol: 'X', bars: [] }), true);
});

test('feed + engine together yield signals and a consistent tally', () => {
  const feed = new SimulatedFeed({ barMs: 5000, history: 200, seed: 11 });
  feed.start();
  feed.stop(); // history is generated synchronously, so stop immediately

  let anySignal = false;
  for (const inst of INSTRUMENTS) {
    const bars = feed.series(inst.symbol);
    const { vwap, ema, signals, lastClosed } = buildSignals(bars, {
      anchor: ANCHOR.DAILY_MIDNIGHT,
      point: pointFor(inst.digits),
      emaPeriod: 9,
      atrPeriod: 14,
      slAtrMult: 1.5,
      rewardR: 3,
    });

    assert.equal(vwap.length, bars.length, `${inst.symbol} vwap aligned`);
    assert.equal(ema.length, bars.length, `${inst.symbol} ema aligned`);
    assert.equal(lastClosed, bars.length - 2);

    for (const s of signals) {
      anySignal = true;
      assert.ok([1, -1].includes(s.dir), 'direction is a sign');
      assert.ok(s.atr > 0, `${inst.symbol} atr positive`);

      // long: stop below entry, target above; short: mirrored
      if (s.dir > 0) {
        assert.ok(s.sl < s.entry, 'long stop below entry');
        assert.ok(s.tp > s.entry, 'long target above entry');
      } else {
        assert.ok(s.sl > s.entry, 'short stop above entry');
        assert.ok(s.tp < s.entry, 'short target below entry');
      }

      // the box is always 1:3 - the target is three times the stop distance
      const risk = Math.abs(s.entry - s.sl);
      assert.ok(Math.abs(Math.abs(s.tp - s.entry) / risk - 3) < 1e-9, '1:3 geometry');

      // signals only ever fire on closed bars
      assert.ok(s.index <= lastClosed, 'signal is on a closed bar');
    }

    const sum = summarise(signals, 3);
    assert.equal(sum.tp + sum.sl + sum.open, signals.length, 'tally covers all');
  }

  assert.ok(anySignal, 'the demo series produces at least one signal');
});

// --- box primitive geometry -------------------------------------------------

function mockContext() {
  const ops = [];
  const rec = (name) => (...args) => ops.push({ name, args });
  const ctx = {
    save: rec('save'),
    restore: rec('restore'),
    beginPath: rec('beginPath'),
    moveTo: rec('moveTo'),
    lineTo: rec('lineTo'),
    stroke: rec('stroke'),
    fillRect: rec('fillRect'),
    fillText: rec('fillText'),
    setLineDash: rec('setLineDash'),
    fillStyle: null,
    strokeStyle: null,
    lineWidth: 0,
    font: null,
    globalAlpha: 1,
  };
  return { ctx, ops };
}

function drawBoxes(boxes, { width = 800, height = 600 } = {}) {
  const { ctx, ops } = mockContext();

  // price -> y: linear, 90..110 mapped onto the pane, inverted like a chart
  const priceToY = (p) => ((110 - p) / (110 - 90)) * height;
  const timeToX = (t) => t; // times are used directly as x for the test

  const prim = new BoxesPrimitive(boxes);
  prim.attached({
    chart: { timeScale: () => ({ timeToCoordinate: timeToX }) },
    series: { priceToCoordinate: priceToY },
    requestUpdate: () => {},
  });

  const views = prim.paneViews();
  views[0].renderer.draw({
    useMediaCoordinateSpace: (fn) => fn({ context: ctx, mediaSize: { width, height } }),
  });

  return ops;
}

test('box primitive draws a profit rect above and a loss rect below', () => {
  const ops = drawBoxes([
    { startTime: 100, endTime: 200, entry: 100, sl: 98, tp: 106, dir: 1, resolved: false },
  ]);

  const rects = ops.filter((o) => o.name === 'fillRect');
  assert.equal(rects.length, 2, 'exactly two filled zones');

  // canvas y grows downward, so the target (higher price) has the smaller y
  const [profit, loss] = rects;
  assert.ok(profit.args[1] < loss.args[1], 'profit zone sits above the loss zone');

  // the profit zone is 3x the loss zone's height for a 1:3 box
  assert.ok(Math.abs(profit.args[3] / loss.args[3] - 3) < 1e-9, 'green is 3x the red');

  // both zones span the same x range and start at entry
  assert.equal(profit.args[0], loss.args[0], 'same left edge');
  assert.equal(profit.args[2], loss.args[2], 'same width');
  assert.equal(profit.args[2], 100, 'width is endTime - startTime');

  // TP / SL labels are drawn
  const texts = ops.filter((o) => o.name === 'fillText').map((o) => o.args[0]);
  assert.ok(texts.includes('TP'), 'TP label');
  assert.ok(texts.includes('SL'), 'SL label');
});

test('box primitive mirrors for a short signal', () => {
  const ops = drawBoxes([
    { startTime: 100, endTime: 200, entry: 100, sl: 102, tp: 94, dir: -1, resolved: false },
  ]);

  const rects = ops.filter((o) => o.name === 'fillRect');
  const [profit, loss] = rects;
  // short: target is a lower price => larger canvas y => below entry
  assert.ok(profit.args[1] > loss.args[1], 'short profit zone sits below the loss zone');
  assert.ok(Math.abs(profit.args[3] / loss.args[3] - 3) < 1e-9, 'still 1:3');
});

test('box primitive draws nothing when off-screen or empty', () => {
  // timeToCoordinate returns null for times outside the visible range
  const { ctx, ops } = mockContext();
  const prim = new BoxesPrimitive([
    { startTime: 100, endTime: 200, entry: 100, sl: 98, tp: 106, dir: 1, resolved: false },
  ]);
  prim.attached({
    chart: { timeScale: () => ({ timeToCoordinate: () => null }) },
    series: { priceToCoordinate: () => 10 },
    requestUpdate: () => {},
  });
  prim.paneViews()[0].renderer.draw({
    useMediaCoordinateSpace: (fn) => fn({ context: ctx, mediaSize: { width: 800, height: 600 } }),
  });
  assert.equal(ops.filter((o) => o.name === 'fillRect').length, 0, 'off-screen draws no rect');

  // empty box list
  const empty = drawBoxes([]);
  assert.equal(empty.length, 0, 'no boxes, no draw calls');
});

test('box primitive dims resolved boxes and calls requestUpdate on update', () => {
  const { ctx, ops } = mockContext();
  let updates = 0;
  const prim = new BoxesPrimitive([]);
  prim.attached({
    chart: { timeScale: () => ({ timeToCoordinate: (t) => t }) },
    series: { priceToCoordinate: (p) => ((110 - p) / 20) * 600 },
    requestUpdate: () => { updates++; },
  });

  prim.update([{ startTime: 100, endTime: 200, entry: 100, sl: 98, tp: 106, dir: 1, resolved: true }]);
  assert.equal(updates, 1, 'update() requests a repaint');

  prim.paneViews()[0].renderer.draw({
    useMediaCoordinateSpace: (fn) => fn({ context: ctx, mediaSize: { width: 800, height: 600 } }),
  });
  assert.ok(ops.some((o) => o.name === 'save'), 'canvas state saved');
  assert.ok(ops.some((o) => o.name === 'restore'), 'canvas state restored');
  assert.ok(ctx.globalAlpha < 1, 'resolved box is dimmed');
});

test('detached primitive releases its handles', () => {
  const prim = new BoxesPrimitive([]);
  prim.attached({
    chart: {},
    series: {},
    requestUpdate: () => {},
  });
  prim.detached();
  // drawing after detach must not throw
  prim.paneViews()[0].renderer.draw({
    useMediaCoordinateSpace: (fn) => fn({ context: mockContext().ctx, mediaSize: { width: 1, height: 1 } }),
  });
});
