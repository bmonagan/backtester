import math

import pytest

from metrics import cagr, max_drawdown, sharpe_ratio, win_rate


def test_sharpe_flat_returns_zero():
    assert sharpe_ratio([100.0, 100.0, 100.0, 100.0]) == 0.0


def test_sharpe_insufficient_data_returns_zero():
    assert sharpe_ratio([]) == 0.0
    assert sharpe_ratio([100.0]) == 0.0


def test_sharpe_positive_trend_positive():
    # steady climb should give positive sharpe (zero vol edge handled, but
    # varying returns give positive mean/std)
    eq = [100.0, 101.0, 102.5, 104.0, 105.5]
    s = sharpe_ratio(eq)
    assert s > 0
    assert math.isfinite(s)


def test_sharpe_accepts_tuples_and_snapshots():
    eq_tuples = [(f"t{i}", v) for i, v in enumerate([100.0, 101.0, 102.5, 104.0])]
    assert sharpe_ratio(eq_tuples) > 0

    class Snap:
        def __init__(self, v):
            self.total_equity = v

    snaps = [Snap(v) for v in [100.0, 101.0, 102.5, 104.0]]
    assert sharpe_ratio(snaps) == pytest.approx(sharpe_ratio([100.0, 101.0, 102.5, 104.0]))


def test_max_drawdown_none_when_rising():
    assert max_drawdown([100.0, 110.0, 120.0]) == pytest.approx(0.0)


def test_max_drawdown_simple():
    # peak 120, trough 90 -> 25%
    assert max_drawdown([100.0, 120.0, 90.0, 110.0]) == pytest.approx(0.25)


def test_max_drawdown_empty():
    assert max_drawdown([]) == 0.0


def test_max_drawdown_accepts_tuples():
    assert max_drawdown([("a", 100.0), ("b", 50.0)]) == pytest.approx(0.5)


def test_cagr_doubles_over_one_year():
    # 253 points = 252 periods = 1 year; 100 -> 200 = 100% CAGR
    eq = [100.0] * 252 + [200.0]
    # len = 253, n = 252 periods
    assert cagr(eq) == pytest.approx(1.0, rel=1e-6)


def test_cagr_flat_is_zero():
    assert cagr([100.0, 100.0, 100.0]) == pytest.approx(0.0)


def test_cagr_invalid_returns_zero():
    assert cagr([]) == 0.0
    assert cagr([100.0]) == 0.0
    assert cagr([0.0, 100.0]) == 0.0


def test_win_rate_empty_is_zero():
    assert win_rate([]) == 0.0


def test_win_rate_all_wins():
    log = [
        {"symbol": "AAPL", "quantity": 10, "fill_price": 5.0},
        {"symbol": "AAPL", "quantity": -10, "fill_price": 7.0},
    ]
    assert win_rate(log) == pytest.approx(1.0)


def test_win_rate_all_losses():
    log = [
        {"symbol": "AAPL", "quantity": 10, "fill_price": 5.0},
        {"symbol": "AAPL", "quantity": -10, "fill_price": 3.0},
    ]
    assert win_rate(log) == pytest.approx(0.0)


def test_win_rate_half():
    log = [
        {"symbol": "AAPL", "quantity": 10, "fill_price": 5.0},
        {"symbol": "AAPL", "quantity": -10, "fill_price": 7.0},  # win
        {"symbol": "AAPL", "quantity": 10, "fill_price": 5.0},
        {"symbol": "AAPL", "quantity": -10, "fill_price": 3.0},  # loss
    ]
    assert win_rate(log) == pytest.approx(0.5)


def test_win_rate_no_closed_trades():
    # buys only -> no closes
    log = [{"symbol": "AAPL", "quantity": 10, "fill_price": 5.0}]
    assert win_rate(log) == 0.0


def test_win_rate_fifo_partial():
    # buy 10@5, sell 4@9 (win), sell 6@4 (loss) -> 1/2
    log = [
        {"symbol": "AAPL", "quantity": 10, "fill_price": 5.0},
        {"symbol": "AAPL", "quantity": -4, "fill_price": 9.0},
        {"symbol": "AAPL", "quantity": -6, "fill_price": 4.0},
    ]
    assert win_rate(log) == pytest.approx(0.5)
