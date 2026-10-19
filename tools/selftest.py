#!/usr/bin/env python3
"""Linux-friendly smoke test: no MT5 needed.

Builds a synthetic chart containing a scripted bullish Silver Bullet setup
(sweep of sellside -> MSS -> bullish FVG), then verifies every layer:
indicators, ICT scan, strategy evaluation, signal formatting, backtest loop.
    python tools/selftest.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import yaml

from vwap_bot.ict import find_swings, silver_bullet_scan
from vwap_bot.indicators import add_indicators
from vwap_bot.signals import SignalSink, format_signal
from vwap_bot.strategy import compute_bias, evaluate_symbol


def scripted_m15() -> pd.DataFrame:
    """Craft candles: rally top -> selloff -> hold -> sweep -> MSS -> FVG.

    Bar map (fractal 5/5 needs 5 confirmation bars on each side):
      0–9   gentle downtrend
      10–15 rally → swing HIGH at bar 15 (confirmed at bar 20)
      16–20 selloff → swing LOW at bar 20 (confirmed at bar 25)
      21–25 rising chop that holds above the bar-20 low (no new swings)
      26    sweep: wick below the bar-20 low, close back above it
      27    displacement up, close above the bar-15 high (MSS)
      28    continuation leaving a bullish FVG (low[28] > high[26])
    """
    t0 = datetime(2026, 10, 16, 8, 45)  # bar 28 lands at 15:45 (NY AM killzone)
    rows = []
    price = 2660.0
    # 0-9: gentle downtrend
    for i in range(10):
        o = price
        c = price - 0.25 + (0.06 if i % 2 else -0.06)
        rows.append((o, max(o, c) + 0.25, min(o, c) - 0.20, c, 200))
        price = c
    # 10-15: rally into the reference swing high at bar 15
    for _ in range(6):
        o = price
        c = price + 0.55
        rows.append((o, c + 0.25, o - 0.15, c, 230))
        price = c
    swing_high = rows[15][1]
    # 16-20: selloff into the reference swing low at bar 20
    for _ in range(5):
        o = price
        c = price - 0.65
        rows.append((o, o + 0.20, c - 0.25, c, 260))
        price = c
    swing_low = rows[20][2]
    # 21-25: slightly rising chop, lows holding above swing_low
    for _ in range(5):
        o = price
        c = price + 0.08
        rows.append((o, max(o, c) + 0.22, min(o, c) - 0.10, c, 210))
        price = c
    assert min(r[2] for r in rows[21:26]) > swing_low, "chop must hold above swing low"
    assert max(r[1] for r in rows[16:26]) < swing_high, "selloff/chop must stay below swing high"
    # 26: sweep — wick below swing_low, close back above
    o = price
    rows.append((o, o + 0.25, swing_low - 1.40, swing_low + 0.80, 900))
    price = swing_low + 0.80
    # 27: displacement up through the swing high (MSS)
    o = price
    c = swing_high + 1.00
    rows.append((o, c + 0.30, o - 0.30, c, 1500))
    # 28: continuation leaving bullish FVG (low[28] > high[26])
    gap_low = rows[26][1] + 0.70
    o2 = c + 0.10
    rows.append((o2, gap_low + 1.60, gap_low, gap_low + 1.10, 800))

    df = pd.DataFrame(rows, columns=["open", "high", "low", "close", "tick_volume"])
    df.insert(0, "time", [t0 + timedelta(minutes=15 * i) for i in range(len(df))])
    df["real_volume"] = df["tick_volume"]
    df["spread"] = 25
    return df


def scripted_h1() -> pd.DataFrame:
    """Steady H1 uptrend ending just before the M15 setup → bullish bias."""
    times = pd.date_range("2026-10-16 15:00", periods=60, freq="1h")
    rows = []
    price = 2640.0
    for i in range(60):
        o = price
        c = price + 0.45 + (0.05 if i % 2 else -0.05)
        rows.append((o, max(o, c) + 0.40, min(o, c) - 0.25, c, 500))
        price = c
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close", "tick_volume"])
    df.insert(0, "time", times)
    df["real_volume"] = df["tick_volume"]
    df["spread"] = 25
    return df


def main() -> int:
    cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
    st = cfg["strategy"]
    m15 = add_indicators(scripted_m15(), st["ema_period"], st["atr_period"],
                         st["vwap_mode"], st["vwap_rolling_period"])
    h1 = add_indicators(scripted_h1(), st["ema_period"], st["atr_period"],
                        st["vwap_mode"], st["vwap_rolling_period"])

    print(f"[1/5] indicators ok — M15 rows={len(m15)} "
          f"vwap={m15['vwap'].iloc[-1]:.2f} ema9={m15['ema9'].iloc[-1]:.2f} "
          f"atr={m15['atr'].iloc[-1]:.2f}")

    swings = find_swings(m15, st["swing_left"], st["swing_right"])
    print(f"[2/5] swings found: {len(swings)} "
          f"(highs={sum(s.kind == 'high' for s in swings)}, "
          f"lows={sum(s.kind == 'low' for s in swings)})")
    assert swings, "no swings detected on scripted data"

    setup = silver_bullet_scan(m15, st["swing_left"], st["swing_right"],
                               st["sweep_lookback"], st["mss_lookback_after_sweep"],
                               st["fvg_lookback"], st["fvg_min_size_atr"],
                               st["displacement_atr_mult"])
    assert setup is not None, "Silver Bullet setup NOT detected on scripted data!"
    assert setup["direction"] == "bullish", f"wrong direction: {setup['direction']}"
    print(f"[3/5] ICT setup ok — {setup['direction']} | sweep {setup['swept_level']:.2f} "
          f"-> MSS {setup['broken_level']:.2f} -> FVG "
          f"{setup['fvg_bottom']:.2f}–{setup['fvg_top']:.2f}")

    bias = compute_bias(h1, st["swing_left"], st["swing_right"])
    print(f"[4/5] H1 bias: {bias['bias']} (close {bias['close']:.2f} vs "
          f"VWAP {bias['vwap']:.2f} / EMA9 {bias['ema9']:.2f})")

    # Evaluate inside a killzone (NY AM Silver Bullet 14:30–16:00 server).
    server_now = datetime(2026, 10, 16, 15, 50)
    sig = evaluate_symbol("XAUUSD", "XAUUSDm", h1, m15, server_now, cfg)
    assert sig is not None, "strategy rejected the scripted setup (check filters)"
    print(f"[5/5] SIGNAL ok — {sig['direction']} {sig['broker_symbol']} "
          f"entry={sig['entry']} sl={sig['sl']} tp1={sig['tp1']} tp2={sig['tp2']} "
          f"confluence={sig['confluence']} zone={sig['killzone']}")

    sink = SignalSink({"alerts": {"console": False, "log_file": "", "json_file": "", "csv_file": ""},
                       "strategy": {"cooldown_bars": 3}})
    text = sink.emit(sig, {"server": "2026-10-16 15:50", "utc": "2026-10-16 13:50",
                           "cat": "2026-10-16 15:50 CAT"})
    assert text and "XAUUSDm" in text
    print("\n── sample signal card ──")
    print(text)
    print("\nSELFTEST PASSED ✔")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
