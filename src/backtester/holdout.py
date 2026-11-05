"""Evaluation of the frozen strategy manifest on its predeclared holdout."""

import math
from dataclasses import replace
from datetime import date, datetime
from typing import Any

from backtester.engine import BacktestEngine
from backtester.extra_strategies import (
    CciStrategy,
    StochasticOscillatorStrategy,
    VwapMeanReversionStrategy,
    WilliamsRStrategy,
)
from backtester.instruments import ExecutionCostModel, InstrumentSpec
from backtester.metrics import (
    benchmark_relative_metrics,
    portfolio_metrics,
)
from backtester.robustness import bootstrap_strategy_summary
from backtester.strategy import (
    BollingerMeanReversionStrategy,
    BuyAndHoldStrategy,
    RsiMomentumStrategy,
)

FROZEN_STRATEGIES = {
    "Bollinger": BollingerMeanReversionStrategy,
    "CCI": CciStrategy,
    "RSI": RsiMomentumStrategy,
    "Stochastic": StochasticOscillatorStrategy,
    "VWAP mean reversion": VwapMeanReversionStrategy,
    "Williams %R": WilliamsRStrategy,
}

COST_SCENARIOS = ("base", "adverse", "severe")


def _calendar_value(value: object) -> date | object:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return value
    return value


def _run_period(
    bars: list[Any],
    strategy,
    *,
    starting_cash: float,
    holdout_start: object,
    holdout_end: object,
    instrument_specs: dict[str, InstrumentSpec],
    execution_models: dict[str, ExecutionCostModel],
):
    pre_holdout = [
        bar for bar in bars if _calendar_value(bar.timestamp) < holdout_start
    ]
    holdout_bars = [
        bar
        for bar in bars
        if holdout_start <= _calendar_value(bar.timestamp) <= holdout_end
    ]
    if not pre_holdout or not holdout_bars:
        raise ValueError("holdout requires pre-period warm-up and in-period bars")
    if len({_calendar_value(bar.timestamp) for bar in holdout_bars}) < 2:
        raise ValueError("holdout requires at least two unique timestamps")

    engine = BacktestEngine(
        feed=pre_holdout + holdout_bars,
        strategy=strategy,
        starting_cash=starting_cash,
        instrument_specs=instrument_specs,
        strict_instruments=True,
        execution_models=execution_models,
        trade_start=holdout_bars[0].timestamp,
    )
    portfolio = engine.run()
    prior = [
        snapshot
        for snapshot in portfolio.history
        if _calendar_value(snapshot.timestamp) < holdout_start
    ]
    test = [
        snapshot
        for snapshot in portfolio.history
        if holdout_start <= _calendar_value(snapshot.timestamp) <= holdout_end
    ]
    if not prior or not test:
        raise ValueError("holdout run produced no warm-up or test equity marks")

    history = []
    for snapshot in [prior[-1], *test]:
        if history and history[-1].timestamp == snapshot.timestamp:
            history[-1] = snapshot
        else:
            history.append(snapshot)
    measured = portfolio_metrics(
        _portfolio_copy(portfolio, history),
        periods_per_year=365 if _is_crypto(instrument_specs) else 252,
    )
    equity_curve = [(snapshot.timestamp, snapshot.total_equity) for snapshot in history]
    return {
        "engine": engine,
        "portfolio": portfolio,
        "equity_curve": equity_curve,
        "metrics": measured,
        "fills": engine.n_fills,
        "rejected": engine.n_rejected,
        "pending_orders": len(engine.pending_orders),
        "open_positions": len(portfolio.positions),
    }


def _portfolio_copy(portfolio, history):
    """Make a shallow metric view without mutating the completed ledger."""
    from copy import copy

    measured = copy(portfolio)
    measured.history = history
    measured.trade_log = [
        trade
        for trade in portfolio.trade_log
        if _calendar_value(trade["timestamp"]) >= _calendar_value(history[1].timestamp)
    ]
    return measured


def _is_crypto(instrument_specs: dict[str, InstrumentSpec]) -> bool:
    return any(spec.asset_class == "crypto" for spec in instrument_specs.values())


