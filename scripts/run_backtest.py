"""Walk-forward market-calibration backtest on data/*.jsonl.

Question answered: are Polymarket prices well calibrated at a given horizon
before resolution, and can a calibration map fitted on EARLIER markets earn
money on LATER markets after fees and slippage?

Method (no look-ahead):
  1. Entry price = last price at (end_ts - horizon).
  2. Chronological split: fit on the first part, trade the last part. Test
     markets whose entry time precedes the last training resolution are dropped.
  3. Strategy: p_model = calibration(price); trade the side with positive edge.

Usage: python scripts/run_backtest.py [--train 0.6] [--bankroll 1000]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from vwapbot.backtest import (  # noqa: E402
    Market,
    load_markets,
    price_at,
    run_backtest,
    split_walk_forward,
)
from vwapbot.calibration import brier_score, fit_calibration, reliability_table  # noqa: E402

DATA = ROOT / "data"
MIN, HOUR = 60, 3600

# category -> (file, horizons in seconds, taker fee rate on stake)
CONFIG = {
    "weather": (DATA / "weather.jsonl", [24 * HOUR, 12 * HOUR, 6 * HOUR, 1 * HOUR], 0.0),
    # CLOB history for these markets is ~10 min apart, so sub-5m horizons just re-read stale points
    "crypto": (DATA / "crypto.jsonl", [10 * MIN, 5 * MIN], 0.02),
}
PRICE_BAND = (0.03, 0.97)  # ignore near-certain prices: no real liquidity to fill
SLIPPAGE = 0.01
MIN_TEST_MARKETS = 30


def label(secs: int) -> str:
    return f"{secs // HOUR}h" if secs >= HOUR else f"{secs // MIN}m"


def entry_pairs(markets: list[Market], horizon: int) -> list[tuple[float, int]]:
    out = []
    for m in markets:
        px = price_at(m, m.end_ts - horizon)
        if px is not None and 0.0 < px < 1.0:
            out.append((px, int(m.yes_won)))
    return out


def median_staleness(markets: list[Market], horizon: int) -> int:
    """Median seconds between the entry price's timestamp and the intended entry time."""
    lags = sorted(
        (m.end_ts - horizon) - max(t for t, _ in m.history if t <= m.end_ts - horizon)
        for m in markets
        if any(t <= m.end_ts - horizon for t, _ in m.history)
    )
    return lags[len(lags) // 2] if lags else -1


def purge(train: list[Market], test: list[Market], horizon: int) -> list[Market]:
    """Drop test markets entered before the last training market resolved."""
    cutoff = max(m.end_ts for m in train)
    return [m for m in test if m.end_ts - horizon > cutoff]


def report(category: str, markets: list[Market], horizons: list[int], fee: float, args) -> None:
    days = len({m.end_ts // 86400 for m in markets})
    print(f"\n=== {category.upper()}  ({len(markets)} resolved markets over {days} calendar days) ===")
    if len(markets) < 2 * MIN_TEST_MARKETS:
        print("  not enough data yet")
        return
    train, test_all = split_walk_forward(markets, args.train)
    for h in horizons:
        test = purge(train, test_all, h)
        tr, te = entry_pairs(train, h), entry_pairs(test, h)
        stale = median_staleness(test, h)
        print(f"\n-- horizon {label(h)}: train {len(tr)} / test {len(te)} markets"
              f" (median price age {stale // MIN}m)")
        if len(tr) < MIN_TEST_MARKETS or len(te) < MIN_TEST_MARKETS:
            print("  too few markets at this horizon")
            continue
        cal = fit_calibration([p for p, _ in tr], [o for _, o in tr], bins=10, shrinkage=args.shrinkage)
        raw_brier = brier_score([p for p, _ in te], [o for _, o in te])
        cal_brier = brier_score([cal(p) for p, _ in te], [o for _, o in te])
        print(f"  test Brier: market price {raw_brier:.4f} | calibrated {cal_brier:.4f}"
              f" ({'better' if cal_brier < raw_brier else 'NOT better'})")
        if h == horizons[0]:
            print("  reliability on TRAIN (price bin -> observed YES freq):")
            for b in reliability_table([p for p, _ in tr], [o for _, o in tr], bins=10):
                print(f"    {b.lo:.1f}-{b.hi:.1f}  n={b.n:4d}  price={b.mean_pred:.3f}  observed={b.freq:.3f}")

        def strategy(m: Market, px: float):
            return cal(px) if PRICE_BAND[0] <= px <= PRICE_BAND[1] else None

        for min_edge in (0.03, 0.06):
            res = run_backtest(
                test, strategy, bankroll=args.bankroll, horizon_secs=h,
                kelly_multiplier=0.25, max_fraction=0.05, min_edge=min_edge,
                fee_rate=fee, slippage=SLIPPAGE,
            )
            print(f"  min_edge {min_edge:.2f}: trades={len(res.trades):4d} win={res.win_rate:5.1%}"
                  f" pnl=${res.pnl:9.2f} roi={res.roi:7.1%} maxDD={res.max_drawdown:5.1%}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=float, default=0.6)
    parser.add_argument("--bankroll", type=float, default=1000.0)
    parser.add_argument("--shrinkage", type=float, default=20.0)
    args = parser.parse_args()

    for category, (path, horizons, fee) in CONFIG.items():
        if not path.exists():
            print(f"\n=== {category.upper()}: {path.name} missing, run scripts/fetch_data.py ===")
            continue
        report(category, load_markets(path), horizons, fee, args)
    print(f"\nCosts: slippage {SLIPPAGE:.0%} on entry, crypto fee {CONFIG['crypto'][2]:.0%} of stake,"
          f" price band {PRICE_BAND}. Past results are not a forecast.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
