import math

import pytest

from backtester.metrics import (
    annualized_volatility,
    benchmark_relative_metrics,
    cagr,
    historical_expected_shortfall,
    historical_var,
    max_drawdown,
    max_drawdown_duration,
    portfolio_metrics,
    sharpe_ratio,
    sortino_ratio,
    win_rate,
)
from backtester.portfolio import Portfolio


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


def test_annualized_volatility_uses_account_returns():
    curve = [100.0, 110.0, 99.0, 108.9]
    returns = [0.1, -0.1, 0.1]
    expected = math.sqrt(sum((value - math.fsum(returns) / 3) ** 2 for value in returns) / 3)
    assert annualized_volatility(curve, periods_per_year=1) == pytest.approx(expected)


def test_sortino_uses_downside_deviation_below_risk_free_target():
    curve = [100.0, 110.0, 99.0, 108.9]
    returns = [0.1, -0.1, 0.1]
    downside = math.sqrt(0.1**2 / 3)
    expected = (math.fsum(returns) / 3) / downside
    assert sortino_ratio(curve, periods_per_year=1) == pytest.approx(expected)


def test_max_drawdown_duration_counts_underwater_observations():
    assert max_drawdown_duration([100, 120, 110, 100, 120, 90, 90, 120]) == 2
    assert max_drawdown_duration([100, 110, 120]) == 0


def test_historical_var_and_expected_shortfall_are_positive_losses():
    curve = [100.0, 110.0, 99.0, 103.95, 83.16, 91.476]
    assert historical_var(curve, confidence_level=0.8) == pytest.approx(0.2)
    assert historical_expected_shortfall(
        curve, confidence_level=0.8
    ) == pytest.approx(0.2)


def test_return_metrics_reject_nonpositive_beginning_equity():
    with pytest.raises(ValueError, match="beginning equity"):
        annualized_volatility([0.0, 1.0])


def test_portfolio_metrics_report_account_return_turnover_and_exposure():
    portfolio = Portfolio(10_000.0)
    assert portfolio.execute_order("t0", "AAPL", 10, 100.0)
    portfolio.mark_to_market("t0", {"AAPL": 100.0})
    portfolio.mark_to_market("t1", {"AAPL": 110.0})

    metrics = portfolio_metrics(portfolio)

    assert metrics["total_return"] == pytest.approx(0.01)
    assert metrics["turnover"] == pytest.approx(1000.0 / 10050.0)
    assert metrics["average_gross_exposure"] == pytest.approx(
        (0.1 + 1100.0 / 10100.0) / 2
    )
    assert metrics["average_margin_utilization"] == 0.0


def test_portfolio_return_metrics_are_invariant_to_proportional_scale():
    outputs = []
    for scale in (1, 2):
        portfolio = Portfolio(10_000.0 * scale)
        assert portfolio.execute_order("t0", "AAPL", 10 * scale, 100.0)
        portfolio.mark_to_market("t0", {"AAPL": 100.0})
        portfolio.mark_to_market("t1", {"AAPL": 105.0})
        portfolio.mark_to_market("t2", {"AAPL": 95.0})
        outputs.append(portfolio_metrics(portfolio))

    for key in (
        "total_return",
        "annualized_return",
        "sharpe",
        "sortino",
        "annualized_volatility",
        "max_drawdown",
        "turnover",
        "average_gross_exposure",
    ):
        assert outputs[0][key] == pytest.approx(outputs[1][key])


def test_portfolio_metrics_consolidate_multiple_marks_at_same_timestamp():
    portfolio = Portfolio(10_000.0)
    assert portfolio.execute_order("t0", "AAPL", 10, 100.0)
    assert portfolio.execute_order("t0", "MSFT", 10, 50.0)
    portfolio.mark_to_market("t0", {"AAPL": 100.0, "MSFT": 50.0})
    portfolio.mark_to_market("t0", {"AAPL": 100.0, "MSFT": 60.0})
    portfolio.mark_to_market("t1", {"AAPL": 110.0, "MSFT": 55.0})

    metrics = portfolio_metrics(portfolio)

    assert metrics["total_return"] == pytest.approx(50.0 / 10100.0)
    assert metrics["sharpe"] == 0.0


def test_benchmark_relative_metrics_align_timestamped_curves():
    strategy = [("d1", 100), ("d2", 110), ("d3", 99)]
    benchmark = [("d1", 100), ("d2", 105), ("d3", 100)]

    metrics = benchmark_relative_metrics(strategy, benchmark, periods_per_year=1)

    assert metrics["benchmark_total_return"] == pytest.approx(0.0)
    assert metrics["active_total_return"] == pytest.approx(-0.01)
    assert metrics["tracking_error"] == pytest.approx(
        abs((0.1 - 0.05) - (-0.1 - (100 / 105 - 1))) / 2
    )


def test_benchmark_relative_metrics_ignores_nonshared_dates():
    metrics = benchmark_relative_metrics(
        [("d1", 100), ("d2", 110), ("d3", 121)],
        [("d1", 100), ("d3", 120)],
        periods_per_year=1,
    )

    assert metrics["benchmark_total_return"] == pytest.approx(0.2)
    assert metrics["active_total_return"] == pytest.approx(0.01)


def test_benchmark_relative_metrics_uses_last_mark_at_duplicate_timestamp():
    metrics = benchmark_relative_metrics(
        [("d1", 100), ("d1", 105), ("d2", 110)],
        [("d1", 100), ("d1", 102), ("d2", 108)],
        periods_per_year=1,
    )

    assert metrics["active_total_return"] == pytest.approx(
        (110 / 105 - 1) - (108 / 102 - 1)
    )


def test_untimestamped_benchmark_curves_must_have_equal_lengths():
    with pytest.raises(ValueError, match="must match"):
        benchmark_relative_metrics([100, 110], [100, 105, 110])


def test_timestamped_and_untimestamped_benchmark_curves_cannot_be_mixed():
    with pytest.raises(ValueError, match="both include timestamps"):
        benchmark_relative_metrics([("d1", 100), ("d2", 110)], [100, 105])
