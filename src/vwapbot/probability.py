"""Probability models that turn raw data into P(event) for binary markets."""

from __future__ import annotations

import math
from typing import Sequence


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def crypto_prob_above(spot: float, strike: float, sigma: float, t_years: float) -> float:
    """P(S_T > K) under zero-drift geometric Brownian motion: N(d2).

    d2 = [ln(S/K) - sigma^2 * T / 2] / (sigma * sqrt(T)).
    `sigma` is annualised volatility, `t_years` the time to expiry in years.
    """
    if spot <= 0 or strike <= 0:
        raise ValueError("spot and strike must be positive")
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    if t_years < 0:
        raise ValueError("t_years must be non-negative")
    if t_years == 0:
        return 1.0 if spot > strike else 0.0
    d2 = (math.log(spot / strike) - 0.5 * sigma**2 * t_years) / (sigma * math.sqrt(t_years))
    return _norm_cdf(d2)


def realized_vol(prices: Sequence[float], periods_per_year: float) -> float:
    """Annualised volatility from the sample std-dev of log returns."""
    if len(prices) < 3:
        raise ValueError("need at least 3 prices to estimate volatility")
    if any(p <= 0 for p in prices):
        raise ValueError("prices must be positive")
    rets = [math.log(b / a) for a, b in zip(prices, prices[1:])]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var * periods_per_year)


def _smoothed(count: int, n: int, smoothing: float) -> float:
    return (count + smoothing) / (n + 2.0 * smoothing)


def ensemble_prob_above(members: Sequence[float], threshold: float, smoothing: float = 0.5) -> float:
    """Share of forecast ensemble members strictly above `threshold`.

    Additive smoothing keeps the result off 0 and 1, since a finite ensemble
    can never justify certainty.
    """
    if not members:
        raise ValueError("members must be non-empty")
    count = sum(1 for m in members if m > threshold)
    return _smoothed(count, len(members), smoothing)


def ensemble_prob_between(
    members: Sequence[float], lo: float, hi: float, smoothing: float = 0.5
) -> float:
    """Share of ensemble members in the half-open interval [lo, hi)."""
    if not members:
        raise ValueError("members must be non-empty")
    count = sum(1 for m in members if lo <= m < hi)
    return _smoothed(count, len(members), smoothing)
