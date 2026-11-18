import pytest

from vwapbot.paper import PaperLedger


def test_buy_reduces_cash_and_opens_position():
    led = PaperLedger(cash=1000.0)
    led2 = led.buy("m1", "YES", price=0.5, stake=100.0)
    assert led.cash == 1000.0  # original untouched (immutable)
    assert led2.cash == pytest.approx(900.0)
    assert led2.positions["m1"].shares == pytest.approx(200.0)


def test_settle_win_pays_one_dollar_per_share():
    led = PaperLedger(cash=1000.0).buy("m1", "YES", 0.5, 100.0)
    led = led.settle("m1", yes_won=True)
    assert led.cash == pytest.approx(1100.0)
    assert "m1" not in led.positions
    assert led.realized_pnl == pytest.approx(100.0)


def test_settle_loss_pays_nothing():
    led = PaperLedger(cash=1000.0).buy("m1", "NO", 0.4, 100.0).settle("m1", yes_won=True)
    assert led.cash == pytest.approx(900.0)
    assert led.realized_pnl == pytest.approx(-100.0)


def test_buy_more_than_cash_is_rejected():
    with pytest.raises(ValueError):
        PaperLedger(cash=50.0).buy("m1", "YES", 0.5, 100.0)


def test_per_market_exposure_limit():
    led = PaperLedger(cash=1000.0, max_market_fraction=0.1)
    with pytest.raises(ValueError):
        led.buy("m1", "YES", 0.5, 150.0)


def test_daily_loss_limit_halts_new_buys():
    led = PaperLedger(cash=1000.0, daily_loss_limit=50.0)
    led = led.buy("m1", "YES", 0.5, 80.0).settle("m1", yes_won=False)
    assert led.halted is True
    with pytest.raises(ValueError):
        led.buy("m2", "YES", 0.5, 10.0)


def test_invalid_side_and_price_rejected():
    led = PaperLedger(cash=1000.0)
    with pytest.raises(ValueError):
        led.buy("m1", "MAYBE", 0.5, 10.0)
    with pytest.raises(ValueError):
        led.buy("m1", "YES", 1.0, 10.0)


def test_settle_unknown_market_is_error():
    with pytest.raises(KeyError):
        PaperLedger(cash=100.0).settle("nope", yes_won=True)


def test_equity_counts_open_positions_at_cost():
    led = PaperLedger(cash=1000.0).buy("m1", "YES", 0.5, 100.0)
    assert led.equity == pytest.approx(1000.0)


def test_adding_to_same_side_accumulates_and_opposite_side_is_rejected():
    led = PaperLedger(cash=1000.0).buy("m1", "YES", 0.5, 100.0).buy("m1", "YES", 0.25, 50.0)
    assert led.positions["m1"].shares == pytest.approx(200.0 + 200.0)
    assert led.positions["m1"].cost == pytest.approx(150.0)
    with pytest.raises(ValueError):
        led.buy("m1", "NO", 0.5, 10.0)


def test_new_day_lifts_halt():
    led = PaperLedger(cash=1000.0, daily_loss_limit=50.0).buy("m1", "YES", 0.5, 80.0).settle("m1", False)
    assert led.halted
    assert not led.new_day().halted
    assert led.new_day().day_pnl == 0.0


def test_non_positive_stake_rejected():
    with pytest.raises(ValueError):
        PaperLedger(cash=100.0).buy("m1", "YES", 0.5, 0.0)
