/**
 * Stand-in for `lightweight-charts` used only by tests/mount.test.js.
 *
 * jsdom has no canvas, so the real library cannot construct a chart. This stub
 * implements the surface Chart.jsx actually touches and records every call, so
 * the test can assert the component drives the chart correctly without a GPU.
 *
 * If Chart.jsx starts calling something this stub does not define, the mount
 * test throws - which is the point.
 */

export const ColorType = { Solid: 'solid' };
export const CandlestickSeries = { type: 'Candlestick' };
export const LineSeries = { type: 'Line' };

export const calls = {
  charts: 0,
  removed: 0,
  series: [],
  markers: [],
  primitives: [],
  fitContent: 0,
};

export function resetCalls() {
  calls.charts = 0;
  calls.removed = 0;
  calls.series = [];
  calls.markers = [];
  calls.primitives = [];
  calls.fitContent = 0;
}

function makeSeries(definition, options) {
  const rec = { definition, options, data: [], markers: [], primitives: [] };
  calls.series.push(rec);
  return {
    setData(d) {
      rec.data = d;
    },
    attachPrimitive(p) {
      rec.primitives.push(p);
      calls.primitives.push(p);
      if (typeof p.attached === 'function') {
        p.attached({
          chart: null,
          series: null,
          requestUpdate: () => {},
          horzScaleBehavior: {},
        });
      }
    },
    priceToCoordinate: () => 10,
    timeScale: () => ({ timeToCoordinate: () => 10 }),
  };
}

export function createChart(container, options) {
  if (!container) throw new Error('createChart called with no container');
  calls.charts++;
  return {
    options,
    addSeries(definition, opts) {
      return makeSeries(definition, opts);
    },
    attachPrimitive() {},
    timeScale() {
      return {
        fitContent() {
          calls.fitContent++;
        },
        timeToCoordinate: () => 10,
      };
    },
    remove() {
      calls.removed++;
    },
  };
}

export function createSeriesMarkers(series, markers) {
  const rec = { series, markers: markers || [] };
  calls.markers.push(rec);
  return {
    setMarkers(m) {
      rec.markers = m;
    },
    getMarkers() {
      return rec.markers;
    },
    detach() {},
  };
}

export const version = 'test-stub';
