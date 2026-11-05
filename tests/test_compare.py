import pytest

from backtester.compare import STRATEGIES, build_strategy, compare, format_table, run_one
from backtester.datafeed import Bar


def _ramp_factory(n=60):
    def make():
        return [
            Bar(timestamp=i, symbol="AAPL", open=c, high=c, low=c, close=c, volume=1)
            for i, c in enumerate(range(n))
        ]

    return make


def test_registry_has_all_sixteen():
    assert sorted(STRATEGIES) == [
        "atrtrail",
        "bollinger",
        "buyhold",
        "cci",
        "donchian",
        "ema",
        "ichimoku",
        "keltner",
        "macd",
        "roc",
        "rsi",
        "sma",
        "stochastic",
        "turtle",
        "vwap",
        "williamsr",
    ]


def test_unknown_strategy_raises():
    with pytest.raises(ValueError):
        build_strategy("nope")


def test_run_one_returns_all_keys():
    row = run_one("buyhold", _ramp_factory(), starting_cash=10000.0)
    for key in [
        "strategy",
        "final_equity",
        "trades",
        "fills",
        "rejected",
        "sharpe",
        "max_drawdown",
        "cagr",
        "win_rate",
        "realized_pnl",
        "sortino",
        "annualized_volatility",
        "max_drawdown_duration",
        "historical_var",
        "expected_shortfall",
        "turnover",
        "average_gross_exposure",
        "average_margin_utilization",
    ]:
        assert key in row
    assert row["strategy"] == "buyhold"
    assert row["trades"] == 1


NAMES = [
    "sma",
    "buyhold",
    "rsi",
    "bollinger",
    "donchian",
    "turtle",
    "ema",
    "macd",
    "roc",
    "stochastic",
    "williamsr",
    "cci",
    "keltner",
    "atrtrail",
    "ichimoku",
    "vwap",
]


def test_compare_runs_every_name_with_fresh_feeds():
    rows = compare(NAMES, _ramp_factory(), starting_cash=10000.0)
    assert [r["strategy"] for r in rows] == NAMES
    assert all(r["final_equity"] > 0 for r in rows)


def test_format_table_lists_names():
    rows = compare(["sma", "buyhold"], _ramp_factory(), starting_cash=10000.0)
    table = format_table(rows)
    assert "sma" in table and "buyhold" in table
    assert "sharpe" in table
    assert "sortino" in table
    assert "expected_shortfall" in table


def test_run_one_adds_benchmark_relative_fields_when_benchmark_given():
    benchmark = [(index, 100 + index) for index in range(60)]
    row = run_one(
        "buyhold",
        _ramp_factory(),
        starting_cash=10000.0,
        benchmark_equity_curve=benchmark,
    )

    assert "active_total_return" in row
    assert "information_ratio" in row
    assert "active_total_return" in format_table([row])
