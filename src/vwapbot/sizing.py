"""Edge and Kelly position sizing for binary (YES/NO) prediction-market contracts.

A YES share costs `price` and pays $1 if the event happens, so the net odds
are b = (1 - price) / price and the Kelly fraction simplifies to
f* = (p - price) / (1 - price).
"""

from __future__ import annotations


def _validate(p_model: float, price: float) -> None:
    if not 0.0 <= p_model <= 1.0:
        raise ValueError(f"p_model must be in [0, 1], got {p_model}")
    if not 0.0 < price < 1.0:
        raise ValueError(f"price must be in (0, 1), got {price}")


def edge(p_model: float, price: float, costs: float = 0.0) -> float:
    """Expected profit per $1 of payout after fees/slippage (`costs`)."""
    _validate(p_model, price)
    return p_model - price - costs


def kelly_fraction(p_model: float, price: float) -> float:
    """Full-Kelly bankroll fraction for buying YES; 0 when there is no edge."""
    _validate(p_model, price)
    return max(0.0, (p_model - price) / (1.0 - price))


def position_size(
    bankroll: float,
    p_model: float,
    price: float,
    *,
    kelly_multiplier: float = 0.25,
    max_fraction: float = 0.05,
    min_edge: float = 0.0,
    costs: float = 0.0,
) -> float:
    """Dollar stake: fractional Kelly, capped, and zero below `min_edge`."""
    if bankroll < 0:
        raise ValueError("bankroll must be non-negative")
    if edge(p_model, price, costs) <= min_edge:
        return 0.0
    fraction = min(kelly_fraction(p_model, price) * kelly_multiplier, max_fraction)
    return bankroll * fraction
