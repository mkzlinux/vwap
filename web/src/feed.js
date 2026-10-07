/**
 * Feed abstraction.
 *
 * Two implementations share one interface so the chart and signal code never
 * care where prices came from:
 *
 *   SimulatedFeed - random walk, runs anywhere, for wiring the UI up.
 *   Mt5BridgeFeed - WebSocket client for the Windows-side bridge.
 *
 * The MetaTrader5 Python package ships win_amd64 wheels only, so the bridge
 * has to run on the machine with the terminal and publish over the network.
 * Nothing in this app can reach a live market on its own.
 */

/** Instruments on the pad: FX majors, index CFDs and spot metals. */
export const INSTRUMENTS = [
  // --- FX majors ---
  { symbol: 'EURUSD', group: 'FX',    base: 1.0850,  digits: 5, vol: 0.00042 },
  { symbol: 'GBPUSD', group: 'FX',    base: 1.2650,  digits: 5, vol: 0.00048 },
  { symbol: 'USDJPY', group: 'FX',    base: 151.20,  digits: 3, vol: 0.055 },
  { symbol: 'AUDUSD', group: 'FX',    base: 0.6580,  digits: 5, vol: 0.00038 },
  { symbol: 'USDCHF', group: 'FX',    base: 0.8950,  digits: 5, vol: 0.00036 },
  { symbol: 'USDCAD', group: 'FX',    base: 1.3580,  digits: 5, vol: 0.00040 },
  // --- indices ---
  { symbol: 'GER30',  group: 'Index', base: 18250.0, digits: 1, vol: 11.0 },
  { symbol: 'US30',   group: 'Index', base: 39800.0, digits: 1, vol: 24.0 },
  { symbol: 'SPX500', group: 'Index', base: 5230.0,  digits: 1, vol: 5.2 },
  { symbol: 'UK100',  group: 'Index', base: 7950.0,  digits: 1, vol: 6.0 },
  // --- spot metals ---
  { symbol: 'XAUUSD', group: 'Metals', base: 2340.50, digits: 2, vol: 1.35 },
  { symbol: 'XAGUSD', group: 'Metals', base: 27.40,   digits: 3, vol: 0.021 },
  // --- stock CFDs ---
  { symbol: 'AAPL',  group: 'Stocks', base: 227.0,  digits: 2, vol: 0.85 },
  { symbol: 'MSFT',  group: 'Stocks', base: 415.0,  digits: 2, vol: 1.60 },
  { symbol: 'NVDA',  group: 'Stocks', base: 121.0,  digits: 2, vol: 0.95 },
  { symbol: 'AMZN',  group: 'Stocks', base: 186.0,  digits: 2, vol: 0.80 },
  { symbol: 'TSLA',  group: 'Stocks', base: 248.0,  digits: 2, vol: 2.40 },
  { symbol: 'GOOGL', group: 'Stocks', base: 164.0,  digits: 2, vol: 0.70 },
  { symbol: 'META',  group: 'Stocks', base: 505.0,  digits: 2, vol: 2.10 },
];

export function pointFor(digits) {
  return Math.pow(10, -digits);
}

/**
 * Fold one feed event into the caller's bar store.
 *
 * Lives here rather than inline in App.jsx so the exact code the app runs is
 * the code the tests exercise. A test that re-implements the handler proves
 * nothing about the handler.
 *
 * `store` is a Map of symbol -> bar array, mutated in place.
 * Returns true when the event carried data the UI should react to.
 */
export function applyFeedEvent(store, evt) {
  switch (evt.type) {
    case 'history': {
      // full rebuild; this is also how a feed seeds itself on connect
      store.set(evt.symbol, [...evt.bars]);
      return true;
    }

    case 'bar': {
      const arr = store.get(evt.symbol);
      if (!arr || arr.length === 0) {
        store.set(evt.symbol, [evt.bar]);
        return true;
      }
      const last = arr.length - 1;
      if (evt.closed) {
        // the bar we were building just finished; overwrite the placeholder
        arr[last] = evt.bar;
      } else if (arr[last].time === evt.bar.time) {
        // same bar still forming, replace in place
        arr[last] = evt.bar;
      } else {
        arr.push(evt.bar);
      }
      return true;
    }

    default:
      return false;
  }
}

