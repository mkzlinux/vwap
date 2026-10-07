import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Chart from './Chart.jsx';
import SignalPad from './SignalPad.jsx';
import { SimulatedFeed, Mt5BridgeFeed, INSTRUMENTS, pointFor, applyFeedEvent } from './feed.js';
import {
  ANCHOR, ENTRY_MODE, AMBIG,
  buildSignals, summarise,
} from './engine.js';

const DEFAULTS = {
  anchor: ANCHOR.DAILY_CUSTOM,
  startHour: 0,
  startMinute: 0,
  rollingBars: 240,
  emaPeriod: 9,
  emaSource: 'close',
  mode: ENTRY_MODE.EMA_CROSS_VWAP,
  touchTolerancePoints: 10,
  requireReclaim: true,
  atrPeriod: 14,
  slAtrMult: 1.5,
  rewardR: 3,
  ambiguous: AMBIG.SL_FIRST,
};

const digitsFor = (symbol) => INSTRUMENTS.find((i) => i.symbol === symbol)?.digits ?? 5;

export default function App() {
  const [settings, setSettings] = useState(DEFAULTS);
  const [feedKind, setFeedKind] = useState('simulated');
  const [bridgeUrl, setBridgeUrl] = useState('ws://127.0.0.1:8765');
  const [feedState, setFeedState] = useState('connecting');
  const [selected, setSelected] = useState('EURUSD');
  const [alerts, setAlerts] = useState([]);
  const [soundOn, setSoundOn] = useState(true);
  const [notifyOn, setNotifyOn] = useState(false);
  // bars live in a ref, so this counter is what actually drives recomputation
  const [tick, forceTick] = useState(0);

  const barsRef = useRef(new Map());
  const seenRef = useRef(new Map()); // symbol -> Set of signal times already alerted
  const primedRef = useRef(false);   // first pass only records history, never alerts
  const feedRef = useRef(null);

  const set = (patch) => setSettings((s) => ({ ...s, ...patch }));

  // --- feed lifecycle -------------------------------------------------
  useEffect(() => {
    const feed =
      feedKind === 'mt5'
        ? new Mt5BridgeFeed({ url: bridgeUrl })
        : new SimulatedFeed({ barMs: 5000, history: 260 });

    feedRef.current = feed;
    setFeedState('connecting');

    const off = feed.subscribe((evt) => {
      if (evt.type === 'ready' || evt.type === 'connected') {
        setFeedState('live');
      } else if (evt.type === 'error' || evt.type === 'disconnected') {
        setFeedState(evt.type === 'disconnected' ? 'disconnected' : 'error');
      } else {
        // 'history' and 'bar' both fold through the shared reducer
        if (applyFeedEvent(barsRef.current, evt) && evt.type === 'history') {
          // the first history payload is what makes the feed usable
          setFeedState('live');
        }
      }
      forceTick((n) => n + 1);
    });

    feed.start();
    return () => {
      off();
      feed.stop();
      feedRef.current = null;
    };
  }, [feedKind, bridgeUrl]);

  // --- recompute signals whenever bars or settings change -------------
  const computed = useMemo(() => {
    const out = new Map();

    for (const inst of INSTRUMENTS) {
      const bars = barsRef.current.get(inst.symbol);
      if (!bars || bars.length < 20) {
        out.set(inst.symbol, { bars: bars || [], vwap: [], ema: [], signals: [], sum: summarise([], settings.rewardR) });
        continue;
      }
      const { vwap, ema, signals } = buildSignals(bars, {
        ...settings,
        point: pointFor(inst.digits),
      });
      out.set(inst.symbol, {
        bars,
        vwap,
        ema,
        signals,
        sum: summarise(signals, settings.rewardR),
      });
    }
    return out;
    // `tick` is bumped by every feed event - without it the ref-stored bars
    // change but nothing in the dep list does, and the pad never updates.
  }, [settings, tick]);

  // --- raise alerts for signals we have not seen yet -------------------
  useEffect(() => {
    const fresh = [];

    for (const inst of INSTRUMENTS) {
      const c = computed.get(inst.symbol);
      if (!c || !c.signals.length) continue;

      let seen = seenRef.current.get(inst.symbol);
      if (!seen) {
        seen = new Set();
        seenRef.current.set(inst.symbol, seen);
      }

      for (const s of c.signals) {
        if (seen.has(s.time)) continue;
        seen.add(s.time);
        if (primedRef.current) {
          fresh.push({
            id: `${inst.symbol}-${s.time}`,
            symbol: inst.symbol,
            time: s.time,
            dir: s.dir,
            entry: s.entry,
            sl: s.sl,
            tp: s.tp,
            digits: inst.digits,
          });
        }
      }
    }

    // The first pass has just absorbed the whole backfilled history; raising
    // it would fire a dozen alerts and a beep at the moment the page opens.
    if (!primedRef.current) {
      primedRef.current = true;
      return;
    }

    if (fresh.length) {
      setAlerts((a) => [...fresh, ...a].slice(0, 60));
      for (const f of fresh) {
        if (notifyOn && 'Notification' in window && Notification.permission === 'granted') {
          new Notification(`${f.symbol} ${f.dir > 0 ? 'BUY' : 'SELL'}`, {
            body: `entry ${f.entry.toFixed(f.digits)}  SL ${f.sl.toFixed(f.digits)}  TP ${f.tp.toFixed(f.digits)}`,
          });
        }
      }
      if (soundOn) beep();
    }
  }, [computed, soundOn, notifyOn]);

  const enableNotify = useCallback(async () => {
    if (!('Notification' in window)) return;
    const p = await Notification.requestPermission();
    setNotifyOn(p === 'granted');
  }, []);

  // --- pad rows --------------------------------------------------------
  const rows = useMemo(
    () =>
      INSTRUMENTS.map((inst) => {
        const c = computed.get(inst.symbol);
        const bars = c?.bars || [];
        const lastBar = bars[bars.length - 1];
        const i = bars.length - 1;
        const lastSignal = c?.signals.length ? c.signals[c.signals.length - 1] : null;
        const vwapVal = c?.vwap[i] ?? null;
        const emaVal = c?.ema[i] ?? null;
        const bias =
          lastBar && vwapVal != null && emaVal != null
            ? lastBar.close > vwapVal && emaVal > vwapVal
              ? 'long'
              : lastBar.close < vwapVal && emaVal < vwapVal
                ? 'short'
                : 'flat'
            : 'flat';

        return {
          symbol: inst.symbol,
          group: inst.group,
          price: lastBar ? lastBar.close : null,
          vwap: vwapVal,
          ema: emaVal,
          bias,
          lastSignal,
          rewardR: settings.rewardR,
          sum: c?.sum ?? summarise([], settings.rewardR),
          fresh: alerts.some((a) => a.symbol === inst.symbol),
        };
      }),
    [computed, settings.rewardR, alerts],
  );

  const sel = computed.get(selected) || { bars: [], vwap: [], ema: [], signals: [] };
  const alertCount = { tp: 0, sl: 0, open: 0 };
  for (const r of rows) {
    if (!r.lastSignal) continue;
    if (r.lastSignal.outcome === 1) alertCount.tp++;
    else if (r.lastSignal.outcome === -1) alertCount.sl++;
    else alertCount.open++;
  }

  return (
    <div className="app">
      <header>
        <div className="brand">
          <h1>VWAP + 9 EMA Signal Pad</h1>
          <span className="sub">session VWAP / EMA9 / ATR stops / 1:{settings.rewardR} targets</span>
        </div>

        <div className={`feed ${feedState}`}>
          <span className="dot" />
          <span className="feed-label">
            {feedKind === 'mt5' ? 'MT5 bridge' : 'SIMULATED FEED'}
          </span>
          <span className="feed-state">{feedState}</span>
        </div>
      </header>

      {feedKind === 'simulated' && (
        <div className="banner">
          <strong>Prices are simulated.</strong> This feed is a random walk for wiring up the
          dashboard — it is not market data and must not be traded on. Switch the source to the
          MT5 bridge for live prices (the MetaTrader5 Python package has no Linux build, so the
          bridge runs on Windows next to your terminal).
        </div>
      )}

      <section className="controls">
        <label>
          Source
          <select value={feedKind} onChange={(e) => setFeedKind(e.target.value)}>
            <option value="simulated">Simulated (demo)</option>
            <option value="mt5">MT5 bridge (WebSocket)</option>
          </select>
        </label>

        {feedKind === 'mt5' && (
          <label>
            Bridge URL
            <input value={bridgeUrl} onChange={(e) => setBridgeUrl(e.target.value)} size={26} />
          </label>
        )}

        <label>
          Entry mode
          <select value={settings.mode} onChange={(e) => set({ mode: Number(e.target.value) })}>
            <option value={0}>EMA9 × VWAP cross</option>
            <option value={1}>Trend stack</option>
            <option value={2}>VWAP pullback</option>
          </select>
        </label>

        <label>
          VWAP anchor
          <select value={settings.anchor} onChange={(e) => set({ anchor: Number(e.target.value) })}>
            <option value={0}>Daily from {String(settings.startHour).padStart(2, '0')}:{String(settings.startMinute).padStart(2, '0')}</option>
            <option value={1}>Daily 00:00</option>
            <option value={2}>Weekly</option>
            <option value={3}>Rolling</option>
          </select>
        </label>

        {settings.anchor === ANCHOR.DAILY_CUSTOM && (
          <>
            <label>
              Hour
              <input
                type="number" min="0" max="23" value={settings.startHour}
                onChange={(e) => set({ startHour: Number(e.target.value) })}
              />
            </label>
            <label>
              Minute
              <input
                type="number" min="0" max="59" value={settings.startMinute}
                onChange={(e) => set({ startMinute: Number(e.target.value) })}
              />
            </label>
          </>
        )}

        {settings.anchor === ANCHOR.ROLLING && (
          <label>
            Bars
            <input
              type="number" min="2" value={settings.rollingBars}
              onChange={(e) => set({ rollingBars: Number(e.target.value) })}
            />
          </label>
        )}

        <label>
          Stop (ATR ×)
          <input
            type="number" step="0.1" min="0.1" value={settings.slAtrMult}
            onChange={(e) => set({ slAtrMult: Number(e.target.value) })}
          />
        </label>

        <label>
          Reward (R)
          <input
            type="number" step="0.5" min="0.5" value={settings.rewardR}
            onChange={(e) => set({ rewardR: Number(e.target.value) })}
          />
        </label>

        <label>
          ATR period
          <input
            type="number" min="1" value={settings.atrPeriod}
            onChange={(e) => set({ atrPeriod: Number(e.target.value) })}
          />
        </label>

        <label className="chk">
          <input type="checkbox" checked={soundOn} onChange={(e) => setSoundOn(e.target.checked)} />
          Sound
        </label>
        <label className="chk">
          <input type="checkbox" checked={notifyOn} onChange={() => enableNotify()} />
          Browser alerts
        </label>
      </section>

      <main>
        <div className="left">
          <Chart
            bars={sel.bars}
            vwap={sel.vwap}
            ema={sel.ema}
            signals={sel.signals}
            digits={digitsFor(selected)}
            symbol={selected}
          />
          <div className="alerts">
            <h2>
              Alerts
              <span className="tally">
                <b className="tp">{alertCount.tp}</b> TP · <b className="sl">{alertCount.sl}</b> SL ·{' '}
                <b>{alertCount.open}</b> open
              </span>
            </h2>
            <ul>
              {alerts.length === 0 && <li className="empty">No signals yet.</li>}
              {alerts.map((a) => (
                <li key={a.id} onClick={() => setSelected(a.symbol)} className={a.dir > 0 ? 'up' : 'down'}>
                  <span className="t">{new Date(a.time * 1000).toLocaleTimeString()}</span>
                  <span className="s">{a.symbol}</span>
                  <span className={`d ${a.dir > 0 ? 'long' : 'short'}`}>{a.dir > 0 ? 'BUY' : 'SELL'}</span>
                  <span className="lv">
                    {a.entry.toFixed(a.digits)} → SL {a.sl.toFixed(a.digits)} / TP {a.tp.toFixed(a.digits)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="right">
          <SignalPad rows={rows} selected={selected} onSelect={setSelected} digitsFor={digitsFor} />
        </div>
      </main>
    </div>
  );
}

// --- alert sound ---------------------------------------------------------
let audioCtx = null;
function beep() {
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const o = audioCtx.createOscillator();
    const g = audioCtx.createGain();
    o.type = 'sine';
    o.frequency.value = 880;
    g.gain.value = 0.05;
    o.connect(g).connect(audioCtx.destination);
    o.start();
    g.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.35);
    o.stop(audioCtx.currentTime + 0.36);
  } catch {
    // autoplay policy or no audio device - not worth breaking the UI over
  }
}