def run_frozen_top25_holdout(
    bars,
    manifest: dict,
    *,
    instrument_specs: dict[str, InstrumentSpec],
    execution_models: dict[str, ExecutionCostModel],
    starting_cash: float = 100_000.0,
    bootstrap_resamples: int = 2_000,
    bootstrap_block_size: int = 5,
    bootstrap_seed: int = 0,
) -> list[dict]:
    """Run all frozen candidates against each configured cost scenario.

    The manifest candidate list and parameters are not re-ranked or modified.
    Explicit complete instrument metadata and per-symbol execution profiles
    are required; the function refuses to fabricate market assumptions.
    """
    selection = manifest["selection"]
    holdout_start = _calendar_value(manifest["holdout"]["start"])
    holdout_end = _calendar_value(manifest["holdout"]["end"])
    candidates = selection["rows"]
    if len(candidates) != 25:
        raise ValueError("frozen manifest must contain exactly 25 candidates")
    if [candidate["rank"] for candidate in candidates] != list(range(1, 26)):
        raise ValueError("frozen candidates must be in rank order from 1 to 25")
    if holdout_start >= holdout_end:
        raise ValueError("holdout start must be before holdout end")
    if (
        isinstance(starting_cash, bool)
        or not isinstance(starting_cash, (int, float))
        or not math.isfinite(starting_cash)
        or starting_cash <= 0
    ):
        raise ValueError("starting_cash must be a positive finite number")
    symbols = {candidate["symbol"] for candidate in candidates}
    for symbol in symbols:
        spec = instrument_specs.get(symbol)
        if spec is None or not spec.metadata_complete:
            raise ValueError(f"complete instrument metadata required for {symbol}")
        if symbol not in execution_models:
            raise ValueError(f"execution cost profile required for {symbol}")
    unknown_strategies = sorted(
        {candidate["strategy"] for candidate in candidates} - FROZEN_STRATEGIES.keys()
    )
    if unknown_strategies:
        raise ValueError(f"unsupported frozen strategies: {unknown_strategies}")

    bars_by_symbol: dict[str, list[Any]] = {symbol: [] for symbol in symbols}
    for bar in bars:
        if bar.symbol in bars_by_symbol:
            bars_by_symbol[bar.symbol].append(bar)
    for symbol, symbol_bars in bars_by_symbol.items():
        symbol_bars.sort(key=lambda bar: bar.timestamp)
        dates = [_calendar_value(bar.timestamp) for bar in symbol_bars]
        if len(set(dates)) != len(dates):
            raise ValueError(f"{symbol} contains duplicate timestamp bars")
        if not any(timestamp < holdout_start for timestamp in dates):
            raise ValueError(f"{symbol} has no pre-holdout warm-up bars")
        if max(dates) < holdout_end:
            raise ValueError(
                f"{symbol} data ends before declared holdout end {holdout_end}"
            )
        if not any(holdout_start <= timestamp <= holdout_end for timestamp in dates):
            raise ValueError(f"{symbol} has no observations in the declared holdout")
        if len(
            {
                timestamp
                for timestamp in dates
                if holdout_start <= timestamp <= holdout_end
            }
        ) < 2:
            raise ValueError(f"{symbol} needs two holdout timestamps for return metrics")
    output = []
    for scenario in COST_SCENARIOS:
        scenario_models = {
            symbol: replace(model, scenario=scenario)
            for symbol, model in execution_models.items()
        }
        returns_by_candidate = {}
        candidate_rows = []
        for candidate in candidates:
            symbol = candidate["symbol"]
            strategy_class = FROZEN_STRATEGIES[candidate["strategy"]]
            strategy = strategy_class(quantity=1, **candidate["parameters"])
            test_bars = bars_by_symbol[symbol]
            result = _run_period(
                test_bars,
                strategy,
                starting_cash=starting_cash,
                holdout_start=holdout_start,
                holdout_end=holdout_end,
                instrument_specs={symbol: instrument_specs[symbol]},
                execution_models={symbol: scenario_models[symbol]},
            )
            benchmark = _run_period(
                test_bars,
                BuyAndHoldStrategy(quantity=1),
                starting_cash=starting_cash,
                holdout_start=holdout_start,
                holdout_end=holdout_end,
                instrument_specs={symbol: instrument_specs[symbol]},
                execution_models={symbol: scenario_models[symbol]},
            )
            metrics = result["metrics"]
            metrics.update(
                {
                    f"buyhold_{name}": value
                    for name, value in benchmark_relative_metrics(
                        result["equity_curve"],
                        benchmark["equity_curve"],
                        periods_per_year=(
                            365
                            if instrument_specs[symbol].asset_class == "crypto"
                            else 252
                        ),
                    ).items()
                }
            )
            metrics.update(
                {
                    f"cash_{name}": value
                    for name, value in benchmark_relative_metrics(
                        result["equity_curve"],
                        [
                            (timestamp, starting_cash)
                            for timestamp, _ in result["equity_curve"]
                        ],
                        periods_per_year=(
                            365
                            if instrument_specs[symbol].asset_class == "crypto"
                            else 252
                        ),
                    ).items()
                }
            )
            portfolio = result["portfolio"]
            metrics["commission_cost"] = portfolio.cost_totals["commission"]
            metrics["spread_cost"] = portfolio.cost_totals["spread"]
            metrics["slippage_cost"] = portfolio.cost_totals["slippage"]
            metrics["impact_cost"] = portfolio.cost_totals["impact"]
            metrics["trades"] = len(portfolio.trade_log)
            row = {
                "rank": candidate["rank"],
                "symbol": symbol,
                "strategy": candidate["strategy"],
                "variant": candidate["variant"],
                "source_sharpe": float(candidate["source_metrics"]["sharpe"]),
                "scenario": scenario,
                "status": "ok",
                "fills": result["fills"],
                "rejected": result["rejected"],
                "pending_orders": result["pending_orders"],
                "open_positions": result["open_positions"],
                **metrics,
            }
            candidate_key = f"rank-{candidate['rank']:02d}"
            returns = [
                current / previous - 1
                for (_, previous), (_, current) in zip(
                    result["equity_curve"], result["equity_curve"][1:]
                )
                if previous > 0
            ]
            returns_by_candidate[candidate_key] = returns
            candidate_rows.append((row, candidate_key))

        robustness = bootstrap_strategy_summary(
            returns_by_candidate,
            resamples=bootstrap_resamples,
            block_size=bootstrap_block_size,
            seed=bootstrap_seed,
        )
        robustness_by_candidate = {
            row["candidate"]: row for row in robustness
        }
        for row, candidate_key in candidate_rows:
            row.update(
                {
                    f"bootstrap_{name}": value
                    for name, value in robustness_by_candidate[candidate_key].items()
                    if name != "candidate"
                }
            )
            output.append(row)
    return output
