#!/usr/bin/env python3
"""Offline backtest for the VWAP + 9EMA + ICT Silver Bullet strategy.

Two modes:
  1. MT5 mode (Windows): pulls history from the Weltrade terminal and walks
     forward bar-by-bar (no lookahead) — `python backtest.py --symbol XAUUSD`
  2. Demo mode (any OS): synthetic random-walk data — `python backtest.py --demo`

Outcome simulation: after each signal, walk the next N M15 bars; if SL prints
first → -1R, if TP1 prints first → +2R (uses cfg tp1_r), else flat at timeout.
Writes trades.csv + prints a summary.
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime

import pandas as pd
import yaml
from dotenv import load_dotenv

from vwap_bot.ict import silver_bullet_scan
from vwap_bot.indicators import add_indicators
from vwap_bot.strategy import compute_bias, in_killzone, parse_killzones

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backtest")


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def simulate_outcome(df: pd.DataFrame, from_pos: int, direction: str,
                     entry: float, sl: float, tp1: float, horizon: int = 32):
    """Walk future bars; return (result_r, exit_time, exit_note)."""
    for k in range(from_pos + 1, min(len(df), from_pos + 1 + horizon)):
        h, l = float(df["high"].iloc[k]), float(df["low"].iloc[k])
        t = df["time"].iloc[k]
        if direction == "bullish":
            hit_sl = l <= sl
            hit_tp = h >= tp1
        else:
            hit_sl = h >= sl
            hit_tp = l <= tp1
        if hit_sl and hit_tp:
            return 0.0, t, "both_same_bar(0R)"
        if hit_sl:
            return -1.0, t, "SL"
        if hit_tp:
            return 2.0, t, "TP1"
    return 0.0, df["time"].iloc[min(len(df) - 1, from_pos + horizon)], "timeout(0R)"


def run_backtest(df_h1: pd.DataFrame, df_m15: pd.DataFrame, cfg: dict,
                 max_hold_bars: int = 32, verbose: bool = False) -> pd.DataFrame:
    st = cfg["strategy"]
    killzones = parse_killzones(st.get("killzones", []))
    use_kz = st.get("use_killzone", True)
    trades = []

    # Walk M15 end-points; at each step only data up to that bar is visible.
    start = max(st.get("swing_left", 5) + st.get("swing_right", 5) + 10, 60)
    for end in range(start, len(df_m15) - 1):
        window = df_m15.iloc[: end + 1]
        setup = silver_bullet_scan(
            window,
            swing_left=st.get("swing_left", 5), swing_right=st.get("swing_right", 5),
            sweep_lookback=st.get("sweep_lookback", 30),
            mss_lookback_after_sweep=st.get("mss_lookback_after_sweep", 5),
            fvg_lookback=st.get("fvg_lookback", 5),
            fvg_min_size_atr=st.get("fvg_min_size_atr", 0.10),
            displacement_atr_mult=st.get("displacement_atr_mult", 0.8),
        )
        if setup is None:
            continue
        # Only take setups whose FVG bar is the current bar (fresh signal, no repeats).
        if setup["fvg_bar_pos"] != end:
            continue
        bar_time = window.iloc[-1]["time"]
        # HTF bias using H1 bars available as of this M15 bar.
        h1_avail = df_h1[df_h1["time"] <= bar_time]
        if len(h1_avail) < 20:
            continue
        bias = compute_bias(h1_avail, st.get("swing_left", 5), st.get("swing_right", 5))
        if st.get("require_htf_alignment", True) and bias["bias"] != setup["direction"]:
            continue
        if use_kz and in_killzone(pd.to_datetime(bar_time).to_pydatetime(), killzones) is None:
            continue
        m15_last = window.iloc[-1]
        if st.get("use_vwap_filter", True):
            if setup["direction"] == "bullish" and float(m15_last["close"]) < float(m15_last["vwap"]):
                continue
            if setup["direction"] == "bearish" and float(m15_last["close"]) > float(m15_last["vwap"]):
                continue
        if st.get("use_ema9_filter", True):
            if setup["direction"] == "bullish" and float(m15_last["close"]) < float(m15_last["ema9"]):
                continue
            if setup["direction"] == "bearish" and float(m15_last["close"]) > float(m15_last["ema9"]):
                continue

        atr = setup["atr_last"]
        buffer = float(st.get("sl_buffer_atr", 0.25)) * atr
        entry = setup["fvg_mid"]
        if setup["direction"] == "bullish":
            sl = setup["sweep_extreme"] - buffer
            risk = entry - sl
            tp1 = entry + float(st.get("tp1_r", 2.0)) * risk
        else:
            sl = setup["sweep_extreme"] + buffer
            risk = sl - entry
            tp1 = entry - float(st.get("tp1_r", 2.0)) * risk
        if risk <= 0:
            continue
        r, exit_time, note = simulate_outcome(df_m15, end, setup["direction"], entry, sl, tp1,
                                              horizon=max_hold_bars)
        trades.append({"time": bar_time, "direction": setup["direction"],
                       "bias_h1": bias["bias"], "entry": round(entry, 5),
                       "sl": round(sl, 5), "tp1": round(tp1, 5), "R": r,
                       "exit_time": exit_time, "exit": note})
        if verbose:
            log.info("%s %s entry=%s R=%s (%s)", bar_time, setup["direction"], entry, r, note)
    return pd.DataFrame(trades)


def make_demo_data(n_h1: int = 600, n_m15: int = 2400, seed: int = 7):
    """Synthetic gold-like random walk with intraday seasonality (for --demo)."""
    import numpy as np

    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-06-01", periods=n_m15, freq="15min")
    rets = rng.normal(0, 0.0011, n_m15) + 0.00003 * np.sin(np.arange(n_m15) / 96 * 2 * np.pi)
    close = 2650 * np.exp(np.cumsum(rets))
    spread = np.abs(rng.normal(0, 0.0006, n_m15))
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * (1 + spread)
    low = np.minimum(open_, close) * (1 - spread)
    vol = rng.integers(50, 500, n_m15)
    m15 = pd.DataFrame({"time": idx, "open": open_, "high": high, "low": low,
                        "close": close, "tick_volume": vol, "real_volume": vol,
                        "spread": 25})
    h1 = m15.set_index("time").resample("1h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "tick_volume": "sum", "real_volume": "sum", "spread": "mean"}).dropna().reset_index()
    return h1, m15


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--bars-h1", type=int, default=1500)
    ap.add_argument("--bars-m15", type=int, default=4000)
    ap.add_argument("--max-hold", type=int, default=32, help="max M15 bars to hold (default 32 = 8h)")
    ap.add_argument("--demo", action="store_true", help="synthetic data (no MT5 needed)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    load_dotenv()
    cfg = load_config(args.config)
    st = cfg["strategy"]

    if args.demo:
        df_h1, df_m15 = make_demo_data()
    else:
        from vwap_bot.mt5_client import MT5Client
        import os

        mt5cfg = cfg["mt5"]
        client = MT5Client(path=os.getenv("MT5_PATH", "") or mt5cfg.get("path", "") or "",
                           login=int(os.getenv("MT5_LOGIN", "0") or mt5cfg.get("login", 0) or 0),
                           password=os.getenv("MT5_PASSWORD", "") or mt5cfg.get("password", "") or "",
                           server=os.getenv("MT5_SERVER", "") or mt5cfg.get("server", "") or "")
        if not client.connect():
            log.error("MT5 connect failed.")
            return 2
        try:
            broker = client.resolve_symbol(args.symbol)
            df_h1 = client.get_rates(broker, "H1", args.bars_h1).iloc[:-1].reset_index(drop=True)
            df_m15 = client.get_rates(broker, "M15", args.bars_m15).iloc[:-1].reset_index(drop=True)
        finally:
            client.shutdown()

    df_h1 = add_indicators(df_h1, st.get("ema_period", 9), st.get("atr_period", 14),
                           st.get("vwap_mode", "session"), st.get("vwap_rolling_period", 50))
    df_m15 = add_indicators(df_m15, st.get("ema_period", 9), st.get("atr_period", 14),
                            st.get("vwap_mode", "session"), st.get("vwap_rolling_period", 50))
    trades = run_backtest(df_h1, df_m15, cfg, max_hold_bars=args.max_hold, verbose=args.verbose)
    if trades.empty:
        print("No trades in backtest window. Try --demo, more bars, or loosen filters.")
        return 0
    trades.to_csv("trades.csv", index=False)
    wins = (trades["R"] > 0).sum()
    losses = (trades["R"] < 0).sum()
    flats = (trades["R"] == 0).sum()
    print(f"Trades: {len(trades)} | Win: {wins} | Loss: {losses} | Flat: {flats} | "
          f"Total R: {trades['R'].sum():.1f}R | Avg R: {trades['R'].mean():.2f}R")
    print("Saved trades.csv")
    print(trades.tail(10).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
