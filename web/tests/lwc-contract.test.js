/**
 * Contract test against the REAL lightweight-charts package.
 *
 * tests/mount.test.js stubs the library, because jsdom has no canvas. That
 * proves App.jsx mounts, but it cannot catch a mismatch with the library's
 * actual API - and v5 changed it substantially (chart.addSeries(CandlestickSeries)
 * replaced v4's chart.addCandlestickSeries()).
 *
 * This imports the installed package and the typings it ships, then checks that
 * every symbol and every option key Chart.jsx relies on really exists. The
 * valid option set is derived from the shipped typings rather than written out
 * by hand, so it cannot drift from what the library declares.
 *
 * Run: cd web && npm test
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as LWC from 'lightweight-charts';

const ROOT = new URL('..', import.meta.url).pathname;
const TYPINGS = readFileSync(`${ROOT}node_modules/lightweight-charts/dist/typings.d.ts`, 'utf8');
const CHART_SRC = readFileSync(`${ROOT}src/Chart.jsx`, 'utf8');

/**
 * Keys declared on an exported interface in the shipped typings, including
 * those inherited via `extends`. Inheritance matters here: SeriesMarkerBar
 * only declares `position` itself and takes time/shape/color/text from
 * SeriesMarkerBase.
 */
function interfaceKeys(name, seen = new Set()) {
  if (seen.has(name)) return new Set();
  seen.add(name);

  const m = TYPINGS.match(new RegExp(`export interface ${name}[^{]*\\{([\\s\\S]*?)\\n\\}`));
  assert.ok(m, `interface ${name} found in typings`);

  const keys = new Set();
  for (const line of m[1].split('\n')) {
    // members are written either as properties (`color: string;`) or as
    // methods, which may carry a generic parameter list of their own
    // (`addSeries<T extends SeriesType>(...): ISeriesApi<...>;`)
    const k = line.match(/^\t([A-Za-z_$][\w$]*)\s*(?:<[^>(]*>)?\s*\??\s*[:(]/);
    if (k) keys.add(k[1]);
  }

  // Walk the extends clause. The generic parameter list has to come off first:
  // SeriesAttachedParameter<HorzScaleItem = Time, TSeriesType extends
  // SeriesType = ...> contains the word "extends" as a constraint, which is
  // not inheritance and sent this helper looking for an interface called
  // SeriesType.
  const header = m[0].slice(0, m[0].indexOf('{'));
  let angle = 0;
  let stripped = '';
  for (const ch of header) {
    if (ch === '<') angle++;
    else if (ch === '>') angle = Math.max(0, angle - 1);
    else if (angle === 0) stripped += ch;
  }

  const ext = stripped.match(/extends\s+([^{]+)/);
  if (ext) {
    for (const raw of ext[1].split(',')) {
      const base = raw.trim().replace(/<.*$/, '').trim();
      if (!base) continue;
      for (const k of interfaceKeys(base, seen)) keys.add(k);
    }
  }
  return keys;
}

/**
 * Top-level option keys passed to chart.addSeries(<def>, { ... }) in Chart.jsx.
 * Brace-matched, so nested objects do not contribute stray keys.
 */
function addSeriesOptions(source, defName) {
  const at = source.indexOf(`addSeries(${defName}, {`);
  assert.ok(at >= 0, `Chart.jsx calls addSeries(${defName}, ...)`);
  const start = source.indexOf('{', at);
  let depth = 0;
  let end = -1;
  for (let i = start; i < source.length; i++) {
    if (source[i] === '{') depth++;
    else if (source[i] === '}') {
      depth--;
      if (depth === 0) { end = i; break; }
    }
  }
  assert.ok(end > start, 'option object is balanced');

  const body = source.slice(start + 1, end);
  const keys = new Set();
  let d = 0;
  for (const line of body.split('\n')) {
    for (const ch of line) {
      if (ch === '{' || ch === '[' || ch === '(') d++;
      else if (ch === '}' || ch === ']' || ch === ')') d--;
    }
    if (d !== 0) continue;
    const k = line.match(/^\s*([A-Za-z_$][\w$]*)\s*:/);
    if (k) keys.add(k[1]);
  }
  return keys;
}

test('the installed library exports what Chart.jsx imports', () => {
  assert.equal(typeof LWC.createChart, 'function');
  assert.equal(typeof LWC.createSeriesMarkers, 'function');
  assert.equal(typeof LWC.ColorType, 'object');
  assert.equal(typeof LWC.ColorType.Solid, 'string');
});

test('series definitions are the v5 shape', () => {
  // v5: chart.addSeries(CandlestickSeries). v4 used chart.addCandlestickSeries(),
  // which no longer exists - relying on it would leave a blank chart.
  assert.equal(typeof LWC.addCandlestickSeries, 'undefined', 'v4 API is gone');

  assert.equal(LWC.CandlestickSeries.type, 'Candlestick');
  assert.equal(LWC.LineSeries.type, 'Line');
  assert.equal(typeof LWC.CandlestickSeries.defaultOptions, 'object');
  assert.equal(typeof LWC.LineSeries.defaultOptions, 'object');
});

test('every option Chart.jsx passes to addSeries is a real option', () => {
  const common = interfaceKeys('SeriesOptionsCommon');
  // sanity: the keys this test was originally written around are common options
  for (const k of ['priceLineVisible', 'lastValueVisible', 'title']) {
    assert.ok(common.has(k), `${k} is declared on SeriesOptionsCommon`);
  }

  for (const [defName, def] of [
    ['CandlestickSeries', LWC.CandlestickSeries],
    ['LineSeries', LWC.LineSeries],
  ]) {
    const typeSpecific = new Set(Object.keys(def.defaultOptions));
    const valid = new Set([...common, ...typeSpecific]);
    const used = addSeriesOptions(CHART_SRC, defName);

    assert.ok(used.size > 0, `${defName} is passed options`);
    for (const key of used) {
      assert.ok(
        valid.has(key),
        `${defName} option "${key}" is declared by the library ` +
        `(not in SeriesOptionsCommon nor ${defName}.defaultOptions)`,
      );
    }
  }
});

test('the chart and series APIs Chart.jsx calls are declared', () => {
  const chartApi = interfaceKeys('IChartApi');
  const seriesApi = interfaceKeys('ISeriesApi');

  for (const m of ['addSeries', 'remove', 'timeScale']) {
    assert.ok(chartApi.has(m), `IChartApi.${m} declared`);
  }
  for (const m of ['setData', 'attachPrimitive', 'priceToCoordinate']) {
    assert.ok(seriesApi.has(m), `ISeriesApi.${m} declared`);
  }

  // requestUpdate is on the ATTACHED PARAMETER, not the series - BoxesPrimitive
  // reads it from there, and that was a real bug once.
  const attached = interfaceKeys('SeriesAttachedParameter');
  assert.ok(attached.has('requestUpdate'), 'SeriesAttachedParameter.requestUpdate declared');
  assert.ok(attached.has('series'), 'SeriesAttachedParameter.series declared');
  assert.ok(attached.has('chart'), 'SeriesAttachedParameter.chart declared');
  assert.ok(!seriesApi.has('requestUpdate'), 'requestUpdate is NOT on the series');
});

test('marker fields Chart.jsx sets are declared', () => {
  const bar = interfaceKeys('SeriesMarkerBar');
  for (const f of ['time', 'position', 'shape', 'color', 'text']) {
    assert.ok(bar.has(f), `SeriesMarkerBar.${f} declared`);
  }
});
