import { useRef, useEffect, useMemo, useState } from 'react';
import { createChart, CandlestickSeries, LineSeries, createSeriesMarkers, ColorType } from 'lightweight-charts';
import { BoxesPrimitive } from './BoxesPrimitive.js';

/**
 * The chart. Candles + session VWAP + 9 EMA, with the TradingView-style
 * profit/loss boxes drawn by a custom pane primitive (lightweight-charts has
 * no built-in box primitive).
 *
 * Markers are the signal arrows; a second marker set records whether each
 * signal hit its stop or its target.
 */
export default function Chart({ bars, vwap, ema, signals, digits, symbol }) {
  const container = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const vwapRef = useRef(null);
  const emaRef = useRef(null);
  const boxesRef = useRef(null);
  const markersRef = useRef(null);
  const fittedFor = useRef(null); // symbol we last auto-fitted the view for
  const [ready, setReady] = useState(false);

  // create once
  useEffect(() => {
    if (!container.current) return;

    const chart = createChart(container.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#0d1117' },
        textColor: '#c9d1d9',
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: 'rgba(48,54,61,0.5)' },
        horzLines: { color: 'rgba(48,54,61,0.5)' },
      },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: '#30363d' },
      timeScale: { borderColor: '#30363d', timeVisible: true, secondsVisible: false },
      autoSize: true,
    });

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderUpColor: '#26a69a',
      borderDownColor: '#ef5350',
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    });

    const vwapSeries = chart.addSeries(LineSeries, {
      color: '#e8b931',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      title: 'VWAP',
    });

    const emaSeries = chart.addSeries(LineSeries, {
      color: '#4f9dff',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      title: 'EMA 9',
    });

    const boxes = new BoxesPrimitive([]);
    candles.attachPrimitive(boxes);

    const markers = createSeriesMarkers(candles, []);

    chartRef.current = chart;
    seriesRef.current = candles;
    vwapRef.current = vwapSeries;
    emaRef.current = emaSeries;
    boxesRef.current = boxes;
    markersRef.current = markers;
    setReady(true);

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      vwapRef.current = null;
      emaRef.current = null;
      boxesRef.current = null;
      markersRef.current = null;
    };
  }, []);

  // push data
  useEffect(() => {
    if (!ready || !seriesRef.current) return;

    const candles = bars.map((b) => ({
      time: b.time,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    }));
    seriesRef.current.setData(candles);

    vwapRef.current.setData(
      bars
        .map((b, i) => (vwap[i] == null ? null : { time: b.time, value: vwap[i] }))
        .filter(Boolean),
    );

    emaRef.current.setData(
      bars
        .map((b, i) => (ema[i] == null ? null : { time: b.time, value: ema[i] }))
        .filter(Boolean),
    );

    // --- signal arrows, plus a hit marker once a trade resolves ---
    const mk = [];
    for (const s of signals) {
      mk.push({
        time: s.time,
        position: s.dir > 0 ? 'belowBar' : 'aboveBar',
        color: s.dir > 0 ? '#3fb950' : '#f85149',
        shape: s.dir > 0 ? 'arrowUp' : 'arrowDown',
        text: s.dir > 0 ? 'BUY' : 'SELL',
      });
      if (s.outcome !== 0) {
        const hitBar = bars[s.hitBar];
        if (hitBar) {
          const win = s.outcome === 1;
          mk.push({
            time: hitBar.time,
            position: win ? 'aboveBar' : 'belowBar',
            color: win ? '#3fb950' : '#f85149',
            shape: win ? 'circle' : 'circle',
            text: win ? 'TP' : 'SL',
          });
        }
      }
    }
    mk.sort((a, b) => a.time - b.time);
    markersRef.current.setMarkers(mk);

    // --- boxes: newest InpMaxSignals worth, truncated at resolution ---
    const shown = signals.slice(-40);
    const boxData = shown.map((s) => {
      const end = s.outcome !== 0 ? bars[s.hitBar] : bars[bars.length - 1];
      return {
        startTime: s.time,
        endTime: end ? end.time : s.time,
        entry: s.entry,
        sl: s.sl,
        tp: s.tp,
        dir: s.dir,
        resolved: s.outcome !== 0,
      };
    });
    boxesRef.current.update(boxData);

    // Fit the view when the instrument changes, not on every data push. The
    // feed ticks every few seconds; re-fitting then would yank the user's zoom
    // and pan back to full width on each tick.
    if (fittedFor.current !== symbol) {
      fittedFor.current = symbol;
      chartRef.current.timeScale().fitContent();
    }
  }, [ready, bars, vwap, ema, signals, symbol]);

  const last = bars[bars.length - 1];

  return (
    <div className="chart-wrap">
      <div ref={container} className="chart" />
      {last && (
        <div className="chart-legend">
          <span className="lg-item"><i style={{ background: '#e8b931' }} />VWAP</span>
          <span className="lg-item"><i style={{ background: '#4f9dff' }} />EMA 9</span>
          <span className="lg-item">
            last {last.close.toFixed(digits)}
          </span>
        </div>
      )}
    </div>
  );
}
