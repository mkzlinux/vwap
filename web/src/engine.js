/**
 * Session VWAP + EMA + ATR + signal engine.
 *
 * This is a deliberate port of MQL5/Include/WeltradeVWAP/VwapCore.mqh so the
 * browser dashboard and the MT5 indicator produce identical signals from the
 * same bars. The C version is executed under gcc by tools/test_vwap_core.py;
 * web/tests/engine.test.js runs the same assertions against this port.
 *
 * All times are UNIX seconds in UTC, matching MQL5's datetime semantics.
 */

export const ANCHOR = {
  DAILY_CUSTOM: 0,
  DAILY_MIDNIGHT: 1,
  WEEKLY: 2,
  ROLLING: 3,
};

export const ENTRY_MODE = {
  EMA_CROSS_VWAP: 0,
  TREND_STACK: 1,
  VWAP_PULLBACK: 2,
};

export const AMBIG = {
  SL_FIRST: 0,
  TP_FIRST: 1,
};

/** VWAP typical price: (O+H+L+C)/4 */
export function typicalPrice(bar) {
  return (bar.open + bar.high + bar.low + bar.close) / 4;
}

function clampHour(h) {
  const v = h | 0;
  return v < 0 ? 0 : v > 23 ? 23 : v;
}

function clampMinute(m) {
  const v = m | 0;
  return v < 0 ? 0 : v > 59 ? 59 : v;
}

/** Midnight (00:00:00 UTC) of a UNIX timestamp. */
export function vwapMidnight(t) {
  return t - (t % 86400);
}

/** Start of the VWAP session containing bar time t. */
export function vwapSessionStart(t, anchor, startHour = 0, startMinute = 0) {
  const secs = clampHour(startHour) * 3600 + clampMinute(startMinute) * 60;

  switch (anchor) {
    case ANCHOR.DAILY_MIDNIGHT:
      return vwapMidnight(t);

    case ANCHOR.DAILY_CUSTOM: {
      let dayStart = vwapMidnight(t) + secs;
      if (t < dayStart) dayStart -= 86400;
      return dayStart;
    }

    case ANCHOR.WEEKLY: {
      // getUTCDay(): 0 = Sunday .. 6 = Saturday, same as MQL5 day_of_week.
      const back = (new Date(t * 1000).getUTCDay() + 6) % 7; // days since Monday
      let wk = vwapMidnight(t) - back * 86400 + secs;
      if (t < wk) wk -= 7 * 86400;
      return wk;
    }

    default:
      return vwapMidnight(t);
  }
}

/**
 * Session VWAP over an array of bars.
 *
 * Returns an array aligned to `bars`; index i is the VWAP for bars[i].
 * Zero-volume bars contribute nothing. A window with no volume at all falls
 * back to the typical price so the line never breaks.
 */
export function computeVwap(bars, opts = {}) {
  const {
    anchor = ANCHOR.DAILY_CUSTOM,
    startHour = 0,
    startMinute = 0,
    rollingBars = 240,
  } = opts;

  const n = bars.length;
  const out = new Array(n).fill(null);
  if (n === 0) return out;

  const rb = Math.max(2, rollingBars | 0);

  const cp = new Float64Array(n + 1); // prefix sum of typical price * volume
  const cv = new Float64Array(n + 1); // prefix sum of volume
  const win = new Int32Array(n);      // window start index per bar

  let sess = 0;
  for (let j = 0; j < n; j++) {
    if (anchor === ANCHOR.ROLLING) {
      win[j] = Math.max(0, j - (rb - 1));
    } else {
      if (
        j > 0 &&
        vwapSessionStart(bars[j].time, anchor, startHour, startMinute) !==
          vwapSessionStart(bars[j - 1].time, anchor, startHour, startMinute)
      ) {
        sess = j;
      }
      win[j] = sess;
    }
    const v = Math.max(0, bars[j].volume);
    cp[j + 1] = cp[j] + typicalPrice(bars[j]) * v;
    cv[j + 1] = cv[j] + v;
  }

  for (let i = 0; i < n; i++) {
    const b = win[i];
    const dv = cv[i + 1] - cv[b];
    out[i] = dv > 0 ? (cp[i + 1] - cp[b]) / dv : typicalPrice(bars[i]);
  }
  return out;
}

