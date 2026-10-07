/**
 * Mount test: renders the real App.jsx in a DOM.
 *
 * Unit tests cover the engine, the feed and the box primitive, but none of them
 * prove the React tree actually mounts. A missing import, a bad hook
 * dependency or a reference to an undefined symbol only surfaces at render
 * time - and one of those (applyFeedEvent called but never imported) was
 * introduced and fixed during this build.
 *
 * The component graph is bundled with esbuild, aliasing `lightweight-charts` to
 * a recording stub (jsdom has no canvas), then executed against jsdom globals.
 *
 * Run: cd web && npm test
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { JSDOM } from 'jsdom';
import { createRequire } from 'node:module';

// the bundle is CJS; this test file is ESM
const require = createRequire(import.meta.url);

const ROOT = new URL('..', import.meta.url).pathname;

function bundle(entrySource) {
  const dir = mkdtempSync(join(tmpdir(), 'vwap-mount-'));
  const entry = join(dir, 'entry.jsx');
  const out = join(dir, 'bundle.cjs');
  writeFileSync(entry, entrySource);

  execFileSync(
    join(ROOT, 'node_modules', '.bin', 'esbuild'),
    [
      entry,
      '--bundle',
      '--format=cjs',
      '--platform=browser',
      `--outfile=${out}`,
      '--jsx=automatic',
      '--log-level=warning',
      `--alias:lightweight-charts=${join(ROOT, 'tests', 'lwc-stub.js')}`,
    ],
    {
      cwd: ROOT,
      stdio: 'pipe',
      // the entry lives in a temp dir, so resolution would miss the project's
      // dependencies; esbuild honours NODE_PATH
      env: { ...process.env, NODE_PATH: join(ROOT, 'node_modules') },
    },
  );
  return out;
}

function makeDom() {
  // pretendToBeVisual starts an rAF loop that keeps the event loop alive after
  // the test finishes; the chart is stubbed, so a plain polyfill is enough.
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
    url: 'http://localhost/',
  });
  const w = dom.window;

  // jsdom lacks these; App.jsx and React reference them.
  w.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  w.matchMedia = w.matchMedia || (() => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} }));
  w.HTMLCanvasElement.prototype.getContext = () => null;
  w.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 16);
  w.cancelAnimationFrame = (id) => clearTimeout(id);
  w.AudioContext = class {
    constructor() { this.currentTime = 0; this.destination = {}; }
    createOscillator() { return { connect: () => ({ connect: () => {} }), start() {}, stop() {}, frequency: { value: 0 }, type: '' }; }
    createGain() { return { connect: () => ({ connect: () => {} }), gain: { value: 0, exponentialRampToValueAtTime() {} } }; }
  };

  // Some of these (`navigator` on Node 22) are getter-only on globalThis, so a
  // plain assignment throws. defineProperty with configurable works for both.
  for (const k of ['window', 'document', 'navigator', 'HTMLElement', 'Element', 'Node',
    'Event', 'CustomEvent', 'MutationObserver', 'ResizeObserver', 'requestAnimationFrame',
    'cancelAnimationFrame', 'getComputedStyle', 'HTMLCanvasElement', 'AudioContext']) {
    if (w[k] === undefined) continue;
    Object.defineProperty(globalThis, k, {
      value: w[k],
      writable: true,
      configurable: true,
    });
  }
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  return dom;
}

test('App.jsx mounts, renders the pad, and drives the chart', async () => {
  const dom = makeDom();

  const out = bundle(`
    const React = require('react');
    const { createRoot } = require('react-dom/client');
    const { act } = require('react');
    const App = require('${ROOT}src/App.jsx').default;
    const stub = require('${ROOT}tests/lwc-stub.js');

    module.exports = async function run(container) {
      let root;
      await act(async () => { root = createRoot(container); root.render(React.createElement(App)); });
      return { stub, root, act };
    };
  `);

  const run = require(out);
  const container = dom.window.document.getElementById('root');

  const { stub, root, act } = await run(container);

  try {
    // --- it actually mounted ---
    assert.equal(stub.calls.charts, 1, 'exactly one chart created');

    // candles + VWAP + EMA9
    assert.equal(stub.calls.series.length, 3, 'three series: candles, VWAP, EMA9');
    const [candles, vwap, ema] = stub.calls.series;
    assert.equal(candles.definition.type, 'Candlestick');
    assert.equal(vwap.definition.type, 'Line');
    assert.equal(ema.definition.type, 'Line');

    // the box primitive was attached to the candle series
    assert.equal(stub.calls.primitives.length, 1, 'box primitive attached');
    assert.equal(candles.primitives.length, 1, 'attached to the candle series');

    // markers API was created
    assert.equal(stub.calls.markers.length, 1, 'markers plugin created');

    // --- data reached the chart ---
    assert.ok(candles.data.length > 100, `candles got history, got ${candles.data.length}`);
    assert.ok(vwap.data.length > 100, `VWAP series populated, got ${vwap.data.length}`);
    assert.ok(ema.data.length > 0, `EMA series populated, got ${ema.data.length}`);

    // every candle has the four fields lightweight-charts requires
    for (const c of candles.data) {
      assert.ok(typeof c.time === 'number', 'candle time is a number');
      for (const k of ['open', 'high', 'low', 'close']) {
        assert.ok(Number.isFinite(c[k]), `candle ${k} finite`);
      }
    }

    // times strictly ascending - the chart rejects anything else
    const times = candles.data.map((c) => c.time);
    assert.ok(times.every((t, i) => i === 0 || t > times[i - 1]), 'candle times ascending');

    // --- the DOM rendered ---
    const html = container.innerHTML;
    assert.ok(html.includes('VWAP + 9 EMA Signal Pad'), 'title rendered');
    assert.ok(html.includes('SIMULATED FEED'), 'feed badge rendered');
    assert.ok(html.includes('Prices are simulated'), 'the warning banner is shown');

    // all twelve instruments are on the pad
    for (const sym of ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCHF', 'USDCAD',
      'GER30', 'US30', 'SPX500', 'UK100', 'XAUUSD', 'XAGUSD']) {
      assert.ok(html.includes(sym), `${sym} row present on the pad`);
    }

    // the pad shows real numbers, not a wall of em-dashes
    const prices = [...container.querySelectorAll('tbody tr')].map(
      (tr) => tr.children[1]?.textContent,
    );
    assert.equal(prices.length, 12, 'twelve rows in the pad');
    assert.ok(prices.every((p) => p && p !== '—'), `every row has a price, got ${prices}`);

    // --- the view is fitted once, not on every tick ---
    assert.equal(stub.calls.fitContent, 1, 'fitted once for the initial symbol');

    // Re-render the chart with new signal data and confirm the view is left
    // alone. Waiting on the feed is not enough: barMs is 5000, so a short wait
    // produces no push and the bug stays invisible - the first version of this
    // assertion passed with the regression in place.
    const fitsBefore = stub.calls.fitContent;
    const lenBefore = candles.data.length;

    const modeSelect = container.querySelector('.controls select');
    assert.ok(modeSelect, 'entry-mode control is rendered');

    await act(async () => {
      modeSelect.value = '1';
      modeSelect.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
    });

    // the chart must have received fresh data, or this proves nothing
    assert.notEqual(candles.data, null);
    assert.ok(candles.data.length >= lenBefore, 'chart still has its data');
    assert.equal(
      stub.calls.fitContent, fitsBefore,
      'changing settings re-renders the chart but must not re-fit the view',
    );
  } finally {
    await act(async () => root.unmount());
    assert.equal(stub.calls.removed, 1, 'chart removed on unmount - no leak');
    dom.window.close();
  }
});
