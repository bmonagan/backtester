"""Chronological data splitting helpers for out-of-sample validation."""

from collections.abc import Iterable
from copy import copy
from dataclasses import dataclass

from backtester.engine import BacktestEngine
from backtester.metrics import portfolio_metrics

@dataclass(frozen=True)
class WalkForwardFold:
    """One expanding-training, forward validation and test fold."""

    index: int
    train: tuple[object, ...]
    validation: tuple[object, ...]
    test: tuple[object, ...]


def walk_forward_splits(
    timestamps: Iterable[object],
    *,
    train_size: int,
    validation_size: int,
    test_size: int,
    step_size: int | None = None,
) -> tuple[WalkForwardFold, ...]:
    """Build expanding chronological folds from unique ordered timestamps.

    Duplicate timestamps, such as one timestamp per symbol in a multi-asset
    feed, are collapsed while preserving order. Training windows expand by
    ``step_size`` on each fold; validation and test windows retain fixed sizes.
    Test windows do not overlap.
    """
    for name, value in (
        ("train_size", train_size),
        ("validation_size", validation_size),
        ("test_size", test_size),
    ):
        _validate_positive_integer(name, value)
    if step_size is None:
        step_size = test_size
    _validate_positive_integer("step_size", step_size)
    if step_size < test_size:
        raise ValueError("step_size must be greater than or equal to test_size")

    ordered = []
    seen = set()
    for timestamp in timestamps:
        try:
            if timestamp in seen:
                continue
            if ordered and timestamp < ordered[-1]:
                raise ValueError("timestamps must be in chronological order")
            seen.add(timestamp)
        except TypeError as error:
            raise ValueError("timestamps must be hashable and mutually comparable") from error
        ordered.append(timestamp)

    folds = []
    offset = 0
    while True:
        train_end = train_size + offset
        validation_end = train_end + validation_size
        test_end = validation_end + test_size
        if test_end > len(ordered):
            break
        folds.append(
            WalkForwardFold(
                index=len(folds),
                train=tuple(ordered[:train_end]),
                validation=tuple(ordered[train_end:validation_end]),
                test=tuple(ordered[validation_end:test_end]),
            )
        )
        offset += step_size

    if not folds:
        required = train_size + validation_size + test_size
        raise ValueError(
            f"at least {required} unique timestamps are required for one fold"
        )
    return tuple(folds)


def run_walk_forward(
    bars: Iterable[object],
    strategy_factory,
    *,
    train_size: int,
    validation_size: int,
    test_size: int,
    step_size: int | None = None,
    starting_cash: float = 10_000.0,
    commission: float = 0.0,
    slippage_bps: float = 0.0,
    allow_shorts: bool = False,
    instrument_specs=None,
    execution_models=None,
    periods_per_year: int = 252,
) -> list[dict]:
    """Run each test fold with fresh strategy state and pre-test warm-up bars.

    The strategy observes training and validation bars to initialize indicator
    state, but orders are only queued from the fold's first test timestamp.
    Each fold starts from fresh cash with no carried positions. The function
    reports test-period account metrics and does not tune strategy parameters.
    """
    bars = list(bars)
    folds = walk_forward_splits(
        (bar.timestamp for bar in bars),
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        step_size=step_size,
    )
    bars_by_timestamp: dict[object, list[object]] = {}
    for bar in bars:
        bars_by_timestamp.setdefault(bar.timestamp, []).append(bar)

    results = []
    for fold in folds:
        test_start = fold.test[0]
        test_end = fold.test[-1]
        feed = [
            bar
            for timestamp in bars_by_timestamp
            if timestamp <= test_end
            for bar in bars_by_timestamp[timestamp]
        ]
        engine = BacktestEngine(
            feed=feed,
            strategy=strategy_factory(),
            starting_cash=starting_cash,
            commission=commission,
            slippage_bps=slippage_bps,
            allow_shorts=allow_shorts,
            instrument_specs=instrument_specs,
            execution_models=execution_models,
            trade_start=test_start,
        )
        portfolio = engine.run()
        prior_marks = [
            snapshot for snapshot in portfolio.history if snapshot.timestamp < test_start
        ]
        test_marks = [
            snapshot
            for snapshot in portfolio.history
            if test_start <= snapshot.timestamp <= test_end
        ]
        unique_prior_timestamps = {snapshot.timestamp for snapshot in prior_marks}
        if not prior_marks or not test_marks:
            raise ValueError(
                f"fold {fold.index} lacks pre-test warm-up or test-period marks"
            )
        last_prior_timestamp = max(unique_prior_timestamps)
        measured = copy(portfolio)
        measured.history = [
            snapshot
            for snapshot in portfolio.history
            if snapshot.timestamp == last_prior_timestamp
            or test_start <= snapshot.timestamp <= test_end
        ]
        measured.trade_log = [
            trade
            for trade in portfolio.trade_log
            if test_start <= trade["timestamp"] <= test_end
        ]
        results.append(
            {
                "fold": fold.index,
                "train_start": fold.train[0],
                "train_end": fold.train[-1],
                "validation_start": fold.validation[0],
                "validation_end": fold.validation[-1],
                "test_start": test_start,
                "test_end": test_end,
                "fills": engine.n_fills,
                "rejected": engine.n_rejected,
                **portfolio_metrics(
                    measured, periods_per_year=periods_per_year
                ),
                "pending_orders": len(engine.pending_orders),
                "open_positions": len(portfolio.positions),
            }
        )
    return results


def _validate_positive_integer(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
