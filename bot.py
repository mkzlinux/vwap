#!/usr/bin/env python3
"""VWAP + 9EMA + ICT Silver Bullet — SIGNAL-ONLY bot for Weltrade MT5.

Reads live bars from the Weltrade MT5 terminal (via the MetaTrader5 Python
package), computes H1 bias + M15 Silver Bullet setups and prints trade ideas.
It NEVER sends orders.

Usage (on the Windows PC/VPS running Weltrade MT5):
    pip install -r requirements.txt
    copy .env.example .env   # then fill in MT5_LOGIN / MT5_PASSWORD / MT5_SERVER
    python bot.py --once     # single scan (test)
    python bot.py            # live loop every 30s (see config.yaml)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

from vwap_bot.indicators import add_indicators
from vwap_bot.mt5_client import MT5_AVAILABLE, MT5Client
from vwap_bot.signals import SignalSink, now_stamps
from vwap_bot.strategy import evaluate_symbol

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # .env overrides for secrets / terminal path
    mt5 = cfg.setdefault("mt5", {})
    if os.getenv("MT5_PATH"):
        mt5["path"] = os.getenv("MT5_PATH")
    if os.getenv("MT5_LOGIN"):
        mt5["login"] = int(os.getenv("MT5_LOGIN"))
    if os.getenv("MT5_PASSWORD"):
        mt5["password"] = os.getenv("MT5_PASSWORD")
    if os.getenv("MT5_SERVER"):
        mt5["server"] = os.getenv("MT5_SERVER")
    return cfg


def closed_bars(df):
    """Drop the still-forming bar (MT5 includes it as the last row)."""
    return df.iloc[:-1].reset_index(drop=True) if len(df) > 1 else df


def scan_once(client: MT5Client, symbols: dict, cfg: dict, sink: SignalSink,
              ignore_killzone: bool = False) -> int:
    st = cfg["strategy"]
    tf_bias = cfg["timeframes"]["bias"]
    tf_entry = cfg["timeframes"]["entry"]
    n_bias = int(cfg.get("history", {}).get("bias_bars", 400))
    n_entry = int(cfg.get("history", {}).get("entry_bars", 400))
    if ignore_killzone:
        cfg = {**cfg, "strategy": {**st, "use_killzone": False}}

    first = next(iter(symbols.values()))
    server_now = client.server_time(first)
    stamps = now_stamps(server_now)
    log.info("Scanning @ server %s (%s) — %d symbol(s)",
             stamps["server"], stamps["cat"], len(symbols))

    count = 0
    for base, broker in symbols.items():
        try:
            h1 = closed_bars(client.get_rates(broker, tf_bias, n_bias))
            m15 = closed_bars(client.get_rates(broker, tf_entry, n_entry))
            h1 = add_indicators(h1, st.get("ema_period", 9), st.get("atr_period", 14),
                                st.get("vwap_mode", "session"),
                                st.get("vwap_rolling_period", 50))
            m15 = add_indicators(m15, st.get("ema_period", 9), st.get("atr_period", 14),
                                 st.get("vwap_mode", "session"),
                                 st.get("vwap_rolling_period", 50))
            sig = evaluate_symbol(base, broker, h1, m15, server_now, cfg)
            if sig:
                sink.emit(sig, stamps)
                count += 1
            else:
                log.info("%s: no setup on %s (bias scan ok, %d M15 bars)",
                         broker, tf_entry, len(m15))
        except Exception as exc:
            log.exception("%s scan failed: %s", broker, exc)
    if count == 0:
        log.info("No signals this scan.")
    return count


def main() -> int:
    ap = argparse.ArgumentParser(description="VWAP+9EMA+ICT Silver Bullet signal bot (Weltrade MT5)")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--once", action="store_true", help="single scan then exit")
    ap.add_argument("--poll", type=int, default=None, help="override poll seconds")
    ap.add_argument("--symbols", default=None, help="comma list, e.g. XAUUSD,XAGUSD")
    ap.add_argument("--no-killzone", action="store_true", help="ignore killzone filter (testing)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    load_dotenv()
    cfg = load_config(args.config)
    if cfg["strategy"].get("mode") != "signal_only":
        log.error("Refusing to run: strategy.mode must be 'signal_only' in this build.")
        return 2
    if not MT5_AVAILABLE:
        log.error("MetaTrader5 package not installed. This bot needs Windows + the Weltrade "
                  "MT5 terminal. For a Linux smoke test run: python tools/selftest.py")
        return 2

    if args.symbols:
        cfg["symbols"] = [s.strip() for s in args.symbols.split(",") if s.strip()]

    mt5cfg = cfg["mt5"]
    client = MT5Client(path=mt5cfg.get("path", "") or "", login=mt5cfg.get("login", 0) or 0,
                       password=mt5cfg.get("password", "") or "",
                       server=mt5cfg.get("server", "") or "",
                       timeout_ms=int(mt5cfg.get("timeout_ms", 60000)))
    if not client.connect():
        log.error("Could not connect to MT5. Is the Weltrade terminal open and logged in?")
        return 2

    symbols = {}
    try:
        for base in cfg["symbols"]:
            broker = client.resolve_symbol(base)
            if broker:
                symbols[base] = broker
        if not symbols:
            log.error("No symbols resolved. Run `python tools/check_symbols.py` to list names.")
            return 2

        sink = SignalSink(cfg)
        poll = args.poll or int(cfg.get("alerts", {}).get("poll_seconds", 30))

        scan_once(client, symbols, cfg, sink, ignore_killzone=args.no_killzone)
        if args.once:
            return 0
        log.info("Live loop started (every %ds). Ctrl+C to stop. Signal-only: no orders sent.", poll)
        while True:
            time.sleep(poll)
            try:
                scan_once(client, symbols, cfg, sink, ignore_killzone=args.no_killzone)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                log.exception("Loop scan failed: %s", exc)
    except KeyboardInterrupt:
        log.info("Stopped by user.")
        return 0
    finally:
        client.shutdown()


if __name__ == "__main__":
    sys.exit(main())