/**
 * Exponential moving average, SMA-seeded so the first value matches the
 * classic definition (and the MT5 iMA output) rather than a naive seed.
 * `source` is 'close' or 'typical'.
 */
export function computeEma(bars, period, source = 'close') {
  const n = bars.length;
  const out = new Array(n).fill(null);
  if (period < 1 || n === 0) return out;

  const k = 2 / (period + 1);
  const value = (b) => (source === 'typical' ? typicalPrice(b) : b.close);

  let sum = 0;
  for (let i = 0; i < n; i++) {
    const s = value(bars[i]);
    if (i < period - 1) {
      sum += s;
    } else if (i === period - 1) {
      sum += s;
      out[i] = sum / period;
    } else {
      out[i] = out[i - 1] + k * (s - out[i - 1]);
    }
  }
  return out;
}

/**
 * Simple average of True Range ending at bar i. Mirrors AtrAt() in the MT5
 * indicator: the first bar has no previous close, so the window starts at 1.
 */
export function atrAt(bars, i, period) {
  if (period < 1) return 0;
  let from = i - period + 1;
  if (from < 1) from = 1;
  if (i - from + 1 < 1) return 0;

  let sum = 0;
  let count = 0;
  for (let j = from; j <= i; j++) {
    let tr = bars[j].high - bars[j].low;
    const up = Math.abs(bars[j].high - bars[j - 1].close);
    const dn = Math.abs(bars[j].low - bars[j - 1].close);
    if (up > tr) tr = up;
    if (dn > tr) tr = dn;
    sum += tr;
    count++;
  }
  return count > 0 ? sum / count : 0;
}

/**
 * Entry signal on bar i, comparing against bar i-1.
 * Returns 1 (long), -1 (short) or 0 (no signal).
 */
export function signalAt(i, bars, vwap, ema, opts = {}) {
  const {
    mode = ENTRY_MODE.EMA_CROSS_VWAP,
    touchTolerancePoints = 10,
    point = 0.00001,
    requireReclaim = true,
  } = opts;

  if (i < 1) return 0;
  const v1 = vwap[i], v2 = vwap[i - 1];
  const e1 = ema[i], e2 = ema[i - 1];
  if (v1 == null || v2 == null || e1 == null || e2 == null) return 0;

  const tol = touchTolerancePoints * point;
  const b = bars[i];

  switch (mode) {
    case ENTRY_MODE.EMA_CROSS_VWAP:
      if (e2 <= v2 && e1 > v1) return 1;
      if (e2 >= v2 && e1 < v1) return -1;
      return 0;

    case ENTRY_MODE.TREND_STACK: {
      const up1 = b.close > v1 && b.close > e1 && e1 > v1;
      const up2 = bars[i - 1].close > v2 && bars[i - 1].close > e2 && e2 > v2;
      const dn1 = b.close < v1 && b.close < e1 && e1 < v1;
      const dn2 = bars[i - 1].close < v2 && bars[i - 1].close < e2 && e2 < v2;
      if (up1 && !up2) return 1;
      if (dn1 && !dn2) return -1;
      return 0;
    }

    case ENTRY_MODE.VWAP_PULLBACK: {
      const upTrend = e1 > v1;
      const dnTrend = e1 < v1;
      const touchedUp = b.low <= v1 + tol;
      const touchedDown = b.high >= v1 - tol;
      const longSig = upTrend && touchedUp && (!requireReclaim || b.close > v1);
      const shortSig = dnTrend && touchedDown && (!requireReclaim || b.close < v1);
      if (longSig && !shortSig) return 1;
      if (shortSig && !longSig) return -1;
      return 0;
    }

    default:
      return 0;
  }
}

