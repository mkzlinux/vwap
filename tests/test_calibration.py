import pytest

from vwapbot.calibration import brier_score, fit_calibration, reliability_table


def test_brier_perfect_forecast_is_zero():
    assert brier_score([1.0, 0.0], [1, 0]) == 0.0


def test_brier_coin_flip_is_quarter():
    assert brier_score([0.5, 0.5], [1, 0]) == pytest.approx(0.25)


def test_brier_rejects_length_mismatch_and_empty():
    with pytest.raises(ValueError):
        brier_score([0.5], [1, 0])
    with pytest.raises(ValueError):
        brier_score([], [])


def test_reliability_table_bins_and_frequencies():
    preds = [0.05, 0.05, 0.95, 0.95]
    outcomes = [0, 1, 1, 1]
    rows = reliability_table(preds, outcomes, bins=10)
    assert [r.n for r in rows] == [2, 2]
    assert rows[0].mean_pred == pytest.approx(0.05)
    assert rows[0].freq == pytest.approx(0.5)
    assert rows[1].freq == pytest.approx(1.0)


def test_reliability_table_puts_one_in_last_bin():
    rows = reliability_table([1.0], [1], bins=10)
    assert rows[0].hi == pytest.approx(1.0)
    assert rows[0].n == 1


def test_fit_calibration_shrinks_toward_price_with_few_samples():
    cal = fit_calibration([0.05] * 2, [1, 1], bins=10, shrinkage=20)
    # 2 samples all YES vs. price 0.05: heavy shrinkage keeps estimate near price
    assert 0.05 < cal(0.05) < 0.25


def test_fit_calibration_learns_with_many_samples():
    preds = [0.05] * 500
    outcomes = [1] * 100 + [0] * 400  # true freq 0.20
    cal = fit_calibration(preds, outcomes, bins=10, shrinkage=20)
    assert cal(0.05) == pytest.approx((500 * 0.2 + 20 * 0.05) / 520)


def test_fit_calibration_unseen_bin_returns_input():
    cal = fit_calibration([0.05], [0], bins=10)
    assert cal(0.55) == pytest.approx(0.55)


def test_reliability_table_rejects_length_mismatch():
    with pytest.raises(ValueError):
        reliability_table([0.5], [1, 0])
