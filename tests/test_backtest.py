import pytest

from vwapbot.backtest import Market, price_at, run_backtest, split_walk_forward

HOUR = 3600


def make_market(mid="m", end=100 * HOUR, yes_won=True, price=0.5, category="weather"):
    history = ((end - 10 * HOUR, price), (end - HOUR, price))
    return Market(id=mid, category=category, end_ts=end, yes_won=yes_won, history=history)


def test_price_at_returns_last_price_at_or_before_ts():
    m = make_market(price=0.4)
    assert price_at(m, m.end_ts - 5 * HOUR) == 0.4
    assert price_at(m, m.end_ts - 20 * HOUR) is None


def test_backtest_yes_win_pnl():
    m = make_market(yes_won=True, price=0.5)
    res = run_backtest(
        [m], lambda mk, px: 0.6, bankroll=1000, horizon_secs=2 * HOUR,
        kelly_multiplier=1.0, max_fraction=0.5, fee_rate=0.0, slippage=0.0,
    )
    # kelly 0.2 -> stake 200, buy at 0.5, win => +200
    assert len(res.trades) == 1
    assert res.trades[0].side == "YES"
    assert res.trades[0].stake == pytest.approx(200)
    assert res.pnl == pytest.approx(200)
    assert res.final_bankroll == pytest.approx(1200)


def test_backtest_yes_loss_pnl():
    m = make_market(yes_won=False, price=0.5)
    res = run_backtest(
        [m], lambda mk, px: 0.6, bankroll=1000, horizon_secs=2 * HOUR,
        kelly_multiplier=1.0, max_fraction=0.5, fee_rate=0.0, slippage=0.0,
    )
    assert res.pnl == pytest.approx(-200)


def test_backtest_buys_no_when_model_below_price():
    m = make_market(yes_won=False, price=0.5)
    res = run_backtest(
        [m], lambda mk, px: 0.4, bankroll=1000, horizon_secs=2 * HOUR,
        kelly_multiplier=1.0, max_fraction=0.5, fee_rate=0.0, slippage=0.0,
    )
    assert res.trades[0].side == "NO"
    assert res.pnl == pytest.approx(200)


def test_backtest_slippage_and_fees_reduce_pnl():
    m = make_market(yes_won=True, price=0.5)
    kwargs = dict(bankroll=1000, horizon_secs=2 * HOUR, kelly_multiplier=0.25, max_fraction=0.5)
    clean = run_backtest([m], lambda mk, px: 0.7, fee_rate=0.0, slippage=0.0, **kwargs)
    costly = run_backtest([m], lambda mk, px: 0.7, fee_rate=0.02, slippage=0.01, **kwargs)
    assert costly.pnl < clean.pnl


def test_backtest_skips_when_edge_below_min_edge():
    m = make_market(price=0.5)
    res = run_backtest(
        [m], lambda mk, px: 0.52, bankroll=1000, horizon_secs=2 * HOUR, min_edge=0.05,
    )
    assert res.trades == ()
    assert res.pnl == 0.0


def test_backtest_skips_when_strategy_returns_none_or_no_price():
    m = make_market(price=0.5)
    assert run_backtest([m], lambda mk, px: None, bankroll=1000, horizon_secs=2 * HOUR).trades == ()
    assert run_backtest([m], lambda mk, px: 0.9, bankroll=1000, horizon_secs=50 * HOUR).trades == ()


def test_backtest_compounds_in_time_order_and_tracks_drawdown():
    m1 = make_market("a", end=100 * HOUR, yes_won=False, price=0.5)
    m2 = make_market("b", end=200 * HOUR, yes_won=True, price=0.5)
    res = run_backtest(
        [m2, m1], lambda mk, px: 0.6, bankroll=1000, horizon_secs=2 * HOUR,
        kelly_multiplier=1.0, max_fraction=0.5, fee_rate=0.0, slippage=0.0,
    )
    assert [t.market_id for t in res.trades] == ["a", "b"]
    assert res.max_drawdown > 0
    assert res.final_bankroll == pytest.approx(1000 - 200 + 160 * 1.0, rel=1e-6)


def test_split_walk_forward_orders_by_time():
    ms = [make_market(str(i), end=i * HOUR) for i in (5, 1, 4, 2, 3)]
    train, test = split_walk_forward(ms, train_fraction=0.6)
    assert [m.id for m in train] == ["1", "2", "3"]
    assert [m.id for m in test] == ["4", "5"]


def test_result_metrics_with_no_trades():
    res = run_backtest([], lambda mk, px: 0.9, bankroll=1000, horizon_secs=HOUR)
    assert res.roi == 0.0
    assert res.win_rate == 0.0
    assert res.max_drawdown == 0.0


def test_backtest_skips_degenerate_prices_and_entries():
    certain = Market("z", "w", 100 * HOUR, True, ((90 * HOUR, 1.0),))
    assert run_backtest([certain], lambda mk, px: 0.5, bankroll=1000, horizon_secs=2 * HOUR).trades == ()
    m = make_market(price=0.99)
    # slippage pushes the YES entry to >= 1.0, so the trade is skipped
    res = run_backtest([m], lambda mk, px: 0.999, bankroll=1000, horizon_secs=2 * HOUR, slippage=0.02)
    assert res.trades == ()
    assert res.roi == 0.0


def test_roi_and_win_rate_after_a_win():
    m = make_market(yes_won=True, price=0.5)
    res = run_backtest(
        [m], lambda mk, px: 0.6, bankroll=1000, horizon_secs=2 * HOUR,
        kelly_multiplier=1.0, max_fraction=0.5,
    )
    assert res.roi == pytest.approx(0.2)
    assert res.win_rate == 1.0


def test_load_markets_reads_jsonl_and_skips_blank_lines(tmp_path):
    import json

    from vwapbot.backtest import load_markets

    rec = {
        "id": "1", "category": "weather", "question": "q", "end_ts": 500,
        "yes_won": True, "yes_token": "t", "history": [[100, 0.2], [200, 0.3]],
    }
    path = tmp_path / "m.jsonl"
    path.write_text(json.dumps(rec) + "\n\n")
    (m,) = load_markets(path)
    assert m == Market("1", "weather", 500, True, ((100, 0.2), (200, 0.3)))


def test_flat_stakes_do_not_compound():
    ms = [make_market(str(i), end=(100 + i) * HOUR, yes_won=True, price=0.5) for i in range(3)]
    kwargs = dict(bankroll=1000, horizon_secs=2 * HOUR, kelly_multiplier=1.0, max_fraction=0.5)
    flat = run_backtest(ms, lambda mk, px: 0.6, flat_stakes=True, **kwargs)
    comp = run_backtest(ms, lambda mk, px: 0.6, **kwargs)
    assert [t.stake for t in flat.trades] == pytest.approx([200.0, 200.0, 200.0])
    assert flat.pnl == pytest.approx(600.0)
    assert comp.pnl > flat.pnl