/**
 * Walk forward from a signal bar and report which level price reached first.
 *
 * Returns { outcome, hitBar } where outcome is +1 take profit, -1 stop loss,
 * 0 neither yet. The scan starts at sigBar+1 because entry is the signal
 * bar's close, so that bar's own range cannot resolve the trade.
 *
 * Touching a level counts as hitting it (<= / >=). When one bar spans both
 * levels the intra-bar order is unknowable, so `ambiguous` picks the
 * assumption. Only bars up to lastClosed count, so an outcome never repaints.
 */
export function evaluateOutcome({
  dir,
  sigBar,
  lastClosed,
  sl,
  tp,
  bars,
  ambiguous = AMBIG.SL_FIRST,
}) {
  for (let j = sigBar + 1; j <= lastClosed; j++) {
    const b = bars[j];
    const tpHit = dir > 0 ? b.high >= tp : b.low <= tp;
    const slHit = dir > 0 ? b.low <= sl : b.high >= sl;

    if (tpHit && slHit) {
      return { outcome: ambiguous === AMBIG.TP_FIRST ? 1 : -1, hitBar: j };
    }
    if (tpHit) return { outcome: 1, hitBar: j };
    if (slHit) return { outcome: -1, hitBar: j };
  }
  return { outcome: 0, hitBar: 0 };
}

/**
 * Build the full signal series for a symbol.
 * Entry is the signal bar's close; the stop is ATR-scaled and the target is
 * rewardR times the stop distance, so the two always scale together.
 */
export function buildSignals(bars, opts = {}) {
  const {
    anchor = ANCHOR.DAILY_CUSTOM,
    startHour = 0,
    startMinute = 0,
    rollingBars = 240,
    emaPeriod = 9,
    emaSource = 'close',
    mode = ENTRY_MODE.EMA_CROSS_VWAP,
    touchTolerancePoints = 10,
    point = 0.00001,
    requireReclaim = true,
    atrPeriod = 14,
    slAtrMult = 1.5,
    rewardR = 3,
    ambiguous = AMBIG.SL_FIRST,
  } = opts;

  const vwap = computeVwap(bars, { anchor, startHour, startMinute, rollingBars });
  const ema = computeEma(bars, emaPeriod, emaSource);
  const lastClosed = bars.length - 2;

  const signals = [];
  for (let i = 1; i <= lastClosed; i++) {
    const dir = signalAt(i, bars, vwap, ema, {
      mode, touchTolerancePoints, point, requireReclaim,
    });
    if (dir === 0) continue;

    const atr = atrAt(bars, i, atrPeriod);
    if (atr <= 0) continue;

    const entry = bars[i].close;
    const risk = atr * slAtrMult;
    const sl = dir > 0 ? entry - risk : entry + risk;
    const tp = dir > 0 ? entry + risk * rewardR : entry - risk * rewardR;

    const { outcome, hitBar } = evaluateOutcome({
      dir, sigBar: i, lastClosed, sl, tp, bars, ambiguous,
    });

    signals.push({ index: i, time: bars[i].time, dir, entry, sl, tp, atr, outcome, hitBar });
  }

  return { vwap, ema, signals, lastClosed };
}

/** Tally resolved signals. Expectancy is in R: a win pays rewardR, a loss 1R. */
export function summarise(signals, rewardR) {
  let tp = 0, sl = 0, open = 0;
  for (const s of signals) {
    if (s.outcome === 1) tp++;
    else if (s.outcome === -1) sl++;
    else open++;
  }
  const resolved = tp + sl;
  return {
    tp,
    sl,
    open,
    resolved,
    hitRate: resolved > 0 ? tp / resolved : 0,
    expectancy: resolved > 0 ? (tp * rewardR - sl) / resolved : 0,
  };
}
