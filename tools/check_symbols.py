#!/usr/bin/env python3
"""List Weltrade broker symbols matching gold/silver/synthetics.

Run on Windows with the Weltrade MT5 terminal open:
    python tools/check_symbols.py
    python tools/check_symbols.py --needle XAU
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from vwap_bot.mt5_client import MT5_AVAILABLE, MT5Client

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("check")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--needle", default=None, help="custom search, e.g. BTC")
    args = ap.parse_args()
    load_dotenv()
    if not MT5_AVAILABLE:
        log.error("MetaTrader5 not installed (Windows + MT5 terminal required).")
        return 2
    client = MT5Client(path=os.getenv("MT5_PATH", "") or "",
                       login=int(os.getenv("MT5_LOGIN", "0") or 0),
                       password=os.getenv("MT5_PASSWORD", "") or "",
                       server=os.getenv("MT5_SERVER", "") or "")
    if not client.connect():
        return 2
    try:
        needles = [args.needle] if args.needle else ["XAU", "XAG", "GOLD", "SILVER", "SYNTH"]
        for n in needles:
            found = client.find_symbols(n)
            print(f"\n── *{n}* ({len(found)}) ──")
            for s in found[:60]:
                print(f"  {s}")
            if len(found) > 60:
                print(f"  … +{len(found) - 60} more")
        print("\nTip: put the BASE name (without suffix) in config.yaml — the bot resolves it.")
    finally:
        client.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
