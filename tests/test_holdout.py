from datetime import date, timedelta

import pytest

from backtester.datafeed import Bar
from backtester.instruments import (
    ExecutionCostModel,
    FeeSchedule,
    InstrumentSpec,
)
from backtester.holdout import run_frozen_top25_holdout


def _spec():
    return InstrumentSpec(
        symbol="AAPL",
        asset_class="equity",
        quote_currency="USD",
        tick_size=0.01,
        quantity_increment=1.0,
        multiplier=1.0,
        calendar="XNYS",
        timezone="America/New_York",
        fee_schedule=FeeSchedule(currency="USD"),
    )


def _manifest(start=date(2026, 1, 5), end=date(2026, 1, 10)):
    rows = [
        {
            "rank": rank,
            "symbol": "AAPL",
            "strategy": "Bollinger",
            "variant": "2:1.0",
            "parameters": {"period": 2, "num_std": 1.0},
            "source_metrics": {"sharpe": str(3 - rank / 10)},
        }
        for rank in range(1, 26)
    ]
    return {
        "selection": {"rows": rows},
        "holdout": {"start": start.isoformat(), "end": end.isoformat()},
    }


def _bars(start=date(2026, 1, 1), count=10):
    prices = [100, 102, 98, 103, 99, 104, 100, 106, 101, 108]
    return [
        Bar(
            start + timedelta(days=index),
            "AAPL",
            price,
            price,
            price,
            price,
            1000,
        )
        for index, price in enumerate(prices[:count])
    ]


def test_frozen_holdout_reports_every_candidate_and_cost_scenario():
    results = run_frozen_top25_holdout(
        _bars(),
        _manifest(),
        instrument_specs={"AAPL": _spec()},
        execution_models={
            "AAPL": ExecutionCostModel(half_spread_bps=1, slippage_bps=2)
        },
        bootstrap_resamples=20,
        bootstrap_block_size=2,
        starting_cash=10_000.0,
    )

    assert len(results) == 75
    assert [(row["rank"], row["scenario"]) for row in results[:4]] == [
        (1, "base"),
        (2, "base"),
        (3, "base"),
        (4, "base"),
    ]
    assert {row["scenario"] for row in results} == {"base", "adverse", "severe"}
    assert all(row["status"] == "ok" for row in results)
    assert all(
        row["source_sharpe"] == pytest.approx(3 - row["rank"] / 10)
        for row in results
    )
    assert all("bootstrap_holm_adjusted_p_value" in row for row in results)
    assert all("cash_active_total_return" in row for row in results)
    assert all("buyhold_active_total_return" in row for row in results)


def test_frozen_holdout_fails_when_predeclared_holdout_is_missing():
    bars = _bars(count=5)

    with pytest.raises(ValueError, match="data ends before declared holdout end"):
        run_frozen_top25_holdout(
            bars,
            _manifest(),
            instrument_specs={"AAPL": _spec()},
            execution_models={"AAPL": ExecutionCostModel()},
            bootstrap_resamples=10,
            bootstrap_block_size=1,
        )


def test_frozen_holdout_requires_complete_metadata_and_cost_profiles():
    with pytest.raises(ValueError, match="complete instrument metadata required"):
        run_frozen_top25_holdout(
            _bars(),
            _manifest(),
            instrument_specs={},
            execution_models={"AAPL": ExecutionCostModel()},
            bootstrap_resamples=10,
            bootstrap_block_size=1,
        )


def test_frozen_holdout_rejects_invalid_candidate_order_and_duplicate_bars():
    manifest = _manifest()
    manifest["selection"]["rows"][0]["rank"] = 2
    with pytest.raises(ValueError, match="rank order"):
        run_frozen_top25_holdout(
            _bars(),
            manifest,
            instrument_specs={"AAPL": _spec()},
            execution_models={"AAPL": ExecutionCostModel()},
        )

    with pytest.raises(ValueError, match="duplicate timestamp"):
        run_frozen_top25_holdout(
            _bars() + [_bars()[0]],
            _manifest(),
            instrument_specs={"AAPL": _spec()},
            execution_models={"AAPL": ExecutionCostModel()},
            bootstrap_resamples=10,
            bootstrap_block_size=1,
        )

    with pytest.raises(ValueError, match="execution cost profile required"):
        run_frozen_top25_holdout(
            _bars(),
            _manifest(),
            instrument_specs={"AAPL": _spec()},
            execution_models={},
            bootstrap_resamples=10,
            bootstrap_block_size=1,
        )
