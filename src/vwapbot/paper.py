"""Paper-trading ledger: immutable, with exposure and daily-loss risk limits."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Mapping, Optional

SIDES = ("YES", "NO")


@dataclass(frozen=True)
class Position:
    side: str
    shares: float
    cost: float


@dataclass(frozen=True)
class PaperLedger:
    cash: float
    positions: Mapping[str, Position] = field(default_factory=lambda: MappingProxyType({}))
    realized_pnl: float = 0.0
    day_pnl: float = 0.0
    max_market_fraction: float = 1.0
    daily_loss_limit: Optional[float] = None
    halted: bool = False

    @property
    def equity(self) -> float:
        """Cash plus open positions at cost (no mark-to-market)."""
        return self.cash + sum(p.cost for p in self.positions.values())

    def buy(self, market_id: str, side: str, price: float, stake: float) -> "PaperLedger":
        if self.halted:
            raise ValueError("trading halted: daily loss limit reached")
        if side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}")
        if not 0.0 < price < 1.0:
            raise ValueError("price must be in (0, 1)")
        if stake <= 0:
            raise ValueError("stake must be positive")
        if stake > self.cash:
            raise ValueError("insufficient cash")

        existing = self.positions.get(market_id)
        if existing is not None and existing.side != side:
            raise ValueError("cannot hold both sides of one market")
        exposure = stake + (existing.cost if existing else 0.0)
        if exposure > self.max_market_fraction * self.equity:
            raise ValueError("per-market exposure limit exceeded")

        pos = Position(
            side=side,
            shares=stake / price + (existing.shares if existing else 0.0),
            cost=exposure,
        )
        positions = {**self.positions, market_id: pos}
        return replace(self, cash=self.cash - stake, positions=MappingProxyType(positions))

    def settle(self, market_id: str, yes_won: bool) -> "PaperLedger":
        pos = self.positions[market_id]  # KeyError for an unknown market
        won = (pos.side == "YES") == yes_won
        payout = pos.shares if won else 0.0
        pnl = payout - pos.cost
        remaining = {k: v for k, v in self.positions.items() if k != market_id}
        day_pnl = self.day_pnl + pnl
        halted = self.halted or (
            self.daily_loss_limit is not None and day_pnl <= -self.daily_loss_limit
        )
        return replace(
            self,
            cash=self.cash + payout,
            positions=MappingProxyType(remaining),
            realized_pnl=self.realized_pnl + pnl,
            day_pnl=day_pnl,
            halted=halted,
        )

    def new_day(self) -> "PaperLedger":
        """Reset the daily loss counter and lift a loss-limit halt."""
        return replace(self, day_pnl=0.0, halted=False)
