import pytest

from vwapbot.sizing import edge, kelly_fraction, position_size


def test_edge_is_model_probability_minus_price_minus_costs():
    assert edge(p_model=0.60, price=0.50, costs=0.02) == pytest.approx(0.08)


def test_kelly_zero_when_no_edge():
    assert kelly_fraction(p_model=0.50, price=0.50) == 0.0


def test_kelly_zero_when_edge_negative():
    assert kelly_fraction(p_model=0.40, price=0.50) == 0.0


def test_kelly_matches_binary_contract_formula():
    # f* = (p - price) / (1 - price)
    assert kelly_fraction(p_model=0.60, price=0.50) == pytest.approx(0.2)


@pytest.mark.parametrize("price", [0.0, 1.0, -0.1, 1.5])
def test_kelly_rejects_invalid_price(price):
    with pytest.raises(ValueError):
        kelly_fraction(p_model=0.6, price=price)


@pytest.mark.parametrize("p", [-0.1, 1.1])
def test_kelly_rejects_invalid_probability(p):
    with pytest.raises(ValueError):
        kelly_fraction(p_model=p, price=0.5)


def test_position_size_uses_fractional_kelly_and_cap():
    # full kelly 0.2 * 0.25 = 0.05 of bankroll = $50
    assert position_size(1000, 0.60, 0.50, kelly_multiplier=0.25, max_fraction=0.10) == pytest.approx(50)
    # cap binds: 0.2 * 1.0 = 0.2 > 0.10 cap
    assert position_size(1000, 0.60, 0.50, kelly_multiplier=1.0, max_fraction=0.10) == pytest.approx(100)


def test_position_size_zero_below_min_edge():
    assert position_size(1000, 0.52, 0.50, min_edge=0.05) == 0.0


def test_position_size_rejects_negative_bankroll():
    with pytest.raises(ValueError):
        position_size(-1, 0.6, 0.5)
