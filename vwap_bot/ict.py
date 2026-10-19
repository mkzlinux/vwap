"""ICT building blocks: swings, liquidity sweep, MSS, FVG, order blocks.

Silver Bullet sequence implemented in :func:`silver_bullet_scan`::

    1. Liquidity sweep  — M15 wick takes out a swing high/low then closes
       back inside (buyside/sellside raid + reclaim).
    2. Market structure shift (MSS) — displacement close through the last
       opposite swing within N bars of the sweep.
    3. Fair value gap (FVG) — 3-candle imbalance on the displacement leg.
       Entry = FVG zone (limit), SL = beyond the sweep extreme.

All functions operate on CLOSED bars only (caller must drop the forming bar).
DataFrame columns required: time, open, high, low, close, atr.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class Swing:
    pos: int
    time: datetime
    price: float
    kind: str  # "high" | "low"


# ── swings ──────────────────────────────────────────────────
def find_swings(df, left: int = 5, right: int = 5) -> List[Swing]:
    """Fractal swings: bar i is a swing high if its high is the max of
    [i-left, i+right], swing low if its low is the min of that window."""
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    times = df["time"].tolist()
    n = len(df)
    swings: List[Swing] = []
    for i in range(left, n - right):
        window_h = highs[i - left:i + right + 1]
        window_l = lows[i - left:i + right + 1]
        if highs[i] == window_h.max() and (highs[i] > highs[i - 1] or highs[i] > highs[i + 1]):
            # Strict-ish fractal: must exceed at least one neighbour to cut plateaus.
            swings.append(Swing(i, times[i], float(highs[i]), "high"))
        if lows[i] == window_l.min() and (lows[i] < lows[i - 1] or lows[i] < lows[i + 1]):
            swings.append(Swing(i, times[i], float(lows[i]), "low"))
    swings.sort(key=lambda s: s.pos)
    return swings


def _last_swing_before(swings: List[Swing], kind: str, pos: int,
                       confirm_right: int, confirmed_at: int) -> Optional[Swing]:
    """Most recent confirmed swing of `kind` strictly before `pos`.

    A swing at p is only *known* at bar p + confirm_right, so for a signal
    evaluated at bar `confirmed_at` we require p + confirm_right <= confirmed_at
    (no lookahead bias in backtests).
    """
    best = None
    for s in swings:
        if s.kind != kind or s.pos >= pos:
            continue
        if s.pos + confirm_right > confirmed_at:
            continue
        best = s
    return best


def _has_twin(swings: List[Swing], ref: Swing, tol: float) -> bool:
    """Equal highs/lows: another swing of same kind within `tol` price."""
    for s in swings:
        if s is ref or s.kind != ref.kind:
            continue
        if abs(s.price - ref.price) <= tol:
            return True
    return False


# ── fair value gaps ─────────────────────────────────────────
def detect_fvgs(df, start: int, end: int, direction: str,
                min_size_atr: float = 0.10) -> List[Dict]:
    """Unmitigated FVGs of `direction` with gap-bar in [start, end].

    Bullish FVG at k: low[k] > high[k-2]  → zone [high[k-2], low[k]].
    Bearish FVG at k: high[k] < low[k-2]  → zone [high[k], low[k-2]].
    Mitigation = a later close through the zone (invalidation).
    """
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    atrs = df["atr"].to_numpy()
    times = df["time"].tolist()
    n = len(df)
    out: List[Dict] = []
    for k in range(max(2, start), min(end, n - 1) + 1):
        atr_k = float(atrs[k]) or 1e-9
        if direction == "bullish":
            bottom, top = float(highs[k - 2]), float(lows[k])
            if top <= bottom:
                continue
            if (top - bottom) < min_size_atr * atr_k:
                continue
            if any(closes[t] < bottom for t in range(k + 1, n)):
                continue  # closed through → mitigated/failed
        else:
            top, bottom = float(lows[k - 2]), float(highs[k])
            if top <= bottom:
                continue
            if (top - bottom) < min_size_atr * atr_k:
                continue
            if any(closes[t] > top for t in range(k + 1, n)):
                continue
        out.append({"top": top, "bottom": bottom, "mid": (top + bottom) / 2.0,
                    "bar_time": times[k], "bar_pos": k})
    return out


def find_order_block(df, start: int, end: int, direction: str) -> Optional[Dict]:
    """Last opposite-colour candle before the displacement leg."""
    opens = df["open"].to_numpy()
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    times = df["time"].tolist()
    for k in range(min(end, len(df) - 1), max(0, start) - 1, -1):
        if direction == "bullish" and closes[k] < opens[k]:
            return {"top": float(opens[k]), "bottom": float(lows[k]),
                    "bar_time": times[k], "bar_pos": k}
        if direction == "bearish" and closes[k] > opens[k]:
            return {"top": float(highs[k]), "bottom": float(opens[k]),
                    "bar_time": times[k], "bar_pos": k}
    return None


# ── Silver Bullet scan ──────────────────────────────────────
def silver_bullet_scan(df, swing_left: int = 5, swing_right: int = 5,
                       sweep_lookback: int = 30,
                       mss_lookback_after_sweep: int = 5,
                       fvg_lookback: int = 5,
                       fvg_min_size_atr: float = 0.10,
                       displacement_atr_mult: float = 0.8) -> Optional[Dict]:
    """Scan M15 closed bars for a completed sweep → MSS → FVG setup.

    Returns the *most recent* valid setup or None. Walk-back design:
    for each candidate sweep bar (newest first) require MSS after it and
    a fresh FVG on/after the MSS leg.
    """
    n = len(df)
    min_bars = swing_left + swing_right + 6
    if n < min_bars:
        return None

    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    atrs = df["atr"].to_numpy()
    times = df["time"].tolist()
    swings = find_swings(df, swing_left, swing_right)
    if not swings:
        return None

    max_sweep_age = mss_lookback_after_sweep + fvg_lookback + 1

    for age in range(0, max_sweep_age + 1):
        i = n - 1 - age  # candidate sweep bar
        if i < swing_left + 2:
            break
        atr_i = float(atrs[i]) or 1e-9

        # Swings known as of bar i (confirmed, strictly before i).
        sw_high = _last_swing_before(swings, "high", i, swing_right, i)
        sw_low = _last_swing_before(swings, "low", i, swing_right, i)

        swept_dir, swept_level, swept_swing = None, None, None
        # Bearish setup precursor: raid on buyside (above swing high), close back under.
        if sw_high is not None and (i - sw_high.pos) <= sweep_lookback:
            if highs[i] > sw_high.price and closes[i] < sw_high.price:
                swept_dir, swept_level, swept_swing = "bearish", sw_high.price, sw_high
        # Bullish setup precursor: raid on sellside (below swing low), close back over.
        if swept_dir is None and sw_low is not None and (i - sw_low.pos) <= sweep_lookback:
            if lows[i] < sw_low.price and closes[i] > sw_low.price:
                swept_dir, swept_level, swept_swing = "bullish", sw_low.price, sw_low
        if swept_dir is None:
            continue

        # ── MSS within N bars after the sweep ──
        mss = None
        mss_end = min(n - 1, i + mss_lookback_after_sweep)
        for j in range(i + 1, mss_end + 1):
            atr_j = float(atrs[j]) or 1e-9
            displacement = (highs[j] - lows[j]) >= displacement_atr_mult * atr_j
            if swept_dir == "bullish":
                level = _last_swing_before(swings, "high", j, swing_right, j)
                if level is not None and closes[j] > level.price and displacement:
                    mss = {"pos": j, "time": times[j], "broken_level": float(level.price),
                           "atr": atr_j, "range": float(highs[j] - lows[j])}
                    break
            else:
                level = _last_swing_before(swings, "low", j, swing_right, j)
                if level is not None and closes[j] < level.price and displacement:
                    mss = {"pos": j, "time": times[j], "broken_level": float(level.price),
                           "atr": atr_j, "range": float(highs[j] - lows[j])}
                    break
        if mss is None:
            continue

        # ── Fresh FVG on/after the MSS leg ──
        fvg_start = max(2, mss["pos"] - 1)
        fvg_end = min(n - 1, mss["pos"] + fvg_lookback)
        fvgs = detect_fvgs(df, fvg_start, fvg_end, swept_dir, fvg_min_size_atr)
        if not fvgs:
            continue
        fvg = fvgs[-1]  # most recent unmitigated gap

        ob = find_order_block(df, i, mss["pos"], swept_dir)
        eql_tol = 0.15 * atr_i
        swept_eql = _has_twin(swings, swept_swing, eql_tol)

        last_close = float(closes[n - 1])
        atr_last = float(atrs[n - 1]) or 1e-9
        in_zone = (fvg["bottom"] - 0.25 * atr_last) <= last_close <= (fvg["top"] + 0.25 * atr_last)

        return {
            "direction": swept_dir,
            "sweep_bar_time": times[i], "sweep_bar_pos": i,
            "swept_level": float(swept_level),
            "swept_swing_time": swept_swing.time,
            "swept_eql": swept_eql,
            "sweep_extreme": float(lows[i]) if swept_dir == "bullish" else float(highs[i]),
            "mss_bar_time": mss["time"], "mss_bar_pos": mss["pos"],
            "broken_level": mss["broken_level"],
            "displacement_range": mss["range"], "atr_at_mss": mss["atr"],
            "fvg_top": fvg["top"], "fvg_bottom": fvg["bottom"], "fvg_mid": fvg["mid"],
            "fvg_bar_time": fvg["bar_time"], "fvg_bar_pos": fvg["bar_pos"],
            "ob_top": ob["top"] if ob else None,
            "ob_bottom": ob["bottom"] if ob else None,
            "ob_bar_time": ob["bar_time"] if ob else None,
            "price_in_zone": in_zone,
            "last_close": last_close, "atr_last": atr_last,
        }
    return None


def last_structure_break(df, swing_left: int = 5, swing_right: int = 5) -> Optional[Dict]:
    """Most recent close through a confirmed swing (for HTF bias context)."""
    n = len(df)
    if n < swing_left + swing_right + 3:
        return None
    closes = df["close"].to_numpy()
    times = df["time"].tolist()
    swings = find_swings(df, swing_left, swing_right)
    for j in range(n - 1, swing_left, -1):
        sh = _last_swing_before(swings, "high", j, swing_right, j)
        sl = _last_swing_before(swings, "low", j, swing_right, j)
        if sh is not None and closes[j] > sh.price and closes[j - 1] <= sh.price:
            return {"direction": "bullish", "bar_time": times[j], "level": float(sh.price)}
        if sl is not None and closes[j] < sl.price and closes[j - 1] >= sl.price:
            return {"direction": "bearish", "bar_time": times[j], "level": float(sl.price)}
    return None
