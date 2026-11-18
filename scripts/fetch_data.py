"""Download resolved Polymarket weather and crypto markets into data/*.jsonl.

Usage: python scripts/fetch_data.py [--weather N] [--crypto N]
Read-only public APIs; no keys required. Safe to re-run (it appends new markets only).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from vwapbot.fetch import collect  # noqa: E402

DATA = ROOT / "data"

# (category, gamma tag, output file, history fidelity in minutes)
SOURCES = {
    "weather": ("weather", "daily-temperature", DATA / "weather.jsonl", 60),
    "crypto": ("crypto", "up-or-down", DATA / "crypto.jsonl", 1),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weather", type=int, default=600, help="max weather markets")
    parser.add_argument("--crypto", type=int, default=400, help="max crypto up/down markets")
    parser.add_argument("--weather-stride", type=int, default=1, help="keep every k-th weather event")
    parser.add_argument("--crypto-stride", type=int, default=1, help="keep every k-th crypto event")
    parser.add_argument("--max-events", type=int, default=1000, help="events to scan per category")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    log = logging.getLogger("fetch_data")

    plan = (
        ("weather", args.weather, args.weather_stride),
        ("crypto", args.crypto, args.crypto_stride),
    )
    for key, limit, stride in plan:
        category, tag, out, fidelity = SOURCES[key]
        if limit <= 0:
            continue
        saved = collect(
            category, tag, out, max_markets=limit, fidelity=fidelity,
            max_events=args.max_events, event_stride=stride,
        )
        log.info("%s: saved %d new markets -> %s", category, saved, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
