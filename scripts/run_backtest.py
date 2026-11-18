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
import random
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
SLIPPAGES = (0.01, 0.03, 0.05)  # thin books: real spreads are unknown, so sweep them
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


def cluster_bootstrap(trades, end_of: dict[str, int], n_boot: int = 2000, seed: int = 7):
    """Mean return-on-stake with a 95% CI from resampling whole calendar days.

    Markets that resolve the same day share weather/price regimes, so days (not
    individual trades) are the independent units.
    """
    by_day: dict[int, list[float]] = {}
    for t in trades:
        by_day.setdefault(end_of[t.market_id] // 86400, []).append(t.pnl / t.stake)
    days = list(by_day.values())
    if len(days) < 3:
        return 0.0, float("-inf"), float("inf")

    def mean_of(sample) -> float:
        flat = [r for d in sample for r in d]
        return sum(flat) / len(flat)

    rng = random.Random(seed)
    boots = sorted(mean_of([rng.choice(days) for _ in days]) for _ in range(n_boot))
    return mean_of(days), boots[int(0.025 * n_boot)], boots[int(0.975 * n_boot)]


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

        end_of = {m.id: m.end_ts for m in test}
        for slip in SLIPPAGES:
            res = run_backtest(
                test, strategy, bankroll=args.bankroll, horizon_secs=h,
                kelly_multiplier=0.25, max_fraction=0.01, min_edge=0.05,
                fee_rate=fee, slippage=slip, flat_stakes=True,
            )
            mean, lo, hi = cluster_bootstrap(res.trades, end_of)
            head = (f"  slip {slip:.0%}: trades={len(res.trades):4d} win={res.win_rate:5.1%}"
                    f" flat-stake pnl=${res.pnl:8.2f}")
            if lo == float("-inf"):
                print(f"{head}  -> too few calendar days for a confidence interval (need >= 3)")
                continue
            verdict = "edge survives" if lo > 0 else "NOT distinguishable from zero/loss"
            print(f"{head}  return/stake {mean:+6.1%} [95% CI {lo:+6.1%}, {hi:+6.1%}] -> {verdict}")


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
    print(f"\nFlat stakes (1% of bankroll, no compounding), min edge 5%, crypto fee"
          f" {CONFIG['crypto'][2]:.0%} of stake, price band {PRICE_BAND}."
          " History has no bid/ask, so treat all results as optimistic. Past results are not a forecast.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
