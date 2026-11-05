# compare.py
"""Run several strategies over the same feed and compare metrics.

feed_factory must be a zero-arg callable returning a FRESH feed each call
(feeds are single-pass iterables, so they cannot be shared across runs).
"""

from typing import Literal

from backtester.engine import BacktestEngine
from backtester.extra_strategies import (
    AtrTrailingBreakoutStrategy,
    CciStrategy,
    EmaCrossoverStrategy,
    IchimokuCloudStrategy,
    KeltnerChannelStrategy,
    MacdStrategy,
    RateOfChangeStrategy,
    StochasticOscillatorStrategy,
    VwapMeanReversionStrategy,
    WilliamsRStrategy,
)
from backtester.metrics import (
    cagr,
    max_drawdown,
    portfolio_metrics,
    sharpe_ratio,
    win_rate,
)
from backtester.strategy import (
    BollingerMeanReversionStrategy,
    BuyAndHoldStrategy,
    DonchianBreakoutStrategy,
    OrderTypeOverride,
    RsiMomentumStrategy,
    SmaCrossoverStrategy,
    TurtleTradingStrategy,
)

STRATEGIES = {
    "sma": SmaCrossoverStrategy,
    "buyhold": BuyAndHoldStrategy,
    "rsi": RsiMomentumStrategy,
    "bollinger": BollingerMeanReversionStrategy,
    "donchian": DonchianBreakoutStrategy,
    "turtle": TurtleTradingStrategy,
    "ema": EmaCrossoverStrategy,
    "macd": MacdStrategy,
    "roc": RateOfChangeStrategy,
    "stochastic": StochasticOscillatorStrategy,
    "williamsr": WilliamsRStrategy,
    "cci": CciStrategy,
    "keltner": KeltnerChannelStrategy,
    "atrtrail": AtrTrailingBreakoutStrategy,
    "ichimoku": IchimokuCloudStrategy,
    "vwap": VwapMeanReversionStrategy,
}


def build_strategy(name: str, **kwargs):
    try:
        cls = STRATEGIES[name]
    except KeyError:
        raise ValueError(f"unknown strategy {name!r}, choose from {sorted(STRATEGIES)}")
    return cls(**kwargs)


def run_one(
    name,
    feed_factory,
    starting_cash=10000.0,
    commission=0.0,
    slippage_bps=0.0,
    strategy_kwargs=None,
    allow_shorts=False,
    order_type: Literal["market", "limit", "stop"] = "market",
    order_price=None,
    benchmark_equity_curve=None,
) -> dict:
    feed = feed_factory()
    kwargs = (strategy_kwargs or {}).get(name, {})
    strategy = build_strategy(name, **kwargs)
    if order_type != "market":
        strategy = OrderTypeOverride(strategy, order_type, order_price)
    engine = BacktestEngine(
        feed=feed,
        strategy=strategy,
        starting_cash=starting_cash,
        commission=commission,
        slippage_bps=slippage_bps,
        allow_shorts=allow_shorts,
    )
    pf = engine.run()
    eq = [s.total_equity for s in pf.history]
    if engine.latest_prices:
        final_equity = pf.current_equity(engine.latest_prices)
    else:
        final_equity = starting_cash
    risk_metrics = portfolio_metrics(
        pf, benchmark_equity_curve=benchmark_equity_curve
    )
    return {
        "strategy": name,
        "final_equity": final_equity,
        "trades": len(pf.trade_log),
        "fills": engine.n_fills,
        "rejected": engine.n_rejected,
        "sharpe": sharpe_ratio(eq),
        "max_drawdown": max_drawdown(eq),
        "cagr": cagr(eq),
        "win_rate": win_rate(pf.trade_log),
        "realized_pnl": pf.realized_pnl,
        **risk_metrics,
    }


def compare(names, feed_factory, **kwargs) -> list[dict]:
    return [run_one(name, feed_factory, **kwargs) for name in names]


def format_table(rows: list[dict]) -> str:
    cols = [
        "strategy",
        "final_equity",
        "trades",
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
    ]
    if rows and "benchmark_total_return" in rows[0]:
        cols.extend(
            [
                "benchmark_total_return",
                "active_total_return",
                "tracking_error",
                "information_ratio",
            ]
        )
    if rows:
        widths = {c: max(len(c), *(len(_fmt(c, r[c])) for r in rows)) for c in cols}
    else:
        widths = {c: len(c) for c in cols}
    header = "  ".join(c.ljust(widths[c]) for c in cols)
    lines = [header]
    for r in rows:
        lines.append("  ".join(_fmt(c, r[c]).ljust(widths[c]) for c in cols))
    return "\n".join(lines)


def _fmt(col: str, val) -> str:
    if col == "final_equity":
        return f"{val:.2f}"
    if col == "trades":
        return str(val)
    if col == "sharpe":
        return f"{val:.3f}"
    if col in (
        "max_drawdown",
        "cagr",
        "win_rate",
        "sortino",
        "annualized_volatility",
        "historical_var",
        "expected_shortfall",
        "average_gross_exposure",
        "average_margin_utilization",
        "benchmark_total_return",
        "active_total_return",
        "tracking_error",
    ):
        return f"{val:.1%}"
    if col == "information_ratio":
        return f"{val:.3f}"
    if col == "max_drawdown_duration":
        return str(val)
    if col in ("turnover",):
        return f"{val:.2f}"
    if col == "realized_pnl":
        return f"{val:.2f}"
    return str(val)
