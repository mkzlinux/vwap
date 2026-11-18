"""Event-driven backtester for binary prediction markets.

Each market is entered at most once, at a fixed horizon before it ends, using
only the price visible at that time. Markets are processed in end-time order
and the bankroll compounds. Positions are treated as sequential (no overlap
accounting), which slightly flatters compounding for markets that overlap.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from .sizing import position_size

# (market, price at entry time) -> model P(YES), or None to skip
Strategy = Callable[["Market", float], Optional[float]]


@dataclass(frozen=True)
class Market:
    id: str
    category: str
    end_ts: int
    yes_won: bool
    history: tuple[tuple[int, float], ...]  # (unix ts, YES price), ascending


@dataclass(frozen=True)
class Trade:
    market_id: str
    category: str
    side: str
    entry: float
    stake: float
    pnl: float
    bankroll_after: float


@dataclass(frozen=True)
class BacktestResult:
    initial_bankroll: float
    final_bankroll: float
    trades: tuple[Trade, ...]
    max_drawdown: float

    @property
    def pnl(self) -> float:
        return self.final_bankroll - self.initial_bankroll

    @property
    def roi(self) -> float:
        return self.pnl / self.initial_bankroll if self.initial_bankroll else 0.0

    @property
    def win_rate(self) -> float:
        return sum(t.pnl > 0 for t in self.trades) / len(self.trades) if self.trades else 0.0


def load_markets(path: Path) -> list[Market]:
    """Load markets written by `vwapbot.fetch.collect` (one JSON object per line)."""
    markets = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        markets.append(
            Market(
                id=rec["id"],
                category=rec["category"],
                end_ts=rec["end_ts"],
                yes_won=rec["yes_won"],
                history=tuple((int(t), float(p)) for t, p in rec["history"]),
            )
        )
    return markets


def price_at(market: Market, ts: int) -> Optional[float]:
    """Last observed YES price at or before `ts`; None if there is none."""
    last = None
    for t, p in market.history:
        if t > ts:
            break
        last = p
    return last


def split_walk_forward(
    markets: Sequence[Market], train_fraction: float = 0.6
) -> tuple[list[Market], list[Market]]:
    """Chronological train/test split so the test set is strictly later."""
    ordered = sorted(markets, key=lambda m: m.end_ts)
    cut = int(len(ordered) * train_fraction)
    return ordered[:cut], ordered[cut:]


def run_backtest(
    markets: Sequence[Market],
    strategy: Strategy,
    *,
    bankroll: float,
    horizon_secs: int,
    kelly_multiplier: float = 0.25,
    max_fraction: float = 0.05,
    min_edge: float = 0.0,
    fee_rate: float = 0.0,
    slippage: float = 0.0,
    flat_stakes: bool = False,
) -> BacktestResult:
    """Simulate the strategy; `fee_rate` is charged on stake, `slippage` on entry price.

    `flat_stakes=True` sizes every bet off the initial bankroll (no compounding).
    Use it when many markets resolve together, where sequential compounding
    would wildly overstate returns.
    """
    cash = bankroll
    peak = bankroll
    max_dd = 0.0
    trades: list[Trade] = []

    for m in sorted(markets, key=lambda x: x.end_ts):
        px = price_at(m, m.end_ts - horizon_secs)
        if px is None or not 0.0 < px < 1.0:
            continue
        p_yes = strategy(m, px)
        if p_yes is None:
            continue

        if p_yes > px:
            side, entry, p_side = "YES", px + slippage, p_yes
        else:
            side, entry, p_side = "NO", (1.0 - px) + slippage, 1.0 - p_yes
        if not 0.0 < entry < 1.0:
            continue

        stake = position_size(
            bankroll if flat_stakes else cash,
            p_side,
            entry,
            kelly_multiplier=kelly_multiplier,
            max_fraction=max_fraction,
            min_edge=min_edge,
            costs=fee_rate * entry,
        )
        if stake <= 0:
            continue

        won = m.yes_won if side == "YES" else not m.yes_won
        gross = stake * (1.0 / entry - 1.0) if won else -stake
        pnl = gross - stake * fee_rate
        cash += pnl
        peak = max(peak, cash)
        max_dd = max(max_dd, (peak - cash) / peak if peak > 0 else 0.0)
        trades.append(Trade(m.id, m.category, side, entry, stake, pnl, cash))

    return BacktestResult(bankroll, cash, tuple(trades), max_dd)