// --- deterministic PRNG so a reload reproduces the same demo session -------
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashSymbol(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/**
 * Simulated feed. Emits { symbol, bar, closed } on every tick.
 *
 * Bars roll every `barMs` (default 5s so the demo moves), and `history`
 * closed bars are generated up front so the chart and the signal engine have
 * something to work with immediately.
 */
export class SimulatedFeed {
  constructor({ instruments = INSTRUMENTS, barMs = 5000, history = 260, seed = 20261007 } = {}) {
    this.instruments = instruments;
    this.barMs = barMs;
    this.history = history;
    this.seed = seed;
    this.listeners = new Set();
    this.state = new Map();
    this.timer = null;
    this.connected = false;
    this.kind = 'simulated';
  }

  subscribe(fn) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  _emit(evt) {
    for (const fn of this.listeners) fn(evt);
  }

  start() {
    if (this.timer) return;
    const nowSec = Math.floor(Date.now() / 1000);
    // align the current bar to a barMs boundary so bars land on round times
    const barSec = Math.max(1, Math.round(this.barMs / 1000));
    const curOpen = Math.floor(nowSec / barSec) * barSec;

    for (const inst of this.instruments) {
      const rnd = mulberry32(hashSymbol(inst.symbol) ^ this.seed);
      const bars = [];
      let price = inst.base * (1 + (rnd() - 0.5) * 0.02);

      for (let i = this.history - 1; i >= 0; i--) {
        // i=0 lands on curOpen-barSec, NOT curOpen: the forming bar already
        // owns curOpen, and lightweight-charts requires strictly ascending
        // timestamps, so a shared one would make the chart throw.
        const t = curOpen - (i + 1) * barSec;
        const open = price;
        // slight mean reversion keeps the demo series from drifting away
        const drift = (inst.base - open) * 0.0006;
        const shock = (rnd() - 0.5) * 2 * inst.vol;
        const close = open + drift + shock;
        const hi = Math.max(open, close) + rnd() * inst.vol * 0.7;
        const lo = Math.min(open, close) - rnd() * inst.vol * 0.7;
        bars.push({
          time: t,
          open,
          high: hi,
          low: lo,
          close,
          volume: Math.round(40 + rnd() * 160),
        });
        price = close;
      }

      this.state.set(inst.symbol, {
        inst,
        rnd,
        bars,
        curOpen,
        barSec,
        cur: {
          time: curOpen,
          open: price,
          high: price,
          low: price,
          close: price,
          volume: 0,
        },
      });
    }

    this.connected = true;
    this._emit({ type: 'ready', kind: this.kind, instruments: this.instruments.map((i) => i.symbol) });

    // Seed subscribers with the backfill. Without this the app only ever sees
    // the one bar per tick that _tick() emits, so the chart opens with a single
    // candle instead of the generated history. Both feed implementations must
    // emit 'history' - App.jsx seeds its bar store from that message alone.
    for (const inst of this.instruments) {
      const st = this.state.get(inst.symbol);
      this._emit({ type: 'history', symbol: inst.symbol, bars: [...st.bars, st.cur] });
    }

    this.timer = setInterval(() => this._tick(), this.barMs);
    // one immediate tick so the pad is populated without waiting a full bar
    this._tick();
  }

  stop() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    this.connected = false;
  }

  _tick() {
    const nowSec = Math.floor(Date.now() / 1000);
    for (const [symbol, st] of this.state) {
      const barOpen = Math.floor(nowSec / st.barSec) * st.barSec;

      // roll: the bar we were building just closed
      if (barOpen !== st.curOpen) {
        st.bars.push(st.cur);
        if (st.bars.length > 1200) st.bars.shift();
        st.curOpen = barOpen;
        const prev = st.cur.close;
        st.cur = { time: barOpen, open: prev, high: prev, low: prev, close: prev, volume: 0 };
        this._emit({ type: 'bar', symbol, bar: { ...st.bars[st.bars.length - 1] }, closed: true });
      }

      // move the forming bar
      const { inst, rnd } = st;
      const drift = (inst.base - st.cur.close) * 0.0006;
      const shock = (rnd() - 0.5) * 2 * inst.vol;
      const next = st.cur.close + drift + shock;
      st.cur.close = next;
      st.cur.high = Math.max(st.cur.high, next);
      st.cur.low = Math.min(st.cur.low, next);
      st.cur.volume += Math.round(1 + rnd() * 6);

      this._emit({ type: 'bar', symbol, bar: { ...st.cur }, closed: false });
    }
  }

  /** Full closed-bar history plus the forming bar, for the chart. */
  series(symbol) {
    const st = this.state.get(symbol);
    if (!st) return [];
    return [...st.bars, st.cur];
  }
}

/**
 * WebSocket client for the MT5 bridge.
 *
 * Expected inbound messages, one JSON object per WebSocket message:
 *   { "type": "ready",    "instruments": ["EURUSD", ...] }
 *   { "type": "history",  "symbol": "EURUSD", "bars": [ {time,open,high,low,close,volume}, ... ] }
 *   { "type": "bar",      "symbol": "EURUSD", "bar": {...}, "closed": true|false }
 *   { "type": "error",    "message": "..." }
 *
 * "error" is emitted both by the bridge (a symbol that failed to read) and by
 * this class itself (socket failure). App.jsx turns either into a visible
 * feed-state badge rather than a silently frozen chart.
 *
 * Bar times per symbol must be strictly ascending and never repeat, or the
 * chart rejects the series.
 *
 * The bridge runs on Windows next to the terminal because the MetaTrader5
 * Python package has no Linux wheel. See web/bridge/README.md.
 */
export class Mt5BridgeFeed {
  constructor({ url, instruments = INSTRUMENTS }) {
    this.url = url;
    this.instruments = instruments;
    this.listeners = new Set();
    this.ws = null;
    this.connected = false;
    this.kind = 'mt5';
    this.history = new Map();
    this.lastError = null;
  }

  subscribe(fn) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  _emit(evt) {
    for (const fn of this.listeners) fn(evt);
  }

  start() {
    try {
      this.ws = new WebSocket(this.url);
    } catch (e) {
      this.lastError = String(e);
      this._emit({ type: 'error', message: this.lastError });
      return;
    }

    this.ws.onopen = () => {
      this.connected = true;
      this._emit({ type: 'connected', kind: this.kind });
    };

    this.ws.onerror = () => {
      this.lastError = 'websocket error';
      this._emit({ type: 'error', message: this.lastError });
    };

    this.ws.onclose = () => {
      this.connected = false;
      this._emit({ type: 'disconnected' });
    };

    this.ws.onmessage = (ev) => {
      let msg;
      try {
        msg = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (msg.type === 'history') {
        this.history.set(msg.symbol, msg.bars);
        this._emit({ type: 'history', symbol: msg.symbol, bars: msg.bars });
      } else {
        this._emit(msg);
      }
    };
  }

  stop() {
    if (this.ws) this.ws.close();
    this.ws = null;
    this.connected = false;
  }

  series(symbol) {
    return this.history.get(symbol) || [];
  }
}
