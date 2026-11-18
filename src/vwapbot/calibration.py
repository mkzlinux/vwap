"""Forecast scoring and empirical calibration (does a 10% price mean 10%?)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

_MIN_P, _MAX_P = 0.001, 0.999


@dataclass(frozen=True)
class Bin:
    lo: float
    hi: float
    n: int
    mean_pred: float
    freq: float


def brier_score(preds: Sequence[float], outcomes: Sequence[int]) -> float:
    """Mean squared error between probabilities and 0/1 outcomes (lower is better)."""
    if len(preds) != len(outcomes):
        raise ValueError("preds and outcomes must be the same length")
    if not preds:
        raise ValueError("need at least one forecast")
    return sum((p - o) ** 2 for p, o in zip(preds, outcomes)) / len(preds)


def _bin_index(p: float, bins: int) -> int:
    return min(int(p * bins), bins - 1)


def reliability_table(preds: Sequence[float], outcomes: Sequence[int], bins: int = 10) -> list[Bin]:
    """Per-bin predicted-vs-observed frequencies; empty bins are omitted."""
    if len(preds) != len(outcomes):
        raise ValueError("preds and outcomes must be the same length")
    grouped: dict[int, list[tuple[float, int]]] = {}
    for p, o in zip(preds, outcomes):
        grouped.setdefault(_bin_index(p, bins), []).append((p, o))
    rows = []
    for idx in sorted(grouped):
        items = grouped[idx]
        n = len(items)
        rows.append(
            Bin(
                lo=idx / bins,
                hi=(idx + 1) / bins,
                n=n,
                mean_pred=sum(p for p, _ in items) / n,
                freq=sum(o for _, o in items) / n,
            )
        )
    return rows


def fit_calibration(
    preds: Sequence[float],
    outcomes: Sequence[int],
    bins: int = 10,
    shrinkage: float = 20.0,
) -> Callable[[float], float]:
    """Fit a bin-wise calibration map, shrunk toward the input price.

    estimate = (n * observed_freq + shrinkage * mean_pred) / (n + shrinkage)
    so sparse bins stay close to the market price and only well-populated
    bins can move the estimate far. Unseen bins return the input unchanged.
    """
    table = {_bin_index(b.mean_pred, bins): b for b in reliability_table(preds, outcomes, bins)}

    def calibrate(price: float) -> float:
        b = table.get(_bin_index(price, bins))
        if b is None:
            return price
        est = (b.n * b.freq + shrinkage * b.mean_pred) / (b.n + shrinkage)
        return min(_MAX_P, max(_MIN_P, est))

    return calibrate
