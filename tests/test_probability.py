import math

import pytest

from vwapbot.probability import (
    crypto_prob_above,
    ensemble_prob_above,
    ensemble_prob_between,
    realized_vol,
)


def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def test_crypto_prob_at_the_money_is_slightly_below_half():
    sigma, t = 0.5, 1 / 365
    expected = norm_cdf(-sigma * math.sqrt(t) / 2)
    assert crypto_prob_above(100, 100, sigma, t) == pytest.approx(expected)
    assert crypto_prob_above(100, 100, sigma, t) < 0.5


def test_crypto_prob_far_in_the_money_is_near_one():
    assert crypto_prob_above(150, 100, 0.5, 1 / 365) > 0.999


def test_crypto_prob_far_out_of_the_money_is_near_zero():
    assert crypto_prob_above(50, 100, 0.5, 1 / 365) < 0.001


def test_crypto_prob_at_expiry_is_deterministic():
    assert crypto_prob_above(101, 100, 0.5, 0) == 1.0
    assert crypto_prob_above(99, 100, 0.5, 0) == 0.0


@pytest.mark.parametrize("args", [(0, 100, 0.5, 1), (100, 0, 0.5, 1), (100, 100, 0, 1), (100, 100, 0.5, -1)])
def test_crypto_prob_rejects_invalid_inputs(args):
    with pytest.raises(ValueError):
        crypto_prob_above(*args)


def test_realized_vol_constant_series_is_zero():
    assert realized_vol([100.0] * 10, periods_per_year=365) == 0.0


def test_realized_vol_matches_manual_calculation():
    prices = [100.0, 101.0, 100.0, 102.0]
    rets = [math.log(b / a) for a, b in zip(prices, prices[1:])]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    assert realized_vol(prices, periods_per_year=365) == pytest.approx(math.sqrt(var * 365))


def test_realized_vol_needs_three_prices():
    with pytest.raises(ValueError):
        realized_vol([100.0, 101.0], periods_per_year=365)


def test_ensemble_prob_all_members_above_is_smoothed_below_one():
    members = [20.0] * 31
    p = ensemble_prob_above(members, 10.0)
    assert p == pytest.approx(31.5 / 32)
    assert p < 1.0


def test_ensemble_prob_no_members_above_is_smoothed_above_zero():
    p = ensemble_prob_above([5.0] * 31, 10.0)
    assert p == pytest.approx(0.5 / 32)
    assert p > 0.0


def test_ensemble_prob_split():
    members = [5.0] * 15 + [15.0] * 16
    assert ensemble_prob_above(members, 10.0) == pytest.approx((16 + 0.5) / 32)


def test_ensemble_prob_between_half_open_interval():
    members = [1.0, 2.0, 3.0, 4.0]
    # [2, 4) contains 2.0 and 3.0
    assert ensemble_prob_between(members, 2.0, 4.0, smoothing=0.0) == pytest.approx(0.5)


def test_ensemble_requires_members():
    with pytest.raises(ValueError):
        ensemble_prob_above([], 10.0)


def test_realized_vol_rejects_non_positive_prices():
    with pytest.raises(ValueError):
        realized_vol([100.0, 0.0, 101.0], periods_per_year=365)


def test_ensemble_between_requires_members():
    with pytest.raises(ValueError):
        ensemble_prob_between([], 0.0, 1.0)
